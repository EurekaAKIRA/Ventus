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
    "type_is",
    "type_in",
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
        llm_retries = _resolve_int("HUNYUAN_LLM_RETRIES", "OPENAI_LLM_RETRIES", default=profile.llm_retries)
        max_tokens = _resolve_optional_int(
            "HUNYUAN_ASSERTION_LLM_MAX_TOKENS",
            "OPENAI_ASSERTION_LLM_MAX_TOKENS",
            fallback_names=("HUNYUAN_LLM_MAX_TOKENS", "OPENAI_LLM_MAX_TOKENS"),
            default=700,
        )
        return cls(
            gateway=ModelGateway(
                ModelGatewayConfig(
                    llm=ModelEndpointConfig(
                        provider="openai",
                        model=llm_model,
                        api_base=base_url,
                        api_key=api_key,
                        timeout=timeout,
                        retries=llm_retries,
                        max_tokens=max_tokens,
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
            "If rule_assertions already contain a status_code assertion, do not generate another status_code assertion",
            "For scalar JSON value checks, source must be a concrete path such as json.title or json.message; never use source=json with eq/contains against a scalar",
            "Avoid exact dynamic response prose unless the field path is known and the value is documented",
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
        expected = item.get("expected")
        if _missing_required_expected(op, expected):
            continue
        if _is_unsafe_llm_header_assertion(source, expected):
            continue
        if _is_json_content_type_assertion(source, expected):
            if str(request.get("method", "")).upper().strip() == "DELETE":
                continue
            if op not in {"eq", "contains"}:
                continue
            op = "contains"
            expected = "application/json"
        source = _repair_or_reject_llm_source(
            source=source,
            op=op,
            expected=expected,
            request=request,
            rule_assertions=rule_assertions,
            known_endpoint_fields=known_endpoint_fields,
        )
        if not source:
            continue
        severity = str(item.get("severity", "major")).strip().lower()
        category = str(item.get("category", "business")).strip().lower()
        cleaned.append(
            {
                "assertion_id": f"{mode}_cand_{index:02d}",
                "source": source,
                "op": op,
                "expected": expected,
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


_ROOT_JSON_SCALAR_OPS = {"eq", "ne", "contains", "not_contains", "startswith", "endswith", "matches", "in", "not_in"}


def _repair_or_reject_llm_source(
    *,
    source: str,
    op: str,
    expected: Any,
    request: dict[str, Any],
    rule_assertions: list[dict[str, Any]],
    known_endpoint_fields: list[str] | None = None,
) -> str:
    normalized = source.strip()
    lowered = normalized.lower()
    if lowered == "status_code" and _has_rule_status_assertion(rule_assertions):
        return ""
    repaired_wrapped = _repair_wrapped_response_source(normalized, request)
    if repaired_wrapped:
        return repaired_wrapped
    if lowered == "json" and op == "exists":
        repaired_exists = _root_json_exists_field_source(expected)
        if repaired_exists:
            return repaired_exists
        return "" if _has_rule_json_assertion(rule_assertions) else normalized
    if lowered == "json" and op == "not_exists":
        return ""
    if lowered == "json" and op in _ROOT_JSON_SCALAR_OPS and _is_scalar_expected(expected):
        if op in {"eq", "ne"}:
            repaired = _source_for_request_body_value(request, expected)
            if repaired:
                return repaired
        return ""
    if lowered == "json":
        if op in {"eq", "ne", "contains", "not_contains", "in", "not_in", "matches", "startswith", "endswith"}:
            return ""
        return "" if _has_rule_json_assertion(rule_assertions) else normalized
    if op in _ROOT_JSON_SCALAR_OPS and not _is_scalar_expected(expected):
        return ""
    if lowered != "json" or op not in _ROOT_JSON_SCALAR_OPS:
        if _is_path_identifier_guess(normalized, expected, request, known_endpoint_fields or []):
            return ""
        return normalized if _is_safe_llm_json_field_source(normalized, request, rule_assertions, known_endpoint_fields or []) else ""
    return ""


def _has_rule_status_assertion(rule_assertions: list[dict[str, Any]]) -> bool:
    return any(str(item.get("source", "")).strip().lower() == "status_code" for item in rule_assertions if isinstance(item, dict))


def _has_rule_json_assertion(rule_assertions: list[dict[str, Any]]) -> bool:
    return any(str(item.get("source", "")).strip().lower() == "json" for item in rule_assertions if isinstance(item, dict))


def _rule_sources(rule_assertions: list[dict[str, Any]]) -> set[str]:
    return {str(item.get("source", "")).strip().lower() for item in rule_assertions if isinstance(item, dict)}


def _is_scalar_expected(value: Any) -> bool:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return True
    if isinstance(value, list):
        return all(isinstance(item, (str, int, float, bool)) or item is None for item in value)
    return False


def _missing_required_expected(op: str, expected: Any) -> bool:
    expected_ops = {
        "eq",
        "ne",
        "ge",
        "le",
        "contains",
        "not_contains",
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
        "type_is",
        "type_in",
        "in",
        "not_in",
    }
    if op not in expected_ops:
        return False
    if expected is None:
        return True
    if op in {"type_in", "in", "not_in"}:
        return not isinstance(expected, list) or not expected
    return False


def _is_json_content_type_exact_assertion(source: str, op: str, expected: Any) -> bool:
    return op == "eq" and _is_json_content_type_assertion(source, expected)


def _is_json_content_type_assertion(source: str, expected: Any) -> bool:
    normalized_source = source.strip().lower()
    if normalized_source not in {"headers.content-type", "headers.content_type"}:
        return False
    return isinstance(expected, str) and expected.strip().lower() == "application/json"


def _is_unsafe_llm_header_assertion(source: str, expected: Any) -> bool:
    lowered = source.strip().lower()
    if not lowered.startswith("headers."):
        return False
    return not _is_json_content_type_assertion(source, expected)


def _root_json_exists_field_source(expected: Any) -> str:
    if not isinstance(expected, str):
        return ""
    field = expected.strip().strip("`").strip()
    if not field or "." in field or "[" in field or "/" in field:
        return ""
    lowered = field.lower()
    if lowered in {"json", "object", "array", "response", "body"}:
        return ""
    if not lowered.replace("_", "").isalnum():
        return ""
    return f"json.{field}"


def _source_for_request_body_value(request: dict[str, Any], expected: Any) -> str:
    body = request.get("json")
    if not isinstance(body, dict):
        return ""
    matches: list[str] = []
    for key, value in body.items():
        if isinstance(value, dict):
            continue
        if value == expected:
            matches.append(str(key))
        elif isinstance(value, (int, float)) and isinstance(expected, str):
            try:
                if value == float(expected):
                    matches.append(str(key))
            except ValueError:
                pass
        elif isinstance(value, str) and isinstance(expected, str) and value.strip() == expected.strip():
            matches.append(str(key))
    if not matches:
        return ""
    preferred = [key for key in matches if key.lower() not in {"id", "user_id", "userid"}]
    field = (preferred or matches)[0]
    source = _response_source_for_request_body_field(request, field)
    if _is_safe_request_body_response_source(source, request):
        return source
    return ""


def _repair_wrapped_response_source(source: str, request: dict[str, Any]) -> str:
    if not source.lower().startswith("json."):
        return ""
    field = source[5:]
    if "." in field or "[" in field:
        return ""
    body = request.get("json")
    if not isinstance(body, dict) or field not in body:
        return ""
    repaired = _response_source_for_request_body_field(request, field)
    return repaired if repaired != source else ""


def _is_safe_llm_json_field_source(
    source: str,
    request: dict[str, Any],
    rule_assertions: list[dict[str, Any]],
    known_endpoint_fields: list[str],
) -> bool:
    lowered = source.strip().lower()
    if not lowered.startswith("json."):
        return True
    if lowered in _rule_sources(rule_assertions):
        return True
    if _is_echo_response_source(lowered, request):
        return True
    if _is_safe_request_body_response_source(source, request):
        return True
    if _is_common_response_metadata_field(lowered):
        return True
    known = {str(field).strip().lower() for field in known_endpoint_fields if str(field).strip()}
    if not known:
        return False
    field_path = source[5:].strip()
    root_field = field_path.split(".", 1)[0].split("[", 1)[0].lower()
    leaf_field = field_path.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if root_field in known or leaf_field in known:
        method = str(request.get("method", "")).upper().strip()
        return method in {"PUT", "PATCH"} or _is_echo_request(request) or _is_wrapped_create_request(request)
    return False


def _is_common_response_metadata_field(source: str) -> bool:
    return source.lower() in {"json.message", "json.code", "json.type", "json.status"}


def _is_path_identifier_guess(
    source: str,
    expected: Any,
    request: dict[str, Any],
    known_endpoint_fields: list[str],
) -> bool:
    lowered = source.strip().lower()
    if not lowered.startswith("json."):
        return False
    if known_endpoint_fields:
        known = {str(field).strip().lower() for field in known_endpoint_fields if str(field).strip()}
        leaf = lowered.rsplit(".", 1)[-1]
        if leaf in known:
            return False
    method = str(request.get("method", "")).upper().strip()
    if method not in {"GET", "DELETE"}:
        return False
    leaf = lowered.rsplit(".", 1)[-1]
    identifier_fields = {
        "id",
        "petid",
        "pet_id",
        "orderid",
        "order_id",
        "bookingid",
        "booking_id",
        "username",
        "user",
        "token",
    }
    if leaf not in identifier_fields:
        return False
    path_tail = _request_path(request).rstrip("/").rsplit("/", 1)[-1].lower()
    expected_text = str(expected or "").strip("{} ").lower()
    return bool(path_tail and (path_tail in expected_text or expected_text in path_tail or expected_text))


def _response_source_for_request_body_field(request: dict[str, Any], field: str) -> str:
    method = str(request.get("method", "")).upper().strip()
    path = _request_path(request)
    if method == "POST" and _is_wrapped_create_request(request):
        return f"json.booking.{field}"
    return f"json.{field}"


def _is_safe_request_body_response_source(source: str, request: dict[str, Any]) -> bool:
    lowered = source.strip().lower()
    body = request.get("json")
    if not isinstance(body, dict):
        return False
    field_path = lowered[5:] if lowered.startswith("json.") else lowered
    leaf = field_path.rsplit(".", 1)[-1]
    body_fields = {str(key).lower() for key in body.keys()}
    if leaf not in body_fields:
        return False
    method = str(request.get("method", "")).upper().strip()
    if method in {"PUT", "PATCH"} and lowered == f"json.{leaf}":
        return True
    if _is_wrapped_create_request(request) and lowered == f"json.booking.{leaf}":
        return True
    if _is_echo_request(request) and _is_echo_response_source(lowered, request):
        return True
    return False


def _is_echo_request(request: dict[str, Any]) -> bool:
    path = _request_path(request).lower()
    return path.endswith("/post") or path.endswith("/anything") or path.endswith("/get")


def _is_echo_response_source(source: str, request: dict[str, Any]) -> bool:
    path = _request_path(request).lower()
    if path.endswith("/get"):
        return source.startswith("json.args.")
    if path.endswith("/post") or path.endswith("/anything"):
        return source.startswith("json.json.") or source.startswith("json.args.")
    return False


def _is_wrapped_create_request(request: dict[str, Any]) -> bool:
    return str(request.get("method", "")).upper().strip() == "POST" and _request_path(request).lower() == "/booking"


def _request_path(request: dict[str, Any]) -> str:
    raw = str(request.get("url", "")).strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        try:
            from urllib.parse import urlparse

            return urlparse(raw).path or raw
        except ValueError:
            return raw
    return raw.split("?", 1)[0]


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


def _resolve_optional_int(
    primary: str,
    fallback: str,
    *,
    fallback_names: tuple[str, ...] = (),
    default: int | None,
) -> int | None:
    for name in (primary, fallback, *fallback_names):
        raw = (os.getenv(name) or "").strip()
        if not raw:
            continue
        if raw.lower() in {"none", "null", "off", "0"}:
            return None
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
