"""Minimal local cloud-load runner built on top of the API request stack."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import count
from typing import Any

from api_runner.executor import (
    _build_runtime_state,
    _classify_exception,
    _normalize_request_spec,
    _perform_http_request,
    _render_templates,
    _sanitize_headers,
    _summarize_request,
    _summarize_response,
)
from platform_shared import ContextBus
from platform_shared.models import ExecutionResult


def execute_load_test_case_dsl(test_case_dsl: dict[str, Any]) -> dict[str, Any]:
    """Execute a minimal local load test for API-like DSL steps."""
    scenario_results: list[dict[str, Any]] = []
    logs: list[dict[str, Any]] = []
    total_step_count = 0
    passed_step_count = 0
    total_requests = 0
    total_success = 0
    elapsed_samples: list[float] = []

    for scenario in test_case_dsl.get("scenarios", []):
        step_results: list[dict[str, Any]] = []
        scenario_failed = False

        for step in scenario.get("steps", []):
            total_step_count += 1
            logs.append(
                {
                    "level": "info",
                    "event": "load_step_start",
                    "scenario_id": scenario.get("scenario_id"),
                    "step_id": step.get("step_id"),
                    "message": step.get("text", ""),
                }
            )
            if not step.get("request"):
                step_result = {
                    "step_id": step.get("step_id"),
                    "step_type": step.get("step_type"),
                    "text": step.get("text"),
                    "status": "failed",
                    "message": "cloud-load runner requires request definitions on each step",
                    "error_category": "request_validation_error",
                    "request_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "success_rate": 0.0,
                    "throughput": 0.0,
                }
            else:
                step_result = _execute_load_step(test_case_dsl, scenario, step)

            if step_result["status"] == "passed":
                passed_step_count += 1
            else:
                scenario_failed = True
            total_requests += int(step_result.get("request_count", 0))
            total_success += int(step_result.get("success_count", 0))
            elapsed_samples.extend(step_result.get("_elapsed_samples", []))
            step_result.pop("_elapsed_samples", None)
            step_results.append(step_result)
            logs.append(
                {
                    "level": "info" if step_result["status"] == "passed" else "error",
                    "event": "load_step_result",
                    "scenario_id": scenario.get("scenario_id"),
                    "step_id": step.get("step_id"),
                    "message": step_result.get("message", ""),
                    "status": step_result.get("status"),
                    "request_count": step_result.get("request_count", 0),
                    "success_rate": step_result.get("success_rate", 0.0),
                    "throughput": step_result.get("throughput", 0.0),
                }
            )

        scenario_results.append(
            {
                "scenario_id": scenario.get("scenario_id"),
                "name": scenario.get("name"),
                "status": "failed" if scenario_failed else "passed",
                "steps": step_results,
            }
        )

    overall_status = "passed" if passed_step_count == total_step_count else "failed"
    total_failures = max(total_requests - total_success, 0)
    wall_time_ms = round(sum(elapsed_samples), 2)
    throughput = round((total_success / (wall_time_ms / 1000)), 2) if wall_time_ms > 0 else 0.0
    result = ExecutionResult(
        task_id=test_case_dsl.get("task_id", "unknown_task"),
        executor="cloud-load-runner",
        status=overall_status,
        scenario_results=scenario_results,
        metrics={
            "scenario_count": len(scenario_results),
            "step_count": total_step_count,
            "passed_step_count": passed_step_count,
            "failed_step_count": total_step_count - passed_step_count,
            "total_requests": total_requests,
            "success_count": total_success,
            "failure_count": total_failures,
            "success_rate": round((total_success / total_requests) * 100, 2) if total_requests else 0.0,
            "avg_elapsed_ms": round(sum(elapsed_samples) / len(elapsed_samples), 2) if elapsed_samples else 0.0,
            "max_elapsed_ms": round(max(elapsed_samples), 2) if elapsed_samples else 0.0,
            "throughput": throughput,
        },
        logs=logs,
    )
    return result.to_dict()


def _execute_load_step(
    test_case_dsl: dict[str, Any],
    scenario: dict[str, Any],
    step: dict[str, Any],
) -> dict[str, Any]:
    context = ContextBus()
    runtime_state = _build_runtime_state(test_case_dsl)
    request_spec = _render_templates(step.get("request") or {}, context)
    request_spec = _normalize_request_spec(request_spec, runtime_state, context)
    profile = _resolve_load_profile(test_case_dsl, scenario, step)
    concurrency = max(int(profile.get("concurrency", 1) or 1), 1)
    total_requests = profile.get("total_requests")
    duration_seconds = profile.get("duration_seconds")
    if total_requests is None and duration_seconds is None:
        total_requests = 1
    if total_requests is not None:
        total_requests = max(int(total_requests), 0)
    if duration_seconds is not None:
        duration_seconds = max(float(duration_seconds), 0.0)

    counter = count()
    lock = threading.Lock()
    records: list[dict[str, Any]] = []
    started = time.perf_counter()
    deadline = started + duration_seconds if duration_seconds else None

    def worker() -> None:
        while True:
            with lock:
                request_index = next(counter)
                if total_requests is not None and request_index >= total_requests:
                    return
                if deadline is not None and time.perf_counter() >= deadline:
                    return
            response_payload: dict[str, Any]
            status = "failed"
            assertion_failures: list[str] = []
            error_category = ""
            try:
                response_payload = _perform_http_request(dict(request_spec), runtime_state["opener"])
                assertion_failures = _evaluate_assertions(step.get("assertions") or [], response_payload)
                status = _resolve_request_status(response_payload, assertion_failures)
                error_category = response_payload.get("error_category") or (
                    "assertion_error" if assertion_failures else ""
                )
            except Exception as exc:  # pragma: no cover
                response_payload = {
                    "status_code": 0,
                    "headers": {},
                    "json": None,
                    "body_text": "",
                    "elapsed_ms": 0.0,
                    "error": str(exc),
                    "error_category": _classify_exception(exc),
                    "parse_error": "",
                }
                assertion_failures = [str(exc)]
                error_category = response_payload["error_category"]

            with lock:
                records.append(
                    {
                        "status": status,
                        "elapsed_ms": float(response_payload.get("elapsed_ms", 0.0) or 0.0),
                        "status_code": int(response_payload.get("status_code", 0) or 0),
                        "error_category": error_category,
                        "assertion_failures": assertion_failures,
                        "response_summary": _summarize_response(response_payload),
                    }
                )

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for _ in range(concurrency):
            executor.submit(worker)

    elapsed_samples = [item["elapsed_ms"] for item in records]
    success_count = sum(1 for item in records if item["status"] == "passed")
    failure_count = max(len(records) - success_count, 0)
    status_codes = sorted({item["status_code"] for item in records if item["status_code"]})
    failure_categories = _collect_failure_categories(records)
    last_response_summary = records[-1]["response_summary"] if records else {}
    run_seconds = max(time.perf_counter() - started, 0.0)
    throughput = round((len(records) / run_seconds), 2) if run_seconds > 0 else 0.0
    status = "passed" if records and failure_count == 0 else "failed"
    return {
        "step_id": step.get("step_id"),
        "step_type": step.get("step_type"),
        "text": step.get("text"),
        "status": status,
        "message": (
            f"load completed with {success_count}/{len(records)} successful requests"
            if records
            else "load profile produced no requests"
        ),
        "error_category": ",".join(failure_categories) if failure_categories else "",
        "request": {
            "method": request_spec.get("method", "GET"),
            "url": request_spec.get("url", ""),
            "headers": _sanitize_headers(request_spec.get("headers") or {}),
            "params": request_spec.get("params") or {},
        },
        "request_summary": _summarize_request(request_spec),
        "response": {
            "status_code": last_response_summary.get("status_code", 0),
            "elapsed_ms": round(sum(elapsed_samples) / len(elapsed_samples), 2) if elapsed_samples else 0.0,
            "status_codes": status_codes,
            "total_requests": len(records),
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": round((success_count / len(records)) * 100, 2) if records else 0.0,
            "throughput": throughput,
            "error_category": failure_categories[0] if failure_categories else "",
            "summary": last_response_summary,
        },
        "response_summary": {
            **last_response_summary,
            "status_codes": status_codes,
            "total_requests": len(records),
            "success_rate": round((success_count / len(records)) * 100, 2) if records else 0.0,
            "throughput": throughput,
        },
        "assertion_summary": {
            "total": len(records) * len(step.get("assertions") or []),
            "passed_requests": success_count,
            "failed_requests": failure_count,
            "sample_failures": _collect_assertion_failures(records),
        },
        "load_profile": {
            "concurrency": concurrency,
            "total_requests": total_requests,
            "duration_seconds": duration_seconds,
        },
        "request_count": len(records),
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": round((success_count / len(records)) * 100, 2) if records else 0.0,
        "avg_elapsed_ms": round(sum(elapsed_samples) / len(elapsed_samples), 2) if elapsed_samples else 0.0,
        "max_elapsed_ms": round(max(elapsed_samples), 2) if elapsed_samples else 0.0,
        "throughput": throughput,
        "_elapsed_samples": elapsed_samples,
    }


def _resolve_load_profile(
    test_case_dsl: dict[str, Any],
    scenario: dict[str, Any],
    step: dict[str, Any],
) -> dict[str, Any]:
    metadata = dict((test_case_dsl.get("metadata") or {}).get("load_profile") or {})
    scenario_profile = dict(scenario.get("load_profile") or {})
    step_profile = dict(step.get("load_profile") or {})
    merged = {**metadata, **scenario_profile, **step_profile}
    return merged


def _evaluate_assertions(assertions: list[dict[str, Any]], response_payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for assertion in assertions:
        source = assertion.get("source")
        op = assertion.get("op", "eq")
        expected = assertion.get("expected")
        actual = _read_assertion_source(source, response_payload)
        if not _compare(actual, op, expected):
            failures.append(f"{source} {op} {expected!r}, actual={actual!r}")
    return failures


def _read_assertion_source(source: str | None, response_payload: dict[str, Any]) -> Any:
    if not source:
        return None
    if source == "status_code":
        return response_payload.get("status_code")
    if source == "elapsed_ms":
        return response_payload.get("elapsed_ms")
    if source.startswith("json."):
        current = response_payload.get("json")
        for token in source[5:].replace("[", ".").replace("]", "").split("."):
            if token == "":
                continue
            if isinstance(current, list) and token.isdigit():
                index = int(token)
                current = current[index] if 0 <= index < len(current) else None
            elif isinstance(current, dict):
                current = current.get(token)
            else:
                return None
        return current
    return None


def _compare(actual: Any, op: str, expected: Any) -> bool:
    if op == "eq":
        return actual == expected
    if op == "ge":
        return actual is not None and actual >= expected
    if op == "gt":
        return actual is not None and actual > expected
    if op == "le":
        return actual is not None and actual <= expected
    if op == "lt":
        return actual is not None and actual < expected
    if op == "exists":
        return actual is not None
    return False


def _resolve_request_status(response_payload: dict[str, Any], assertion_failures: list[str]) -> str:
    if assertion_failures:
        return "failed"
    status_code = int(response_payload.get("status_code", 0) or 0)
    if response_payload.get("error_category"):
        return "failed"
    return "passed" if 200 <= status_code < 400 else "failed"


def _collect_failure_categories(records: list[dict[str, Any]]) -> list[str]:
    categories = []
    for item in records:
        category = item.get("error_category")
        if category and category not in categories:
            categories.append(category)
    return categories


def _collect_assertion_failures(records: list[dict[str, Any]]) -> list[str]:
    samples: list[str] = []
    for item in records:
        for failure in item.get("assertion_failures") or []:
            if len(samples) >= 5:
                return samples
            samples.append(failure)
    return samples
