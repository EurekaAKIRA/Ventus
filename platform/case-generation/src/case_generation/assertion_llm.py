"""Optional LLM enhancement for assertion generation."""

from __future__ import annotations

import os
from dataclasses import dataclass
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


ALLOWED_ASSERTION_OPS = {
    "eq",
    "ne",
    "ge",
    "le",
    "contains",
    "not_contains",
    "exists",
    "not_exists",
    "gt",
    "lt",
    "startswith",
    "endswith",
    "matches",
    "len_eq",
    "len_gt",
    "len_lt",
    "len_ge",
    "len_le",
    "in",
    "not_in",
    "is_true",
    "is_false",
}
ALLOWED_ASSERTION_CATEGORIES = {
    "status",
    "schema",
    "field_presence",
    "field_value",
    "collection",
    "text",
    "performance",
    "business",
}
ALLOWED_ASSERTION_SEVERITIES = {"critical", "major", "minor"}


@dataclass(slots=True)
class AssertionLLMConfig:
    gateway: ModelGateway
    provider_profile: str

    @classmethod
    def from_env(cls, provider_profile: str | None = None) -> "AssertionLLMConfig | None":
        api_key = _first_env("HUNYUAN_API_KEY", "OPENAI_API_KEY")
        if not api_key:
            return None
        runtime = get_requirement_analysis_runtime_config()
        requested_profile = provider_profile or runtime.assertion_enhancement.provider_profile
        profile_name, profile = get_requirement_analysis_model_profile(requested_profile)
        base_url = (_first_env("HUNYUAN_BASE_URL", "OPENAI_BASE_URL") or profile.base_url).rstrip("/")
        llm_model = (_first_env("HUNYUAN_LLM_MODEL", "OPENAI_LLM_MODEL") or profile.llm_model).strip()
        timeout = _resolve_float("HUNYUAN_TIMEOUT_SECONDS", "OPENAI_TIMEOUT_SECONDS", default=profile.timeout_seconds)
        retries = _resolve_int("HUNYUAN_RETRIES", "OPENAI_RETRIES", default=profile.retries)
        return cls(
            gateway=ModelGateway(
                ModelGatewayConfig(
                    llm=ModelEndpointConfig(
                        provider="openai",
                        model=llm_model,
                        api_base=base_url,
                        api_key=api_key,
                        timeout=timeout,
                        retries=retries,
                    )
                )
            ),
            provider_profile=profile_name,
        )


def generate_assertion_candidates(
    *,
    mode: str,
    task_context: dict[str, Any],
    parsed_requirement: dict[str, Any],
    scenario: dict[str, Any],
    step: dict[str, Any],
    request: dict[str, Any],
    rule_assertions: list[dict[str, Any]],
    known_endpoint_fields: list[str],
    provider_profile: str | None = None,
) -> tuple[list[dict[str, Any]], str, str]:
    config = AssertionLLMConfig.from_env(provider_profile)
    if config is None:
        return [], "llm_not_configured", "MissingAPIKey"
    prompt = {
        "task": "Generate structured API assertions",
        "mode": mode,
        "task_context": {
            "task_id": task_context.get("task_id", ""),
            "task_name": task_context.get("task_name", ""),
        },
        "scenario": {
            "scenario_id": scenario.get("scenario_id", ""),
            "name": scenario.get("name", ""),
            "goal": scenario.get("goal", ""),
        },
        "step": {
            "step_id": step.get("step_id", ""),
            "step_type": step.get("step_type", step.get("type", "")),
            "text": step.get("text", ""),
        },
        "request": request,
        "rule_assertions": rule_assertions,
        "known_endpoint_fields": known_endpoint_fields[:10],
        "requirement_summary": {
            "objective": parsed_requirement.get("objective", ""),
            "actions": list(parsed_requirement.get("actions") or [])[:6],
            "expected_results": list(parsed_requirement.get("expected_results") or [])[:6],
            "api_endpoints": list(parsed_requirement.get("api_endpoints") or [])[:8],
        },
        "output_schema": {
            "assertions": [
                {
                    "source": "string",
                    "op": "string",
                    "expected": "any",
                    "severity": "critical|major|minor",
                    "category": "status|schema|field_presence|field_value|collection|text|performance|business",
                    "confidence": "0.0-1.0",
                    "generated_by": "llm|llm_repair",
                    "reasoning": "string",
                }
            ]
        },
        "constraints": [
            "Return strict JSON only",
            "Only use supported operators",
            "Prefer executable assertions over natural language",
            "Avoid duplicating the existing rule assertions unless you are strengthening them",
            "Do not invent fields unless strongly implied by request or expected results",
            "Keep at most 4 assertions",
        ],
    }
    try:
        payload = config.gateway.chat_json(
            system_prompt="You generate structured API assertions. Return strict JSON only.",
            user_payload=prompt,
            temperature=0.1,
        )
    except ModelGatewayResponseError as exc:
        return [], "llm_response_invalid", exc.__class__.__name__
    except ModelGatewayTimeoutError as exc:
        return [], "llm_timeout", exc.__class__.__name__
    except ModelGatewayError as exc:
        return [], "llm_runtime_error", exc.__class__.__name__
    except Exception as exc:  # pragma: no cover - defensive fallback
        return [], "llm_runtime_error", exc.__class__.__name__
    assertions = payload.get("assertions")
    if not isinstance(assertions, list):
        return [], "llm_response_invalid", "InvalidAssertionPayload"
    cleaned: list[dict[str, Any]] = []
    for index, item in enumerate(assertions, start=1):
        if not isinstance(item, dict):
            continue
        source = str(item.get("source", "")).strip()
        op = str(item.get("op", "")).strip()
        if not source or op not in ALLOWED_ASSERTION_OPS:
            continue
        severity = str(item.get("severity", "major")).strip().lower()
        category = str(item.get("category", "business")).strip().lower()
        cleaned.append(
            {
                "assertion_id": f"{mode}_cand_{index:02d}",
                "source": source,
                "op": op,
                "expected": item.get("expected"),
                "severity": severity if severity in ALLOWED_ASSERTION_SEVERITIES else "major",
                "category": category if category in ALLOWED_ASSERTION_CATEGORIES else "business",
                "confidence": _clamp_confidence(item.get("confidence")),
                "generated_by": "llm_repair" if mode == "repair" else "llm",
                "reasoning": str(item.get("reasoning", "")).strip()[:200],
                "fallback_used": False,
            }
        )
    if not cleaned:
        return [], "llm_response_invalid", "EmptyAssertionPayload"
    return cleaned, "", ""


def _clamp_confidence(raw: Any) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 0.5
    return max(0.0, min(1.0, round(value, 4)))


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
