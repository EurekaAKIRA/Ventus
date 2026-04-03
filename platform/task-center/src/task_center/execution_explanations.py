"""Rule-based explanations for failed execution steps (no LLM)."""

from __future__ import annotations

from typing import Any


def build_execution_explanations(execution_result: dict[str, Any], *, top_n: int = 5) -> dict[str, Any]:
    """Classify failures from execution_result and suggest remediation."""
    task_id = str(execution_result.get("task_id", ""))
    execution_id = str(execution_result.get("execution_id") or "")
    scenario_results = execution_result.get("scenario_results") or []

    failed_steps = 0
    categories: dict[str, dict[str, Any]] = {}
    examples: dict[str, list[str]] = {}

    for scenario in scenario_results:
        for step in scenario.get("steps") or []:
            if step.get("status") == "passed":
                continue
            failed_steps += 1
            msg = str(step.get("message") or "")
            cat = _classify_failure(msg, step)
            bucket = categories.setdefault(cat, {"category": cat, "count": 0, "recommended_actions": _actions_for(cat)})
            bucket["count"] += 1
            ex = examples.setdefault(cat, [])
            if len(ex) < 3:
                snippet = msg[:200] if msg else str(step.get("error_category") or "unknown")
                ex.append(snippet)

    for cat, data in categories.items():
        data["examples"] = examples.get(cat, [])

    ordered = sorted(categories.values(), key=lambda x: x["count"], reverse=True)
    top_reasons = [x["category"] for x in ordered[:top_n]]

    return {
        "task_id": task_id,
        "execution_id": execution_id or None,
        "summary": {
            "failed_scenarios": sum(1 for s in scenario_results if s.get("status") != "passed"),
            "failed_steps": failed_steps,
        },
        "failure_groups": ordered[:top_n],
        "top_reasons": top_reasons,
    }


def _classify_failure(message: str, step: dict[str, Any]) -> str:
    lowered = message.lower()
    err_cat = str(step.get("error_category") or "").lower()

    if "missing context" in lowered or err_cat == "context_error":
        return "context_missing"
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
