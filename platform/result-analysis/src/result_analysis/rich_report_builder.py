"""Rich analysis report builder for platform test assets."""

from __future__ import annotations

from collections import Counter
from typing import Any

from platform_shared.models import AnalysisReport, TaskContext, ValidationReport

from .assertion_stats import compute_assertion_execution_stats


def build_analysis_report(
    task_context: TaskContext,
    validation_report: ValidationReport,
    scenario_count: int,
    execution_result: dict[str, Any] | None = None,
    test_case_dsl: dict[str, Any] | None = None,
) -> dict:
    """Build an analysis report suitable for dashboard display and demos."""
    execution_result = execution_result or {}
    test_case_dsl = test_case_dsl or {}

    warnings = len(validation_report.warnings)
    validation_errors = len(validation_report.errors)
    step_stats = _collect_step_stats(execution_result, test_case_dsl, validation_report)
    quality_status = _resolve_quality_status(
        validation_report=validation_report,
        failed_step_count=step_stats["failed_step_count"],
    )
    summary = {
        "scenario_count": scenario_count,
        "total_steps": step_stats["total_steps"],
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
        "context_defined_keys": step_stats["context_stats"]["defined_key_count"],
        "context_used_keys": step_stats["context_stats"]["used_key_count"],
        "context_extracted_keys": step_stats["context_stats"]["extracted_key_count"],
    }
    findings = _build_findings(validation_report, step_stats["failed_steps"], step_stats["failure_reasons"])
    execution_overview = {
        "executor": execution_result.get("executor"),
        "status": execution_result.get("status", "not_started"),
        "scenario_count": len(execution_result.get("scenario_results") or []),
        "log_count": len(execution_result.get("logs") or []),
        "has_failures": bool(step_stats["failed_step_count"]),
        "top_failure_category": step_stats["failure_reasons"][0]["category"]
        if step_stats["failure_reasons"]
        else None,
    }

    report = AnalysisReport(
        task_id=task_context.task_id,
        task_name=task_context.task_name,
        quality_status=quality_status,
        summary=summary,
        dashboard=_build_dashboard(task_context, quality_status, summary, step_stats["failure_reasons"]),
        execution_overview=execution_overview,
        failed_steps=step_stats["failed_steps"],
        failure_reasons=step_stats["failure_reasons"],
        assertion_stats=step_stats["assertion_stats"],
        context_stats=step_stats["context_stats"],
        task_summary_text=_build_task_summary_text(task_context.task_name, quality_status, summary),
        findings=findings,
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
                "avg_elapsed_ms": step_stats["avg_elapsed_ms"],
                "max_elapsed_ms": step_stats["max_elapsed_ms"],
            },
            "failure_reasons": {
                item["category"]: item["count"] for item in step_stats["failure_reasons"]
            },
        },
    )
    return report.to_dict()


def _resolve_quality_status(
    validation_report: ValidationReport,
    failed_step_count: int,
) -> str:
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

    total_steps = 0
    passed_step_count = 0
    failed_steps: list[dict[str, Any]] = []
    elapsed_samples: list[float] = []
    failure_counter: Counter[str] = Counter()

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
                        "elapsed_ms": elapsed_ms,
                        "request": step.get("request", {}),
                        "response": step.get("response", {}),
                    }
                )

            if isinstance(elapsed_ms, (int, float)):
                elapsed_samples.append(float(elapsed_ms))

    if total_steps == 0:
        total_steps = int(metrics.get("step_count", 0) or 0)
        passed_step_count = int(metrics.get("passed_step_count", 0) or 0)
    failed_step_count = max(total_steps - passed_step_count, len(failed_steps))

    if not elapsed_samples:
        avg_elapsed_ms = round(float(metrics.get("avg_elapsed_ms", 0) or 0), 2)
        max_elapsed_ms = round(float(metrics.get("max_elapsed_ms", 0) or 0), 2)
    else:
        avg_elapsed_ms = round(sum(elapsed_samples) / len(elapsed_samples), 2)
        max_elapsed_ms = round(max(elapsed_samples), 2)

    total_assertions, passed_assertion_count, failed_assertion_count = compute_assertion_execution_stats(
        scenario_results, test_case_dsl
    )
    used_context_keys = sorted(
        {
            key
            for step in dsl_steps
            for key in (step.get("uses_context") or [])
        }
    )
    save_context_map = {}
    for step in dsl_steps:
        for key, source in (step.get("save_context") or {}).items():
            save_context_map[key] = source

    return {
        "total_steps": total_steps,
        "passed_step_count": passed_step_count,
        "failed_step_count": failed_step_count,
        "success_rate": round((passed_step_count / total_steps) * 100, 2) if total_steps else 0.0,
        "failure_rate": round((failed_step_count / total_steps) * 100, 2) if total_steps else 0.0,
        "avg_elapsed_ms": avg_elapsed_ms,
        "max_elapsed_ms": max_elapsed_ms,
        "failed_steps": failed_steps,
        "failure_reasons": [
            {"category": category, "count": count}
            for category, count in failure_counter.most_common()
        ],
        "assertion_stats": {
            "total": total_assertions,
            "passed": passed_assertion_count,
            "failed": failed_assertion_count,
            "pass_rate": round((passed_assertion_count / total_assertions) * 100, 2)
            if total_assertions
            else 0.0,
            "validation_errors": len(validation_report.errors),
            "validation_warnings": len(validation_report.warnings),
        },
        "context_stats": {
            "defined_keys": sorted(save_context_map.keys()),
            "defined_key_count": len(save_context_map),
            "used_keys": used_context_keys,
            "used_key_count": len(used_context_keys),
            "extracted_key_count": int(metrics.get("context_key_count", 0) or 0),
            "unused_defined_keys": sorted(set(save_context_map) - set(used_context_keys)),
            "save_rules": save_context_map,
        },
    }


def _flatten_dsl_steps(test_case_dsl: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for scenario in test_case_dsl.get("scenarios", []):
        steps.extend(scenario.get("steps", []))
    return steps


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
        },
        "cards": cards,
        "totals": {
            "scenarios": summary["scenario_count"],
            "steps": summary["total_steps"],
            "assertions": summary["assertion_total"],
        },
        "top_failure_reason": failure_reasons[0] if failure_reasons else None,
        "failure_reason_breakdown": failure_reasons,
        "headline": f"{summary['passed_steps']}/{summary['total_steps']} steps passed",
    }


def _build_task_summary_text(task_name: str, quality_status: str, summary: dict[str, Any]) -> str:
    return (
        f"任务 {task_name} 当前状态为 {quality_status}，"
        f"共分析 {summary['scenario_count']} 个场景、{summary['total_steps']} 个步骤，"
        f"通过 {summary['passed_steps']} 个、失败 {summary['failed_steps']} 个，"
        f"成功率 {summary['success_rate']}%，平均耗时 {summary['avg_elapsed_ms']}ms，"
        f"最大耗时 {summary['max_elapsed_ms']}ms。"
    )
