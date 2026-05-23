"""Rule-based and optional LLM explanations for failed execution steps."""

from __future__ import annotations

import json
import os
from typing import Any

from platform_shared import (
    ModelEndpointConfig,
    ModelGateway,
    ModelGatewayConfig,
    ModelGatewayError,
    ModelGatewayResponseError,
    ModelGatewayTimeoutError,
    get_requirement_analysis_model_profile,
)


def build_execution_explanations(execution_result: dict[str, Any], *, top_n: int = 5) -> dict[str, Any]:
    """Classify failures from execution_result and suggest remediation."""
    task_id = str(execution_result.get("task_id", ""))
    execution_id = str(execution_result.get("execution_id") or "")
    scenario_results = execution_result.get("scenario_results") or []

    failed_steps = 0
    categories: dict[str, dict[str, Any]] = {}
    examples: dict[str, list[str]] = {}

    failed_step_examples: list[dict[str, Any]] = []
    for scenario in scenario_results:
        for step in scenario.get("steps") or []:
            if step.get("status") == "passed":
                continue
            failed_steps += 1
            msg = str(step.get("message") or "")
            cat = _classify_failure(msg, step)
            bucket = categories.setdefault(cat, {"category": cat, "count": 0, "recommended_actions": _actions_for(cat)})
            bucket["count"] += 1
            hints = _repair_hints_for(step, cat)
            if hints:
                bucket.setdefault("repair_hints", []).extend(hints)
            ex = examples.setdefault(cat, [])
            if len(ex) < 3:
                snippet = msg[:200] if msg else str(step.get("error_category") or "unknown")
                ex.append(snippet)
            if len(failed_step_examples) < 8:
                failed_step_examples.append(_compact_failed_step(scenario, step, cat))

    for cat, data in categories.items():
        data["examples"] = examples.get(cat, [])
        if data.get("repair_hints"):
            data["repair_hints"] = _dedupe_hints(data["repair_hints"])[:5]

    ordered = sorted(categories.values(), key=lambda x: x["count"], reverse=True)
    top_reasons = [x["category"] for x in ordered[:top_n]]

    payload = {
        "task_id": task_id,
        "execution_id": execution_id or None,
        "summary": {
            "failed_scenarios": sum(1 for s in scenario_results if s.get("status") != "passed"),
            "failed_steps": failed_steps,
        },
        "failure_groups": ordered[:top_n],
        "top_reasons": top_reasons,
    }
    payload.update(_build_llm_execution_insights(payload, failed_step_examples))
    return payload


def _build_llm_execution_insights(rule_payload: dict[str, Any], failed_steps: list[dict[str, Any]]) -> dict[str, Any]:
    if not failed_steps:
        return {
            "llm_diagnosis": None,
            "defect_summaries": [],
            "llm_metadata": {"attempted": False, "used": False, "fallback_reason": "no_failed_steps", "error_type": ""},
        }
    config = _ExecutionInsightLLMConfig.from_env()
    if config is None:
        return {
            "llm_diagnosis": None,
            "defect_summaries": _rule_defect_summaries(failed_steps),
            "llm_metadata": {"attempted": False, "used": False, "fallback_reason": "llm_not_configured", "error_type": "MissingAPIKey"},
        }
    prompt = {
        "task": "Diagnose API test execution failures and draft defect summaries",
        "rule_summary": rule_payload.get("summary", {}),
        "failure_groups": rule_payload.get("failure_groups", []),
        "failed_steps": failed_steps,
        "output_schema": {
            "diagnosis": {
                "summary": "string",
                "root_cause": "string",
                "confidence": 0.0,
                "next_actions": ["string"],
            },
            "defect_summaries": [
                {
                    "step_id": "string",
                    "title": "string",
                    "severity": "low|medium|high|critical",
                    "expected_result": "string",
                    "actual_result": "string",
                    "reproduction_steps": "string",
                }
            ],
        },
        "constraints": [
            "Return strict JSON only",
            "Do not invent endpoints not present in failed_steps",
            "Prefer concise defect titles that can be saved into a defect tracker",
            "Use Chinese for summary and defect fields",
        ],
    }
    try:
        response = config.gateway.chat_json(
            system_prompt="You are an API test failure diagnostician. Return strict JSON only.",
            user_payload=prompt,
            temperature=0.1,
        )
    except ModelGatewayResponseError as exc:
        return _llm_fallback(failed_steps, "llm_response_invalid", exc.__class__.__name__)
    except ModelGatewayTimeoutError as exc:
        return _llm_fallback(failed_steps, "llm_timeout", exc.__class__.__name__)
    except ModelGatewayError as exc:
        return _llm_fallback(failed_steps, "llm_runtime_error", exc.__class__.__name__)
    except Exception as exc:  # pragma: no cover - defensive fallback
        return _llm_fallback(failed_steps, "llm_runtime_error", exc.__class__.__name__)

    diagnosis = response.get("diagnosis") if isinstance(response.get("diagnosis"), dict) else None
    defect_summaries = _normalize_defect_summaries(response.get("defect_summaries"), failed_steps)
    if diagnosis is None and not defect_summaries:
        return _llm_fallback(failed_steps, "llm_response_invalid", "EmptyInsightPayload")
    return {
        "llm_diagnosis": _normalize_diagnosis(diagnosis),
        "defect_summaries": defect_summaries or _rule_defect_summaries(failed_steps),
        "llm_metadata": {
            "attempted": True,
            "used": True,
            "fallback_reason": "",
            "error_type": "",
            "provider_profile": config.provider_profile,
        },
    }


def _llm_fallback(failed_steps: list[dict[str, Any]], reason: str, error_type: str) -> dict[str, Any]:
    return {
        "llm_diagnosis": None,
        "defect_summaries": _rule_defect_summaries(failed_steps),
        "llm_metadata": {"attempted": True, "used": False, "fallback_reason": reason, "error_type": error_type},
    }


class _ExecutionInsightLLMConfig:
    def __init__(self, gateway: ModelGateway, provider_profile: str):
        self.gateway = gateway
        self.provider_profile = provider_profile

    @classmethod
    def from_env(cls) -> "_ExecutionInsightLLMConfig | None":
        api_key = _first_env("HUNYUAN_API_KEY", "OPENAI_API_KEY")
        if not api_key:
            return None
        requested_profile = (os.getenv("EXECUTION_DIAGNOSIS_MODEL_PROFILE") or "").strip() or None
        profile_name, profile = get_requirement_analysis_model_profile(requested_profile)
        base_url = (_first_env("HUNYUAN_BASE_URL", "OPENAI_BASE_URL") or profile.base_url).rstrip("/")
        llm_model = (_first_env("HUNYUAN_LLM_MODEL", "OPENAI_LLM_MODEL") or profile.llm_model).strip()
        timeout = _resolve_float("EXECUTION_DIAGNOSIS_TIMEOUT_SECONDS", default=min(profile.timeout_seconds, 30.0))
        retries = _resolve_int("EXECUTION_DIAGNOSIS_LLM_RETRIES", default=0)
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


def _compact_failed_step(scenario: dict[str, Any], step: dict[str, Any], category: str) -> dict[str, Any]:
    response = step.get("response") if isinstance(step.get("response"), dict) else {}
    request_payload = step.get("request") if isinstance(step.get("request"), dict) else {}
    failures = step.get("assertion_failures") or []
    return {
        "scenario_name": scenario.get("name") or scenario.get("scenario_id") or "",
        "step_id": step.get("step_id") or "",
        "step_text": step.get("text") or "",
        "category": category,
        "error_category": step.get("error_category") or response.get("error_category") or "",
        "message": str(step.get("message") or "")[:500],
        "request": {
            "method": request_payload.get("method") or "",
            "url": request_payload.get("url") or "",
            "status_code": response.get("status_code"),
        },
        "assertion_failures": [
            {
                "source": item.get("source"),
                "op": item.get("op"),
                "expected": item.get("expected"),
                "actual": item.get("actual"),
                "failure_kind": item.get("failure_kind"),
            }
            for item in failures[:3]
            if isinstance(item, dict)
        ],
        "body_preview": str(response.get("body_preview") or "")[:300],
    }


def _normalize_diagnosis(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    next_actions = raw.get("next_actions") if isinstance(raw.get("next_actions"), list) else []
    return {
        "summary": str(raw.get("summary") or "").strip()[:500],
        "root_cause": str(raw.get("root_cause") or "").strip()[:500],
        "confidence": _clamp_float(raw.get("confidence"), default=0.5),
        "next_actions": [str(item).strip()[:160] for item in next_actions if str(item).strip()][:5],
    }


def _normalize_defect_summaries(raw: Any, failed_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    known_ids = {str(item.get("step_id") or "") for item in failed_steps}
    output: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        step_id = str(item.get("step_id") or "").strip()
        if known_ids and step_id and step_id not in known_ids:
            continue
        severity = str(item.get("severity") or "medium").strip().lower()
        if severity not in {"low", "medium", "high", "critical"}:
            severity = "medium"
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        output.append(
            {
                "step_id": step_id,
                "title": title[:180],
                "severity": severity,
                "expected_result": str(item.get("expected_result") or "").strip()[:800],
                "actual_result": str(item.get("actual_result") or "").strip()[:800],
                "reproduction_steps": str(item.get("reproduction_steps") or "").strip()[:1000],
                "generated_by": "llm",
            }
        )
    return output[:8]


def _rule_defect_summaries(failed_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in failed_steps:
        title = f"[{item.get('category') or 'execution'}] {item.get('scenario_name') or ''} / {item.get('step_text') or item.get('step_id')}"
        request_payload = item.get("request") if isinstance(item.get("request"), dict) else {}
        output.append(
            {
                "step_id": item.get("step_id") or "",
                "title": title[:180],
                "severity": _severity_for_category(str(item.get("error_category") or item.get("category") or "")),
                "expected_result": _expected_from_failure(item),
                "actual_result": str(item.get("message") or "")[:800],
                "reproduction_steps": f"执行步骤 {item.get('step_id') or '-'}：{request_payload.get('method') or ''} {request_payload.get('url') or ''}".strip(),
                "generated_by": "rules",
            }
        )
    return output


def _expected_from_failure(item: dict[str, Any]) -> str:
    failures = item.get("assertion_failures") if isinstance(item.get("assertion_failures"), list) else []
    if failures:
        failure = failures[0]
        return f"{failure.get('source') or 'assertion'} {failure.get('op') or ''} {failure.get('expected')!r}"
    return "接口应按测试用例返回预期状态、结构和业务值"


def _severity_for_category(category: str) -> str:
    lowered = category.lower()
    if lowered in {"auth_error", "http_server_error", "upstream_error", "tls_error"}:
        return "critical"
    if lowered in {"context_missing", "context_error", "network_timeout", "timeout_error", "assertion_shape_mismatch"}:
        return "high"
    return "medium"


def _first_env(*names: str) -> str:
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


def _resolve_float(name: str, *, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except ValueError:
        return float(default)


def _resolve_int(name: str, *, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if raw.isdigit():
        return int(raw)
    return int(default)


def _clamp_float(raw: Any, *, default: float) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = default
    return max(0.0, min(1.0, round(value, 4)))


def _classify_failure(message: str, step: dict[str, Any]) -> str:
    lowered = message.lower()
    err_cat = str(step.get("error_category") or "").lower()
    assertion_failures = step.get("assertion_failures") or []

    if "missing context" in lowered or err_cat == "context_error":
        return "context_missing"
    if err_cat == "assertion_shape_mismatch" or "assertion_shape_mismatch" in lowered:
        return "assertion_shape_mismatch"
    if any(str(item.get("failure_kind") or "").lower() == "assertion_shape_mismatch" for item in assertion_failures):
        return "assertion_shape_mismatch"
    if "status_code eq 201" in lowered and "actual=200" in lowered:
        return "status_code_mismatch"
    if "status_code" in lowered and ("actual=401" in lowered or "actual=403" in lowered):
        return "auth_failure"
    if "status_code" in lowered and "actual=404" in lowered:
        return "not_found"
    if "status_code" in lowered and "actual=422" in lowered:
        return "validation_error"
    if "json." in lowered and ("exists" in lowered or "actual=none" in lowered):
        return "field_mapping"
    if err_cat in {"http_client_error", "network_error"} or "connection" in lowered or "timed out" in lowered:
        return "network_timeout"
    if "assertion" in lowered:
        return "assertion_other"
    return "unknown"


def _actions_for(category: str) -> list[str]:
    mapping: dict[str, list[str]] = {
        "context_missing": [
            "检查前置步骤是否成功写入 save_context（如 task_id）",
            "确认 DSL 中 uses_context 与 URL 占位符 {{task_id}} 一致",
        ],
        "status_code_mismatch": [
            "将控制类接口（parse/execute/scenarios/generate）的期望状态码改为 200",
            "在 case-generation 中为该路径补充控制类接口规则",
        ],
        "auth_failure": [
            "在环境配置中补齐 auth 或 Authorization 头",
            "确认 Token 是否过期",
        ],
        "not_found": [
            "确认 task_id 与资源路径是否正确",
            "检查上一步是否因 4xx 未返回资源 ID",
        ],
        "validation_error": [
            "对照 OpenAPI 检查请求体字段名（如 task_name 而非 name）",
            "使用 dsl_generator 已知接口白名单模板",
        ],
        "field_mapping": [
            "将断言路径从 json.id 调整为 json.data.*（统一 envelope）",
            "检查 save_context 的 json 路径是否与真实响应一致",
        ],
        "assertion_shape_mismatch": [
            "查看 response_profile.root_type，确认响应根类型",
            "顶层数组响应优先断言 json type_is array 或 json len_gt 0",
            "不要把 /posts 等路径自动映射成 json.posts，除非响应明确有 posts 字段",
            "将修复后的断言写回 DSL 后重跑",
        ],
        "network_timeout": [
            "提高步骤 timeout 或检查目标服务可用性",
            "查看是否为间歇性网络问题，可依赖执行器重试",
        ],
        "assertion_other": [
            "在执行详情中展开 assertion_summary，逐项核对期望值",
        ],
        "unknown": [
            "查看 execution logs 与 response body_preview",
        ],
    }
    return mapping.get(category, mapping["unknown"])


def _repair_hints_for(step: dict[str, Any], category: str) -> list[dict[str, Any]]:
    if category != "assertion_shape_mismatch":
        return []

    hints: list[dict[str, Any]] = []
    for failure in step.get("assertion_failures") or []:
        if not isinstance(failure, dict):
            continue
        profile = failure.get("response_profile") or {}
        hint = {
            "assertion_id": failure.get("assertion_id"),
            "current_source": failure.get("source"),
            "suggested_source": failure.get("suggested_source"),
            "suggested_op": failure.get("suggested_op"),
            "suggested_expected": failure.get("suggested_expected"),
            "response_root_type": profile.get("root_type"),
            "response_collection_path": profile.get("collection_path"),
        }
        compact = {key: value for key, value in hint.items() if value is not None}
        if compact:
            hints.append(compact)
    return hints


def _dedupe_hints(hints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[tuple[str, str], ...]] = set()
    unique: list[dict[str, Any]] = []
    for hint in hints:
        marker = tuple(sorted((key, str(value)) for key, value in hint.items()))
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(hint)
    return unique
