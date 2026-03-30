"""Enhanced analysis report builder for platform test assets."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any

from platform_shared.models import AnalysisReport, TaskContext, ValidationReport


def build_analysis_report(
    task_context: TaskContext,
    validation_report: ValidationReport,
    scenario_count: int,
    execution_result: dict[str, Any] | None = None,
    test_case_dsl: dict[str, Any] | None = None,
) -> dict:
    """Build an analysis report suitable for dashboard display and demos."""
    execution_result = _to_mapping(execution_result)
    test_case_dsl = _to_mapping(test_case_dsl)

    warnings = len(validation_report.warnings)
    validation_errors = len(validation_report.errors)
    step_stats = _collect_step_stats(execution_result, test_case_dsl, validation_report)
    scenario_overview = _collect_scenario_overview(execution_result)
    quality_status = _resolve_quality_status(validation_report, step_stats["failed_step_count"])
    summary = {
        "scenario_count": scenario_count,
        "executed_scenarios": scenario_overview["executed_scenarios"],
        "passed_scenarios": scenario_overview["passed_scenarios"],
        "failed_scenarios": scenario_overview["failed_scenarios"],
        "total_steps": step_stats["total_steps"],
        "executed_steps": step_stats["executed_step_count"],
        "passed_steps": step_stats["passed_step_count"],
        "failed_steps": step_stats["failed_step_count"],
        "success_rate": step_stats["success_rate"],
        "failure_rate": step_stats["failure_rate"],
        "avg_elapsed_ms": step_stats["avg_elapsed_ms"],
        "max_elapsed_ms": step_stats["max_elapsed_ms"],
        "validation_passed": validation_report.passed,
        "warning_count": warnings,
        "error_count": validation_errors,
        "execution_status": execution_result.get("status", "not_started"),
        "assertion_total": step_stats["assertion_stats"]["total"],
        "assertion_passed": step_stats["assertion_stats"]["passed"],
        "assertion_failed": step_stats["assertion_stats"]["failed"],
        "assertion_pass_rate": step_stats["assertion_stats"]["pass_rate"],
        "context_defined_keys": step_stats["context_stats"]["defined_key_count"],
        "context_used_keys": step_stats["context_stats"]["used_key_count"],
        "context_extracted_keys": step_stats["context_stats"]["extracted_key_count"],
    }
    task_summary_text = _build_task_summary_text(task_context.task_name, quality_status, summary)
    failure_reasons = step_stats["failure_reasons"]
    report = AnalysisReport(
        task_id=task_context.task_id,
        task_name=task_context.task_name,
        quality_status=quality_status,
        generated_at=datetime.now(timezone.utc).isoformat(),
        summary=summary,
        dashboard=_build_dashboard(
            task_context=task_context,
            quality_status=quality_status,
            summary=summary,
            failure_reasons=failure_reasons,
            assertion_stats=step_stats["assertion_stats"],
            context_stats=step_stats["context_stats"],
            task_summary_text=task_summary_text,
        ),
        execution_overview={
            "executor": execution_result.get("executor"),
            "status": execution_result.get("status", "not_started"),
            "scenario_count": scenario_overview["executed_scenarios"],
            "passed_scenarios": scenario_overview["passed_scenarios"],
            "failed_scenarios": scenario_overview["failed_scenarios"],
            "log_count": len(execution_result.get("logs") or []),
            "has_failures": bool(step_stats["failed_step_count"]),
            "top_failure_category": failure_reasons[0]["category"] if failure_reasons else None,
        },
        failed_steps=step_stats["failed_steps"],
        failure_reasons=failure_reasons,
        assertion_stats=step_stats["assertion_stats"],
        context_stats=step_stats["context_stats"],
        task_summary_text=task_summary_text,
        findings=_build_findings(validation_report, step_stats["failed_steps"], failure_reasons),
        chart_data={
            "validation": {
                "passed": 1 if validation_report.passed else 0,
                "failed": 0 if validation_report.passed else 1,
                "warnings": warnings,
                "errors": validation_errors,
            },
            "execution": {
                "passed_steps": step_stats["passed_step_count"],
                "failed_steps": step_stats["failed_step_count"],
                "success_rate": step_stats["success_rate"],
                "failure_rate": step_stats["failure_rate"],
                "avg_elapsed_ms": step_stats["avg_elapsed_ms"],
                "max_elapsed_ms": step_stats["max_elapsed_ms"],
            },
            "assertions": {
                "passed": step_stats["assertion_stats"]["passed"],
                "failed": step_stats["assertion_stats"]["failed"],
                "pass_rate": step_stats["assertion_stats"]["pass_rate"],
            },
            "context": {
                "defined": step_stats["context_stats"]["defined_key_count"],
                "used": step_stats["context_stats"]["used_key_count"],
                "extracted": step_stats["context_stats"]["extracted_key_count"],
            },
            "failure_reasons": {
                item["category"]: item["count"] for item in failure_reasons
            },
        },
    )
    return report.to_dict()


def _resolve_quality_status(validation_report: ValidationReport, failed_step_count: int) -> str:
    if failed_step_count or not validation_report.passed or validation_report.errors:
        return "failed"
    if validation_report.warnings:
        return "warning"
    return "passed"


def _collect_step_stats(
    execution_result: dict[str, Any],
    test_case_dsl: dict[str, Any],
    validation_report: ValidationReport,
) -> dict[str, Any]:
    scenario_results = execution_result.get("scenario_results") or []
    metrics = execution_result.get("metrics") or {}
    dsl_steps = _flatten_dsl_steps(test_case_dsl)
    has_execution = _has_execution_data(execution_result)

    total_steps = 0
    passed_step_count = 0
    failed_steps: list[dict[str, Any]] = []
    elapsed_samples: list[float] = []
    failure_counter: Counter[str] = Counter()
    failure_examples: dict[str, list[dict[str, Any]]] = {}
    failed_assertion_count = 0
    context_snapshots: list[dict[str, Any]] = []

    for scenario in scenario_results:
        for index, step in enumerate(scenario.get("steps", []), start=1):
            total_steps += 1
            response = step.get("response") or {}
            elapsed_ms = response.get("elapsed_ms")
            if step.get("status") == "passed":
                passed_step_count += 1
            else:
                category = _categorize_failure(step)
                failure_counter[category] += 1
                failure_examples.setdefault(category, []).append(
                    {
                        "step_id": step.get("step_id"),
                        "scenario_name": scenario.get("name"),
                        "message": step.get("message", ""),
                    }
                )
                failed_steps.append(
                    {
                        "scenario_id": scenario.get("scenario_id"),
                        "scenario_name": scenario.get("name"),
                        "step_id": step.get("step_id"),
                        "step_index": index,
                        "step_type": step.get("step_type"),
                        "text": step.get("text"),
                        "status": step.get("status", "failed"),
                        "message": step.get("message", ""),
                        "category": category,
                        "reason_detail": _build_reason_detail(step, category),
                        "elapsed_ms": elapsed_ms,
                        "request": step.get("request", {}),
                        "response": step.get("response", {}),
                        "request_summary": _build_request_summary(step.get("request") or {}),
                        "response_summary": _build_response_summary(step.get("response") or {}),
                    }
                )
                if category == "assertion_failed":
                    failed_assertion_count += 1

            if isinstance(elapsed_ms, (int, float)):
                elapsed_samples.append(float(elapsed_ms))
            if isinstance(step.get("context_snapshot"), dict):
                context_snapshots.append(step["context_snapshot"])

    executed_step_count = total_steps
    if total_steps == 0 and has_execution:
        total_steps = int(metrics.get("step_count", 0) or 0)
        passed_step_count = int(metrics.get("passed_step_count", 0) or 0)
        executed_step_count = total_steps
    elif total_steps == 0:
        total_steps = len(dsl_steps)

    metrics_failed_steps = int(metrics.get("failed_step_count", 0) or 0)
    failed_step_count = max(total_steps - passed_step_count, len(failed_steps), metrics_failed_steps) if has_execution else 0

    if not elapsed_samples:
        avg_elapsed_ms = round(float(metrics.get("avg_elapsed_ms", 0) or 0), 2)
        max_elapsed_ms = round(float(metrics.get("max_elapsed_ms", 0) or 0), 2)
    else:
        avg_elapsed_ms = round(sum(elapsed_samples) / len(elapsed_samples), 2)
        max_elapsed_ms = round(max(elapsed_samples), 2)

    total_assertions = sum(len(step.get("assertions") or []) for step in dsl_steps)
    used_context_keys = sorted({key for step in dsl_steps for key in (step.get("uses_context") or [])})
    save_context_map: dict[str, Any] = {}
    for step in dsl_steps:
        for key, source in (step.get("save_context") or {}).items():
            save_context_map[key] = source
        for key in (step.get("saves_context") or []):
            save_context_map.setdefault(key, "unspecified")

    passed_assertion_count = max(total_assertions - failed_assertion_count, 0)
    extracted_keys = _collect_extracted_keys(metrics, context_snapshots, save_context_map)

    return {
        "total_steps": total_steps,
        "executed_step_count": executed_step_count,
        "passed_step_count": passed_step_count,
        "failed_step_count": failed_step_count,
        "success_rate": round((passed_step_count / executed_step_count) * 100, 2) if executed_step_count else 0.0,
        "failure_rate": round((failed_step_count / executed_step_count) * 100, 2) if executed_step_count else 0.0,
        "avg_elapsed_ms": avg_elapsed_ms,
        "max_elapsed_ms": max_elapsed_ms,
        "failed_steps": failed_steps,
        "failure_reasons": [
            {
                "category": category,
                "label": _failure_category_label(category),
                "count": count,
                "examples": failure_examples.get(category, [])[:3],
            }
            for category, count in failure_counter.most_common()
        ],
        "assertion_stats": {
            "total": total_assertions,
            "passed": passed_assertion_count,
            "failed": failed_assertion_count,
            "pass_rate": round((passed_assertion_count / total_assertions) * 100, 2) if total_assertions else 0.0,
            "validation_errors": len(validation_report.errors),
            "validation_warnings": len(validation_report.warnings),
        },
        "context_stats": {
            "defined_keys": sorted(save_context_map.keys()),
            "defined_key_count": len(save_context_map),
            "used_keys": used_context_keys,
            "used_key_count": len(used_context_keys),
            "extracted_keys": extracted_keys,
            "extracted_key_count": len(extracted_keys),
            "unused_defined_keys": sorted(set(save_context_map) - set(used_context_keys)),
            "undefined_used_keys": sorted(set(used_context_keys) - set(save_context_map)),
            "save_rules": save_context_map,
        },
    }


def _flatten_dsl_steps(test_case_dsl: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for scenario in test_case_dsl.get("scenarios", []):
        steps.extend(scenario.get("steps", []))
    return steps


def _collect_scenario_overview(execution_result: dict[str, Any]) -> dict[str, int]:
    scenario_results = execution_result.get("scenario_results") or []
    passed_scenarios = 0
    failed_scenarios = 0
    for scenario in scenario_results:
        status = scenario.get("status")
        if not status:
            steps = scenario.get("steps") or []
            status = "failed" if any(step.get("status") != "passed" for step in steps) else "passed"
        if status == "passed":
            passed_scenarios += 1
        else:
            failed_scenarios += 1
    return {
        "executed_scenarios": len(scenario_results),
        "passed_scenarios": passed_scenarios,
        "failed_scenarios": failed_scenarios,
    }


def _has_execution_data(execution_result: dict[str, Any]) -> bool:
    metrics = execution_result.get("metrics") or {}
    return bool(
        execution_result.get("scenario_results")
        or metrics.get("step_count")
        or metrics.get("passed_step_count")
        or metrics.get("failed_step_count")
        or execution_result.get("status") not in (None, "", "not_started")
    )


def _categorize_failure(step: dict[str, Any]) -> str:
    message = str(step.get("message", "")).lower()
    response = step.get("response") or {}
    status_code = response.get("status_code", 0) or 0
    if "missing context" in message:
        return "missing_context"
    if "assertion failed" in message:
        return "assertion_failed"
    if status_code >= 500:
        return "server_error"
    if status_code >= 400:
        return "client_error"
    if "timed out" in message or "timeout" in message:
        return "timeout"
    if "urlopen error" in message or "connection" in message:
        return "network_error"
    return "execution_error"


def _failure_category_label(category: str) -> str:
    labels = {
        "missing_context": "Context Missing",
        "assertion_failed": "Assertion Failed",
        "server_error": "Server Error",
        "client_error": "Client Error",
        "timeout": "Timeout",
        "network_error": "Network Error",
        "execution_error": "Execution Error",
    }
    return labels.get(category, "Unknown Failure")


def _build_reason_detail(step: dict[str, Any], category: str) -> str:
    response = step.get("response") or {}
    status_code = response.get("status_code")
    if category in {"server_error", "client_error"} and status_code:
        return f"HTTP {status_code}"
    if step.get("message"):
        return str(step["message"])
    return _failure_category_label(category)


def _build_request_summary(request_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "method": request_payload.get("method"),
        "url": request_payload.get("url"),
        "has_headers": bool(request_payload.get("headers")),
        "has_params": bool(request_payload.get("params")),
        "has_json": request_payload.get("json") is not None,
        "has_data": request_payload.get("data") is not None,
    }


def _build_response_summary(response_payload: dict[str, Any]) -> dict[str, Any]:
    headers = response_payload.get("headers") or {}
    return {
        "status_code": response_payload.get("status_code"),
        "elapsed_ms": response_payload.get("elapsed_ms"),
        "has_json": response_payload.get("json") is not None,
        "header_count": len(headers),
        "body_preview": response_payload.get("body_preview", ""),
    }


def _collect_extracted_keys(
    metrics: dict[str, Any],
    context_snapshots: list[dict[str, Any]],
    save_context_map: dict[str, Any],
) -> list[str]:
    metric_keys = metrics.get("context_keys")
    if isinstance(metric_keys, list):
        return sorted(str(item) for item in metric_keys)

    runtime_only_keys = {"last_response", "last_status_code"}
    snapshot_keys = {
        key
        for snapshot in context_snapshots
        for key in snapshot.keys()
        if key not in runtime_only_keys
    }
    if snapshot_keys:
        return sorted(snapshot_keys)

    context_key_count = int(metrics.get("context_key_count", 0) or 0)
    if context_key_count and save_context_map:
        return sorted(list(save_context_map.keys())[:context_key_count])
    return []


def _build_findings(
    validation_report: ValidationReport,
    failed_steps: list[dict[str, Any]],
    failure_reasons: list[dict[str, Any]],
) -> list[str]:
    findings = list(validation_report.errors) + list(validation_report.warnings)
    findings.extend(
        f"{item['scenario_name']} / {item['step_id']}: {item['message']}"
        for item in failed_steps[:5]
        if item.get("message")
    )
    if failure_reasons:
        findings.append(
            "Failure categories: "
            + ", ".join(f"{item['category']}={item['count']}" for item in failure_reasons)
        )
    return findings


def _build_dashboard(
    task_context: TaskContext,
    quality_status: str,
    summary: dict[str, Any],
    failure_reasons: list[dict[str, Any]],
    assertion_stats: dict[str, Any],
    context_stats: dict[str, Any],
    task_summary_text: str,
) -> dict[str, Any]:
    cards = [
        {"key": "scenarios", "label": "Scenarios", "value": summary["scenario_count"]},
        {"key": "steps", "label": "Total Steps", "value": summary["total_steps"]},
        {"key": "passed_steps", "label": "Passed", "value": summary["passed_steps"]},
        {"key": "failed_steps", "label": "Failed", "value": summary["failed_steps"]},
        {"key": "success_rate", "label": "Success Rate", "value": summary["success_rate"]},
        {"key": "avg_elapsed_ms", "label": "Avg Elapsed(ms)", "value": summary["avg_elapsed_ms"]},
        {"key": "max_elapsed_ms", "label": "Max Elapsed(ms)", "value": summary["max_elapsed_ms"]},
    ]
    headline = f"{summary['passed_steps']}/{summary['total_steps']} steps passed" if summary["total_steps"] else "No executable steps"
    return {
        "task_id": task_context.task_id,
        "task_name": task_context.task_name,
        "quality_status": quality_status,
        "execution_status": summary["execution_status"],
        "summary": {
            "success_rate": summary["success_rate"],
            "failure_rate": summary["failure_rate"],
            "passed_steps": summary["passed_steps"],
            "failed_steps": summary["failed_steps"],
            "avg_elapsed_ms": summary["avg_elapsed_ms"],
            "max_elapsed_ms": summary["max_elapsed_ms"],
            "assertion_pass_rate": assertion_stats["pass_rate"],
            "context_extracted_keys": context_stats["extracted_key_count"],
        },
        "cards": cards,
        "totals": {
            "scenarios": summary["scenario_count"],
            "steps": summary["total_steps"],
            "assertions": summary["assertion_total"],
        },
        "status_breakdown": {
            "passed_scenarios": summary["passed_scenarios"],
            "failed_scenarios": summary["failed_scenarios"],
            "passed_steps": summary["passed_steps"],
            "failed_steps": summary["failed_steps"],
        },
        "top_failure_reason": failure_reasons[0] if failure_reasons else None,
        "failure_reason_breakdown": failure_reasons,
        "headline": headline,
        "summary_text": task_summary_text,
    }


def _build_task_summary_text(task_name: str, quality_status: str, summary: dict[str, Any]) -> str:
    if summary["execution_status"] == "not_started":
        return (
            f"任务 {task_name} 当前处于 {quality_status} 状态，已生成 {summary['scenario_count']} 个场景、"
            f"{summary['total_steps']} 个步骤，尚未开始执行。"
        )
    return (
        f"任务 {task_name} 当前处于 {quality_status} 状态，共分析 {summary['scenario_count']} 个场景、"
        f"{summary['total_steps']} 个步骤，通过 {summary['passed_steps']} 个、失败 {summary['failed_steps']} 个，"
        f"成功率 {summary['success_rate']}%，平均耗时 {summary['avg_elapsed_ms']}ms，"
        f"最大耗时 {summary['max_elapsed_ms']}ms。"
    )


def _to_mapping(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if is_dataclass(payload):
        return asdict(payload)
    if hasattr(payload, "to_dict"):
        value = payload.to_dict()
        if isinstance(value, dict):
            return value
    return dict(payload)
