"""Optional enhancement helpers backed by shared model gateway.

Default provider profile is Tencent Hunyuan (OpenAI-compatible API).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import sqrt
from typing import Any

from platform_shared import (
    ModelEndpointConfig,
    ModelGateway,
    ModelGatewayConfig,
    ModelGatewayError,
    ModelGatewayResponseError,
    ModelGatewayTimeoutError,
    get_requirement_analysis_model_profile,
    get_requirement_analysis_runtime_config,
)


@dataclass(slots=True)
class OpenAIEnhancementConfig:
    gateway: ModelGateway

    @classmethod
    def from_env(cls, model_profile: str | None = None) -> "OpenAIEnhancementConfig | None":
        api_key = _first_env("HUNYUAN_API_KEY", "OPENAI_API_KEY")
        if not api_key:
            return None
        _, profile = get_requirement_analysis_model_profile(model_profile)
        base_url = (_first_env("HUNYUAN_BASE_URL", "OPENAI_BASE_URL") or profile.base_url).rstrip("/")
        embedding_model = (_first_env("HUNYUAN_EMBEDDING_MODEL", "OPENAI_EMBEDDING_MODEL") or profile.embedding_model).strip()
        llm_model = (_first_env("HUNYUAN_LLM_MODEL", "OPENAI_LLM_MODEL") or profile.llm_model).strip()
        timeout = _resolve_float("HUNYUAN_TIMEOUT_SECONDS", "OPENAI_TIMEOUT_SECONDS", default=profile.timeout_seconds)
        retries = _resolve_int("HUNYUAN_RETRIES", "OPENAI_RETRIES", default=profile.retries)
        gateway = ModelGateway(
            ModelGatewayConfig(
                llm=ModelEndpointConfig(
                    provider="openai",
                    model=llm_model,
                    api_base=base_url,
                    api_key=api_key,
                    timeout=timeout,
                    retries=retries,
                ),
                embedding=ModelEndpointConfig(
                    provider="openai",
                    model=embedding_model,
                    api_base=base_url,
                    api_key=api_key,
                    timeout=timeout,
                    retries=retries,
                ),
                vision=ModelEndpointConfig(
                    provider="openai",
                    model=(_first_env("HUNYUAN_VISION_MODEL", "OPENAI_VISION_MODEL") or profile.vision_model).strip(),
                    api_base=base_url,
                    api_key=api_key,
                    timeout=timeout,
                    retries=retries,
                ),
            )
        )
        return cls(gateway=gateway)


def request_embeddings(
    texts: list[str],
    config: OpenAIEnhancementConfig,
    *,
    batch_size: int | None = None,
) -> list[list[float]]:
    if not texts:
        return []
    normalized = [str(text or "") for text in texts]
    resolved_batch = batch_size or get_requirement_analysis_runtime_config().embedding_batch_size
    resolved_batch = max(1, min(256, resolved_batch))

    vectors: list[list[float]] = []
    for start in range(0, len(normalized), resolved_batch):
        batch = normalized[start : start + resolved_batch]
        response_vectors = config.gateway.embedding(batch)
        if len(response_vectors) != len(batch):
            raise ModelGatewayResponseError(
                f"embedding size mismatch: expected={len(batch)} actual={len(response_vectors)}"
            )
        vectors.extend(response_vectors)
    return vectors


def enhance_parsed_requirement(
    requirement_text: str,
    retrieved_context: list[dict[str, Any]],
    rule_based_result: dict[str, Any],
    config: OpenAIEnhancementConfig,
) -> dict[str, Any] | None:
    payload, _, _ = enhance_parsed_requirement_with_metadata(
        requirement_text=requirement_text,
        retrieved_context=retrieved_context,
        rule_based_result=rule_based_result,
        config=config,
    )
    return payload


_MAX_REQUIREMENT_CHARS = 1500
_MAX_CHUNK_CONTENT_CHARS = 300
_MAX_CONTEXT_CHUNKS = 3
_MAX_RESULT_LIST_ITEMS = 5
_MAX_RESULT_ITEM_CHARS = 150


def enhance_parsed_requirement_with_metadata(
    requirement_text: str,
    retrieved_context: list[dict[str, Any]],
    rule_based_result: dict[str, Any],
    config: OpenAIEnhancementConfig,
) -> tuple[dict[str, Any] | None, str, str]:
    truncated_text = requirement_text[:_MAX_REQUIREMENT_CHARS]
    context_preview = [
        {
            "chunk_id": item.get("chunk_id", ""),
            "section_title": item.get("section_title", ""),
            "content": item.get("content", "")[:_MAX_CHUNK_CONTENT_CHARS],
            "score": item.get("score", 0),
        }
        for item in retrieved_context[:_MAX_CONTEXT_CHUNKS]
    ]
    truncated_rule = _truncate_rule_based_result(rule_based_result)
    prompt = {
        "task": "Enhance parsed requirement JSON",
        "requirement_text": truncated_text,
        "retrieved_context": context_preview,
        "rule_based_result": truncated_rule,
        "output_schema": {
            "objective": "string",
            "actors": ["string"],
            "entities": ["string"],
            "preconditions": ["string"],
            "actions": ["string"],
            "expected_results": ["string"],
            "constraints": ["string"],
            "ambiguities": ["string"],
            "api_endpoints": [{"method": "string", "path": "string", "description": "string"}],
        },
        "constraints": [
            "Return strict JSON only",
            "Keep language aligned with requirement text",
            "Do not fabricate unavailable domain facts",
            "Prefer concrete and testable actions/assertions",
            "If the document contains explicit API paths (e.g. POST /api/login), extract each into api_endpoints with method, path, and a short description; leave api_endpoints empty if none are present",
        ],
    }
    try:
        parsed = config.gateway.chat_json(
            system_prompt="You are a QA requirement parser. Return strict JSON only.",
            user_payload=prompt,
            temperature=0.1,
        )
    except ModelGatewayResponseError as exc:
        return None, "llm_response_invalid", exc.__class__.__name__
    except ModelGatewayTimeoutError as exc:
        return None, "llm_timeout", exc.__class__.__name__
    except ModelGatewayError as exc:
        reason, error_type = _classify_gateway_error(exc)
        return None, reason, error_type
    except Exception as exc:  # pragma: no cover - defensive fallback
        return None, "llm_runtime_error", exc.__class__.__name__
    if not isinstance(parsed, dict):
        return None, "llm_response_invalid", "NonDictJSONResponse"
    allowed = {
        "objective",
        "actors",
        "entities",
        "preconditions",
        "actions",
        "expected_results",
        "constraints",
        "ambiguities",
        "api_endpoints",
    }
    cleaned: dict[str, Any] = {}
    for key, value in parsed.items():
        if key not in allowed:
            continue
        if key == "api_endpoints":
            if isinstance(value, list):
                endpoints = []
                for ep in value:
                    if isinstance(ep, dict) and ep.get("path"):
                        endpoints.append({
                            "method": str(ep.get("method", "POST")).strip().upper(),
                            "path": str(ep.get("path", "")).strip(),
                            "description": str(ep.get("description", "")).strip(),
                        })
                cleaned[key] = endpoints
        elif isinstance(value, list):
            cleaned[key] = [str(item).strip() for item in value if str(item).strip()]
        elif value is None:
            continue
        else:
            cleaned[key] = str(value).strip()
    if not cleaned:
        return None, "llm_response_invalid", "EmptyJSONPayload"
    return cleaned, "", ""


def _classify_gateway_error(exc: ModelGatewayError) -> tuple[str, str]:
    message = str(exc).lower()
    error_type = exc.__class__.__name__
    if "http 401" in message or "unauthorized" in message or "api_key is empty" in message:
        return "llm_auth_error", error_type
    if "http 403" in message or "forbidden" in message:
        return "llm_auth_error", error_type
    if "http 429" in message or "rate limit" in message or "quota" in message:
        return "llm_rate_limit", error_type
    if "http " in message:
        return "llm_http_error", error_type
    return "llm_runtime_error", error_type


def _first_env(*names: str) -> str:
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


def _resolve_int(primary: str, fallback: str, *, default: int) -> int:
    for name in (primary, fallback):
        raw = (os.getenv(name) or "").strip()
        if raw.isdigit():
            return int(raw)
    return default


def _resolve_float(primary: str, fallback: str, *, default: float) -> float:
    for name in (primary, fallback):
        raw = (os.getenv(name) or "").strip()
        if not raw:
            continue
        try:
            return float(raw)
        except ValueError:
            continue
    return default


def _truncate_rule_based_result(result: dict[str, Any]) -> dict[str, Any]:
    """Trim list fields so the LLM prompt stays within a reasonable token budget."""
    out: dict[str, Any] = {}
    for key, value in result.items():
        if isinstance(value, list):
            trimmed = [str(item)[:_MAX_RESULT_ITEM_CHARS] for item in value[:_MAX_RESULT_LIST_ITEMS]]
            out[key] = trimmed
        elif isinstance(value, str):
            out[key] = value[:_MAX_REQUIREMENT_CHARS]
        else:
            out[key] = value
    return out


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sqrt(sum(a * a for a in vec_a))
    norm_b = sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


