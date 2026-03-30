"""FastAPI application for the platform task-center."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from execution_engine_core import run_dsl
from platform_shared.models import EnvironmentConfig, TaskContext, ValidationReport

from .api_models import (
    ApiResponse,
    CreateTaskRequest,
    ErrorResponse,
    ExecuteTaskRequest,
    HealthInfo,
    StopExecutionResponse,
    TaskListResponse,
    TaskStatus,
    UpsertEnvironmentRequest,
    VersionInfo,
)
from .artifact_manager import ensure_task_subdirs, write_json_artifact
from .input_handler import normalize_input
from .pipeline import run_analysis_pipeline
from .registry import DEFAULT_ARTIFACT_TYPES, TaskRegistry
from result_analysis import build_analysis_report


APP_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_ROOT = str(APP_ROOT / "api_artifacts")
APP_VERSION = "0.2.0"
registry = TaskRegistry(ARTIFACTS_ROOT)
app = FastAPI(title="Platform Task Center API", version=APP_VERSION)


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
    metadata["execution"] = execution
    payload["metadata"] = metadata
    return payload


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


def _ensure_pipeline(task) -> dict[str, Any]:
    if task.pipeline_result is not None:
        return task.pipeline_result
    result = run_analysis_pipeline(
        task_name=task.task_name,
        requirement_text=task.requirement_text,
        source_type=task.source_type,
        source_path=task.source_path,
        artifacts_base_dir=registry.artifacts_root,
    )
    task.pipeline_result = result
    task.status = "parsed"
    task.task_context = result.get("task_context", task.task_context)
    task.artifact_dir = _find_latest_artifact_dir(task.task_name)
    registry.save(task)
    return result


def _find_latest_artifact_dir(task_name: str) -> str | None:
    root = Path(registry.artifacts_root)
    matches = sorted(root.glob(f"{task_name}_*"), key=lambda path: path.stat().st_mtime, reverse=True)
    return str(matches[0]) if matches else None


def _build_task_analysis_report(task) -> dict[str, Any]:
    result = _ensure_pipeline(task)
    report = build_analysis_report(
        task_context=TaskContext(**result["task_context"]),
        validation_report=ValidationReport(**result["validation_report"]),
        scenario_count=len(result.get("scenarios", [])),
        execution_result=task.execution_result,
        test_case_dsl=result.get("test_case_dsl"),
    )
    result["analysis_report"] = report
    _persist_task_runtime(task)
    return report


def _persist_task_runtime(task) -> None:
    if not task.artifact_dir:
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
    normalized = normalize_input(
        task_name=payload.task_name,
        requirement_text=payload.requirement_text,
        source_type=payload.source_type,
        source_path=payload.source_path,
    )
    context = TaskContext(**normalized["task_context"]).to_dict()
    record = registry.create_task(
        task_id=context["task_id"],
        task_name=payload.task_name,
        source_type=payload.source_type,
        requirement_text=payload.requirement_text,
        source_path=payload.source_path,
        target_system=payload.target_system,
        environment=payload.environment,
        task_context=context,
    )
    registry.save(record)
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


@app.get("/api/tasks/{task_id}", response_model=ApiResponse)
def get_task(task_id: str):
    task = _must_get_task(task_id)
    return _success_response({
        **task.to_summary(),
        "task_context": task.task_context,
        "artifact_dir": task.artifact_dir,
    }, code="TASK_DETAIL_OK", message="task detail")


@app.delete("/api/tasks/{task_id}", response_model=ApiResponse)
def delete_task(task_id: str):
    if not registry.archive(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return _success_response({"task_id": task_id, "archived": True}, code="TASK_ARCHIVED", message="task archived")


@app.post("/api/tasks/{task_id}/parse", response_model=ApiResponse)
def parse_task(task_id: str):
    task = _must_get_task(task_id)
    result = _ensure_pipeline(task)
    return _success_response({
        "task_id": task_id,
        "status": task.status,
        "parsed_requirement": result.get("parsed_requirement"),
    }, code="TASK_PARSED", message="task parsed")


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
    )
    dsl["execution_mode"] = payload.execution_mode
    execution_result = run_dsl(dsl, execution_mode=payload.execution_mode)
    execution_metadata = dict(execution_result.get("metadata") or {})
    execution_metadata["execution"] = {
        "environment": selected_environment,
        "execution_mode": payload.execution_mode,
        "base_url": (environment_config.base_url if environment_config else ""),
        "default_headers": (environment_config.default_headers if environment_config else {}),
        "auth": (environment_config.auth if environment_config else {}),
        "cookies": (environment_config.cookies if environment_config else {}),
    }
    execution_metadata["executed_at"] = _utc_now_iso()
    execution_result["metadata"] = execution_metadata
    task.execution_result = execution_result
    task.environment = selected_environment
    task.status = execution_result.get("status", "executed")
    result["analysis_report"] = _build_task_analysis_report(task)
    _persist_task_runtime(task)
    _record_execution_history(task, execution_result)
    return _success_response(execution_result, code="TASK_EXECUTED", message="task executed")


@app.get("/api/tasks/{task_id}/execution", response_model=ApiResponse)
def get_execution(task_id: str):
    task = _must_get_task(task_id)
    if task.execution_result is None:
        payload = {"task_id": task_id, "executor": None, "status": "not_started", "scenario_results": [], "metrics": {}, "logs": []}
        return _success_response(payload, code="EXECUTION_OK", message="execution fetched")
    return _success_response(task.execution_result, code="EXECUTION_OK", message="execution fetched")


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
    task.execution_result["status"] = "stopped"
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
    analysis_report = _build_task_analysis_report(task)
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
def get_artifacts(task_id: str):
    task = _must_get_task(task_id)
    result = _ensure_pipeline(task)
    artifacts = []
    for artifact_type, resolver in DEFAULT_ARTIFACT_TYPES.items():
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
