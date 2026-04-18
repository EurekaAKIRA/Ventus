"""Rule-based assertion planning plus optional LLM enhancement."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from platform_shared import TaskContext, get_requirement_analysis_runtime_config
from platform_shared.endpoint_policy import expects_json_envelope

from .assertion_llm import (
    ALLOWED_ASSERTION_CATEGORIES,
    ALLOWED_ASSERTION_OPS,
    ALLOWED_ASSERTION_SEVERITIES,
    generate_assertion_candidates,
)

FIELD_TOKEN_RE = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_]*)`|\"([a-zA-Z_][a-zA-Z0-9_]*)\"|'([a-zA-Z_][a-zA-Z0-9_]*)'")
FIELD_NAME_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b")
SUCCESS_STATUS_RE = re.compile(r"\b(200|201|202|204)\b")
ASSERTION_FIELD_STOPWORDS = {
    "api",
    "code",
    "data",
    "environment",
    "execute",
    "execution_mode",
    "field",
    "fields",
    "json",
    "message",
    "parse",
    "query",
    "report",
    "request",
    "requirement_text",
    "response",
    "step",
    "success",
    "task",
    "tasks",
    "text",
    "timestamp",
    "validate",
}
QUERY_ENDPOINT_FIELD_ALLOWLIST: tuple[tuple[str, set[str]], ...] = (
    ("/parsed-requirement", {"task_id", "status", "parsed_requirement", "parse_metadata"}),
    ("/retrieved-context", {"task_id", "status", "retrieved_context", "retrieval_context", "retrieval_items"}),
    ("/scenarios/generate", {"task_id", "status", "scenarios"}),
    ("/scenarios", {"scenario_id", "scenarios", "steps", "name", "priority"}),
    ("/dsl", {"dsl_version", "task_id", "task_name", "feature_name", "scenarios", "metadata"}),
    ("/feature", {"feature_text", "task_id", "task_name"}),
    ("/execution/logs", {"task_id", "logs", "entries", "status"}),
    ("/execution", {"task_id", "status", "scenario_results", "summary", "started_at", "finished_at"}),
    (
        "/analysis-report",
        {"task_id", "status", "summary", "warnings", "analysis_report", "assertion_quality_summary"},
    ),
)
TASK_DETAIL_FIELD_ALLOWLIST = {
    "task_id",
    "task_name",
    "status",
    "task_context",
    "parse_metadata",
    "parsed_requirement",
    "retrieved_context",
    "scenarios",
    "test_case_dsl",
    "validation_report",
    "analysis_report",
    "feature_text",
    "execution_result",
}
REQUEST_ASSERTION_SOURCE_ALLOWLIST: tuple[tuple[str, set[str]], ...] = (
    (
        "/api/tasks",
        {
            "status_code",
            "json",
            "json.data",
            "json.data.task_id",
            "json.data.task_context",
            "json.data.task_context.task_id",
            "json.data.task_context.task_name",
            "json.data.task_context.source_type",
            "elapsed_ms",
            "headers.content-type",
        },
    ),
    (
        "/api/tasks/{task_id}",
        {
            "status_code",
            "json",
            "json.data",
            "json.data.task_id",
            "json.data.task_name",
            "json.data.status",
            "json.data.task_context",
            "json.data.parse_metadata",
            "json.data.parsed_requirement",
            "json.data.retrieved_context",
            "json.data.scenarios",
            "json.data.test_case_dsl",
            "json.data.analysis_report",
            "json.data.execution_result",
            "elapsed_ms",
            "headers.content-type",
        },
    ),
    (
        "/api/tasks/{task_id}/parse",
        {
            "status_code",
            "json",
            "json.task_id",
            "json.status",
            "json.parsed_requirement",
            "json.parse_metadata",
            "elapsed_ms",
            "headers.content-type",
        },
    ),
    (
        "/api/tasks/{task_id}/parsed-requirement",
        {
            "status_code",
            "json",
            "json.objective",
            "json.actions",
            "json.expected_results",
            "json.api_endpoints",
            "json.entities",
            "elapsed_ms",
            "headers.content-type",
        },
    ),
    (
        "/api/tasks/{task_id}/retrieved-context",
        {
            "status_code",
            "json",
            "json.data",
            "json.items",
            "elapsed_ms",
            "headers.content-type",
        },
    ),
    (
        "/api/tasks/{task_id}/scenarios/generate",
        {
            "status_code",
            "json",
            "json.task_id",
            "json.scenario_count",
            "json.scenarios",
            "elapsed_ms",
            "headers.content-type",
        },
    ),
    (
        "/api/tasks/{task_id}/scenarios",
        {
            "status_code",
            "json",
            "json.scenarios",
            "json.items",
            "elapsed_ms",
            "headers.content-type",
        },
    ),
    (
        "/api/tasks/{task_id}/dsl",
        {
            "status_code",
            "json",
            "json.task_id",
            "json.task_name",
            "json.scenarios",
            "json.metadata",
            "json.dsl_version",
            "elapsed_ms",
            "headers.content-type",
        },
    ),
)
SIMPLE_ENDPOINT_SEGMENTS = frozenset({
    "health", "healthz", "ready", "readyz", "live", "livez",
    "ping", "version", "info", "docs", "openapi.json", "swagger",
    "status", "metrics", "favicon.ico",
})
PLACEHOLDER_SEGMENT_RE = re.compile(r"\{\{?\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}?\}")


def _is_simple_endpoint(url: str) -> bool:
    """Return True for infrastructure/utility endpoints that need only minimal assertions."""
    last_segment = url.rstrip("/").rsplit("/", 1)[-1].lower()
    return last_segment in SIMPLE_ENDPOINT_SEGMENTS


NON_EXECUTABLE_ASSERTION_HINTS = (
    "当前 task-center api 统一使用如下响应结构",
    "因此，联调和断言设计中不应",
    "不应把任务详情查询接口当作列表接口",
    "不应假设存在",
    "响应结构",
    "断言设计",
    "联调",
)
HIGH_VALUE_ASSERTION_ENDPOINT_SUFFIXES = (
    "/api/tasks",
    "/api/tasks/{task_id}/parse",
    "/api/tasks/{task_id}/scenarios/generate",
    "/api/tasks/{task_id}/dsl",
    "/api/tasks/{task_id}/execute",
    "/api/tasks/{task_id}/analysis-report",
    "/api/tasks/{task_id}/validation-report",
)
# Hostnames (exact, no port) for external APIs where LLM assertion enhancement is allowed.
LLM_ASSERTION_ALLOWED_API_HOSTS: frozenset[str] = frozenset(
    {
        "restful-booker.herokuapp.com",
    }
)
_ASSERTION_LLM_CACHE: dict[str, tuple[list[dict[str, Any]], str, str]] = {}


@dataclass(slots=True)
class PlannedAssertions:
    assertions: list[dict[str, Any]]
    quality: dict[str, Any]


class AssertionPlanner:
    """Create deterministic assertions and optionally enhance them with an LLM."""

    def __init__(
        self,
        *,
        task_context: TaskContext,
        parsed_requirement: dict[str, Any],
        scenario: dict[str, Any],
        step: dict[str, Any],
        request: dict[str, Any],
        save_context: dict[str, str],
        intent: str,
        fallback_assertions: list[dict[str, Any] | str] | None = None,
        enable_llm: bool | None = None,
    ):
        self.task_context = task_context
        self.parsed_requirement = parsed_requirement
        self.scenario = scenario
        self.step = step
        self.request = request
        self.save_context = save_context
        self.intent = intent
        self.fallback_assertions = fallback_assertions or []
        self.runtime = get_requirement_analysis_runtime_config().assertion_enhancement
        self.enable_llm = self.runtime.enabled if enable_llm is None else (self.runtime.enabled and enable_llm)

    def build(self) -> PlannedAssertions:
        if not self.request:
            normalized = normalize_assertions(
                self._coerce_assertions(self.fallback_assertions),
                max_assertions=max(1, self.runtime.max_assertions_per_step),
                request=self.request,
            )
            return PlannedAssertions(
                assertions=normalized,
                quality=_build_quality_summary(normalized, llm_attempted=False, fallback_reason="", invalid_count=0),
            )

        rule_assertions = RuleAssertionBuilder(
            parsed_requirement=self.parsed_requirement,
            scenario=self.scenario,
            step=self.step,
            request=self.request,
            save_context=self.save_context,
            intent=self.intent,
        ).build()

        llm_attempted = False
        fallback_reason = ""
        invalid_count = 0
        llm_assertions: list[dict[str, Any]] = []
        llm_error_type = ""
        known_fields = _extract_known_fields(self.parsed_requirement, self.step)
        if self.enable_llm and _should_attempt_llm_for_step(self.step, self.request):
            llm_attempted = True
            llm_assertions, fallback_reason, llm_error_type = _generate_assertion_candidates_cached(
                mode="enhance",
                task_context=self.task_context.to_dict(),
                parsed_requirement=self.parsed_requirement,
                scenario=self.scenario,
                step=self.step,
                request=self.request,
                rule_assertions=rule_assertions,
                known_endpoint_fields=known_fields,
                provider_profile=self.runtime.provider_profile,
            )
            if self.runtime.repair_enabled and _is_weak_assertion_set(rule_assertions + llm_assertions):
                repair_assertions, repair_reason, repair_error_type = _generate_assertion_candidates_cached(
                    mode="repair",
                    task_context=self.task_context.to_dict(),
                    parsed_requirement=self.parsed_requirement,
                    scenario=self.scenario,
                    step=self.step,
                    request=self.request,
                    rule_assertions=rule_assertions + llm_assertions,
                    known_endpoint_fields=known_fields,
                    provider_profile=self.runtime.provider_profile,
                )
                if repair_assertions:
                    llm_assertions.extend(repair_assertions)
                    fallback_reason = ""
                    llm_error_type = ""
                elif not fallback_reason:
                    fallback_reason = repair_reason
                    llm_error_type = repair_error_type

        combined = rule_assertions + llm_assertions
        normalized = normalize_assertions(
            combined,
            min_confidence=self.runtime.min_confidence if self.runtime.quality_gate_enabled else 0.0,
            max_assertions=self.runtime.max_assertions_per_step,
            request=self.request,
        )
        invalid_count = max(len(combined) - len(normalized), 0)
        if not normalized:
            normalized = normalize_assertions(
                rule_assertions,
                max_assertions=self.runtime.max_assertions_per_step,
                request=self.request,
            )
            fallback_reason = fallback_reason or "quality_gate_rejected_all"
        if fallback_reason:
            for assertion in normalized:
                if assertion.get("generated_by") == "rules":
                    assertion["fallback_used"] = True
        quality = _build_quality_summary(
            normalized,
            llm_attempted=llm_attempted,
            fallback_reason=fallback_reason,
            invalid_count=invalid_count,
        )
        if llm_error_type:
            quality["llm_error_type"] = llm_error_type
        return PlannedAssertions(assertions=normalized, quality=quality)

    @staticmethod
    def _coerce_assertions(assertions: list[dict[str, Any] | str]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for index, item in enumerate(assertions, start=1):
            if isinstance(item, str):
                output.append(
                    {
                        "assertion_id": f"fallback_{index:02d}",
                        "source": "text",
                        "op": "contains",
                        "expected": item,
                        "severity": "major",
                        "category": "business",
                        "confidence": 0.4,
                        "generated_by": "manual",
                        "reasoning": "legacy_string_assertion",
                        "fallback_used": False,
                    }
                )
            elif isinstance(item, dict):
                output.append(dict(item))
        return output


class RuleAssertionBuilder:
    def __init__(
        self,
        *,
        parsed_requirement: dict[str, Any],
        scenario: dict[str, Any],
        step: dict[str, Any],
        request: dict[str, Any],
        save_context: dict[str, str],
        intent: str,
    ):
        self.parsed_requirement = parsed_requirement
        self.scenario = scenario
        self.step = step
        self.request = request
        self.save_context = save_context
        self.intent = intent

    def build(self) -> list[dict[str, Any]]:
        assertions: list[dict[str, Any]] = []
        expected_statuses = _resolve_expected_statuses(self.intent, self.request, self.step, self.parsed_requirement)
        capability = _request_capability(self.request, self.parsed_requirement, self.intent)
        header_only_save = any(str(source).startswith("headers.") for source in self.save_context.values())
        non_json_response = _prefers_non_json_response(self.request, self.parsed_requirement)
        if len(expected_statuses) == 1:
            assertions.append(_assertion("status_code", "eq", expected_statuses[0], "critical", "status", 0.98, "request_status_template", "rules"))
        else:
            assertions.append(_assertion("status_code", "in", expected_statuses, "critical", "status", 0.96, "request_status_template", "rules"))

        for source in _dedupe_preserve(self.save_context.values()):
            category = "field_presence" if str(source).startswith("json") else "business"
            assertions.append(_assertion(source, "exists", None, "major", category, 0.93, "saved_context_exists", "rules"))

        url = str(self.request.get("url", ""))
        lowered_text = str(self.step.get("text", "")).lower()
        if self.intent == "login":
            login_sources = [str(source) for source in self.save_context.values()]
            if any(source.endswith(".token") for source in login_sources) or any(token in lowered_text for token in ("token", "bearer", "jwt")):
                assertions.append(_assertion("json.token", "exists", None, "critical", "field_presence", 0.95, "login_token_expected", "rules"))
            elif not non_json_response:
                assertions.append(_assertion("json", "exists", None, "major", "schema", 0.76, "login_response_present", "rules"))
            else:
                assertions.append(_assertion("body_text", "exists", None, "major", "text", 0.7, "login_body_present", "rules"))
            if "session" in lowered_text or "session" in url:
                assertions.append(_assertion("headers.set-cookie", "exists", None, "major", "field_presence", 0.85, "login_session_expected", "rules"))
        if self.intent == "create":
            if any(token in url for token in ("/parse", "/execute", "/execution/stop", "/scenarios/generate")):
                return assertions
            if url.endswith("/tasks"):
                assertions.append(_assertion("json.data.task_id", "exists", None, "critical", "field_presence", 0.94, "task_create_identifier", "rules"))
            elif url.endswith("/booking"):
                assertions.append(_assertion("json.bookingid", "exists", None, "critical", "field_presence", 0.94, "booking_create_identifier", "rules"))
            elif not header_only_save and not non_json_response:
                # Avoid unsafe generic json.id assumptions for external APIs.
                assertions.append(_assertion("json", "exists", None, "major", "schema", 0.72, "create_response_present", "rules"))
        if self.intent == "query":
            if not _is_simple_endpoint(url) and expects_json_envelope(url) and not non_json_response:
                assertions.append(_assertion("json", "exists", None, "major", "schema", 0.82, "query_response_present", "rules"))
                if capability == "filter":
                    pass
                elif capability == "list" or _looks_like_collection(self.request, self.step):
                    assertions.append(_assertion(_infer_collection_source(self.request, self.step), "len_gt", 0, "major", "collection", 0.86, "collection_not_empty", "rules"))
                    identifier_source = _infer_collection_identifier_source(self.request, self.parsed_requirement)
                    if identifier_source:
                        assertions.append(_assertion(identifier_source, "exists", None, "major", "field_presence", 0.81, "collection_identifier_present", "rules"))
        if self.intent == "update" and not non_json_response:
            assertions.append(_assertion("json", "exists", None, "major", "schema", 0.76, "update_response_present", "rules"))
        if self.intent == "delete":
            assertions.append(_assertion("error", "not_exists", None, "major", "business", 0.68, "delete_no_runtime_error", "rules"))

        for field in _extract_known_fields(self.parsed_requirement, self.step, self.request):
            if field.lower() in {"token", "task_id", "order_id", "pet_id", "username", "session_id", "booking_id", "bookingid", "resource_id", "id", "user"}:
                continue
            if self.intent in {"query", "update"}:
                assertions.append(_assertion(f"json.{field}", "exists", None, "major", "field_presence", 0.72, "expected_field_present", "rules"))

        assertions.extend(_infer_echo_assertions(self.request))
        return assertions


def normalize_assertions(
    assertions: list[dict[str, Any]],
    *,
    min_confidence: float = 0.0,
    max_assertions: int = 6,
    request: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, raw in enumerate(assertions, start=1):
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("source", "")).strip()
        op = str(raw.get("op", "")).strip()
        if not source or op not in ALLOWED_ASSERTION_OPS:
            continue
        if request and not _is_allowed_source_for_request(source, request):
            continue
        try:
            confidence = float(raw.get("confidence", 0.5) or 0.5)
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = _clamp(confidence, 0.0, 1.0)
        if confidence < min_confidence:
            continue
        severity = str(raw.get("severity", "major")).strip().lower()
        category = str(raw.get("category", "business")).strip().lower()
        if severity not in ALLOWED_ASSERTION_SEVERITIES:
            severity = "major"
        if category not in ALLOWED_ASSERTION_CATEGORIES:
            category = "business"
        expected = raw.get("expected")
        dedupe_key = (source, op, repr(expected))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        item = {
            "assertion_id": str(raw.get("assertion_id", f"assertion_{index:02d}")),
            "source": source,
            "op": op,
            "severity": severity,
            "category": category,
            "confidence": round(confidence, 4),
            "generated_by": str(raw.get("generated_by", "rules")),
            "reasoning": str(raw.get("reasoning", "")).strip()[:200],
            "fallback_used": bool(raw.get("fallback_used", False)),
        }
        if "expected" in raw:
            item["expected"] = expected
        normalized.append(item)
        if len(normalized) >= max_assertions:
            break
    normalized.sort(key=lambda item: (_severity_rank(item["severity"]), -item["confidence"], item["source"]))
    return normalized


def _build_quality_summary(
    assertions: list[dict[str, Any]],
    *,
    llm_attempted: bool,
    fallback_reason: str,
    invalid_count: int,
) -> dict[str, Any]:
    generated_by_counts = {
        "rules": 0,
        "llm": 0,
        "llm_repair": 0,
        "manual": 0,
    }
    for assertion in assertions:
        generated_by = str(assertion.get("generated_by", "rules"))
        generated_by_counts[generated_by] = generated_by_counts.get(generated_by, 0) + 1
    weak_assertion = _is_weak_assertion_set(assertions)
    return {
        "llm_attempted": llm_attempted,
        "fallback_reason": fallback_reason,
        "invalid_assertion_count": invalid_count,
        "generated_by_counts": generated_by_counts,
        "high_confidence_count": len([item for item in assertions if float(item.get("confidence", 0.0)) >= 0.8]),
        "weak_assertion": weak_assertion,
        "warning": "weak_assertion_set" if weak_assertion else "",
    }


def _assertion(
    source: str,
    op: str,
    expected: Any,
    severity: str,
    category: str,
    confidence: float,
    reasoning: str,
    generated_by: str,
) -> dict[str, Any]:
    payload = {
        "source": source,
        "op": op,
        "severity": severity,
        "category": category,
        "confidence": confidence,
        "generated_by": generated_by,
        "reasoning": reasoning,
        "fallback_used": False,
    }
    if expected is not None or op in {"eq", "ne", "in", "not_in", "gt", "lt", "ge", "le", "len_eq", "len_gt", "len_lt", "len_ge", "len_le", "contains", "not_contains", "matches"}:
        payload["expected"] = expected
    return payload


def _resolve_expected_statuses(intent: str, request: dict[str, Any], step: dict[str, Any], parsed_requirement: dict[str, Any]) -> list[int]:
    request_url = str(request.get("url", ""))
    request_method = str(request.get("method", "")).upper()
    endpoint = _matched_endpoint(parsed_requirement, request)
    endpoint_path = str((endpoint or {}).get("path", "")).strip()
    canonical_path = _canonicalize_path(endpoint_path or request_url).lower()
    status_hints: list[str] = [str(step.get("text", ""))]
    if endpoint_path:
        matched_constraints = [
            item
            for item in (parsed_requirement.get("constraints", []) or [])
            if request_method.lower() in str(item).lower() and endpoint_path.lower() in str(item).lower()
        ]
        explicit = [int(match.group(1)) for item in matched_constraints for match in SUCCESS_STATUS_RE.finditer(str(item))]
        if explicit:
            return list(dict.fromkeys(explicit))
        status_hints.extend(matched_constraints)
        status_hints.extend(_relevant_expected_results(parsed_requirement, request, step))
    else:
        status_hints.extend(parsed_requirement.get("expected_results", []))
    request_text = " ".join(status_hints)
    explicit = [int(match.group(1)) for match in SUCCESS_STATUS_RE.finditer(request_text)]
    if explicit:
        return list(dict.fromkeys(explicit))
    if request_method == "GET" and canonical_path == "/heartbeat":
        return [204]
    if intent == "create":
        if request_url.endswith("/tasks"):
            return [201]
        return [200, 201]
    if intent == "delete":
        if request_method == "DELETE" and (request_url.endswith("/booking") or "/booking/" in request_url):
            return [201]
        return [200, 204]
    return [200]


def _extract_known_fields(parsed_requirement: dict[str, Any], step: dict[str, Any], request: dict[str, Any] | None = None) -> list[str]:
    if request:
        req_url = str(request.get("url", ""))
        if not expects_json_envelope(req_url) or _is_simple_endpoint(req_url):
            return []
    capability = _request_capability(request or {}, parsed_requirement, "")
    endpoint_fields = _endpoint_response_fields(parsed_requirement, request or {})
    if capability == "auth":
        return endpoint_fields[:8]
    if capability == "filter":
        return []
    text = " ".join(
        [
            str(step.get("text", "")),
            " ".join(_relevant_expected_results(parsed_requirement, request or {}, step)),
            " ".join(_relevant_constraints(parsed_requirement, request or {}, step)),
        ]
    )
    fields: list[str] = []
    for groups in FIELD_TOKEN_RE.findall(text):
        token = next((item for item in groups if item), "").strip()
        if token and token.lower() not in ASSERTION_FIELD_STOPWORDS and token.lower() != "user" and token not in fields:
            fields.append(token)
    for token in FIELD_NAME_RE.findall(text):
        lowered = token.lower()
        if lowered in ASSERTION_FIELD_STOPWORDS or lowered in {"get", "post", "put", "patch", "delete", "http"}:
            continue
        if lowered == "user":
            continue
        if token not in fields and any(keyword in lowered for keyword in ("token", "session", "user", "profile", "order", "task", "nick", "name", "id", "items", "roles")):
            fields.append(token)
    for field in endpoint_fields:
        if field not in fields:
            fields.append(field)
    placeholder_fields = _endpoint_placeholder_fields(parsed_requirement, request or {})
    if placeholder_fields:
        fields = [field for field in fields if field.lower() not in placeholder_fields or field in endpoint_fields]
    if capability == "list":
        fields = [field for field in fields if field.lower() in {"id", "bookingid", "booking_id", "order_id", "pet_id", "username", "task_id", "resource_id"}]
    filtered = _filter_known_fields_for_request(fields[:8], request or {})
    return filtered


def _filter_known_fields_for_request(fields: list[str], request: dict[str, Any]) -> list[str]:
    url = str(request.get("url", "")).lower()
    if not url:
        return fields
    if re.fullmatch(r".*/api/tasks/\{\{?(task_id|resource_id)\}?\}$", url):
        allowed = TASK_DETAIL_FIELD_ALLOWLIST
    else:
        allowed = next((candidate for suffix, candidate in QUERY_ENDPOINT_FIELD_ALLOWLIST if url.endswith(suffix)), None)
    if not allowed:
        return fields
    return [field for field in fields if field.lower() in allowed]


def _is_allowed_source_for_request(source: str, request: dict[str, Any]) -> bool:
    normalized_source = source.strip().lower()
    if not normalized_source:
        return False
    if normalized_source == "request":
        return True
    if normalized_source.startswith("request.") or normalized_source.startswith("request["):
        return True
    if normalized_source.startswith("context."):
        return True
    if normalized_source.startswith("response."):
        return False

    url = str(request.get("url", ""))
    url_lower = url.lower()

    if normalized_source in {"status_code", "elapsed_ms", "error", "body_text"}:
        return True
    if normalized_source.startswith("headers."):
        return True

    if not expects_json_envelope(url):
        return normalized_source in {"status_code", "elapsed_ms", "error", "body_text", "headers.content-type"}

    if normalized_source == "json":
        return True
    if normalized_source.startswith("json["):
        return True

    for suffix, allowed in REQUEST_ASSERTION_SOURCE_ALLOWLIST:
        if url_lower.endswith(suffix):
            return normalized_source in allowed
    if _is_simple_endpoint(url_lower):
        return normalized_source in {"status_code", "json", "elapsed_ms", "error"}
    if normalized_source.startswith("json."):
        return True
    return False


def _normalize_request_host(url: str) -> str:
    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return ""
    netloc = (parsed.netloc or "").lower().strip()
    if not netloc:
        return ""
    return netloc.split(":", 1)[0]


def _is_high_value_assertion_url(url: str) -> bool:
    if not url:
        return False
    url_lower = url.lower()
    if any(url_lower.endswith(suffix) for suffix in HIGH_VALUE_ASSERTION_ENDPOINT_SUFFIXES):
        return True
    return _normalize_request_host(url) in LLM_ASSERTION_ALLOWED_API_HOSTS


def _should_attempt_llm_for_step(step: dict[str, Any], request: dict[str, Any]) -> bool:
    text = str(step.get("text", "")).strip()
    lowered = text.lower()
    url = str(request.get("url", "")).lower()
    if not request or not text:
        return False
    if any(hint in lowered for hint in NON_EXECUTABLE_ASSERTION_HINTS):
        return False
    if len(text) > 120 and "`/" not in text and "/api/" not in lowered:
        return False
    if not _is_high_value_assertion_url(str(request.get("url", ""))):
        return False
    return True


def _generate_assertion_candidates_cached(**kwargs: Any) -> tuple[list[dict[str, Any]], str, str]:
    cache_key = json.dumps(
        {
            "mode": kwargs.get("mode"),
            "request": kwargs.get("request"),
            "step_text": str((kwargs.get("step") or {}).get("text", "")),
            "rule_assertions": kwargs.get("rule_assertions"),
            "known_endpoint_fields": kwargs.get("known_endpoint_fields"),
            "provider_profile": kwargs.get("provider_profile"),
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    cached = _ASSERTION_LLM_CACHE.get(cache_key)
    if cached is not None:
        assertions, fallback_reason, error_type = cached
        return deepcopy(assertions), fallback_reason, error_type
    result = generate_assertion_candidates(**kwargs)
    _ASSERTION_LLM_CACHE[cache_key] = (deepcopy(result[0]), result[1], result[2])
    return deepcopy(result[0]), result[1], result[2]


def _looks_like_collection(request: dict[str, Any], step: dict[str, Any]) -> bool:
    text = str(step.get("text", "")).lower()
    url = str(request.get("url", "")).lower()
    return any(keyword in text for keyword in ("list", "items", "search", "query", "filter", "firstname", "lastname", "checkin", "checkout")) or url.endswith("/items") or url.endswith("/orders") or ("?" in url and "=" in url)


def _infer_collection_source(request: dict[str, Any], step: dict[str, Any]) -> str:
    text = str(step.get("text", "")).lower()
    url = str(request.get("url", "")).lower()
    if "items" in text or url.endswith("/items"):
        return "json.items"
    if "orders" in text or url.endswith("/orders"):
        return "json.orders"
    return "json"


def _canonical_placeholder_name(name: str) -> str:
    lowered = str(name or "").strip().lower()
    if lowered in {"username", "user_name"}:
        return "username"
    if lowered in {"orderid", "order_id"}:
        return "order_id"
    if lowered in {"petid", "pet_id"}:
        return "pet_id"
    if lowered in {"bookingid", "booking_id"}:
        return "booking_id"
    if lowered in {"todoid", "todo_id"}:
        return "todo_id"
    if lowered in {"challengerguid", "challenger_guid", "guid"}:
        return "challenger_guid"
    if lowered in {"taskid", "task_id"}:
        return "task_id"
    if lowered == "id":
        return "resource_id"
    return lowered


def _canonicalize_path(path: str) -> str:
    normalized = str(path or "").strip()
    if not normalized:
        return normalized
    if normalized != "/" and normalized.endswith("/"):
        normalized = normalized[:-1]
    normalized = re.sub(r"/\d+(?=/|$)", "/{id}", normalized)
    normalized = PLACEHOLDER_SEGMENT_RE.sub(lambda m: "{" + _canonical_placeholder_name(m.group(1)) + "}", normalized)
    normalized = normalized.replace("/booking/{resource_id}", "/booking/{booking_id}")
    normalized = normalized.replace("/todos/{resource_id}", "/todos/{todo_id}")
    normalized = normalized.replace("/tasks/{resource_id}", "/tasks/{task_id}")
    return normalized


def _paths_match(request_path: str, endpoint_path: str) -> bool:
    left = _canonicalize_path(request_path)
    right = _canonicalize_path(endpoint_path)
    if left == right:
        return True
    left_parts = [part for part in left.split("/") if part]
    right_parts = [part for part in right.split("/") if part]
    if len(left_parts) != len(right_parts):
        return False
    for left_part, right_part in zip(left_parts, right_parts):
        if left_part == right_part:
            continue
        if left_part.startswith("{") and right_part.startswith("{"):
            continue
        return False
    return True


def _matched_endpoint(parsed_requirement: dict[str, Any], request: dict[str, Any]) -> dict[str, Any] | None:
    method = str(request.get("method", "")).upper().strip()
    path = str(request.get("url", "")).strip()
    for endpoint in parsed_requirement.get("api_endpoints", []) or []:
        if str(endpoint.get("method", "")).upper().strip() != method:
            continue
        if _paths_match(path, str(endpoint.get("path", ""))):
            return endpoint
    return None


def _request_capability(request: dict[str, Any], parsed_requirement: dict[str, Any], fallback_intent: str) -> str:
    endpoint = _matched_endpoint(parsed_requirement, request)
    path = _canonicalize_path(str((endpoint or {}).get("path") or request.get("url", ""))).lower()
    method = str((endpoint or {}).get("method") or request.get("method", "")).upper().strip()
    if any(token in path for token in ("/ping", "/health", "/ready", "/version")):
        return "health"
    if any(token in path for token in ("/auth", "/login", "/session")):
        return "auth"
    if method == "GET" and "?" in path and "=" in path:
        return "filter"
    has_placeholder = "{" in path and "}" in path
    path_parts = [part for part in path.split("/") if part]
    if (
        method == "GET"
        and has_placeholder
        and path_parts
        and path_parts[-1].startswith("{")
        and len([part for part in path_parts if not part.startswith("{")]) >= 2
    ):
        return "filter"
    if method == "GET" and not has_placeholder:
        return "list"
    if method == "POST":
        return "create"
    if method == "GET" and has_placeholder:
        return "detail"
    if method == "PUT":
        return "replace"
    if method == "PATCH":
        return "patch"
    if method == "DELETE":
        return "delete"
    return fallback_intent or "other"


def _relevant_expected_results(parsed_requirement: dict[str, Any], request: dict[str, Any], step: dict[str, Any]) -> list[str]:
    endpoint = _matched_endpoint(parsed_requirement, request)
    if endpoint is None:
        return list(parsed_requirement.get("expected_results", []) or [])
    method = str(endpoint.get("method", "")).upper().strip()
    path = str(endpoint.get("path", "")).strip()
    segments = [segment for segment in _canonicalize_path(path).lower().split("/") if segment and not segment.startswith("{")]
    require_explicit_surface = ("{" in _canonicalize_path(path) and "}" in _canonicalize_path(path)) or len(segments) <= 1
    matched: list[str] = []
    for item in parsed_requirement.get("expected_results", []) or []:
        lowered = str(item).lower()
        if method and method.lower() in lowered and _canonicalize_path(path).lower() in lowered:
            matched.append(str(item))
            continue
        if not require_explicit_surface and segments and any(segment in lowered for segment in segments):
            matched.append(str(item))
    return matched or [str(step.get("text", ""))]


def _relevant_constraints(parsed_requirement: dict[str, Any], request: dict[str, Any], step: dict[str, Any]) -> list[str]:
    endpoint = _matched_endpoint(parsed_requirement, request)
    if endpoint is None:
        return list(parsed_requirement.get("constraints", []) or [])
    method = str(endpoint.get("method", "")).upper().strip()
    path = _canonicalize_path(str(endpoint.get("path", "")).strip()).lower()
    matched: list[str] = []
    for item in parsed_requirement.get("constraints", []) or []:
        lowered = str(item).lower()
        if method and method.lower() in lowered and path in lowered:
            matched.append(str(item))
    return matched


def _endpoint_response_fields(parsed_requirement: dict[str, Any], request: dict[str, Any]) -> list[str]:
    endpoint = _matched_endpoint(parsed_requirement, request)
    if endpoint is None:
        return []
    fields: list[str] = []
    for item in endpoint.get("response_fields") or []:
        name = str((item or {}).get("name", "")).strip()
        if not name:
            continue
        lowered = name.lower()
        if any(ch.isdigit() for ch in name):
            continue
        if lowered in ASSERTION_FIELD_STOPWORDS:
            continue
        if lowered in {"jim", "james", "brown", "jamie", "breakfast", "lunch", "dinner", "false", "true"}:
            continue
        if "." in name:
            leaf = name.split(".")[-1]
            if leaf and leaf not in fields:
                fields.append(leaf)
            continue
        if name not in fields:
            fields.append(name)
    return fields


def _endpoint_placeholder_fields(parsed_requirement: dict[str, Any], request: dict[str, Any]) -> set[str]:
    endpoint = _matched_endpoint(parsed_requirement, request)
    path = str((endpoint or {}).get("path") or request.get("url", "")).strip()
    names = {
        _canonical_placeholder_name(match.group(1)).lower()
        for match in PLACEHOLDER_SEGMENT_RE.finditer(path)
    }
    aliases = {
        "username": {"username", "user_name"},
        "order_id": {"order_id", "orderid", "id"},
        "pet_id": {"pet_id", "petid", "id"},
        "booking_id": {"booking_id", "bookingid"},
        "todo_id": {"todo_id", "todoid", "id"},
        "challenger_guid": {"challenger_guid", "challengerguid", "guid"},
        "task_id": {"task_id", "taskid", "id"},
    }
    expanded: set[str] = set()
    for name in names:
        expanded.update(aliases.get(name, {name}))
    return expanded


def _infer_collection_identifier_source(request: dict[str, Any], parsed_requirement: dict[str, Any]) -> str:
    endpoint = _matched_endpoint(parsed_requirement, request)
    path = str((endpoint or {}).get("path") or request.get("url", "")).lower()
    if "?" in path and "=" in path:
        return ""
    field_names = {field.lower() for field in _endpoint_response_fields(parsed_requirement, request)}
    if "booking" in path or "bookingid" in field_names or "booking_id" in field_names:
        return "json[0].bookingid"
    if "task_id" in field_names or "tasks" in path:
        return "json[0].task_id"
    if "order_id" in field_names or "orders" in path:
        return "json[0].order_id"
    if "id" in field_names:
        return "json[0].id"
    return ""


def _prefers_non_json_response(request: dict[str, Any], parsed_requirement: dict[str, Any]) -> bool:
    endpoint = _matched_endpoint(parsed_requirement, request)
    path = _canonicalize_path(str((endpoint or {}).get("path") or request.get("url", ""))).lower()
    method = str((endpoint or {}).get("method") or request.get("method", "")).upper().strip()
    if path.startswith("/status/"):
        return True
    if (method, path) in {
        ("POST", "/challenger"),
        ("POST", "/secret/token"),
        ("GET", "/secret/note"),
        ("POST", "/secret/note"),
        ("GET", "/heartbeat"),
    }:
        return True
    return False


def _is_weak_assertion_set(assertions: list[dict[str, Any]]) -> bool:
    structured = [item for item in assertions if isinstance(item, dict)]
    if not structured:
        return True
    non_status = [item for item in structured if item.get("source") != "status_code"]
    return len(non_status) == 0


def _severity_rank(severity: str) -> int:
    return {"critical": 0, "major": 1, "minor": 2}.get(severity, 1)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _infer_echo_assertions(request: dict[str, Any]) -> list[dict[str, Any]]:
    assertions: list[dict[str, Any]] = []
    url = str(request.get("url", "")).lower()
    method = str(request.get("method", "")).upper().strip()
    json_body = request.get("json")
    params = request.get("params")

    if any(url.endswith(suffix) for suffix in ("/post", "/anything")) and isinstance(json_body, dict):
        for key, value in list(json_body.items())[:2]:
            if not isinstance(value, (str, int, float, bool)) or str(key).lower() in {"password", "token", "secret"}:
                continue
            assertions.append(
                _assertion(
                    f"json.json.{key}",
                    "eq",
                    value,
                    "major",
                    "business",
                    0.84,
                    "echo_json_body_value",
                    "rules",
                )
            )
    if method == "GET" and url.endswith("/get") and isinstance(params, dict):
        for key, value in list(params.items())[:2]:
            if not isinstance(value, (str, int, float, bool)):
                continue
            assertions.append(
                _assertion(
                    f"json.args.{key}",
                    "eq",
                    value,
                    "major",
                    "business",
                    0.84,
                    "echo_query_value",
                    "rules",
                )
            )
    return assertions
