"""FastAPI application for the platform task-center."""

from __future__ import annotations

import concurrent.futures
import asyncio
import hashlib
from dataclasses import replace
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.gzip import GZipMiddleware
from pydantic import ValidationError

from execution_engine_core import run_dsl
from platform_shared.models import EnvironmentConfig, TaskContext, ValidationReport

from .api_models import (
    AnalysisParseRequest,
    ApiResponse,
    CreateTaskRequest,
    ErrorResponse,
    ExecuteTaskRequest,
    HealthInfo,
    ParseMetadata,
    PreflightCheckRequest,
    TaskParseRequest,
    StopExecutionResponse,
    TaskListResponse,
    TaskStatus,
    UpsertEnvironmentRequest,
    VersionInfo,
)
from .artifact_manager import ensure_task_subdirs, write_json_artifact
from .execution_explanations import build_execution_explanations
from .input_handler import normalize_input
from .preflight import run_preflight_check
from .pipeline import run_analysis_pipeline
from .registry import DEFAULT_ARTIFACT_TYPES, TaskRegistry
from requirement_analysis import AnalysisParseOptions, parse_requirement_bundle
from result_analysis import build_analysis_report


APP_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_ROOT = str(APP_ROOT / "api_artifacts")
APP_VERSION = "0.2.0"
EXECUTION_TIMEOUT_SECONDS = 300  # 5 分钟执行上限，防止慢接口挂起
registry = TaskRegistry(ARTIFACTS_ROOT)
app = FastAPI(title="Platform Task Center API", version=APP_VERSION)
_ASYNC_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)
_RUNNING_EXECUTION_FUTURES: dict[str, concurrent.futures.Future] = {}
_RUNNING_EXECUTION_LOCK = threading.Lock()

# Frontend (Vite) runs on a different origin (port), so browser requests may trigger
# CORS preflight (`OPTIONS`). Without this middleware, preflight can fail with 405.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev/MVP: allow all origins
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=512, compresslevel=6)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_to_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _success_response(
    data: Any,
    *,
    code: str = "OK",
    message: str = "success",
    status_code: int = 200,
) -> JSONResponse:
    payload = ApiResponse(
        success=True,
        code=code,
        message=message,
        data=data,
        timestamp=_utc_now_iso(),
    )
    return JSONResponse(status_code=status_code, content=_model_to_dict(payload))


def _error_response(
    *,
    code: str,
    message: str,
    detail: Any = None,
    status_code: int = 400,
) -> JSONResponse:
    payload = ErrorResponse(
        code=code,
        message=message,
        data={"detail": detail},
        timestamp=_utc_now_iso(),
    )
    return JSONResponse(status_code=status_code, content=_model_to_dict(payload))


@app.exception_handler(HTTPException)
async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    code_map = {
        400: "BAD_REQUEST",
        404: "TASK_NOT_FOUND",
        422: "VALIDATION_ERROR",
        500: "INTERNAL_ERROR",
    }
    return _error_response(
        code=code_map.get(exc.status_code, f"HTTP_{exc.status_code}"),
        message=str(exc.detail),
        detail=exc.detail,
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def _request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    message = errors[0].get("msg", "request validation failed") if errors else "request validation failed"
    return _error_response(
        code="VALIDATION_ERROR",
        message=message,
        detail=errors,
        status_code=422,
    )


@app.exception_handler(ValidationError)
async def _validation_exception_handler(_: Request, exc: ValidationError) -> JSONResponse:
    return _error_response(
        code="VALIDATION_ERROR",
        message="request validation failed",
        detail=exc.errors(),
        status_code=422,
    )


@app.exception_handler(Exception)
async def _unexpected_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    return _error_response(
        code="INTERNAL_ERROR",
        message="unexpected server error",
        detail=str(exc),
        status_code=500,
    )


def _must_get_task(task_id: str):
    task = registry.get(task_id)
    if task is None or task.archived:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return task


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _detect_suspicious_inline_requirement(raw_text: str) -> list[str]:
    text = str(raw_text or "")
    stripped = text.rstrip()
    if not stripped:
        return []

    issues: list[str] = []
    size_aligned = len(text) >= 512 and len(text) % 1024 == 0
    unclosed_code_fence = stripped.count("```") % 2 == 1
    unbalanced_jsonish = stripped.count("{") > stripped.count("}") or stripped.count("[") > stripped.count("]")
    trailing_incomplete = bool(stripped) and stripped[-1] in {'"', "'", "{", "[", ":", ",", "-", "_"}

    if size_aligned and unclosed_code_fence:
        issues.append(f"文本长度为 {len(text)}，且 Markdown 代码块未闭合")
    if size_aligned and unbalanced_jsonish:
        issues.append(f"文本长度为 {len(text)}，且结构化片段括号未闭合")
    if size_aligned and trailing_incomplete:
        issues.append(f"文本长度为 {len(text)}，且末尾停在未完成片段")
    return _dedupe_strings(issues)


def _parse_iso_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    value = raw.strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _filter_tasks_by_time(items: list, start_time: str | None, end_time: str | None) -> list:
    start = _parse_iso_timestamp(start_time)
    end = _parse_iso_timestamp(end_time)
    if start is None and end is None:
        return items

    filtered = []
    for item in items:
        created_at = _parse_iso_timestamp(item.created_at)
        if created_at is None:
            continue
        if start and created_at < start:
            continue
        if end and created_at > end:
            continue
        filtered.append(item)
    return filtered


def _filter_dict_items_by_time(
    items: list[dict[str, Any]],
    timestamp_key: str,
    start_time: str | None,
    end_time: str | None,
) -> list[dict[str, Any]]:
    start = _parse_iso_timestamp(start_time)
    end = _parse_iso_timestamp(end_time)
    if start is None and end is None:
        return items

    filtered: list[dict[str, Any]] = []
    for item in items:
        recorded_at = _parse_iso_timestamp(item.get(timestamp_key))
        if recorded_at is None:
            continue
        if start and recorded_at < start:
            continue
        if end and recorded_at > end:
            continue
        filtered.append(item)
    return filtered


def _paginate(items: list[dict[str, Any]], page: int, page_size: int) -> dict[str, Any]:
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "total": len(items),
        "page": page,
        "page_size": page_size,
    }


def _resolve_environment_config(task, environment_name: str | None) -> EnvironmentConfig | None:
    selected_name = environment_name or task.environment
    environment_config = registry.get_environment(selected_name)
    if environment_name and environment_config is None:
        raise HTTPException(status_code=404, detail=f"Environment not found: {environment_name}")
    return environment_config


def _inject_environment_into_dsl(
    dsl: dict[str, Any],
    environment_name: str | None,
    environment_config: EnvironmentConfig | None,
    fallback_base_url: str = "",
) -> dict[str, Any]:
    payload = dict(dsl)
    metadata = dict(payload.get("metadata") or {})
    execution = dict(metadata.get("execution") or {})
    if environment_config is not None:
        if environment_config.base_url:
            execution["base_url"] = environment_config.base_url
        if environment_config.default_headers:
            execution["default_headers"] = environment_config.default_headers
        if environment_config.auth:
            execution["auth"] = environment_config.auth
        if environment_config.cookies:
            execution["cookies"] = environment_config.cookies
    if environment_name:
        execution["environment"] = environment_name
    if not execution.get("base_url") and fallback_base_url:
        execution["base_url"] = fallback_base_url
    metadata["execution"] = execution
    payload["metadata"] = metadata
    return payload


def _derive_fallback_base_url(task) -> str:
    if task.target_system:
        parsed = urlparse(task.target_system)
        if parsed.scheme and parsed.netloc:
            return task.target_system.rstrip("/")
    return ""


def _record_execution_history(task, execution_result: dict[str, Any]) -> None:
    metadata = execution_result.get("metadata") or {}
    execution_meta = metadata.get("execution") or {}
    analysis_report = (task.pipeline_result or {}).get("analysis_report") or {}
    summary = analysis_report.get("summary") or {}
    registry.append_execution_history(
        {
            "task_id": task.task_id,
            "task_name": task.task_name,
            "environment": execution_meta.get("environment") or task.environment,
            "execution_mode": execution_meta.get("execution_mode"),
            "status": execution_result.get("status"),
            "executor": execution_result.get("executor"),
            "executed_at": metadata.get("executed_at", _utc_now_iso()),
            "metrics": execution_result.get("metrics") or {},
            "analysis_summary": {
                "success_rate": summary.get("success_rate", 0.0),
                "failed_steps": summary.get("failed_steps", 0),
                "avg_elapsed_ms": summary.get("avg_elapsed_ms", 0.0),
            },
        }
    )


def _run_dsl_with_timeout(dsl: dict[str, Any], execution_mode: str) -> dict[str, Any]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _executor:
        _future = _executor.submit(run_dsl, dsl, execution_mode=execution_mode)
        try:
            return _future.result(timeout=EXECUTION_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError as exc:
            raise HTTPException(
                status_code=408,
                detail=f"execution timed out after {EXECUTION_TIMEOUT_SECONDS}s",
            ) from exc


def _apply_execution_metadata(
    execution_result: dict[str, Any],
    *,
    selected_environment: str,
    execution_mode: str,
    environment_config: EnvironmentConfig | None,
    dsl: dict[str, Any],
) -> dict[str, Any]:
    execution_metadata = dict(execution_result.get("metadata") or {})
    execution_metadata["execution"] = {
        "environment": selected_environment,
        "execution_mode": execution_mode,
        "base_url": (
            (environment_config.base_url if environment_config and environment_config.base_url else "")
            or str((dsl.get("metadata") or {}).get("execution", {}).get("base_url", ""))
        ),
        "default_headers": (environment_config.default_headers if environment_config else {}),
        "auth": (environment_config.auth if environment_config else {}),
        "cookies": (environment_config.cookies if environment_config else {}),
        "context": {"task_id": str(dsl.get("task_id") or "")},
    }
    execution_metadata["executed_at"] = _utc_now_iso()
    execution_result["metadata"] = execution_metadata
    return execution_result


def _build_running_execution_result(task_id: str, execution_mode: str, selected_environment: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "executor": "api-runner",
        "status": "running",
        "scenario_results": [],
        "metrics": {},
        "logs": [
            {
                "time": _utc_now_iso(),
                "level": "INFO",
                "message": "Execution started in async mode",
            }
        ],
        "metadata": {
            "execution": {
                "execution_mode": execution_mode,
                "environment": selected_environment,
            },
            "executed_at": _utc_now_iso(),
        },
    }


def _run_async_execution_job(
    task_id: str,
    dsl: dict[str, Any],
    execution_mode: str,
    selected_environment: str,
    environment_config: EnvironmentConfig | None,
) -> None:
    try:
        progress_lock = threading.Lock()
        last_progress_persist_at = 0.0

        def _normalize_level(raw: Any) -> str:
            level = str(raw or "INFO").upper()
            if level not in {"INFO", "WARN", "ERROR"}:
                return "INFO"
            return level

        def _merge_scenario_snapshot(existing: list[dict[str, Any]], event: dict[str, Any]) -> list[dict[str, Any]]:
            scenario_id = str(event.get("scenario_id") or "")
            scenario_name = str(event.get("scenario_name") or "")
            status = str(event.get("status") or "").lower() or "running"

            copied = [dict(item) for item in existing]
            hit_index = -1
            for index, item in enumerate(copied):
                if scenario_id and str(item.get("scenario_id") or "") == scenario_id:
                    hit_index = index
                    break
                if scenario_name and str(item.get("name") or "") == scenario_name:
                    hit_index = index
                    break

            merged_item: dict[str, Any] = {
                "scenario_id": scenario_id or None,
                "name": scenario_name or (scenario_id or "未命名场景"),
                "status": status,
            }
            failed_steps = event.get("failed_steps")
            if isinstance(failed_steps, int):
                merged_item["failed_steps"] = failed_steps

            if hit_index >= 0:
                copied[hit_index] = {**copied[hit_index], **merged_item}
            else:
                copied.append(merged_item)
            return copied

        def _on_progress(event: dict[str, Any]) -> None:
            nonlocal last_progress_persist_at
            with progress_lock:
                task = registry.get(task_id)
                if task is None:
                    return
                if str((task.execution_result or {}).get("status") or "") == "stopped":
                    return

                base = task.execution_result or _build_running_execution_result(task_id, execution_mode, selected_environment)
                logs = list(base.get("logs") or [])
                scenarios = list(base.get("scenario_results") or [])

                normalized_event = dict(event)
                normalized_event["time"] = _utc_now_iso()
                normalized_event["level"] = _normalize_level(normalized_event.get("level"))
                logs.append(normalized_event)

                event_name = str(normalized_event.get("event") or "")
                if event_name in {"step_start", "step_result", "scenario_result"}:
                    scenarios = _merge_scenario_snapshot(scenarios, normalized_event)

                task.execution_result = {
                    **base,
                    "status": "running",
                    "scenario_results": scenarios,
                    "logs": logs[-400:],
                }

                now = time.time()
                should_persist = event_name in {"scenario_result", "step_result"}
                if should_persist or (now - last_progress_persist_at) >= 1.0:
                    _persist_task_runtime(task)
                    last_progress_persist_at = now

        started_at = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _executor:
            worker_future = _executor.submit(
                run_dsl,
                dsl,
                execution_mode=execution_mode,
                progress_callback=_on_progress,
            )
            last_tick_second = -1
            while not worker_future.done():
                elapsed = int(time.time() - started_at)
                if elapsed >= EXECUTION_TIMEOUT_SECONDS:
                    worker_future.cancel()
                    raise HTTPException(
                        status_code=408,
                        detail=f"execution timed out after {EXECUTION_TIMEOUT_SECONDS}s",
                    )
                task = registry.get(task_id)
                if task is None:
                    return
                current_status = str((task.execution_result or {}).get("status") or "")
                if current_status == "stopped":
                    worker_future.cancel()
                    return
                if elapsed != last_tick_second:
                    last_tick_second = elapsed
                    base = task.execution_result or _build_running_execution_result(task_id, execution_mode, selected_environment)
                    logs = list(base.get("logs") or [])
                    logs.append(
                        {
                            "time": _utc_now_iso(),
                            "level": "INFO",
                            "event": "heartbeat",
                            "message": f"Execution running... {elapsed}s",
                        }
                    )
                    task.execution_result = {
                        **base,
                        "status": "running",
                        "logs": logs[-200:],
                    }
                    _persist_task_runtime(task)
                time.sleep(1)
            execution_result = worker_future.result()
        execution_result = _apply_execution_metadata(
            execution_result,
            selected_environment=selected_environment,
            execution_mode=execution_mode,
            environment_config=environment_config,
            dsl=dsl,
        )
        task = registry.get(task_id)
        if task is None:
            return
        current_status = str((task.execution_result or {}).get("status") or "")
        if current_status == "stopped":
            logs = list((task.execution_result or {}).get("logs") or [])
            logs.append(
                {
                    "time": _utc_now_iso(),
                    "level": "WARN",
                    "message": "Execution finished after stop request; keeping stopped status",
                }
            )
            task.execution_result = {
                **(task.execution_result or {}),
                "logs": logs,
            }
            _persist_task_runtime(task)
            return
        task.execution_result = execution_result
        task.environment = selected_environment
        task.status = execution_result.get("status", "executed")
        _build_task_analysis_report(task)
        _record_execution_history(task, execution_result)
    except Exception as exc:
        task = registry.get(task_id)
        if task is None:
            return
        base = task.execution_result or _build_running_execution_result(task_id, execution_mode, selected_environment)
        logs = list(base.get("logs") or [])
        logs.append({"time": _utc_now_iso(), "level": "ERROR", "message": f"Execution failed: {exc}"})
        task.execution_result = {
            **base,
            "status": "failed",
            "logs": logs,
        }
        task.status = "failed"
        _persist_task_runtime(task)
    finally:
        with _RUNNING_EXECUTION_LOCK:
            _RUNNING_EXECUTION_FUTURES.pop(task_id, None)


def _numeric(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _compute_regression_verdict(
    *,
    failed_steps_delta: int,
    success_rate_delta: float,
) -> str:
    if failed_steps_delta > 0 or success_rate_delta < 0:
        return "regressed"
    if failed_steps_delta < 0 or success_rate_delta > 0:
        return "improved"
    return "unchanged"


def _build_regression_diff(
    task_id: str,
    base_item: dict[str, Any],
    target_item: dict[str, Any],
) -> dict[str, Any]:
    base_summary = base_item.get("analysis_summary") or {}
    target_summary = target_item.get("analysis_summary") or {}
    base_metrics = base_item.get("metrics") or {}
    target_metrics = target_item.get("metrics") or {}

    base_failed_steps = int(_numeric(base_summary.get("failed_steps", base_metrics.get("failed_step_count", 0)), 0))
    target_failed_steps = int(_numeric(target_summary.get("failed_steps", target_metrics.get("failed_step_count", 0)), 0))
    base_success_rate = _numeric(base_summary.get("success_rate", 0.0), 0.0)
    target_success_rate = _numeric(target_summary.get("success_rate", 0.0), 0.0)
    base_avg_elapsed = _numeric(base_summary.get("avg_elapsed_ms", base_metrics.get("avg_elapsed_ms", 0.0)), 0.0)
    target_avg_elapsed = _numeric(target_summary.get("avg_elapsed_ms", target_metrics.get("avg_elapsed_ms", 0.0)), 0.0)

    failed_steps_delta = target_failed_steps - base_failed_steps
    success_rate_delta = round(target_success_rate - base_success_rate, 2)
    avg_elapsed_delta = round(target_avg_elapsed - base_avg_elapsed, 2)

    return {
        "task_id": task_id,
        "base_execution_id": str(base_item.get("executed_at") or ""),
        "target_execution_id": str(target_item.get("executed_at") or ""),
        "metrics_diff": {
            "base_executed_at": base_item.get("executed_at"),
            "target_executed_at": target_item.get("executed_at"),
            "failed_steps_delta": failed_steps_delta,
            "success_rate_delta": success_rate_delta,
            "avg_elapsed_ms_delta": avg_elapsed_delta,
            "failed_steps": {"base": base_failed_steps, "target": target_failed_steps, "delta": failed_steps_delta},
            "success_rate": {"base": base_success_rate, "target": target_success_rate, "delta": success_rate_delta},
            "avg_elapsed_ms": {"base": base_avg_elapsed, "target": target_avg_elapsed, "delta": avg_elapsed_delta},
        },
        "failure_type_diff": [
            {
                "category": "failed_steps",
                "base": base_failed_steps,
                "target": target_failed_steps,
                "delta": failed_steps_delta,
            }
        ],
        "verdict": _compute_regression_verdict(
            failed_steps_delta=failed_steps_delta,
            success_rate_delta=success_rate_delta,
        ),
    }


def _task_parse_option_overrides(task) -> dict[str, Any]:
    """Build parse option overrides from persisted task_context (e.g. rag_enabled at creation)."""
    tc = task.task_context or {}
    out: dict[str, Any] = {}
    for key in ("use_llm", "rag_enabled", "retrieval_top_k", "rerank_enabled", "model_profile"):
        if key in tc:
            out[key] = tc[key]
    return out


def _resolve_parse_options(payload: Any = None) -> AnalysisParseOptions:
    if payload is None:
        return AnalysisParseOptions.resolve()
    data = _model_to_dict(payload)
    return AnalysisParseOptions.resolve(
        {
            "use_llm": data.get("use_llm"),
            "rag_enabled": data.get("rag_enabled"),
            "retrieval_top_k": data.get("retrieval_top_k"),
            "rerank_enabled": data.get("rerank_enabled"),
            "model_profile": data.get("model_profile"),
        }
    )


def _normalize_parse_metadata_rag_fields(meta: dict[str, Any]) -> None:
    """Keep rag_enabled and rag_used in sync (canonical key: rag_enabled)."""
    has_e = "rag_enabled" in meta
    has_u = "rag_used" in meta
    if has_e and not has_u:
        meta["rag_used"] = bool(meta.get("rag_enabled"))
    elif has_u and not has_e:
        meta["rag_enabled"] = bool(meta.get("rag_used"))
    elif has_e and has_u:
        meta["rag_used"] = bool(meta.get("rag_enabled"))


def _parse_metadata_rag_enabled(meta: dict[str, Any]) -> bool:
    if meta.get("rag_enabled") is not None:
        return bool(meta["rag_enabled"])
    return bool(meta.get("rag_used", False))


def _parse_metadata_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, ParseMetadata):
        return _model_to_dict(raw)
    if not isinstance(raw, dict):
        return _model_to_dict(ParseMetadata())
    try:
        normalized = dict(raw)
        _normalize_parse_metadata_rag_fields(normalized)
        return _model_to_dict(ParseMetadata(**normalized))
    except Exception:
        out = dict(raw)
        _normalize_parse_metadata_rag_fields(out)
        return out


def _encode_sse(data: Any, event: str | None = None) -> str:
    if isinstance(data, str):
        payload = data
    else:
        payload = json.dumps(data, ensure_ascii=False)
    lines = []
    if event:
        lines.append(f"event: {event}")
    for line in payload.splitlines() or [""]:
        lines.append(f"data: {line}")
    return "\n".join(lines) + "\n\n"


_ANALYSIS_REPORT_INPUT_FP_KEY = "_analysis_report_input_fp"


def _analysis_report_input_fingerprint(task, result: dict[str, Any]) -> str:
    """Stable hash of inputs that affect build_analysis_report (skip rebuild when unchanged)."""
    er = task.execution_result or {}
    vr = result.get("validation_report")
    if hasattr(vr, "model_dump"):
        vr_d = vr.model_dump()
    elif isinstance(vr, dict):
        vr_d = vr
    else:
        vr_d = {}
    scenarios = result.get("scenarios") or []
    scenario_n = len(scenarios) if isinstance(scenarios, list) else 0
    dsl = result.get("test_case_dsl") or {}
    dsl_n = 0
    if isinstance(dsl, dict):
        ds = dsl.get("scenarios")
        dsl_n = len(ds) if isinstance(ds, list) else 0
    payload = {
        "task_id": task.task_id,
        "exec_status": str(er.get("status", "")),
        "exec_scenarios": len(er.get("scenario_results") or []),
        "exec_logs": len(er.get("logs") or []),
        "vr_passed": bool(vr_d.get("passed")),
        "vr_err": len(vr_d.get("errors") or []),
        "vr_warn": len(vr_d.get("warnings") or []),
        "scenario_n": scenario_n,
        "dsl_n": dsl_n,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _ensure_pipeline(task, parse_options: AnalysisParseOptions | None = None) -> dict[str, Any]:
    if task.pipeline_result is not None:
        parse_metadata = _parse_metadata_payload(task.pipeline_result.get("parse_metadata", {}))
        if parse_options is None:
            task.pipeline_result["parse_metadata"] = parse_metadata
            return task.pipeline_result
        same_config = (
            parse_metadata.get("llm_attempted", False) == parse_options.use_llm
            and _parse_metadata_rag_enabled(parse_metadata) == parse_options.rag_enabled
            and int(parse_metadata.get("retrieval_top_k", 5)) == parse_options.retrieval_top_k
            and parse_metadata.get("rerank_enabled", False) == parse_options.rerank_enabled
            and str(parse_metadata.get("model_profile", "default")) == parse_options.model_profile
        )
        if same_config:
            task.pipeline_result["parse_metadata"] = parse_metadata
            return task.pipeline_result

    resolved: AnalysisParseOptions
    if parse_options is not None:
        resolved = parse_options
    else:
        resolved = AnalysisParseOptions.resolve(_task_parse_option_overrides(task))

    result = run_analysis_pipeline(
        task_name=task.task_name,
        requirement_text=task.requirement_text,
        source_type=task.source_type,
        source_path=task.source_path,
        artifacts_base_dir=registry.artifacts_root,
        task_id=task.task_id,
        created_at=(task.task_context or {}).get("created_at") or task.created_at,
        task_status=(task.task_context or {}).get("status") or task.status or "received",
        artifact_dir_name=task.task_id,
        use_llm=resolved.use_llm,
        rag_enabled=resolved.rag_enabled,
        retrieval_top_k=resolved.retrieval_top_k,
        rerank_enabled=resolved.rerank_enabled,
        model_profile=resolved.model_profile,
    )
    task.pipeline_result = result
    task.pipeline_result["parse_metadata"] = _parse_metadata_payload(result.get("parse_metadata", {}))
    task.status = "parsed"
    task.task_context = result.get("task_context", task.task_context)
    task.artifact_dir = result.get("artifact_dir") or task.artifact_dir
    registry.save(task)
    return result


def _build_task_analysis_report(task, *, persist_registry: bool = True) -> dict[str, Any]:
    result = _ensure_pipeline(task)
    fp = _analysis_report_input_fingerprint(task, result)
    cached = result.get("analysis_report")
    if cached is not None and result.get(_ANALYSIS_REPORT_INPUT_FP_KEY) == fp:
        return cached
    report = build_analysis_report(
        task_context=TaskContext(**result["task_context"]),
        validation_report=ValidationReport(**result["validation_report"]),
        scenario_count=len(result.get("scenarios", [])),
        execution_result=task.execution_result,
        test_case_dsl=result.get("test_case_dsl"),
    )
    result["analysis_report"] = report
    result[_ANALYSIS_REPORT_INPUT_FP_KEY] = fp
    _persist_task_runtime(task, persist_registry=persist_registry)
    return report


def _persist_task_runtime(task, *, persist_registry: bool = True) -> None:
    if not task.artifact_dir:
        if persist_registry:
            registry.save(task)
        return
    subdirs = ensure_task_subdirs(task.artifact_dir)
    if task.pipeline_result is not None:
        write_json_artifact(
            str(Path(subdirs["validation"]) / "analysis_report.json"),
            task.pipeline_result.get("analysis_report", {}),
        )
    if task.execution_result is not None:
        write_json_artifact(
            str(Path(subdirs["execution"]) / "execution_result.json"),
            task.execution_result,
        )
    if persist_registry:
        registry.save(task)


@app.get("/health", response_model=ApiResponse)
def health_check():
    payload = _model_to_dict(HealthInfo(status="ok", service="platform-task-center", version=APP_VERSION))
    return _success_response(payload, code="HEALTH_OK", message="service healthy")


@app.get("/version", response_model=ApiResponse)
def version_info():
    payload = _model_to_dict(VersionInfo(
        service="platform-task-center",
        version=APP_VERSION,
        api_version=APP_VERSION,
    ))
    return _success_response(payload, code="VERSION_OK", message="service version")


@app.post("/api/tasks", response_model=ApiResponse)
def create_task(payload: CreateTaskRequest):
    inline_requirement = str(payload.requirement_text or "")
    if not (payload.source_path or "").strip():
        integrity_issues = _detect_suspicious_inline_requirement(inline_requirement)
        if integrity_issues:
            raise HTTPException(
                status_code=400,
                detail=(
                    "inline requirement_text 疑似在上传前被截断："
                    + "；".join(integrity_issues)
                    + "。请重新提交完整文本，或改用 source_path / 文件导入。"
                ),
            )
    normalized = normalize_input(
        task_name=payload.task_name,
        requirement_text=payload.requirement_text,
        source_type=payload.source_type,
        source_path=payload.source_path,
    )
    base_ctx = TaskContext(**normalized["task_context"])
    if payload.rag_enabled is not None:
        base_ctx = replace(base_ctx, rag_enabled=bool(payload.rag_enabled))
    context = base_ctx.to_dict()
    record = registry.create_task(
        task_id=context["task_id"],
        task_name=context["task_name"],
        source_type=payload.source_type,
        requirement_text=payload.requirement_text,
        source_path=payload.source_path,
        target_system=payload.target_system,
        environment=payload.environment,
        task_context=context,
    )
    return _success_response(
        {"task_id": record.task_id, "task_context": record.task_context},
        code="TASK_CREATED",
        message="task created",
        status_code=201,
    )


@app.get("/api/tasks", response_model=ApiResponse)
def list_tasks(
    status: TaskStatus | None = None,
    keyword: str | None = None,
    environment: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    items = registry.list(status=status.value if status else None, keyword=keyword)
    if environment:
        items = [item for item in items if item.environment == environment]
    payload = _paginate([item.to_summary() for item in items], page, page_size)
    TaskListResponse(**payload)
    return _success_response(payload, code="TASK_LIST_OK", message="tasks listed")


def _shrink_execution_for_summary(er: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strip heavy logs / per-step payloads for fast first paint (detail_level=summary)."""
    if not er:
        return None
    keys = ("scenario_id", "scenario_name", "status", "duration_ms", "passed_steps", "failed_steps")
    slim_scenarios: list[dict[str, Any]] = []
    for raw in er.get("scenario_results") or []:
        if not isinstance(raw, dict):
            continue
        slim_scenarios.append({k: raw.get(k) for k in keys})
    return {
        "task_id": str(er.get("task_id", "")),
        "executor": er.get("executor"),
        "status": str(er.get("status", "not_started")),
        "scenario_results": slim_scenarios,
        "metrics": er.get("metrics") if isinstance(er.get("metrics"), dict) else {},
        "logs": [],
    }


@app.get("/api/tasks/{task_id}", response_model=ApiResponse)
def get_task(
    task_id: str,
    detail_level: Literal["full", "summary"] = Query(
        "full",
        description="full: complete payload; summary: small first paint (merge with full client-side).",
    ),
):
    task = _must_get_task(task_id)
    pipeline = task.pipeline_result or {}
    base = {
        **task.to_summary(),
        "task_context": task.task_context,
        "artifact_dir": task.artifact_dir,
        "parse_metadata": _parse_metadata_payload(pipeline.get("parse_metadata", {})),
    }
    if detail_level == "summary":
        return _success_response(
            {
                **base,
                "parsed_requirement": None,
                "retrieved_context": None,
                "scenarios": None,
                "test_case_dsl": None,
                "validation_report": None,
                "analysis_report": None,
                "feature_text": None,
                "execution_result": _shrink_execution_for_summary(
                    task.execution_result if isinstance(task.execution_result, dict) else None,
                ),
            },
            code="TASK_DETAIL_OK",
            message="task detail summary",
        )
    return _success_response(
        {
            **base,
            "parsed_requirement": pipeline.get("parsed_requirement"),
            "retrieved_context": pipeline.get("retrieved_context"),
            "scenarios": pipeline.get("scenarios"),
            "test_case_dsl": pipeline.get("test_case_dsl"),
            "validation_report": pipeline.get("validation_report"),
            "analysis_report": pipeline.get("analysis_report"),
            "feature_text": pipeline.get("feature_text"),
            "execution_result": task.execution_result,
        },
        code="TASK_DETAIL_OK",
        message="task detail",
    )


@app.delete("/api/tasks/{task_id}", response_model=ApiResponse)
def delete_task(task_id: str):
    if not registry.archive(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return _success_response({"task_id": task_id, "archived": True}, code="TASK_ARCHIVED", message="task archived")


@app.post("/api/tasks/{task_id}/parse", response_model=ApiResponse)
def parse_task(task_id: str, payload: TaskParseRequest | None = None):
    task = _must_get_task(task_id)
    parse_options = _resolve_parse_options(payload)
    result = _ensure_pipeline(task, parse_options=parse_options)
    return _success_response({
        "task_id": task_id,
        "status": task.status,
        "parsed_requirement": result.get("parsed_requirement"),
        "parse_metadata": _parse_metadata_payload(result.get("parse_metadata", {})),
    }, code="TASK_PARSED", message="task parsed")


@app.post("/api/analysis/parse", response_model=ApiResponse)
def parse_analysis(payload: AnalysisParseRequest):
    if not (payload.requirement_text or "").strip() and not (payload.source_path or "").strip():
        raise HTTPException(status_code=400, detail="requirement_text or source_path is required")
    parse_options = _resolve_parse_options(payload)
    normalized = normalize_input(
        task_name=payload.task_name,
        requirement_text=payload.requirement_text,
        source_type=payload.source_type,
        source_path=payload.source_path,
    )
    normalized_task_name = str(normalized["task_context"]["task_name"])
    result = parse_requirement_bundle(
        requirement_text=payload.requirement_text,
        source_path=payload.source_path,
        options=parse_options,
    )
    return _success_response(
        {
            "task_name": normalized_task_name,
            "source_type": payload.source_type,
            "parsed_requirement": result.get("parsed_requirement", {}),
            "retrieved_context": result.get("retrieved_context", []),
            "validation_report": result.get("validation_report", {}),
            "parse_metadata": _parse_metadata_payload(result.get("parse_metadata", {})),
        },
        code="ANALYSIS_PARSED",
        message="analysis parsed",
    )


@app.get("/api/tasks/{task_id}/parsed-requirement", response_model=ApiResponse)
def get_parsed_requirement(task_id: str):
    task = _must_get_task(task_id)
    result = _ensure_pipeline(task)
    return _success_response(result.get("parsed_requirement", {}), code="PARSED_REQUIREMENT_OK", message="parsed requirement")


@app.get("/api/tasks/{task_id}/retrieved-context", response_model=ApiResponse)
def get_retrieved_context(task_id: str):
    task = _must_get_task(task_id)
    result = _ensure_pipeline(task)
    return _success_response(result.get("retrieved_context", []), code="RETRIEVED_CONTEXT_OK", message="retrieved context")


@app.post("/api/tasks/{task_id}/scenarios/generate", response_model=ApiResponse)
def generate_scenarios(task_id: str):
    task = _must_get_task(task_id)
    result = _ensure_pipeline(task)
    task.status = TaskStatus.GENERATED.value
    registry.save(task)
    return _success_response({
        "task_id": task_id,
        "scenario_count": len(result.get("scenarios", [])),
        "scenarios": result.get("scenarios", []),
    }, code="SCENARIOS_READY", message="scenarios generated")


@app.get("/api/tasks/{task_id}/scenarios", response_model=ApiResponse)
def get_scenarios(task_id: str):
    task = _must_get_task(task_id)
    result = _ensure_pipeline(task)
    return _success_response(result.get("scenarios", []), code="SCENARIOS_OK", message="scenarios fetched")


@app.get("/api/tasks/{task_id}/dsl", response_model=ApiResponse)
def get_dsl(task_id: str):
    task = _must_get_task(task_id)
    result = _ensure_pipeline(task)
    return _success_response(result.get("test_case_dsl", {}), code="DSL_OK", message="dsl fetched")


@app.get("/api/tasks/{task_id}/feature", response_model=ApiResponse)
def get_feature(task_id: str):
    task = _must_get_task(task_id)
    result = _ensure_pipeline(task)
    return _success_response({"feature_text": result.get("feature_text", "")}, code="FEATURE_OK", message="feature fetched")


@app.post("/api/tasks/{task_id}/preflight-check", response_model=ApiResponse)
def preflight_check(task_id: str, payload: PreflightCheckRequest | None = None):
    task = _must_get_task(task_id)
    body = payload or PreflightCheckRequest()
    selected_environment = body.environment or task.environment or "test"
    environment_config = _resolve_environment_config(task, selected_environment)
    base = ""
    if environment_config and environment_config.base_url:
        base = str(environment_config.base_url).strip()
    if not base:
        base = _derive_fallback_base_url(task)
    data = run_preflight_check(
        task_id=task_id,
        base_url=base,
        default_headers=(environment_config.default_headers if environment_config else {}) or {},
        auth=(environment_config.auth if environment_config else {}) or {},
        latency_threshold_ms=body.latency_threshold_ms,
        checks=body.checks,
    )
    return _success_response(data, code="PREFLIGHT_OK", message="preflight complete")


@app.post("/api/tasks/{task_id}/execute", response_model=ApiResponse)
def execute_task(task_id: str, payload: ExecuteTaskRequest):
    task = _must_get_task(task_id)
    result = _ensure_pipeline(task)
    selected_environment = payload.environment or task.environment or "test"
    environment_config = _resolve_environment_config(task, selected_environment)
    dsl = _inject_environment_into_dsl(
        dict(result.get("test_case_dsl", {})),
        selected_environment,
        environment_config,
        fallback_base_url=_derive_fallback_base_url(task),
    )
    resolved_base_url = str((dsl.get("metadata") or {}).get("execution", {}).get("base_url", "")).strip()
    if payload.execution_mode == "api" and not resolved_base_url:
        raise HTTPException(
            status_code=400,
            detail=(
                "Missing execution base_url. Configure environment.base_url or task.target_system; "
                "request-based fallback is not supported."
            ),
        )
    dsl["execution_mode"] = payload.execution_mode
    if payload.async_mode:
        with _RUNNING_EXECUTION_LOCK:
            running_future = _RUNNING_EXECUTION_FUTURES.get(task_id)
            if running_future and not running_future.done():
                running_payload = task.execution_result or _build_running_execution_result(
                    task_id,
                    payload.execution_mode,
                    selected_environment,
                )
                return _success_response(
                    running_payload,
                    code="TASK_EXECUTION_ALREADY_RUNNING",
                    message="task execution already running",
                )
        running_payload = _build_running_execution_result(task_id, payload.execution_mode, selected_environment)
        task.execution_result = running_payload
        task.environment = selected_environment
        task.status = "running"
        _persist_task_runtime(task)
        future = _ASYNC_EXECUTOR.submit(
            _run_async_execution_job,
            task_id,
            dsl,
            payload.execution_mode,
            selected_environment,
            environment_config,
        )
        with _RUNNING_EXECUTION_LOCK:
            _RUNNING_EXECUTION_FUTURES[task_id] = future
        return _success_response(running_payload, code="TASK_EXECUTION_STARTED", message="task execution started")

    execution_result = _run_dsl_with_timeout(dsl, payload.execution_mode)
    execution_result = _apply_execution_metadata(
        execution_result,
        selected_environment=selected_environment,
        execution_mode=payload.execution_mode,
        environment_config=environment_config,
        dsl=dsl,
    )
    task.execution_result = execution_result
    task.environment = selected_environment
    task.status = execution_result.get("status", "executed")
    result["analysis_report"] = _build_task_analysis_report(task)
    _record_execution_history(task, execution_result)
    return _success_response(execution_result, code="TASK_EXECUTED", message="task executed")


@app.get("/api/tasks/{task_id}/execution", response_model=ApiResponse)
def get_execution(task_id: str):
    task = _must_get_task(task_id)
    if task.execution_result is None:
        payload = {"task_id": task_id, "executor": None, "status": "not_started", "scenario_results": [], "metrics": {}, "logs": []}
        return _success_response(payload, code="EXECUTION_OK", message="execution fetched")
    return _success_response(task.execution_result, code="EXECUTION_OK", message="execution fetched")


@app.get("/api/tasks/{task_id}/execution/stream")
async def stream_execution(
    task_id: str,
    interval_ms: int = Query(800, ge=200, le=5000),
    timeout_s: int = Query(60, ge=5, le=600),
):
    _must_get_task(task_id)

    async def _event_generator():
        started_at = datetime.now(timezone.utc)
        last_status: str | None = None
        last_log_index = 0

        yield _encode_sse({"task_id": task_id, "connected_at": _utc_now_iso()}, event="connected")

        while True:
            task = _must_get_task(task_id)
            execution = task.execution_result or {}
            status = str(execution.get("status") or "")

            if status != last_status:
                yield _encode_sse({"task_id": task_id, "status": status or "waiting"}, event="status")
                last_status = status

            logs = execution.get("logs")
            log_entries = logs if isinstance(logs, list) else []
            if last_log_index < len(log_entries):
                for entry in log_entries[last_log_index:]:
                    event_name = "message"
                    if isinstance(entry, dict):
                        raw_event = str(entry.get("event") or "").strip()
                        if raw_event:
                            event_name = raw_event
                    yield _encode_sse(entry, event=event_name)
                last_log_index = len(log_entries)

            if status in {"passed", "failed", "stopped"}:
                yield _encode_sse(
                    {"task_id": task_id, "status": status, "finished_at": _utc_now_iso()},
                    event="execution_done",
                )
                break

            elapsed_s = (datetime.now(timezone.utc) - started_at).total_seconds()
            if elapsed_s >= timeout_s:
                yield _encode_sse(
                    {"task_id": task_id, "status": status or "waiting", "reason": "stream_timeout"},
                    event="execution_done",
                )
                break

            yield _encode_sse({"task_id": task_id, "at": _utc_now_iso()}, event="heartbeat")
            await asyncio.sleep(interval_ms / 1000)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/tasks/{task_id}/execution/explanations", response_model=ApiResponse)
def get_execution_explanations(task_id: str, top_n: int = Query(5, ge=1, le=20)):
    task = _must_get_task(task_id)
    if task.execution_result is None:
        raise HTTPException(status_code=404, detail="No execution result; run execute first")
    er = dict(task.execution_result)
    er.setdefault("task_id", task_id)
    data = build_execution_explanations(er, top_n=top_n)
    return _success_response(data, code="EXECUTION_EXPLANATIONS_OK", message="execution explanations")


@app.get("/api/tasks/{task_id}/regression-diff", response_model=ApiResponse)
def get_regression_diff(
    task_id: str,
    base_execution_id: str | None = None,
    target_execution_id: str | None = None,
):
    _must_get_task(task_id)
    items = registry.list_execution_history(task_id=task_id)
    items = [item for item in items if item.get("task_id") == task_id]
    items.sort(key=lambda item: str(item.get("executed_at") or ""))

    if len(items) < 2:
        return _error_response(
            code="REGRESSION_DIFF_NOT_READY",
            message="insufficient execution history for regression diff",
            detail={"task_id": task_id, "compared_runs": len(items)},
            status_code=409,
        )

    indexed = {str(item.get("executed_at") or ""): item for item in items}
    if base_execution_id and target_execution_id:
        base_item = indexed.get(base_execution_id)
        target_item = indexed.get(target_execution_id)
        if base_item is None or target_item is None:
            return _error_response(
                code="BAD_REQUEST",
                message="base_execution_id or target_execution_id not found",
                detail={"task_id": task_id, "base_execution_id": base_execution_id, "target_execution_id": target_execution_id},
                status_code=400,
            )
    else:
        target_item = items[-1]
        base_item = items[-2]

    payload = _build_regression_diff(task_id, base_item, target_item)
    return _success_response(payload, code="REGRESSION_DIFF_OK", message="regression diff")


@app.get("/api/tasks/{task_id}/execution/logs", response_model=ApiResponse)
def get_execution_logs(task_id: str):
    task = _must_get_task(task_id)
    payload = [] if task.execution_result is None else task.execution_result.get("logs", [])
    return _success_response(payload, code="EXECUTION_LOGS_OK", message="execution logs")


@app.post("/api/tasks/{task_id}/execution/stop", response_model=ApiResponse)
def stop_execution(task_id: str):
    task = _must_get_task(task_id)
    if task.execution_result is None or task.execution_result.get("status") != "running":
        payload = _model_to_dict(StopExecutionResponse(task_id=task_id, stopped=False, message="No running execution to stop"))
        return _success_response(payload, code="EXECUTION_STOP_SKIPPED", message="no running execution")
    cancel_requested = False
    with _RUNNING_EXECUTION_LOCK:
        future = _RUNNING_EXECUTION_FUTURES.get(task_id)
    if future is not None:
        cancel_requested = future.cancel()
    task.execution_result["status"] = "stopped"
    logs = list(task.execution_result.get("logs") or [])
    logs.append(
        {
            "time": _utc_now_iso(),
            "level": "WARN",
            "message": "Stop requested by user" + (" (worker cancelled)" if cancel_requested else ""),
        }
    )
    task.execution_result["logs"] = logs
    task.status = TaskStatus.STOPPED.value
    _persist_task_runtime(task)
    payload = _model_to_dict(StopExecutionResponse(task_id=task_id, stopped=True, message="Execution stopped"))
    return _success_response(payload, code="EXECUTION_STOPPED", message="execution stopped")


@app.get("/api/tasks/{task_id}/validation-report", response_model=ApiResponse)
def get_validation_report(task_id: str):
    task = _must_get_task(task_id)
    result = _ensure_pipeline(task)
    return _success_response(result.get("validation_report", {}), code="VALIDATION_REPORT_OK", message="validation report")


@app.get("/api/tasks/{task_id}/analysis-report", response_model=ApiResponse)
def get_analysis_report(task_id: str):
    task = _must_get_task(task_id)
    return _success_response(_build_task_analysis_report(task), code="ANALYSIS_REPORT_OK", message="analysis report")


@app.get("/api/tasks/{task_id}/dashboard", response_model=ApiResponse)
def get_dashboard(task_id: str):
    task = _must_get_task(task_id)
    result = _ensure_pipeline(task)
    execution = task.execution_result or {"status": "not_started", "metrics": {}, "logs": []}
    analysis_report = _build_task_analysis_report(task, persist_registry=False)
    return _success_response({
        "task": task.to_summary(),
        "analysis_report": analysis_report,
        "dashboard": analysis_report.get("dashboard", {}),
        "dashboard_summary": analysis_report.get("dashboard_summary", analysis_report.get("dashboard", {}).get("summary", {})),
        "summary": analysis_report.get("summary", {}),
        "task_summary": analysis_report.get("task_summary", {}),
        "execution_overview": analysis_report.get("execution_overview", {}),
        "performance_stats": analysis_report.get("performance_stats", {}),
        "assertion_stats": analysis_report.get("assertion_stats", {}),
        "step_assertion_quality": analysis_report.get("step_assertion_quality", []),
        "context_stats": analysis_report.get("context_stats", {}),
        "task_summary_text": analysis_report.get("task_summary_text", ""),
        "findings": analysis_report.get("findings", []),
        "chart_data": analysis_report.get("chart_data", {}),
        "report_sections": analysis_report.get("report_sections", []),
        "failed_steps": analysis_report.get("failed_steps", []),
        "failure_reasons": analysis_report.get("failure_reasons", []),
        "validation_report": result.get("validation_report", {}),
        "execution": execution,
        "dsl": result.get("test_case_dsl", {}),
    }, code="DASHBOARD_OK", message="dashboard data")


@app.get("/api/tasks/{task_id}/artifacts", response_model=ApiResponse)
def get_artifacts(
    task_id: str,
    shallow: bool = Query(False, description="If true, return only artifact types (no embedded content)."),
):
    task = _must_get_task(task_id)
    result = _ensure_pipeline(task)
    artifacts: list[dict[str, Any]] = []
    for artifact_type, resolver in DEFAULT_ARTIFACT_TYPES.items():
        if shallow:
            artifacts.append({"type": artifact_type})
        else:
            artifacts.append({"type": artifact_type, "content": resolver(result)})
    return _success_response({"task_id": task_id, "artifacts": artifacts}, code="ARTIFACTS_OK", message="artifacts fetched")


@app.get("/api/tasks/{task_id}/artifacts/{artifact_type}", response_model=ApiResponse)
def get_artifact_content(task_id: str, artifact_type: str):
    task = _must_get_task(task_id)
    result = _ensure_pipeline(task)
    resolver = DEFAULT_ARTIFACT_TYPES.get(artifact_type)
    if resolver is None:
        raise HTTPException(status_code=404, detail=f"Unknown artifact type: {artifact_type}")
    return _success_response(
        {"task_id": task_id, "type": artifact_type, "content": resolver(result)},
        code="ARTIFACT_OK",
        message="artifact fetched",
    )


@app.get("/api/history/tasks", response_model=ApiResponse)
def get_history_tasks(
    status: TaskStatus | None = None,
    keyword: str | None = None,
    environment: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    items = registry.list(status=status.value if status else None, keyword=keyword, include_archived=True)
    if environment:
        items = [item for item in items if item.environment == environment]
    items = _filter_tasks_by_time(items, start_time, end_time)
    payload = _paginate([item.to_summary() for item in items], page, page_size)
    return _success_response(payload, code="TASK_HISTORY_OK", message="task history")


@app.get("/api/environments", response_model=ApiResponse)
def list_environments():
    payload = [item.to_dict() for item in registry.list_environments()]
    return _success_response(payload, code="ENVIRONMENTS_OK", message="environments listed")


@app.post("/api/environments", response_model=ApiResponse)
def create_or_update_environment(payload: UpsertEnvironmentRequest):
    config = EnvironmentConfig(
        name=payload.name,
        base_url=payload.base_url,
        default_headers=payload.default_headers,
        auth=payload.auth,
        cookies=payload.cookies,
        description=payload.description,
    )
    registry.save_environment(config)
    return _success_response(config.to_dict(), code="ENVIRONMENT_SAVED", message="environment saved", status_code=201)


@app.get("/api/environments/{environment_name}", response_model=ApiResponse)
def get_environment(environment_name: str):
    config = registry.get_environment(environment_name)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Environment not found: {environment_name}")
    return _success_response(config.to_dict(), code="ENVIRONMENT_OK", message="environment fetched")


@app.put("/api/environments/{environment_name}", response_model=ApiResponse)
def update_environment(environment_name: str, payload: UpsertEnvironmentRequest):
    config = EnvironmentConfig(
        name=environment_name,
        base_url=payload.base_url,
        default_headers=payload.default_headers,
        auth=payload.auth,
        cookies=payload.cookies,
        description=payload.description,
    )
    registry.save_environment(config)
    return _success_response(config.to_dict(), code="ENVIRONMENT_UPDATED", message="environment updated")


@app.delete("/api/environments/{environment_name}", response_model=ApiResponse)
def delete_environment(environment_name: str):
    if not registry.delete_environment(environment_name):
        raise HTTPException(status_code=404, detail=f"Environment not found: {environment_name}")
    return _success_response({"name": environment_name, "deleted": True}, code="ENVIRONMENT_DELETED", message="environment deleted")


@app.get("/api/history/executions", response_model=ApiResponse)
def get_execution_history(
    task_id: str | None = None,
    status: TaskStatus | None = None,
    keyword: str | None = None,
    environment: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    items = registry.list_execution_history(
        task_id=task_id,
        status=status.value if status else None,
        keyword=keyword,
        environment=environment,
    )
    items = _filter_dict_items_by_time(items, "executed_at", start_time, end_time)
    payload = _paginate(items, page, page_size)
    return _success_response(payload, code="EXECUTION_HISTORY_OK", message="execution history")
