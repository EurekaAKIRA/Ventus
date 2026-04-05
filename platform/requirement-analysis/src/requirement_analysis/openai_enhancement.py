"""Optional enhancement helpers backed by shared model gateway.

Default provider profile is Tencent Hunyuan (OpenAI-compatible API).
"""

from __future__ import annotations

import logging
import os
import time
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

_LOG = logging.getLogger(__name__)


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
        embedding_retries = _resolve_int("HUNYUAN_RETRIES", "OPENAI_RETRIES", default=profile.retries)
        llm_retries = _resolve_int("HUNYUAN_LLM_RETRIES", "OPENAI_LLM_RETRIES", default=profile.llm_retries)
        gateway = ModelGateway(
            ModelGatewayConfig(
                llm=ModelEndpointConfig(
                    provider="openai",
                    model=llm_model,
                    api_base=base_url,
                    api_key=api_key,
                    timeout=timeout,
                    retries=llm_retries,
                ),
                embedding=ModelEndpointConfig(
                    provider="openai",
                    model=embedding_model,
                    api_base=base_url,
                    api_key=api_key,
                    timeout=timeout,
                    retries=embedding_retries,
                ),
                vision=ModelEndpointConfig(
                    provider="openai",
                    model=(_first_env("HUNYUAN_VISION_MODEL", "OPENAI_VISION_MODEL") or profile.vision_model).strip(),
                    api_base=base_url,
                    api_key=api_key,
                    timeout=timeout,
                    retries=embedding_retries,
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


def _env_int_bounded(name: str, *, default: int, min_value: int, max_value: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if raw.isdigit():
        return max(min_value, min(max_value, int(raw)))
    return default


def _llm_parse_max_requirement_chars() -> int:
    # Keep default prompts compact enough to avoid provider-side latency spikes on long specs.
    return _env_int_bounded("LLM_PARSE_MAX_REQUIREMENT_CHARS", default=8_000, min_value=1_500, max_value=100_000)


def _llm_parse_head_tail_chars() -> tuple[int, int]:
    head = _env_int_bounded("LLM_PARSE_HEAD_CHARS", default=4_500, min_value=500, max_value=80_000)
    tail = _env_int_bounded("LLM_PARSE_TAIL_CHARS", default=2_500, min_value=500, max_value=80_000)
    return head, tail


def _llm_parse_context_limits() -> tuple[int, int]:
    max_chunks = _env_int_bounded("LLM_PARSE_MAX_CONTEXT_CHUNKS", default=4, min_value=1, max_value=20)
    max_chunk_chars = _env_int_bounded("LLM_PARSE_MAX_CHUNK_CHARS", default=800, min_value=100, max_value=8_000)
    return max_chunks, max_chunk_chars


def _llm_parse_rule_list_limits() -> tuple[int, int]:
    max_items = _env_int_bounded("LLM_PARSE_MAX_RULE_LIST_ITEMS", default=8, min_value=3, max_value=50)
    max_item_chars = _env_int_bounded("LLM_PARSE_MAX_RULE_ITEM_CHARS", default=240, min_value=50, max_value=2_000)
    return max_items, max_item_chars


def _compose_requirement_text_for_llm(full_text: str) -> str:
    """Fit long specs into the LLM budget: full text if short, else head + tail with a clear gap marker."""
    max_total = _llm_parse_max_requirement_chars()
    text = (full_text or "").strip()
    if len(text) <= max_total:
        return text
    head_n, tail_n = _llm_parse_head_tail_chars()
    marker = "\n\n--- [文档中间已省略; 以下为文档末尾摘录] ---\n\n"
    budget = max_total - len(marker)
    if budget < 800:
        return text[:max_total]
    head_n = min(head_n, max(budget - 100, budget // 2))
    tail_n = min(tail_n, max(budget - head_n, 0))
    if tail_n <= 0:
        return text[:max_total]
    return text[:head_n] + marker + text[-tail_n:]


def _build_retrieved_context_preview(retrieved_context: list[dict[str, Any]]) -> list[dict[str, Any]]:
    max_chunks, max_chunk_chars = _llm_parse_context_limits()
    preview: list[dict[str, Any]] = []
    for item in retrieved_context[:max_chunks]:
        preview.append({
            "chunk_id": item.get("chunk_id", ""),
            "section_title": item.get("section_title", ""),
            "content": str(item.get("content", ""))[:max_chunk_chars],
            "score": item.get("score", 0),
        })
    return preview


def _fill_llm_enhancement_phase_timings_ms(
    out: dict[str, float] | None,
    *,
    t0: float,
    t_compose: float,
    t_after_chat: float,
    t_end: float,
) -> None:
    if out is None:
        return
    out["llm_compose_prompt_ms"] = round((t_compose - t0) * 1000, 2)
    out["llm_gateway_chat_ms"] = round((t_after_chat - t_compose) * 1000, 2)
    out["llm_normalize_response_ms"] = round((t_end - t_after_chat) * 1000, 2)


def enhance_parsed_requirement_with_metadata(
    requirement_text: str,
    retrieved_context: list[dict[str, Any]],
    rule_based_result: dict[str, Any],
    config: OpenAIEnhancementConfig,
    *,
    out_phase_timings_ms: dict[str, float] | None = None,
) -> tuple[dict[str, Any] | None, str, str]:
    """Call the model with requirement text, retrieved snippet previews, and rule hints."""
    t0 = time.perf_counter()
    composed_requirement = _compose_requirement_text_for_llm(requirement_text)
    context_preview = _build_retrieved_context_preview(retrieved_context)
    truncated_rule = _truncate_rule_based_result(rule_based_result)
    prompt = {
        "task": "Enhance parsed requirement JSON",
        "requirement_text": composed_requirement,
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
            "api_endpoints": [{"method": "string", "path": "string", "description": "string", "group": "string", "depends_on": ["string"]}],
        },
        "constraints": [
            "Return strict JSON only",
            "Keep language aligned with requirement text",
            "Do not fabricate unavailable domain facts",
            "Prefer concrete and testable actions/assertions",
            "If the document contains explicit API paths (e.g. POST /api/login), extract each into api_endpoints with method, path, and a short description; leave api_endpoints empty if none are present",
            "For API specification tables (Method | Path | ...), normalize paths: strip markdown backticks; every valid HTTP method + path row should become one api_endpoints entry; method must be GET, POST, PUT, PATCH, or DELETE; path must start with /",
            "For numbered end-to-end / main-flow narratives (e.g. 创建→解析→执行), express them as a small set of high-level, ordered actions in business language—do not copy raw markdown table rows into actions or preconditions",
            "Do not treat documentation meta-lines (e.g. 本文档不是测试步骤书, 字段以契约为准) as the sole primary user action; prefer real product flows and API surfaces described in the body",
            "Merge duplicate api_endpoints entries with the same method and path",
        ],
    }
    try:
        llm_ep = config.gateway.config.llm
    except AttributeError:
        llm_ep = None
    if llm_ep is not None:
        llm_label = f"model={llm_ep.model!r} base={llm_ep.api_base!r} timeout_s={llm_ep.timeout} max_attempts={llm_ep.retries + 1}"
    else:
        llm_label = "llm_endpoint=unknown"
    ctx_chars = sum(len(str(c.get("content", ""))) for c in context_preview)
    _LOG.info(
        "LLM requirement enhancement request start %s req_chars=%s context_chunks=%s context_body_chars=%s rule_keys=%s",
        llm_label,
        len(composed_requirement),
        len(context_preview),
        ctx_chars,
        sorted(truncated_rule.keys()),
    )
    t_compose = time.perf_counter()
    try:
        parsed = config.gateway.chat_json(
            system_prompt=(
                "You are a senior QA/requirements analyst. Parse technical product and API specification "
                "documents into structured JSON for test scenario generation. "
                "Respect the user's language (e.g. zh-CN). Return strict JSON only, no markdown fences."
            ),
            user_payload=prompt,
            temperature=0.1,
        )
    except ModelGatewayResponseError as exc:
        t_err = time.perf_counter()
        _fill_llm_enhancement_phase_timings_ms(
            out_phase_timings_ms, t0=t0, t_compose=t_compose, t_after_chat=t_err, t_end=t_err
        )
        _LOG.warning("LLM requirement enhancement failed reason=llm_response_invalid error_type=%s %s", exc.__class__.__name__, exc)
        return None, "llm_response_invalid", exc.__class__.__name__
    except ModelGatewayTimeoutError as exc:
        t_err = time.perf_counter()
        _fill_llm_enhancement_phase_timings_ms(
            out_phase_timings_ms, t0=t0, t_compose=t_compose, t_after_chat=t_err, t_end=t_err
        )
        max_att = (llm_ep.retries + 1) if llm_ep is not None else 0
        _LOG.warning(
            "LLM requirement enhancement failed reason=llm_timeout error_type=%s after_max_attempts=%s %s",
            exc.__class__.__name__,
            max_att,
            exc,
        )
        return None, "llm_timeout", exc.__class__.__name__
    except ModelGatewayError as exc:
        t_err = time.perf_counter()
        _fill_llm_enhancement_phase_timings_ms(
            out_phase_timings_ms, t0=t0, t_compose=t_compose, t_after_chat=t_err, t_end=t_err
        )
        reason, error_type = _classify_gateway_error(exc)
        _LOG.warning("LLM requirement enhancement failed reason=%s error_type=%s %s", reason, error_type, exc)
        return None, reason, error_type
    except Exception as exc:  # pragma: no cover - defensive fallback
        t_err = time.perf_counter()
        _fill_llm_enhancement_phase_timings_ms(
            out_phase_timings_ms, t0=t0, t_compose=t_compose, t_after_chat=t_err, t_end=t_err
        )
        _LOG.warning("LLM requirement enhancement failed reason=llm_runtime_error error_type=%s %s", exc.__class__.__name__, exc)
        return None, "llm_runtime_error", exc.__class__.__name__
    t_after_chat = time.perf_counter()
    if not isinstance(parsed, dict):
        _fill_llm_enhancement_phase_timings_ms(
            out_phase_timings_ms, t0=t0, t_compose=t_compose, t_after_chat=t_after_chat, t_end=t_after_chat
        )
        _LOG.warning("LLM requirement enhancement failed reason=llm_response_invalid error_type=NonDictJSONResponse")
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
    list_string_fields = {
        "actors",
        "entities",
        "preconditions",
        "actions",
        "expected_results",
        "constraints",
        "ambiguities",
    }

    def _normalize_string_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            stripped = value.strip()
            return [stripped] if stripped else []
        return []

    cleaned: dict[str, Any] = {}
    for key, value in parsed.items():
        if key not in allowed:
            continue
        if key == "api_endpoints":
            if isinstance(value, list):
                endpoints = []
                for ep in value:
                    if isinstance(ep, dict) and ep.get("path"):
                        entry: dict[str, Any] = {
                            "method": str(ep.get("method", "POST")).strip().upper(),
                            "path": str(ep.get("path", "")).strip(),
                            "description": str(ep.get("description", "")).strip(),
                        }
                        if ep.get("group"):
                            entry["group"] = str(ep["group"]).strip()
                        if ep.get("depends_on") and isinstance(ep["depends_on"], list):
                            entry["depends_on"] = [str(d).strip() for d in ep["depends_on"] if str(d).strip()]
                        endpoints.append(entry)
                cleaned[key] = endpoints
        elif key in list_string_fields:
            cleaned[key] = _normalize_string_list(value)
        elif value is None:
            continue
        else:
            cleaned[key] = str(value).strip()
    if not cleaned:
        t_end = time.perf_counter()
        _fill_llm_enhancement_phase_timings_ms(
            out_phase_timings_ms, t0=t0, t_compose=t_compose, t_after_chat=t_after_chat, t_end=t_end
        )
        _LOG.warning("LLM requirement enhancement failed reason=llm_response_invalid error_type=EmptyJSONPayload")
        return None, "llm_response_invalid", "EmptyJSONPayload"
    t_end = time.perf_counter()
    _fill_llm_enhancement_phase_timings_ms(
        out_phase_timings_ms, t0=t0, t_compose=t_compose, t_after_chat=t_after_chat, t_end=t_end
    )
    _LOG.info(
        "LLM requirement enhancement succeeded %s payload_keys=%s api_endpoints=%s",
        llm_label,
        sorted(cleaned.keys()),
        len(cleaned.get("api_endpoints", [])) if isinstance(cleaned.get("api_endpoints"), list) else 0,
    )
    return cleaned, "", ""


def _classify_gateway_error(exc: ModelGatewayError) -> tuple[str, str]:
    message = str(exc).lower()
    error_type = exc.__class__.__name__
    if "10035" in message or "wsaewouldblock" in message or "would block" in message:
        return "llm_network_error", error_type
    if any(
        token in message
        for token in (
            "connection reset",
            "connection aborted",
            "connection refused",
            "name or service not known",
            "temporary failure in name resolution",
            "ssl",
        )
    ):
        return "llm_network_error", error_type
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
    max_items, max_item_chars = _llm_parse_rule_list_limits()
    max_str = _llm_parse_max_requirement_chars()
    out: dict[str, Any] = {}
    for key, value in result.items():
        if isinstance(value, list):
            trimmed = [str(item)[:max_item_chars] for item in value[:max_items]]
            out[key] = trimmed
        elif isinstance(value, str):
            out[key] = value[:max_str]
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
