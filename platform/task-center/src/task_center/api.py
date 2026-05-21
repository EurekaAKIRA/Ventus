"""FastAPI application for the platform task-center."""

from __future__ import annotations

import concurrent.futures
import asyncio
import hashlib
import inspect
import os
import re
import uuid
from dataclasses import replace
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode, urljoin, urlparse

import requests
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles
from pydantic import ValidationError

from execution_engine_core import run_dsl
from platform_shared.models import EnvironmentConfig, TaskContext, ValidationReport

from .auth_service import (
    build_access_token,
    build_refresh_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    load_auth_config,
    verify_password,
    verify_refresh_token,
)
from .api_models import (
    AddProjectMemberRequest,
    AnalysisParseRequest,
    ApiResponse,
    CreateDefectRequest,
    CreateInterfaceAssetRequest,
    CreateProjectRequest,
    CreateTaskRequest,
    CreateTestCaseAssetRequest,
    CreateTestSuiteAssetRequest,
    DebugInterfaceAssetRequest,
    ExecuteTestCaseAssetRequest,
    ExecuteTestSuiteAssetRequest,
    TaskDraftAgentRequest,
    TaskAgentChatRequest,
    ErrorResponse,
    ExecuteTaskRequest,
    HealthInfo,
    ImportInterfaceAssetsFromTaskRequest,
    ImportOpenApiInterfaceAssetsRequest,
    ImportTestCaseAssetsFromTaskRequest,
    LoginRequest,
    ParseMetadata,
    PreflightCheckRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TaskParseRequest,
    StopExecutionResponse,
    TaskListResponse,
    TaskStatus,
    UpdateDefectRequest,
    UpdateInterfaceAssetRequest,
    UpdateTestCaseAssetRequest,
    UpdateTestSuiteAssetRequest,
    UpsertEnvironmentRequest,
    UpdateProfileRequest,
    VersionInfo,
)
from .artifact_manager import ensure_task_subdirs, write_json_artifact
from .execution_explanations import build_execution_explanations
from .input_handler import normalize_input
from .preflight import run_preflight_check
from .pipeline import run_analysis_pipeline
from .registry import DEFAULT_ARTIFACT_TYPES, TaskRegistry
from .runtime_store import build_runtime_state_store
from .secure_config import mask_environment_config, merge_masked_environment_config
from .session_store import build_session_state_store
from requirement_analysis import AnalysisParseOptions, parse_requirement_bundle
from requirement_analysis.knowledge_index import build_index as build_requirement_knowledge_index
from requirement_analysis.knowledge_library import load_curated_knowledge_chunks
from requirement_analysis.retriever import retrieve_relevant_chunks as retrieve_requirement_knowledge_chunks
from requirement_analysis.service import build_retrieval_queries as build_requirement_retrieval_queries
from result_analysis import build_analysis_report


APP_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_ROOT = str(Path(os.getenv("TASK_CENTER_ARTIFACTS_ROOT", str(APP_ROOT / "api_artifacts"))))
PUBLIC_STATIC_ROOT = Path(ARTIFACTS_ROOT) / "public"
AVATAR_UPLOAD_ROOT = PUBLIC_STATIC_ROOT / "avatars"
APP_VERSION = "0.2.0"
VALID_DEFECT_STATUSES = {"open", "in_progress", "resolved", "closed"}
VALID_DEFECT_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_INTERFACE_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
VALID_INTERFACE_STATUSES = {"active", "deprecated", "draft"}
VALID_TEST_CASE_STATUSES = {"active", "draft", "disabled", "archived"}
VALID_TEST_CASE_PRIORITIES = {"P0", "P1", "P2", "P3"}
VALID_TEST_SUITE_STATUSES = {"active", "draft", "disabled", "archived"}
AVATAR_ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
AVATAR_MAX_BYTES = 2 * 1024 * 1024
EXECUTION_TIMEOUT_SECONDS = 300
_EXECUTION_MAX_WORKERS = max(1, int(str(os.getenv("TASK_CENTER_EXECUTION_WORKERS", "4")).strip() or "4"))
_ANALYSIS_MAX_WORKERS = max(1, int(str(os.getenv("TASK_CENTER_ANALYSIS_WORKERS", "4")).strip() or "4"))
registry = TaskRegistry(ARTIFACTS_ROOT)
runtime_state_store = build_runtime_state_store()
session_state_store = build_session_state_store()
auth_config = load_auth_config()
app = FastAPI(title="Platform Task Center API", version=APP_VERSION)
AVATAR_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(PUBLIC_STATIC_ROOT)), name="static")
_EXECUTION_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=_EXECUTION_MAX_WORKERS)
_ANALYSIS_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=_ANALYSIS_MAX_WORKERS)
_RUNNING_EXECUTION_FUTURES: dict[str, concurrent.futures.Future] = {}
_RUNNING_EXECUTION_LOCK = threading.Lock()
_RUNNING_ANALYSIS_FUTURES: dict[str, concurrent.futures.Future] = {}
_RUNNING_ANALYSIS_LOCK = threading.Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=512, compresslevel=6)


def _ensure_default_admin_account() -> None:
    store = registry.db_store
    if store is None:
        return
    enabled = str(os.getenv("TASK_CENTER_BOOTSTRAP_ADMIN_ENABLED", "true")).strip().lower()
    if enabled in {"0", "false", "off", "no"}:
        return

    username = str(os.getenv("TASK_CENTER_DEFAULT_ADMIN_USERNAME", "admin")).strip() or "admin"
    password = str(os.getenv("TASK_CENTER_DEFAULT_ADMIN_PASSWORD", "123456"))
    email = str(os.getenv("TASK_CENTER_DEFAULT_ADMIN_EMAIL", "admin@local.test")).strip() or None
    display_name = str(os.getenv("TASK_CENTER_DEFAULT_ADMIN_DISPLAY_NAME", "Administrator")).strip() or username

    existing = store.get_user_by_username(username)
    if existing is not None:
        if existing.get("platform_role") != "admin":
            existing = store.set_user_platform_role(user_id=str(existing["id"]), platform_role="admin")
        store.ensure_default_workspace_and_project(user_id=str(existing["id"]), username=str(existing["username"]))
        return

    created = store.create_user(
        username=username,
        email=email,
        display_name=display_name,
        password_hash=hash_password(password),
        platform_role="admin",
    )
    store.ensure_default_workspace_and_project(user_id=str(created["id"]), username=str(created["username"]))


_ensure_default_admin_account()


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


def _must_get_visible_task(task_id: str, current_user: dict[str, Any] | None):
    task = _must_get_task(task_id)
    _ensure_task_visible_to_user(task, current_user)
    return task


def _db_store_or_503():
    store = registry.db_store
    if store is None:
        raise HTTPException(status_code=503, detail="DB persistence backend is required for user APIs")
    return store


def _extract_bearer_token(authorization: str | None) -> str | None:
    raw = str(authorization or "").strip()
    if not raw:
        return None
    prefix = "bearer "
    if raw.lower().startswith(prefix):
        return raw[len(prefix):].strip()
    return None


def _request_ip(request: Request) -> str | None:
    client = request.client
    return client.host if client else None


def _append_audit_log_safe(
    *,
    user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    detail_json: dict[str, Any] | list[Any] | None = None,
    ip_address: str | None = None,
) -> None:
    store = registry.db_store
    if store is None:
        return
    try:
        store.append_audit_log(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail_json=detail_json,
            ip_address=ip_address,
        )
    except Exception:
        return


def _platform_admin_usernames() -> set[str]:
    default_admin = str(os.getenv("TASK_CENTER_DEFAULT_ADMIN_USERNAME", "admin")).strip() or "admin"
    configured = str(os.getenv("TASK_CENTER_PLATFORM_ADMIN_USERNAMES", "")).strip()
    names = {default_admin}
    if configured:
        names.update(item.strip() for item in configured.split(",") if item.strip())
    return names


def _is_platform_admin_user(user: dict[str, Any] | None) -> bool:
    if not user:
        return False
    if str(user.get("platform_role") or "").strip().lower() == "admin":
        return True
    return str(user.get("username") or "").strip() in _platform_admin_usernames()


def _decorate_user_payload(user: dict[str, Any] | None) -> dict[str, Any] | None:
    if user is None:
        return None
    payload = dict(user)
    is_admin = _is_platform_admin_user(payload)
    payload["is_platform_admin"] = is_admin
    payload["platform_role"] = "admin" if is_admin else str(payload.get("platform_role") or "user")
    return payload


def _safe_avatar_extension(content_type: str) -> str:
    normalized = content_type.split(";")[0].strip().lower()
    if normalized not in AVATAR_ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Avatar must be a jpg, png, webp, or gif image")
    return AVATAR_ALLOWED_CONTENT_TYPES[normalized]


def _current_user_project_ids(user_id: str) -> list[str]:
    store = _db_store_or_503()
    return [item["id"] for item in store.list_projects_for_user(user_id)]


def _ensure_task_visible_to_user(task, current_user: dict[str, Any] | None) -> None:
    if current_user is None:
        return
    current_user_id = str(current_user["user"]["id"])
    if task.created_by and str(task.created_by) == current_user_id:
        return
    if task.project_id:
        if task.project_id in _current_user_project_ids(current_user_id):
            return
    raise HTTPException(status_code=403, detail="You do not have access to this task")


def _require_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer access token")
    try:
        claims = decode_access_token(token, auth_config)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid access token: {exc}") from exc
    jti = str(claims.get("jti") or "")
    if jti and session_state_store.is_token_jti_revoked(jti):
        raise HTTPException(status_code=401, detail="Access token has been revoked")
    store = _db_store_or_503()
    user = store.get_user_by_id(str(claims.get("sub") or ""))
    if user is None or user.get("status") != "active":
        raise HTTPException(status_code=401, detail="User not found or inactive")
    user = _decorate_user_payload(user)
    session_id = str(claims.get("session_id") or "")
    if session_id:
        cached_session = session_state_store.get_session(session_id)
        if cached_session is None:
            db_session = store.get_user_session_by_id(session_id)
            if db_session is None or db_session.get("revoked_at"):
                raise HTTPException(status_code=401, detail="Session expired or not found")
            expires_at = _parse_iso_timestamp(str(db_session["expires_at"]))
            if expires_at is None:
                raise HTTPException(status_code=401, detail="Session expired or not found")
            ttl_seconds = int((expires_at - datetime.now(timezone.utc)).total_seconds())
            if ttl_seconds <= 0:
                raise HTTPException(status_code=401, detail="Session expired or not found")
            session_state_store.set_session(
                session_id,
                {
                    "user_id": str(user["id"]),
                    "username": str(user["username"]),
                    "expires_at": db_session["expires_at"],
                },
                ttl_seconds=ttl_seconds,
            )
    return {"user": user, "claims": claims, "access_token": token}


def _optional_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any] | None:
    token = _extract_bearer_token(authorization)
    if not token:
        return None
    return _require_current_user(authorization)


def _ensure_project_access(project_id: str, current_user: dict[str, Any]) -> dict[str, Any]:
    store = _db_store_or_503()
    project = store.get_project_for_user(project_id=project_id, user_id=str(current_user["user"]["id"]))
    if project is None:
        raise HTTPException(status_code=403, detail="You do not have access to this project")
    return project


def _require_platform_admin(current_user: dict[str, Any] = Depends(_require_current_user)) -> dict[str, Any]:
    if not _is_platform_admin_user(current_user.get("user")):
        raise HTTPException(status_code=403, detail="Platform administrator permission is required")
    return current_user


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


def _derive_task_name_hint(*, task_name: str, source_path: str | None, requirement_text: str) -> str:
    explicit = str(task_name or "").strip()
    if explicit:
        return explicit

    raw_source = str(source_path or "").strip()
    if raw_source:
        stem = Path(raw_source).stem.strip()
        if stem:
            return stem

    text = str(requirement_text or "")
    for line in text.splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        if normalized.startswith("#"):
            candidate = normalized.lstrip("#").strip(" -:：\t")
            if candidate:
                return candidate[:80]
        if len(normalized) <= 80:
            return normalized.strip(" -:：\t")[:80]
    return ""


def _extract_base_url_hint(requirement_text: str, fallback_target_system: str | None = None) -> str:
    fallback = str(fallback_target_system or "").strip()
    if fallback:
        return fallback.rstrip("/")

    content = str(requirement_text or "").strip()
    if not content:
        return ""

    labeled_patterns = [
        r"(?:base\s*url|baseurl|服务地址|服务域名|接口地址|接口域名|请求地址|环境地址)\s*[:：|]\s*`?(https?:\/\/[^\s)`>\"']+)`?",
        r"^\s*[-*]?\s*(?:默认\s*)?(?:base\s*url|baseurl|服务地址|服务域名|接口地址|接口域名|请求地址|环境地址)\s+`?(https?:\/\/[^\s)`>\"']+)`?\s*$",
    ]
    for raw_pattern in labeled_patterns:
        matched = re.search(raw_pattern, content, flags=re.IGNORECASE | re.MULTILINE)
        if matched and matched.group(1):
            return matched.group(1).rstrip("/")

    absolute_urls = [
        item.group(0).rstrip("/")
        for item in re.finditer(r"https?:\/\/[^\s)`>\"']+", content, flags=re.IGNORECASE | re.MULTILINE)
    ]
    if len(absolute_urls) == 1:
        return absolute_urls[0]
    return ""


def _normalize_base_url_for_match(raw_url: str | None) -> str:
    value = str(raw_url or "").strip().rstrip("/")
    if not value:
        return ""
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return value
    host = (parsed.hostname or parsed.netloc).lower()
    port = parsed.port
    include_port = port is not None and not (
        (parsed.scheme.lower() == "http" and port == 80)
        or (parsed.scheme.lower() == "https" and port == 443)
    )
    netloc = f"{host}:{port}" if include_port else host
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme.lower()}://{netloc}{path}"


def _extract_url_host(raw_url: str | None) -> str:
    normalized = _normalize_base_url_for_match(raw_url)
    if not normalized:
        return ""
    parsed = urlparse(normalized)
    return (parsed.hostname or "").lower()


def _normalize_endpoint_token(raw_value: str) -> str:
    token = str(raw_value or "").strip().strip("`").rstrip(".,;)")
    if not token:
        return ""
    lowered = token.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        parsed = urlparse(token)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        return path
    return token


def _extract_requirement_endpoint_signatures(requirement_text: str) -> list[tuple[str, str]]:
    text = str(requirement_text or "")
    pattern = re.compile(r"`?(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+([^\s`]+)`?", flags=re.IGNORECASE)
    seen: set[tuple[str, str]] = set()
    endpoints: list[tuple[str, str]] = []
    for matched in pattern.finditer(text):
        method = str(matched.group(1) or "").upper()
        raw_path = _normalize_endpoint_token(str(matched.group(2) or ""))
        if not raw_path or not (raw_path.startswith("/") or raw_path.startswith("http")):
            continue
        signature = (method, raw_path)
        if signature in seen:
            continue
        seen.add(signature)
        endpoints.append(signature)
    return endpoints


def _infer_requirement_resource_key(path: str) -> str:
    raw_path = _normalize_endpoint_token(path)
    parsed = urlparse(raw_path)
    normalized_path = parsed.path or raw_path
    segments = [segment for segment in normalized_path.split("/") if segment]
    for segment in segments:
        lowered = segment.lower()
        if lowered in {"api", "internal", "openapi"}:
            continue
        if re.fullmatch(r"v\d+", lowered):
            continue
        if segment.isdigit():
            continue
        if (segment.startswith("{") and segment.endswith("}")) or segment.startswith(":") or (segment.startswith("<") and segment.endswith(">")):
            continue
        return lowered
    return ""


def _endpoint_requires_live_resource(method: str, path: str) -> bool:
    upper_method = str(method or "").upper()
    if upper_method in {"PUT", "PATCH", "DELETE"}:
        return True
    normalized_path = _normalize_endpoint_token(path)
    if upper_method != "GET":
        return False
    return bool(
        re.search(r"/(?:\{[^/]+\}|:[^/]+|<[^/]+>|[^/]+Id)(?:$|[/?])", normalized_path, flags=re.IGNORECASE)
        or re.search(r"/\d+(?:$|[/?])", normalized_path)
    )


def _extract_requirement_auth_hints(requirement_text: str) -> list[str]:
    text = str(requirement_text or "")
    keyword_map = [
        (r"\bbearer\b|authorization", "Bearer"),
        (r"\bx-api-key\b|api[-_\s]?key", "API Key"),
        (r"\bbasic\b|\bbasic auth\b", "Basic"),
        (r"\bcookie\b|session", "Cookie"),
        (r"\bjwt\b|\btoken\b", "Token"),
        (r"登录|鉴权|认证", "登录态"),
    ]
    hints: list[str] = []
    for pattern, label in keyword_map:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hints.append(label)
    return _dedupe_strings(hints)


def _merge_requirement_text_with_document_action(raw_text: str, action: dict[str, Any]) -> str:
    current_text = str(raw_text or "")
    content = str(action.get("content") or "")
    if not content.strip():
        return current_text
    mode = str(action.get("mode") or "").strip().lower()
    if mode == "prepend":
        return f"{content}{current_text}".strip()
    return f"{current_text.rstrip()}\n{content}".strip()


def _build_task_draft_agent_knowledge_support(
    *,
    requirement_text: str,
) -> dict[str, Any]:
    cleaned_text = str(requirement_text or "").strip()
    if not cleaned_text:
        return {
            "knowledge_hits": [],
            "knowledge_summary": "",
            "rag_support": {
                "knowledge_applied": False,
                "knowledge_chunk_count": 0,
                "retrieved_hit_count": 0,
                "query_count": 0,
                "query_variants_preview": [],
                "source_file_count": 0,
                "source_file_diversity": 0.0,
                "doc_type_count": 0,
            },
        }

    knowledge_chunks = load_curated_knowledge_chunks(raw_text=requirement_text, cleaned_text=cleaned_text)
    if not knowledge_chunks:
        return {
            "knowledge_hits": [],
            "knowledge_summary": "",
            "rag_support": {
                "knowledge_applied": False,
                "knowledge_chunk_count": 0,
                "retrieved_hit_count": 0,
                "query_count": 0,
                "query_variants_preview": [],
                "source_file_count": 0,
                "source_file_diversity": 0.0,
                "doc_type_count": 0,
            },
        }

    queries = build_requirement_retrieval_queries(requirement_text, cleaned_text)
    index = build_requirement_knowledge_index(knowledge_chunks, enable_vector_rag=False, embedding_config=None)
    diagnostics: dict[str, Any] = {}
    hits = retrieve_requirement_knowledge_chunks(
        index,
        queries,
        top_k=3,
        use_vector_rag=False,
        embedding_config=None,
        rerank=False,
        out_diagnostics=diagnostics,
    )
    knowledge_hits: list[dict[str, Any]] = []
    for item in hits:
        excerpt = str(item.get("content") or "").replace("\n", " ").strip()
        knowledge_hits.append(
            {
                "title": str(item.get("section_title") or item.get("source_file") or "Knowledge"),
                "source_file": str(item.get("source_file") or ""),
                "doc_type": str(item.get("doc_type") or ""),
                "score": float(item.get("score", 0.0) or 0.0),
                "query_match_count": int(item.get("query_match_count", 0) or 0),
                "excerpt": excerpt[:180],
            }
        )
    knowledge_sources = _dedupe_strings(hit["source_file"] for hit in knowledge_hits)
    doc_types = _dedupe_strings(hit["doc_type"] for hit in knowledge_hits)
    knowledge_summary = ""
    if knowledge_hits:
        knowledge_summary = (
            f"已从知识库匹配到 {len(knowledge_hits)} 条参考片段"
            + (f"，覆盖 {len(knowledge_sources)} 份来源文档" if knowledge_sources else "")
        )
    return {
        "knowledge_hits": knowledge_hits,
        "knowledge_summary": knowledge_summary,
        "rag_support": {
            "knowledge_applied": bool(knowledge_hits),
            "knowledge_chunk_count": len(knowledge_chunks),
            "retrieved_hit_count": len(knowledge_hits),
            "query_count": len(queries),
            "query_variants_preview": diagnostics.get("retrieval_query_variants_preview", queries[:4]),
            "source_file_count": len(knowledge_sources),
            "source_file_diversity": round((len(knowledge_sources) / len(knowledge_hits)), 3) if knowledge_hits else 0.0,
            "doc_type_count": len(doc_types),
        },
    }


def _build_task_draft_follow_up_questions(
    *,
    detected_base_url: str,
    recommended_environment: str,
    request_block_count: int,
    expected_block_count: int,
    has_context_flow: bool,
    lifecycle_resource_risk: bool,
    auth_hints: list[str],
    available_action_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    action_keys = available_action_keys or set()
    questions: list[dict[str, Any]] = []
    if not detected_base_url:
        questions.append(
            {
                "key": "target_system",
                "field": "target_system",
                "priority": "high",
                "question": "目标系统的 Base URL 是什么？",
                "reason": "没有 Base URL 时，环境匹配和后续执行都无法稳定进行",
                "action_kind": "focus_field",
                "action_label": "去填写",
                "answer_mode": "field",
                "answer_placeholder": "例如：https://api.example.com",
            }
        )
    if not recommended_environment:
        questions.append(
            {
                "key": "environment",
                "field": "environment",
                "priority": "high",
                "question": "这份任务应该绑定哪个执行环境？",
                "reason": "只有执行环境明确后，任务才能直接进入执行链路",
                "action_kind": "focus_field",
                "action_label": "去选择",
            }
        )
    if request_block_count == 0:
        question = {
            "key": "request_structure",
            "field": "requirement_text",
            "priority": "medium",
            "question": "能否把关键步骤改写成 `**Request:**` 结构？",
            "reason": "明确请求边界后，场景拆分和接口覆盖识别会更稳定",
        }
        if "request_expected_template" in action_keys:
            question.update(
                {
                    "action_kind": "apply_document_action",
                    "action_label": "插入模板",
                    "document_action_key": "request_expected_template",
                }
            )
        else:
            question.update({"action_kind": "focus_field", "action_label": "去补充"})
        questions.append(question)
    if expected_block_count == 0:
        question = {
            "key": "expected_structure",
            "field": "requirement_text",
            "priority": "medium",
            "question": "每个步骤的预期结果能否显式写成 `**Expected:**`？",
            "reason": "没有预期结果时，断言生成会偏弱",
        }
        if "request_expected_template" in action_keys:
            question.update(
                {
                    "action_kind": "apply_document_action",
                    "action_label": "插入模板",
                    "document_action_key": "request_expected_template",
                }
            )
        else:
            question.update({"action_kind": "focus_field", "action_label": "去补充"})
        questions.append(question)
    if lifecycle_resource_risk and not has_context_flow:
        question = {
            "key": "resource_source",
            "field": "requirement_text",
            "priority": "high",
            "question": "这些 detail/update/patch/delete 接口依赖的资源 id 是从哪里来的？",
            "reason": "需要明确 create、list/detail 保存 id，或预置资源来源，避免场景裸跑",
        }
        if "resource_source_template" in action_keys:
            question.update(
                {
                    "action_kind": "apply_document_action",
                    "action_label": "插入来源说明",
                    "document_action_key": "resource_source_template",
                }
            )
        else:
            question.update({"action_kind": "focus_field", "action_label": "去补充"})
        question.update(
            {
                "answer_mode": "append_requirement",
                "answer_placeholder": "例如：先调用 POST /booking 创建，再复用返回的 booking_id",
                "answer_template": "\n**资源来源:**\n- {answer}\n",
            }
        )
        questions.append(question)
    if auth_hints:
        questions.append(
            {
                "key": "auth_confirmation",
                "field": "requirement_text",
                "priority": "low",
                "question": f"鉴权信息是否需要明确写成 header / cookie / token 传递方式？",
                "reason": "文档已出现鉴权提示，补清传递方式后更利于环境配置和场景执行",
                "action_kind": "focus_field",
                "action_label": "补充说明",
                "answer_mode": "append_requirement",
                "answer_placeholder": "例如：Header `Authorization: Bearer {{token}}`",
                "answer_template": "\n**鉴权说明:**\n- {answer}\n",
            }
        )
    return questions


def _build_task_draft_document_preview(
    *,
    requirement_text: str,
    suggested_task_name: str,
    detected_base_url: str,
    recognized_endpoints: list[str],
    document_actions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    normalized_actions = [action for action in document_actions if str(action.get("content") or "").strip()]
    normalized_text = str(requirement_text or "").strip()
    auth_hints = _extract_requirement_auth_hints(requirement_text)
    if not normalized_actions and not normalized_text:
        return None

    applied_action_keys: list[str] = [
        action_key
        for action in normalized_actions
        if (action_key := str(action.get("key") or "").strip())
    ]
    action_key_set = set(applied_action_keys)

    draft_lines: list[str] = []
    document_title = str(suggested_task_name or "").strip() or "API 测试需求"
    draft_lines.append(f"# {document_title}")
    draft_lines.append("")
    draft_lines.append("## 目标")
    draft_lines.append(f"- 验证 {document_title} 的核心接口链路与关键结果")
    draft_lines.append("")
    draft_lines.append("## 环境信息")
    draft_lines.append(f"- Base URL: {detected_base_url or 'https://your-api-host'}")
    if auth_hints:
        draft_lines.append(f"- 鉴权提示: {'、'.join(auth_hints)}")
    draft_lines.append("")

    if recognized_endpoints:
        draft_lines.append("## 涉及接口")
        for endpoint in recognized_endpoints[:8]:
            draft_lines.append(f"- `{endpoint}`")
        draft_lines.append("")

    draft_lines.append("## 场景清单")
    if recognized_endpoints:
        for index, endpoint in enumerate(recognized_endpoints[: min(3, len(recognized_endpoints))], start=1):
            draft_lines.append(f"### Scenario {index}: {endpoint}")
            draft_lines.append(f"**Request:** `{endpoint}`")
            draft_lines.append("**Expected:** 返回 200，且响应结构符合预期")
            draft_lines.append("")
    else:
        draft_lines.append("### Scenario 1: 示例场景")
        draft_lines.append("**Request:** `GET /resource`")
        draft_lines.append("**Expected:** 返回 200，且响应结构符合预期")
        draft_lines.append("")

    if "context_flow_template" in action_key_set:
        draft_lines.append("## 上下文传递")
        draft_lines.append("**save_context:**")
        draft_lines.append("resource_id ← json.id")
        draft_lines.append("")
        draft_lines.append("**uses_context:**")
        draft_lines.append("resource_id")
        draft_lines.append("")

    if "resource_source_template" in action_key_set:
        draft_lines.append("## 资源来源")
        draft_lines.append("- 同场景 `POST /resource` 创建")
        draft_lines.append("- 或先通过 `GET /resource` 获取并保存 id")
        draft_lines.append("")

    if normalized_text:
        draft_lines.append("## 补充说明")
        draft_lines.append(normalized_text)

    preview_content = "\n".join(draft_lines).strip()
    title_summary = "结构化草稿"
    return {
        "content": preview_content.strip(),
        "summary": f"已生成 {title_summary}",
        "action_count": len(normalized_actions),
        "applied_action_keys": applied_action_keys,
    }


def _build_task_draft_document_diagnostics(
    *,
    requirement_text: str,
    detected_base_url: str,
    recommended_environment: str,
    selected_environment: str,
    environment_target_aligned: bool,
    suggested_task_name: str,
) -> dict[str, Any]:
    text = str(requirement_text or "")
    endpoint_signatures = _extract_requirement_endpoint_signatures(text)
    endpoint_count = len(endpoint_signatures)
    unique_method_count = len({method for method, _ in endpoint_signatures})
    recognized_endpoints = [f"{method} {path}" for method, path in endpoint_signatures[:8]]
    request_block_count = len(re.findall(r"\*\*Request:\*\*", text, flags=re.IGNORECASE))
    expected_block_count = len(re.findall(r"\*\*Expected:\*\*", text, flags=re.IGNORECASE))
    save_context_count = len(re.findall(r"\*\*save_context:\*\*", text, flags=re.IGNORECASE))
    uses_context_count = len(re.findall(r"\*\*uses_context:\*\*", text, flags=re.IGNORECASE))
    explicit_resource_source = bool(
        re.search(r"资源来源|关键依赖|预置资源|fixture|preseed|seed data|existing resource", text, flags=re.IGNORECASE)
    )
    auth_hints = _extract_requirement_auth_hints(text)
    has_context_flow = save_context_count > 0 or uses_context_count > 0
    lifecycle_resource_risk = False
    has_heading = bool(re.search(r"^\s*#\s+\S+", text, flags=re.MULTILINE))

    if request_block_count > 0 and expected_block_count > 0:
        document_shape = "结构化"
        document_shape_tone = "success"
    elif endpoint_count > 0 or has_context_flow:
        document_shape = "半结构化"
        document_shape_tone = "default"
    elif text.strip():
        document_shape = "自由描述"
        document_shape_tone = "warning"
    else:
        document_shape = "空白"
        document_shape_tone = "warning"

    signals: list[dict[str, Any]] = [
        {
            "key": "document_shape",
            "label": "文档形态",
            "value": document_shape,
            "tone": document_shape_tone,
        },
        {
            "key": "endpoint_count",
            "label": "接口识别",
            "value": f"{endpoint_count} 个接口 / {unique_method_count} 种方法" if endpoint_count else "未识别到接口标识",
            "tone": "success" if endpoint_count else "warning",
        },
        {
            "key": "request_expected",
            "label": "结构锚点",
            "value": f"Request {request_block_count} / Expected {expected_block_count}",
            "tone": (
                "success"
                if request_block_count > 0 and expected_block_count > 0 and request_block_count == expected_block_count
                else "warning"
                if request_block_count > 0 or expected_block_count > 0
                else "default"
            ),
        },
        {
            "key": "context_flow",
            "label": "上下文传递",
            "value": (
                f"save_context {save_context_count} / uses_context {uses_context_count}"
                if has_context_flow
                else "未显式声明"
            ),
            "tone": "success" if has_context_flow else "default",
        },
        {
            "key": "auth_hints",
            "label": "鉴权提示",
            "value": "、".join(auth_hints) if auth_hints else "未识别到明显鉴权提示",
            "tone": "success" if auth_hints else "default",
        },
        {
            "key": "environment_match",
            "label": "执行环境",
            "value": recommended_environment or selected_environment or "待匹配",
            "tone": (
                "success"
                if recommended_environment and environment_target_aligned
                else "warning"
                if recommended_environment or selected_environment
                else "default"
            ),
        },
    ]

    highlights: list[str] = []
    risks: list[str] = []
    if detected_base_url:
        highlights.append(f"已识别目标系统 {detected_base_url}")
    if endpoint_count > 0:
        highlights.append(f"识别到 {endpoint_count} 个接口标识，后续场景生成会更稳定")
    if request_block_count > 0 and expected_block_count > 0:
        highlights.append("文档已使用 Request / Expected 结构锚点，解析稳定性更高")
    if has_context_flow:
        highlights.append("文档已显式描述上下文传递，可支持跨步骤复用资源 ID")
    if auth_hints:
        highlights.append(f"检测到 { '、'.join(auth_hints) } 鉴权提示，可提前核对环境配置")
    if recommended_environment and environment_target_aligned:
        highlights.append(f"已匹配到与目标系统对齐的执行环境“{recommended_environment}”")

    if not detected_base_url:
        risks.append("未明确目标系统地址，执行前仍需手动确认 Base URL")
    if endpoint_count == 0 and request_block_count == 0:
        risks.append("未识别到明确的 `METHOD /path` 或 `**Request:**`，自动场景生成覆盖率可能偏低")
    if request_block_count > 0 and expected_block_count == 0:
        risks.append("存在 `**Request:**` 但缺少 `**Expected:**`，断言生成信息可能不足")
    if expected_block_count > 0 and request_block_count == 0:
        risks.append("存在 `**Expected:**` 但缺少 `**Request:**`，步骤边界可能不清晰")
    if request_block_count > 0 and expected_block_count > 0 and request_block_count != expected_block_count:
        risks.append(f"`Request` 与 `Expected` 数量不一致（{request_block_count}/{expected_block_count}），建议核对步骤边界")

    by_resource: dict[str, list[tuple[str, str]]] = {}
    for method, path in endpoint_signatures:
        resource_key = _infer_requirement_resource_key(path)
        if not resource_key:
            continue
        by_resource.setdefault(resource_key, []).append((method, path))

    read_only_endpoint_count = sum(1 for method, path in endpoint_signatures if method == "GET" and not _endpoint_requires_live_resource(method, path))
    write_endpoint_count = sum(1 for method, _ in endpoint_signatures if method in {"POST", "PUT", "PATCH", "DELETE"})
    lifecycle_chain_count = 0
    uncovered_live_resource_endpoints: list[str] = []

    if not explicit_resource_source:
        for resource_key, entries in by_resource.items():
            methods = {method for method, _ in entries}
            has_list_like_query = any(method == "GET" and not _endpoint_requires_live_resource(method, path) for method, path in entries)
            requires_live_resource = any(_endpoint_requires_live_resource(method, path) for method, path in entries)
            has_live_source = "POST" in methods or (has_list_like_query and has_context_flow)
            if requires_live_resource and has_live_source:
                lifecycle_chain_count += 1
            if requires_live_resource and not has_live_source:
                lifecycle_resource_risk = True
                risks.append(
                    f"检测到 {resource_key} 资源存在 detail/update/patch/delete，但未看到资源来源、create 或显式上下文传递，独立场景可能缺少活资源"
                )
                uncovered_live_resource_endpoints.extend(
                    f"{method} {path}" for method, path in entries if _endpoint_requires_live_resource(method, path)
                )
    else:
        lifecycle_chain_count = sum(
            1
            for entries in by_resource.values()
            if any(_endpoint_requires_live_resource(method, path) for method, path in entries)
        )

    recognized_endpoint_set = set(recognized_endpoints)
    uncovered_live_resource_endpoints = [
        endpoint
        for endpoint in _dedupe_strings(uncovered_live_resource_endpoints)
        if endpoint in recognized_endpoint_set
    ]
    standalone_endpoint_count = max(endpoint_count - max(lifecycle_chain_count, 0), 0)
    estimated_scenario_count = 0
    if endpoint_count == 0:
        estimated_scenario_count = 1 if text.strip() else 0
    elif by_resource:
        read_only_resource_count = sum(
            1
            for entries in by_resource.values()
            if any(method == "GET" and not _endpoint_requires_live_resource(method, path) for method, path in entries)
            and not any(_endpoint_requires_live_resource(method, path) for method, path in entries)
        )
        estimated_scenario_count = max(lifecycle_chain_count + read_only_resource_count, 1)
        if endpoint_count <= 2 and request_block_count <= 1:
            estimated_scenario_count = max(estimated_scenario_count, endpoint_count)
    else:
        estimated_scenario_count = max(min(request_block_count or endpoint_count, 4), 1)

    scenario_shape = "依赖链型" if lifecycle_chain_count else "单接口/松散型" if endpoint_count else "待补充"
    resource_groups: list[dict[str, Any]] = []
    for resource_key, entries in by_resource.items():
        methods = sorted({method for method, _ in entries})
        endpoints = [f"{method} {path}" for method, path in entries]
        has_list_like_query = any(method == "GET" and not _endpoint_requires_live_resource(method, path) for method, path in entries)
        has_live_resource = any(_endpoint_requires_live_resource(method, path) for method, path in entries)
        has_create = "POST" in methods
        has_live_source = has_create or (has_list_like_query and has_context_flow) or explicit_resource_source
        if has_live_resource and has_live_source:
            status = "complete"
        elif has_live_resource:
            status = "needs_source"
        elif has_list_like_query:
            status = "read_only"
        else:
            status = "single_step"
        resource_groups.append(
            {
                "resource_key": resource_key,
                "methods": methods,
                "endpoints": endpoints,
                "status": status,
                "has_create": has_create,
                "has_context_flow": has_context_flow,
                "has_live_resource": has_live_resource,
                "has_list_source": has_list_like_query,
                "estimated_scenarios": 1 if endpoints else 0,
            }
        )
    resource_groups.sort(key=lambda item: (str(item.get("status") or ""), str(item.get("resource_key") or "")))
    scenario_outlook = {
        "estimated_scenario_count": estimated_scenario_count,
        "endpoint_count": endpoint_count,
        "resource_group_count": len(by_resource),
        "write_endpoint_count": write_endpoint_count,
        "read_only_endpoint_count": read_only_endpoint_count,
        "lifecycle_chain_count": lifecycle_chain_count,
        "standalone_endpoint_count": standalone_endpoint_count,
        "uncovered_live_resource_endpoints": uncovered_live_resource_endpoints,
        "scenario_shape": scenario_shape,
    }

    signals.append(
        {
            "key": "scenario_outlook",
            "label": "场景预估",
            "value": (
                f"约 {estimated_scenario_count} 个场景"
                if estimated_scenario_count
                else "待补充接口或步骤后再预估"
            ),
            "tone": "warning" if lifecycle_resource_risk else "success" if estimated_scenario_count else "default",
        }
    )

    if estimated_scenario_count:
        highlights.append(f"按当前文档形态，预计可形成约 {estimated_scenario_count} 个场景")
    if uncovered_live_resource_endpoints:
        risks.append(f"以下接口仍缺少活资源来源：{', '.join(uncovered_live_resource_endpoints[:3])}")

    if recommended_environment and not environment_target_aligned:
        risks.append(f"当前环境建议为“{recommended_environment}”，但与识别到的目标系统还未完全对齐")
    elif detected_base_url and not recommended_environment:
        risks.append("已识别目标系统，但尚未匹配到可执行环境")

    document_fixes: list[str] = []
    document_actions: list[dict[str, Any]] = []
    if suggested_task_name and not has_heading:
        document_fixes.append("建议补充文档标题，便于任务目标和文档主题保持一致")
        document_actions.append(
            {
                "key": "title_template",
                "title": "补充文档标题",
                "mode": "prepend",
                "reason": "补齐标题后，任务目标和文档主题会更清晰",
                "content": f"# {suggested_task_name}\n\n",
            }
        )
    if not detected_base_url:
        document_fixes.append("在文档顶部补充 `Base URL: https://...`，避免目标系统无法自动识别")
        document_actions.append(
            {
                "key": "base_url_template",
                "title": "补充 Base URL",
                "mode": "prepend",
                "reason": "先明确目标系统地址，后续环境匹配和场景执行会更稳定",
                "content": "Base URL: https://your-api-host\n",
            }
        )
    if endpoint_count == 0:
        document_fixes.append("将关键接口统一写成 `METHOD /path`，例如 `POST /booking`，提升接口识别率")
        document_actions.append(
            {
                "key": "method_path_template",
                "title": "插入接口标识模板",
                "mode": "append",
                "reason": "显式写出 `METHOD /path`，Agent 才能稳定识别接口覆盖范围",
                "content": "\n## 接口清单\n- `GET /resource`\n- `POST /resource`\n",
            }
        )
    if request_block_count == 0:
        document_fixes.append("为每个步骤补充 `**Request:**`，明确请求边界")
        request_line = recognized_endpoints[0] if recognized_endpoints else "GET /resource"
        document_actions.append(
            {
                "key": "request_expected_template",
                "title": "插入步骤模板",
                "mode": "append",
                "reason": "补齐 Request / Expected 结构锚点，便于场景和断言生成",
                "content": (
                    "\n## Scenario: 示例场景\n"
                    f"**Request:** `{request_line}`\n"
                    "**Expected:** 返回 200，且响应结构符合预期\n"
                ),
            }
        )
    if expected_block_count == 0:
        document_fixes.append("为每个步骤补充 `**Expected:**`，让断言生成更稳定")
    if endpoint_count > 1 and not has_context_flow:
        document_fixes.append("跨步骤依赖资源 ID 时，显式增加 `**save_context:**` 和 `**uses_context:**`")
        document_actions.append(
            {
                "key": "context_flow_template",
                "title": "插入上下文传递模板",
                "mode": "append",
                "reason": "跨步骤依赖资源 ID 时，显式声明上下文字段能减少场景缺失",
                "content": (
                    "\n**save_context:**\n"
                    "resource_id ← json.id\n\n"
                    "**uses_context:**\n"
                    "resource_id\n"
                ),
            }
        )
    if lifecycle_resource_risk and not explicit_resource_source:
        document_fixes.append("对 detail/update/patch/delete 这类依赖活资源的接口，补充资源来源，或并入 create/list 依赖链")
        document_actions.append(
            {
                "key": "resource_source_template",
                "title": "插入资源来源说明",
                "mode": "append",
                "reason": "需要活资源的接口不应裸跑，补充来源后场景依赖更完整",
                "content": (
                    "\n**资源来源:**\n"
                    "- 同场景 `POST /resource` 创建\n"
                    "- 或先通过 `GET /resource` 获取并保存 id\n"
                ),
            }
        )
    if auth_hints and not recommended_environment:
        document_fixes.append("文档已提示鉴权要求，但执行环境未匹配成功，建议先核对环境中的 auth/cookies 配置")

    follow_up_questions = _build_task_draft_follow_up_questions(
        detected_base_url=detected_base_url,
        recommended_environment=recommended_environment,
        request_block_count=request_block_count,
        expected_block_count=expected_block_count,
        has_context_flow=has_context_flow,
        lifecycle_resource_risk=lifecycle_resource_risk,
        auth_hints=auth_hints,
        available_action_keys={
            str(item.get("key") or "").strip()
            for item in document_actions
            if str(item.get("key") or "").strip()
        },
    )

    return {
        "signals": signals,
        "recognized_endpoints": recognized_endpoints,
        "highlights": _dedupe_strings(highlights),
        "risks": _dedupe_strings(risks),
        "document_fixes": _dedupe_strings(document_fixes),
        "document_actions": document_actions,
        "follow_up_questions": follow_up_questions,
        "lifecycle_resource_risk": lifecycle_resource_risk,
        "has_context_flow": has_context_flow,
        "request_block_count": request_block_count,
        "expected_block_count": expected_block_count,
        "auth_hints": auth_hints,
        "scenario_outlook": scenario_outlook,
        "resource_groups": resource_groups,
    }


def _build_task_draft_environment_candidates(
    *,
    project_id: str | None,
    detected_base_url: str,
    selected_environment: str | None,
) -> list[dict[str, Any]]:
    normalized_detected_base_url = _normalize_base_url_for_match(detected_base_url)
    detected_host = _extract_url_host(normalized_detected_base_url)
    selected_environment_name = str(selected_environment or "").strip()
    ranked_candidates: list[tuple[int, dict[str, Any]]] = []
    seen_names: set[str] = set()

    for config in registry.list_environments(project_id=project_id, include_global=project_id is not None):
        match_type = ""
        score = 0
        normalized_env_base_url = _normalize_base_url_for_match(config.base_url)
        env_host = _extract_url_host(normalized_env_base_url)

        if normalized_detected_base_url and normalized_env_base_url and normalized_env_base_url == normalized_detected_base_url:
            match_type = "exact_base_url"
            score = 100
        elif detected_host and env_host and env_host == detected_host:
            match_type = "same_host"
            score = 80
        elif selected_environment_name and config.name == selected_environment_name:
            match_type = "selected_environment"
            score = 60

        if not match_type or config.name in seen_names:
            continue

        seen_names.add(config.name)
        ranked_candidates.append(
            (
                score,
                {
                    "name": config.name,
                    "base_url": config.base_url,
                    "description": config.description,
                    "match_type": match_type,
                },
            )
        )

    ranked_candidates.sort(key=lambda item: (-item[0], str(item[1].get("name") or "")))
    return [item[1] for item in ranked_candidates]


def _build_task_draft_quality_gates(
    *,
    requirement_ready: bool,
    target_ready: bool,
    environment_ready: bool,
    environment_target_aligned: bool,
    diagnostics: dict[str, Any],
    knowledge_support: dict[str, Any],
) -> list[dict[str, Any]]:
    request_count = int(diagnostics.get("request_block_count", 0) or 0)
    expected_count = int(diagnostics.get("expected_block_count", 0) or 0)
    endpoint_count = len(diagnostics.get("recognized_endpoints") or [])
    lifecycle_resource_risk = bool(diagnostics.get("lifecycle_resource_risk"))
    has_context_flow = bool(diagnostics.get("has_context_flow"))
    knowledge_hits = knowledge_support.get("knowledge_hits") or []

    gates = [
        {
            "key": "parseability",
            "label": "解析稳定性",
            "status": "pass" if request_count and expected_count else "warn" if endpoint_count else "block",
            "detail": (
                f"已识别 {request_count} 个 Request 与 {expected_count} 个 Expected"
                if request_count or expected_count
                else "缺少 Request/Expected 锚点，场景边界会更依赖自然语言推断"
            ),
        },
        {
            "key": "coverage",
            "label": "接口覆盖",
            "status": "pass" if endpoint_count >= 3 else "warn" if endpoint_count else "block",
            "detail": (
                f"已识别 {endpoint_count} 个接口，可据此评估覆盖范围"
                if endpoint_count
                else "未识别到 METHOD /path，覆盖率无法可靠估算"
            ),
        },
        {
            "key": "dependency_integrity",
            "label": "依赖完整性",
            "status": "block" if lifecycle_resource_risk else "pass" if has_context_flow else "warn",
            "detail": (
                "存在需要活资源的接口但缺少资源来源"
                if lifecycle_resource_risk
                else "已显式声明上下文传递"
                if has_context_flow
                else "未发现明显跨步骤上下文，若包含 detail/update/delete 需再核对资源来源"
            ),
        },
        {
            "key": "execution_readiness",
            "label": "执行准备",
            "status": "pass" if requirement_ready and target_ready and environment_ready and environment_target_aligned else "warn",
            "detail": (
                "任务名、目标系统、执行环境已基本齐备"
                if requirement_ready and target_ready and environment_ready and environment_target_aligned
                else "创建或执行前仍需补齐目标系统、环境或环境对齐信息"
            ),
        },
        {
            "key": "knowledge_support",
            "label": "知识依据",
            "status": "pass" if knowledge_hits else "warn",
            "detail": (
                f"已匹配 {len(knowledge_hits)} 条知识片段，可解释当前建议来源"
                if knowledge_hits
                else "未命中知识片段，建议主要来自文档结构规则"
            ),
        },
    ]
    return gates


def _build_task_draft_action_plan(
    *,
    ready_to_create: bool,
    ready_to_execute: bool,
    diagnostics: dict[str, Any],
    document_preview: dict[str, Any] | None,
    knowledge_support: dict[str, Any],
) -> list[dict[str, Any]]:
    has_followups = bool(diagnostics.get("follow_up_questions"))
    has_document_actions = bool(diagnostics.get("document_actions"))
    has_risks = bool(diagnostics.get("risks"))
    has_knowledge = bool(knowledge_support.get("knowledge_hits"))
    scenario_count = int((diagnostics.get("scenario_outlook") or {}).get("estimated_scenario_count", 0) or 0)

    return [
        {
            "key": "understand_input",
            "title": "识别任务输入",
            "detail": "已提取任务名称、目标系统、接口标识、环境候选与文档结构信号",
            "status": "done" if diagnostics.get("recognized_endpoints") or document_preview else "review",
            "action_label": "看概览",
            "target_view": "overview",
        },
        {
            "key": "resolve_blockers",
            "title": "处理阻断项",
            "detail": (
                "先回答高优先级追问，尤其是 Base URL、执行环境和资源来源"
                if has_followups or has_risks
                else "当前未发现明显阻断项"
            ),
            "status": "blocked" if has_risks else "next" if has_followups else "done",
            "action_label": "处理追问",
            "target_view": "followups",
        },
        {
            "key": "normalize_document",
            "title": "修正文档结构",
            "detail": (
                "可插入缺失的标题、Base URL、Request/Expected、上下文或资源来源片段"
                if has_document_actions
                else "文档结构暂不需要自动插入片段"
            ),
            "status": "next" if has_document_actions else "done",
            "action_label": "看修正",
            "target_view": "document",
        },
        {
            "key": "review_scenarios",
            "title": "审阅场景蓝图",
            "detail": f"预计形成约 {scenario_count} 个场景，重点检查接口覆盖与资源生命周期",
            "status": "next" if scenario_count else "review",
            "action_label": "看链路",
            "target_view": "overview",
        },
        {
            "key": "create_or_execute",
            "title": "创建并执行",
            "detail": (
                "当前可直接创建并进入执行链路"
                if ready_to_execute
                else "当前可创建任务，但执行前仍建议处理待确认项"
                if ready_to_create
                else "创建前仍需补齐关键输入"
            ),
            "status": "done" if ready_to_execute else "next" if ready_to_create else "blocked",
            "action_label": "回到创建",
            "target_view": "overview",
        },
        {
            "key": "explain_with_knowledge",
            "title": "查看知识依据",
            "detail": (
                f"已命中 {len(knowledge_support.get('knowledge_hits') or [])} 条知识片段，可辅助解释建议"
                if has_knowledge
                else "暂无知识命中，后续可继续补充规范库"
            ),
            "status": "done" if has_knowledge else "review",
            "action_label": "看依据",
            "target_view": "knowledge",
        },
    ]


def _build_task_draft_scenario_blueprint(
    *,
    diagnostics: dict[str, Any],
) -> list[dict[str, Any]]:
    resource_groups = diagnostics.get("resource_groups") or []
    recognized_endpoints = diagnostics.get("recognized_endpoints") or []
    blueprints: list[dict[str, Any]] = []

    for group in resource_groups[:6]:
        status = str(group.get("status") or "")
        resource_key = str(group.get("resource_key") or "resource")
        endpoints = [str(item) for item in group.get("endpoints") or [] if str(item).strip()]
        if status == "complete":
            title = f"{resource_key} 生命周期链路"
            objective = "覆盖创建/查询/修改/删除或同资源依赖链，验证资源状态流转"
            dependency = "资源来源已具备，可按链路组织场景"
            blueprint_status = "ready"
            gaps: list[str] = []
        elif status == "needs_source":
            title = f"{resource_key} 活资源链路"
            objective = "覆盖 detail/update/patch/delete 前，先确认可复用的资源 id"
            dependency = "缺少 create、list/detail 保存 id 或预置资源说明"
            blueprint_status = "needs_context"
            gaps = ["补充资源来源", "声明 save_context / uses_context"]
        elif status == "read_only":
            title = f"{resource_key} 只读查询链路"
            objective = "覆盖列表/查询类接口，验证读取能力与基础响应结构"
            dependency = "无需活资源创建，适合作为独立只读场景"
            blueprint_status = "read_only"
            gaps = []
        else:
            title = f"{resource_key} 单接口场景"
            objective = "覆盖单接口基础可用性，后续可并入更完整依赖链"
            dependency = "暂无明确上下游依赖"
            blueprint_status = "single_step"
            gaps = []
        blueprints.append(
            {
                "key": f"{resource_key}-{status}",
                "title": title,
                "objective": objective,
                "endpoints": endpoints,
                "dependency": dependency,
                "status": blueprint_status,
                "gaps": gaps,
            }
        )

    if not blueprints and recognized_endpoints:
        for index, endpoint in enumerate(recognized_endpoints[:4], start=1):
            blueprints.append(
                {
                    "key": f"endpoint-{index}",
                    "title": f"接口基础场景 {index}",
                    "objective": "先验证单接口基础可达性，再根据响应数据补充链路关系",
                    "endpoints": [str(endpoint)],
                    "dependency": "暂无明确依赖",
                    "status": "single_step",
                    "gaps": [],
                }
            )
    return blueprints


def _build_task_draft_coverage_gaps(*, diagnostics: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    scenario_outlook = diagnostics.get("scenario_outlook") or {}
    if not diagnostics.get("recognized_endpoints"):
        gaps.append("未识别到接口标识，无法可靠估算接口覆盖率")
    if int(diagnostics.get("request_block_count", 0) or 0) == 0:
        gaps.append("缺少 Request 锚点，场景边界可能依赖自然语言推断")
    if int(diagnostics.get("expected_block_count", 0) or 0) == 0:
        gaps.append("缺少 Expected 锚点，自动断言信息会偏弱")
    if diagnostics.get("lifecycle_resource_risk"):
        gaps.append("存在需要活资源的接口，但资源来源尚未闭合")
    uncovered = scenario_outlook.get("uncovered_live_resource_endpoints") or []
    if uncovered:
        gaps.append(f"仍有 {len(uncovered)} 个接口缺资源来源")
    return _dedupe_strings(gaps)


def _build_task_draft_diagnostic_verdict(
    *,
    ready_to_create: bool,
    ready_to_execute: bool,
    diagnostics: dict[str, Any],
    quality_gates: list[dict[str, Any]],
    coverage_gaps: list[str],
) -> dict[str, Any]:
    blocking_gates = [item for item in quality_gates if str(item.get("status") or "") == "block"]
    warning_gates = [item for item in quality_gates if str(item.get("status") or "") == "warn"]
    document_actions = diagnostics.get("document_actions") or []
    follow_up_questions = diagnostics.get("follow_up_questions") or []
    scenario_outlook = diagnostics.get("scenario_outlook") or {}
    blockers = _dedupe_strings(
        [
            str(item.get("detail") or item.get("label") or "").strip()
            for item in blocking_gates
            if str(item.get("detail") or item.get("label") or "").strip()
        ]
        + [str(item).strip() for item in diagnostics.get("risks") or [] if str(item).strip()]
    )[:5]

    if blocking_gates:
        status = "blocked"
        severity = "error"
        label = "存在阻断项"
        primary_action = "先处理阻断门禁和高优先级追问"
        summary = f"发现 {len(blocking_gates)} 个阻断门禁，暂不建议直接交给工作流生成。"
    elif not ready_to_create:
        status = "blocked"
        severity = "error"
        label = "关键输入不足"
        primary_action = "先补齐任务名、需求文本和目标系统"
        summary = "任务创建所需的关键输入还不完整，建议先补齐基础信息。"
    elif warning_gates or coverage_gaps or document_actions or follow_up_questions:
        status = "fixable"
        severity = "warning"
        label = "可修复后交付"
        primary_action = "优先应用自动修正，再处理剩余追问"
        summary = (
            f"当前可继续整理，发现 {len(warning_gates)} 个待确认门禁、"
            f"{len(document_actions)} 个可自动修正项。"
        )
    elif ready_to_execute:
        status = "pass"
        severity = "success"
        label = "可交付工作流"
        primary_action = "带回创建页提交执行"
        summary = "输入质量、依赖链和执行准备均已通过，可交给工作流创建并执行。"
    else:
        status = "fixable"
        severity = "warning"
        label = "可创建但需核对执行"
        primary_action = "回到创建页前核对执行环境"
        summary = "文档基本可创建任务，但执行环境或环境对齐仍建议人工核对。"

    blocked_endpoint_count = len(scenario_outlook.get("uncovered_live_resource_endpoints") or [])
    return {
        "status": status,
        "severity": severity,
        "label": label,
        "summary": summary,
        "primary_action": primary_action,
        "can_handoff": status == "pass" or (status == "fixable" and ready_to_create),
        "can_execute": bool(ready_to_execute and status == "pass"),
        "blockers": blockers,
        "auto_fix_count": len(document_actions),
        "manual_action_count": len(follow_up_questions) + len(coverage_gaps) + len(warning_gates),
        "endpoint_count": int(scenario_outlook.get("endpoint_count", 0) or 0),
        "estimated_scenario_count": int(scenario_outlook.get("estimated_scenario_count", 0) or 0),
        "blocked_endpoint_count": blocked_endpoint_count,
    }


def _build_task_draft_agent_payload(payload: TaskDraftAgentRequest, *, project_id: str | None = None) -> dict[str, Any]:
    normalized_project_id = str(project_id or payload.project_id or "").strip() or None
    requirement_text = str(payload.requirement_text or "")
    selected_environment = str(payload.environment or "").strip()
    suggested_task_name = _derive_task_name_hint(
        task_name=payload.task_name,
        source_path=payload.source_path,
        requirement_text=requirement_text,
    )
    detected_base_url = _extract_base_url_hint(
        requirement_text=requirement_text,
        fallback_target_system=payload.target_system,
    )
    warnings = _detect_suspicious_inline_requirement(requirement_text)
    if not requirement_text.strip():
        warnings.append("需求描述为空，Agent 无法给出有效建议")
    if not suggested_task_name:
        warnings.append("未识别到可用的任务名称")
    if not detected_base_url:
        warnings.append("未识别到目标系统地址")

    selected_environment_config = registry.get_environment(selected_environment, project_id=normalized_project_id) if selected_environment else None
    environment_candidates = _build_task_draft_environment_candidates(
        project_id=normalized_project_id,
        detected_base_url=detected_base_url,
        selected_environment=selected_environment,
    )
    if selected_environment and selected_environment_config is None:
        warnings.append(f"执行环境“{selected_environment}”不存在，请确认环境配置")

    selected_environment_base_url = _normalize_base_url_for_match(
        selected_environment_config.base_url if selected_environment_config is not None else ""
    )
    detected_base_url_normalized = _normalize_base_url_for_match(detected_base_url)
    environment_target_aligned = True
    if (
        selected_environment_config is not None
        and selected_environment_base_url
        and detected_base_url_normalized
        and selected_environment_base_url != detected_base_url_normalized
    ):
        environment_target_aligned = False
        warnings.append(
            f"当前执行环境“{selected_environment}”的 Base URL 为 {selected_environment_config.base_url}，"
            f"与识别到的目标系统 {detected_base_url} 不一致"
        )

    recommended_environment = ""
    recommended_environment_reason = ""
    if selected_environment and selected_environment_config is not None and environment_target_aligned:
        recommended_environment = selected_environment
        recommended_environment_reason = "沿用当前选择且已对齐目标系统的执行环境"
    elif environment_candidates:
        recommended_environment = str(environment_candidates[0].get("name") or "")
        match_type = str(environment_candidates[0].get("match_type") or "")
        if match_type == "exact_base_url":
            recommended_environment_reason = "已匹配到与目标系统一致的执行环境"
        elif match_type == "same_host":
            recommended_environment_reason = "已匹配到与目标系统同主机的执行环境"
        elif match_type == "selected_environment":
            recommended_environment_reason = "沿用当前选择的执行环境"
        else:
            recommended_environment_reason = "已匹配到建议的执行环境"
    elif selected_environment and selected_environment_config is not None:
        recommended_environment = selected_environment
        recommended_environment_reason = "当前保留你选择的执行环境，但还需要核对目标系统地址"

    suggestions: list[dict[str, Any]] = []
    if suggested_task_name:
        suggestions.append(
            {
                "field": "task_name",
                "value": suggested_task_name,
                "reason": "根据标题、首行内容或文件名推断",
            }
        )
    if detected_base_url:
        suggestions.append(
            {
                "field": "target_system",
                "value": detected_base_url,
                "reason": "根据需求文本中的 Base URL / 服务地址提取",
            }
        )
    if recommended_environment:
        suggestions.append(
            {
                "field": "environment",
                "value": recommended_environment,
                "reason": recommended_environment_reason,
            }
        )

    requirement_ready = bool(requirement_text.strip())
    task_name_ready = bool(suggested_task_name)
    target_ready = bool(detected_base_url)
    environment_ready = bool(recommended_environment)
    ready_fields = sum((requirement_ready, task_name_ready, target_ready, environment_ready))
    ready_to_create = requirement_ready and task_name_ready and target_ready
    ready_to_execute = ready_to_create and environment_ready and environment_target_aligned

    if suggested_task_name and detected_base_url and recommended_environment:
        reply = (
            f"已识别任务名“{suggested_task_name}”、目标系统 {detected_base_url}，"
            f"并建议使用执行环境“{recommended_environment}”。"
        )
    elif suggested_task_name and detected_base_url:
        reply = f"已识别任务名“{suggested_task_name}”和目标系统 {detected_base_url}。"
    elif suggested_task_name:
        reply = f"已识别任务名“{suggested_task_name}”，但目标系统还需要你确认。"
    elif detected_base_url:
        reply = f"已识别目标系统 {detected_base_url}，但任务名还需要你确认。"
    else:
        reply = "当前信息不足，建议先补充完整需求文本。"

    next_actions: list[str] = []
    if not requirement_ready:
        next_actions.append("补充需求描述或导入需求文档")
    if not target_ready:
        next_actions.append("确认目标系统地址")
    if not task_name_ready:
        next_actions.append("补充任务名称")
    if not environment_ready:
        next_actions.append("选择可用的执行环境")
    if environment_ready and not environment_target_aligned:
        next_actions.append("核对执行环境与目标系统地址是否一致")

    diagnostics = _build_task_draft_document_diagnostics(
        requirement_text=requirement_text,
        detected_base_url=detected_base_url,
        recommended_environment=recommended_environment,
        selected_environment=selected_environment,
        environment_target_aligned=environment_target_aligned,
        suggested_task_name=suggested_task_name,
    )
    knowledge_support = _build_task_draft_agent_knowledge_support(requirement_text=requirement_text)
    document_preview = _build_task_draft_document_preview(
        requirement_text=requirement_text,
        suggested_task_name=suggested_task_name,
        detected_base_url=detected_base_url,
        recognized_endpoints=diagnostics["recognized_endpoints"],
        document_actions=diagnostics["document_actions"],
    )
    quality_gates = _build_task_draft_quality_gates(
        requirement_ready=requirement_ready,
        target_ready=target_ready,
        environment_ready=environment_ready,
        environment_target_aligned=environment_target_aligned,
        diagnostics=diagnostics,
        knowledge_support=knowledge_support,
    )
    action_plan = _build_task_draft_action_plan(
        ready_to_create=ready_to_create,
        ready_to_execute=ready_to_execute,
        diagnostics=diagnostics,
        document_preview=document_preview,
        knowledge_support=knowledge_support,
    )
    scenario_blueprint = _build_task_draft_scenario_blueprint(diagnostics=diagnostics)
    coverage_gaps = _build_task_draft_coverage_gaps(diagnostics=diagnostics)
    diagnostic_verdict = _build_task_draft_diagnostic_verdict(
        ready_to_create=ready_to_create,
        ready_to_execute=ready_to_execute,
        diagnostics=diagnostics,
        quality_gates=quality_gates,
        coverage_gaps=coverage_gaps,
    )
    checks = [
        {
            "key": "requirement_text",
            "status": "ready" if requirement_ready else "attention",
            "message": "需求描述已提供" if requirement_ready else "请先补充需求描述或导入文档",
        },
        {
            "key": "task_name",
            "status": "ready" if task_name_ready else "attention",
            "message": f"任务名称建议为“{suggested_task_name}”" if task_name_ready else "未识别到任务名称",
        },
        {
            "key": "target_system",
            "status": "ready" if target_ready else "attention",
            "message": f"目标系统建议为 {detected_base_url}" if target_ready else "未识别到目标系统地址",
        },
        {
            "key": "environment",
            "status": "ready" if environment_ready else "attention",
            "message": (
                f"执行环境建议为“{recommended_environment}”"
                if environment_ready
                else "尚未匹配到可执行环境"
            ),
        },
        {
            "key": "environment_target_alignment",
            "status": "ready" if environment_target_aligned else "warning",
            "message": (
                "执行环境与目标系统地址一致"
                if environment_target_aligned
                else "当前执行环境与识别到的目标系统地址不一致"
            ),
        },
    ]

    form_patch: dict[str, Any] = {}
    if suggested_task_name and suggested_task_name != str(payload.task_name or "").strip():
        form_patch["task_name"] = suggested_task_name
    if detected_base_url and detected_base_url != _normalize_base_url_for_match(payload.target_system):
        form_patch["target_system"] = detected_base_url
    if recommended_environment and recommended_environment != selected_environment:
        form_patch["environment"] = recommended_environment

    confidence_score = max(
        0,
        min(
            100,
            int(
                (ready_fields / 4) * 60
                + min(len(diagnostics["recognized_endpoints"]) * 5, 15)
                + min(len(knowledge_support["knowledge_hits"]) * 5, 10)
                - min(len(diagnostics["risks"]) * 12, 36)
            ),
        ),
    )
    confidence_level = "high" if confidence_score >= 80 else "medium" if confidence_score >= 55 else "low"

    return {
        "reply": reply,
        "summary": {
            "ready_score": ready_fields,
            "max_score": 4,
            "requirement_chars": len(requirement_text),
            "ready_to_create": ready_to_create,
            "ready_to_execute": ready_to_execute,
            "highlight_count": len(diagnostics["highlights"]),
            "risk_count": len(diagnostics["risks"]),
            "confidence_score": confidence_score,
            "confidence_level": confidence_level,
        },
        "diagnostic_verdict": diagnostic_verdict,
        "suggested_task_name": suggested_task_name,
        "detected_base_url": detected_base_url,
        "selected_environment": selected_environment or None,
        "recommended_environment": recommended_environment or None,
        "environment_candidates": environment_candidates,
        "checks": checks,
        "form_patch": form_patch,
        "signals": diagnostics["signals"],
        "recognized_endpoints": diagnostics["recognized_endpoints"],
        "scenario_outlook": diagnostics["scenario_outlook"],
        "resource_groups": diagnostics["resource_groups"],
        "action_plan": action_plan,
        "scenario_blueprint": scenario_blueprint,
        "quality_gates": quality_gates,
        "coverage_gaps": coverage_gaps,
        "highlights": diagnostics["highlights"],
        "risks": diagnostics["risks"],
        "document_fixes": diagnostics["document_fixes"],
        "document_actions": diagnostics["document_actions"],
        "document_preview": document_preview,
        "knowledge_hits": knowledge_support["knowledge_hits"],
        "knowledge_summary": knowledge_support["knowledge_summary"],
        "rag_support": knowledge_support["rag_support"],
        "follow_up_questions": diagnostics["follow_up_questions"],
        "warnings": _dedupe_strings(warnings),
        "next_actions": _dedupe_strings(next_actions),
        "suggestions": suggestions,
        "capabilities": {
            "backend_ready": True,
            "mcp_direct_supported": False,
            "requires_backend_proxy": True,
            "auto_analysis_supported": True,
            "diagnostics_supported": True,
            "document_actions_supported": True,
            "knowledge_rag_supported": True,
        },
    }


def _build_task_agent_chat_reply(message: str, agent_payload: dict[str, Any]) -> str:
    normalized = str(message or "").strip().lower()
    reply = str(agent_payload.get("reply") or "").strip()
    next_actions = [str(item).strip() for item in agent_payload.get("next_actions") or [] if str(item).strip()]
    risks = [str(item).strip() for item in agent_payload.get("risks") or [] if str(item).strip()]
    warnings = [str(item).strip() for item in agent_payload.get("warnings") or [] if str(item).strip()]
    coverage_gaps = [str(item).strip() for item in agent_payload.get("coverage_gaps") or [] if str(item).strip()]
    quality_gates = [item for item in agent_payload.get("quality_gates") or [] if isinstance(item, dict)]
    scenario_outlook = agent_payload.get("scenario_outlook") if isinstance(agent_payload.get("scenario_outlook"), dict) else {}
    knowledge_hits = agent_payload.get("knowledge_hits") if isinstance(agent_payload.get("knowledge_hits"), list) else []
    knowledge_summary = str(agent_payload.get("knowledge_summary") or "").strip()

    if any(token in normalized for token in ("你好", "您好", "hello", "hi", "在吗")):
        return "你好，我在。你可以把接口需求、文档片段或要测试的业务流程发给我，我会结合当前草稿帮你拆测试场景、断言和风险点。"
    if any(token in normalized for token in ("你会", "能做", "功能", "帮助", "怎么用")):
        return "\n".join(
            [
                "我可以帮你做这些事：",
                "1. 根据当前任务草稿整理正向、异常、边界和权限类测试场景。",
                "2. 检查状态码、字段、业务状态、上下文变量和跨步骤一致性断言。",
                "3. 提醒文档缺失的路径、方法、鉴权、参数和接口依赖。",
                "4. 结合 RAG 命中结果判断知识依据是否足够。",
            ]
        )
    if any(token in normalized for token in ("断言", "校验", "检查点")):
        pending_gates = [str(item.get("label") or "").strip() for item in quality_gates if item.get("status") != "pass" and str(item.get("label") or "").strip()]
        if pending_gates:
            return "建议优先补这些断言：" + "、".join(pending_gates[:4]) + "。同时保留状态码、关键字段、上下文变量和错误分支校验。"
        return "当前没有明显阻断门禁。建议继续补充状态码、业务状态、资源 ID 传递、权限边界、重复提交和失败重试断言。"
    if any(token in normalized for token in ("场景", "用例", "测试点")):
        estimated_count = int(scenario_outlook.get("estimated_scenario_count") or 0)
        base = f"当前预计可设计 {estimated_count} 个测试场景。" if estimated_count else "建议先按业务流程设计测试场景。"
        gaps = coverage_gaps[:3]
        suffix = "还要注意：" + "；".join(gaps) if gaps else "优先覆盖主链路、异常参数、鉴权失败、资源不存在和状态流转异常。"
        return f"{base}{suffix}"
    if any(token in normalized for token in ("风险", "问题", "缺陷", "隐患")):
        points = (risks + warnings + coverage_gaps)[:4]
        return "目前最需要关注：" + "；".join(points) if points else "当前没有明显高风险提示。建议继续检查鉴权、跨接口变量、异步回调和幂等重试。"
    if any(token in normalized for token in ("rag", "知识", "依据", "检索")):
        if knowledge_hits:
            return f"RAG 当前命中 {len(knowledge_hits)} 条知识依据。{knowledge_summary or '建议核对知识来源是否覆盖接口约束、错误码和业务规则。'}"
        return "当前没有知识命中。建议补充接口规范、错误码说明、业务规则文档后重新分析。"
    if next_actions:
        return f"{reply} 下一步建议：" + "；".join(next_actions[:3])
    return reply or "我已经收到。你可以继续补充接口、参数、业务流程或预期结果，我会帮你拆成测试场景、断言点和风险点。"


def _parse_iso_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    value = raw.strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


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
    environment_config = registry.get_environment(selected_name, project_id=getattr(task, "project_id", None))
    if environment_name and environment_config is None:
        raise HTTPException(status_code=404, detail=f"Environment not found: {environment_name}")
    return environment_config


def _resolve_project_environment_config(project_id: str, environment_name: str | None) -> EnvironmentConfig | None:
    selected_name = str(environment_name or "").strip()
    if not selected_name:
        return None
    environment_config = registry.get_environment(selected_name, project_id=project_id)
    if environment_config is None:
        raise HTTPException(status_code=404, detail=f"Environment not found: {selected_name}")
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
    parse_metadata = _parse_metadata_payload((task.pipeline_result or {}).get("parse_metadata", {}))
    summary = analysis_report.get("summary") or {}
    artifact_root = Path(task.artifact_dir) if task.artifact_dir else None
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
            "parse_mode": parse_metadata.get("parse_mode"),
            "llm_used": bool(parse_metadata.get("llm_used", False)),
            "rag_enabled": bool(parse_metadata.get("rag_enabled", False)),
            "rag_used": bool(parse_metadata.get("rag_used", False)),
            "duration_ms": (execution_result.get("metrics") or {}).get("duration_ms"),
            "progress_snapshot": _build_runtime_progress_payload(task),
            "runtime_context_snapshot_path": (
                str(artifact_root / "execution" / "runtime_context_snapshot.json") if artifact_root else None
            ),
            "analysis_report_path": (
                str(artifact_root / "validation" / "analysis_report.json") if artifact_root else None
            ),
            "execution_result_path": (
                str(artifact_root / "execution" / "execution_result.json") if artifact_root else None
            ),
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


def _run_dsl_with_optional_progress(
    dsl: dict[str, Any],
    *,
    execution_mode: str,
    progress_callback,
):
    try:
        signature = inspect.signature(run_dsl)
    except (TypeError, ValueError):
        signature = None
    if signature is not None and "progress_callback" in signature.parameters:
        return run_dsl(dsl, execution_mode=execution_mode, progress_callback=progress_callback)
    return run_dsl(dsl, execution_mode=execution_mode)


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


def _build_runtime_progress_payload(task) -> dict[str, Any]:
    execution = task.execution_result or {}
    scenario_results = execution.get("scenario_results")
    scenarios = scenario_results if isinstance(scenario_results, list) else []
    done_count = 0
    for item in scenarios:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").lower()
        if status in {"passed", "failed", "stopped"}:
            done_count += 1
    return {
        "task_id": task.task_id,
        "status": str(execution.get("status") or task.status or "received"),
        "scenario_total": len(scenarios),
        "scenario_done": done_count,
        "log_count": len(execution.get("logs") or []),
        "updated_at": _utc_now_iso(),
    }


def _build_analysis_progress_payload(
    task_id: str,
    *,
    stage: str,
    percent: int,
    status: str,
    message: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "task_id": task_id,
        "kind": "analysis",
        "stage": stage,
        "percent": max(0, min(100, int(percent))),
        "status": status,
        "message": message,
        "updated_at": _utc_now_iso(),
    }
    if detail:
        payload["detail"] = detail
    return payload


def _save_analysis_progress(
    task_id: str,
    *,
    stage: str,
    percent: int,
    status: str,
    message: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _build_analysis_progress_payload(
        task_id,
        stage=stage,
        percent=percent,
        status=status,
        message=message,
        detail=detail,
    )
    runtime_state_store.save_progress(task_id, payload)
    return payload


def _resolve_analysis_progress(task) -> dict[str, Any]:
    if task.pipeline_result is not None:
        return _build_analysis_progress_payload(
            task.task_id,
            stage="ready",
            percent=100,
            status="completed",
            message="任务解析完成，可进入详情页查看",
            detail={"scenario_count": len((task.pipeline_result or {}).get("scenarios") or [])},
        )
    cached = runtime_state_store.load_progress(task.task_id) or {}
    if cached.get("kind") == "analysis":
        return cached
    with _RUNNING_ANALYSIS_LOCK:
        future = _RUNNING_ANALYSIS_FUTURES.get(task.task_id)
    if future is not None and not future.done():
        return _build_analysis_progress_payload(
            task.task_id,
            stage="queued",
            percent=5,
            status="running",
            message="解析任务已入队，等待执行",
        )
    return _build_analysis_progress_payload(
        task.task_id,
        stage="idle",
        percent=0,
        status="idle",
        message="尚未启动解析",
    )


def _submit_analysis_job_if_needed(task_id: str) -> dict[str, Any]:
    task = _must_get_task(task_id)
    progress = _resolve_analysis_progress(task)
    if progress.get("status") == "completed":
        return progress

    with _RUNNING_ANALYSIS_LOCK:
        future = _RUNNING_ANALYSIS_FUTURES.get(task_id)
        if future is not None and future.done():
            _RUNNING_ANALYSIS_FUTURES.pop(task_id, None)
            future = None
        if future is None:
            progress = _save_analysis_progress(
                task_id,
                stage="queued",
                percent=5,
                status="running",
                message="解析任务已启动，等待后台处理",
            )
            _RUNNING_ANALYSIS_FUTURES[task_id] = _ANALYSIS_EXECUTOR.submit(_run_async_analysis_job, task_id)
            return progress

    latest_task = registry.get(task_id)
    if latest_task is None:
        return progress
    return _resolve_analysis_progress(latest_task)


def _build_runtime_context_payload(task) -> dict[str, Any]:
    execution = task.execution_result or {}
    execution_meta = ((execution.get("metadata") or {}).get("execution") or {})
    return {
        "task_id": task.task_id,
        "task_name": task.task_name,
        "status": task.status,
        "environment": task.environment,
        "task_context": dict(task.task_context or {}),
        "execution": {
            "status": execution.get("status"),
            "execution_mode": execution_meta.get("execution_mode"),
            "base_url": execution_meta.get("base_url"),
            "context": execution_meta.get("context") or {},
        },
        "updated_at": _utc_now_iso(),
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
            event_name = str(event.get("event") or "")
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

            step_id = str(event.get("step_id") or "")
            if step_id:
                previous = copied[hit_index] if hit_index >= 0 else {}
                steps = [dict(item) for item in (previous.get("steps") or []) if isinstance(item, dict)]
                step_index = next((index for index, item in enumerate(steps) if str(item.get("step_id") or "") == step_id), -1)
                step_status = {
                    "step_start": "running",
                    "request_prepared": "requesting",
                    "response_received": "response_received",
                    "context_saved": "context_saved",
                    "assertions_evaluated": "asserting",
                    "step_result": status if status in {"passed", "failed"} else "done",
                }.get(event_name, status)
                step_payload = {
                    "step_id": step_id,
                    "step_type": event.get("step_type"),
                    "text": event.get("message") or step_id,
                    "status": step_status,
                    "message": event.get("message") or "",
                    "error_category": event.get("error_category") or "",
                    "request_summary": event.get("request_summary"),
                    "response_summary": event.get("response_summary"),
                    "assertion_summary": event.get("assertion_summary"),
                    "updated_at": event.get("time") or _utc_now_iso(),
                }
                step_payload = {key: value for key, value in step_payload.items() if value not in (None, "")}
                if step_index >= 0:
                    steps[step_index] = {**steps[step_index], **step_payload}
                else:
                    steps.append(step_payload)
                merged_item["steps"] = steps
                merged_item["passed_steps"] = len([item for item in steps if item.get("status") == "passed"])
                merged_item["failed_steps"] = len([item for item in steps if item.get("status") == "failed"])
                if event_name != "scenario_result":
                    merged_item["status"] = "failed" if step_status == "failed" else "running"

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
                if event_name in {"step_start", "request_prepared", "response_received", "context_saved", "assertions_evaluated", "step_result", "scenario_result"}:
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
                _run_dsl_with_optional_progress,
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


def _with_task_context_status(task_context: dict[str, Any] | None, status: str) -> dict[str, Any]:
    payload = dict(task_context or {})
    payload["status"] = status
    return payload


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
    task.task_context = _with_task_context_status(result.get("task_context", task.task_context), task.status)
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
    progress_snapshot = _build_runtime_progress_payload(task)
    runtime_context_snapshot = _build_runtime_context_payload(task)
    runtime_state_store.save_progress(task.task_id, progress_snapshot)
    runtime_state_store.save_context(task.task_id, runtime_context_snapshot)
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
    write_json_artifact(
        str(Path(subdirs["execution"]) / "progress_snapshot.json"),
        progress_snapshot,
    )
    write_json_artifact(
        str(Path(subdirs["execution"]) / "runtime_context_snapshot.json"),
        runtime_context_snapshot,
    )
    if persist_registry:
        registry.save(task)


def _run_async_analysis_job(task_id: str) -> None:
    task = registry.get(task_id)
    if task is None:
        return
    try:
        parse_options = AnalysisParseOptions.resolve(_task_parse_option_overrides(task))
        _save_analysis_progress(
            task_id,
            stage="queued",
            percent=5,
            status="running",
            message="解析任务已启动，准备加载文档",
        )

        def _on_progress(stage: str, payload: dict[str, Any]) -> None:
            current_task = registry.get(task_id)
            if current_task is None:
                return
            percent = int(payload.get("percent", 0) or 0)
            message = str(payload.get("message") or stage)
            detail = {key: value for key, value in payload.items() if key not in {"stage", "percent", "message"}}
            if stage == "requirement_parsed":
                current_task.status = "parsed"
                current_task.task_context = _with_task_context_status(current_task.task_context, "parsed")
                registry.save(current_task)
            elif stage in {"scenarios_built", "dsl_ready", "analysis_report_ready"}:
                current_task.status = "generated"
                current_task.task_context = _with_task_context_status(current_task.task_context, "generated")
                registry.save(current_task)
            _save_analysis_progress(
                task_id,
                stage=stage,
                percent=percent,
                status="running",
                message=message,
                detail=detail or None,
            )

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
            use_llm=parse_options.use_llm,
            rag_enabled=parse_options.rag_enabled,
            retrieval_top_k=parse_options.retrieval_top_k,
            rerank_enabled=parse_options.rerank_enabled,
            model_profile=parse_options.model_profile,
            progress_callback=_on_progress,
        )
        current_task = registry.get(task_id)
        if current_task is None:
            return
        current_task.pipeline_result = result
        current_task.status = "generated"
        current_task.task_context = _with_task_context_status(result.get("task_context", current_task.task_context), "generated")
        current_task.artifact_dir = result.get("artifact_dir") or current_task.artifact_dir
        registry.save(current_task)
        _save_analysis_progress(
            task_id,
            stage="ready",
            percent=100,
            status="completed",
            message="任务解析完成，可进入详情页查看",
            detail={"scenario_count": len(result.get("scenarios") or [])},
        )
    except Exception as exc:
        current_task = registry.get(task_id)
        if current_task is not None:
            current_task.status = "failed"
            current_task.task_context = _with_task_context_status(current_task.task_context, "failed")
            registry.save(current_task)
        _save_analysis_progress(
            task_id,
            stage="failed",
            percent=100,
            status="failed",
            message=f"任务解析失败：{exc}",
        )
    finally:
        with _RUNNING_ANALYSIS_LOCK:
            _RUNNING_ANALYSIS_FUTURES.pop(task_id, None)


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


@app.post("/api/auth/register", response_model=ApiResponse)
def register_user(payload: RegisterRequest, request: Request):
    store = _db_store_or_503()
    normalized_username = payload.username.strip()
    if not normalized_username:
        raise HTTPException(status_code=400, detail="username is required")
    display_name = str(payload.display_name or normalized_username).strip() or normalized_username
    try:
        user = store.create_user(
            username=normalized_username,
            email=(payload.email.strip() if payload.email else None),
            display_name=display_name,
            password_hash=hash_password(payload.password),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    default_project = store.ensure_default_workspace_and_project(user_id=str(user["id"]), username=normalized_username)
    store.append_audit_log(
        user_id=str(user["id"]),
        action="auth.register",
        resource_type="user",
        resource_id=str(user["id"]),
        detail_json={"username": normalized_username, "default_project_id": default_project["id"]},
        ip_address=_request_ip(request),
    )
    return _success_response(
        {"user": _decorate_user_payload(user), "default_project": default_project},
        code="AUTH_REGISTERED",
        message="user registered",
        status_code=201,
    )


@app.post("/api/auth/login", response_model=ApiResponse)
def login_user(payload: LoginRequest, request: Request):
    store = _db_store_or_503()
    identity = store.get_user_credential_by_username(payload.username.strip())
    if identity is None or not verify_password(payload.password, str(identity["password_hash"])):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    refresh_token = build_refresh_token()
    refresh_hash = hash_refresh_token(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=max(auth_config.refresh_token_ttl_days, 1))
    session_payload = store.create_user_session(
        user_id=str(identity["id"]),
        refresh_token_hash=refresh_hash,
        expires_at=expires_at,
        client_type=payload.client_type,
        user_agent=request.headers.get("user-agent"),
        ip_address=_request_ip(request),
    )
    session_state_store.set_session(
        str(session_payload["id"]),
        {
            "user_id": str(identity["id"]),
            "username": str(identity["username"]),
            "expires_at": session_payload["expires_at"],
        },
        ttl_seconds=int((expires_at - datetime.now(timezone.utc)).total_seconds()),
    )
    access_token, claims = build_access_token(
        user_id=str(identity["id"]),
        username=str(identity["username"]),
        session_id=str(session_payload["id"]),
        project_ids=_current_user_project_ids(str(identity["id"])),
        config=auth_config,
    )
    store.touch_user_login(str(identity["id"]))
    store.append_audit_log(
        user_id=str(identity["id"]),
        action="auth.login",
        resource_type="session",
        resource_id=str(session_payload["id"]),
        detail_json={"client_type": payload.client_type},
        ip_address=_request_ip(request),
    )
    return _success_response(
        {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": auth_config.access_token_ttl_minutes * 60,
            "refresh_token": refresh_token,
            "user": _decorate_user_payload(store.get_user_by_id(str(identity["id"]))),
            "projects": store.list_projects_for_user(str(identity["id"])),
            "claims": claims,
        },
        code="AUTH_LOGGED_IN",
        message="login success",
    )


@app.post("/api/auth/refresh", response_model=ApiResponse)
def refresh_login(payload: RefreshTokenRequest):
    store = _db_store_or_503()
    matched_session = store.get_user_session_by_refresh_token_hash(hash_refresh_token(payload.refresh_token))
    if matched_session is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if not verify_refresh_token(payload.refresh_token, str(matched_session["refresh_token_hash"])):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if matched_session.get("revoked_at"):
        raise HTTPException(status_code=401, detail="Refresh session already revoked")
    expires_at = _parse_iso_timestamp(str(matched_session["expires_at"]))
    if expires_at is None:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")
    user = store.get_user_by_id(str(matched_session["user_id"]))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    access_token, claims = build_access_token(
        user_id=str(user["id"]),
        username=str(user["username"]),
        session_id=str(matched_session["id"]),
        project_ids=_current_user_project_ids(str(user["id"])),
        config=auth_config,
    )
    return _success_response(
        {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": auth_config.access_token_ttl_minutes * 60,
            "user": _decorate_user_payload(user),
            "projects": store.list_projects_for_user(str(user["id"])),
            "claims": claims,
        },
        code="AUTH_REFRESHED",
        message="token refreshed",
    )


@app.post("/api/auth/logout", response_model=ApiResponse)
def logout_user(request: Request, current_user: dict[str, Any] = Depends(_require_current_user)):
    store = _db_store_or_503()
    claims = current_user["claims"]
    session_id = str(claims.get("session_id") or "")
    jti = str(claims.get("jti") or "")
    if session_id:
        session_state_store.clear_session(session_id)
        store.revoke_user_session(session_id)
    if jti:
        ttl_seconds = max(int(claims.get("exp", 0) - datetime.now(timezone.utc).timestamp()), 1)
        session_state_store.revoke_token_jti(jti, ttl_seconds=ttl_seconds)
    store.append_audit_log(
        user_id=str(current_user["user"]["id"]),
        action="auth.logout",
        resource_type="session",
        resource_id=session_id or None,
        detail_json={"jti": jti},
        ip_address=_request_ip(request),
    )
    return _success_response({"logged_out": True}, code="AUTH_LOGGED_OUT", message="logout success")


@app.get("/api/auth/me", response_model=ApiResponse)
def auth_me(current_user: dict[str, Any] = Depends(_require_current_user)):
    store = _db_store_or_503()
    return _success_response(
        {
            "user": current_user["user"],
            "projects": store.list_projects_for_user(str(current_user["user"]["id"])),
            "claims": current_user["claims"],
        },
        code="AUTH_ME_OK",
        message="current user",
    )


@app.get("/api/users/me", response_model=ApiResponse)
def get_my_profile(current_user: dict[str, Any] = Depends(_require_current_user)):
    return _success_response(current_user["user"], code="USER_ME_OK", message="user profile")


@app.get("/api/users", response_model=ApiResponse)
def list_users(
    keyword: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    store = _db_store_or_503()
    payload = store.list_users(keyword=keyword, limit=limit)
    return _success_response(payload, code="USERS_OK", message="users listed")


@app.patch("/api/users/me", response_model=ApiResponse)
def update_my_profile(
    payload: UpdateProfileRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    store = _db_store_or_503()
    try:
        updated = store.update_user_profile(
            user_id=str(current_user["user"]["id"]),
            display_name=payload.display_name,
            email=payload.email,
            avatar_url=payload.avatar_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="user.profile.update",
        resource_type="user",
        resource_id=str(current_user["user"]["id"]),
        detail_json={"display_name": updated.get("display_name"), "email": updated.get("email")},
        ip_address=_request_ip(request),
    )
    return _success_response(updated, code="USER_ME_UPDATED", message="user profile updated")


@app.post("/api/users/me/avatar", response_model=ApiResponse)
async def upload_my_avatar(
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    content_type = str(request.headers.get("content-type") or "")
    extension = _safe_avatar_extension(content_type)
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Avatar image is empty")
    if len(body) > AVATAR_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Avatar image must be <= 2MB")

    store = _db_store_or_503()
    user_id = str(current_user["user"]["id"])
    filename = f"{user_id}_{uuid.uuid4().hex}{extension}"
    avatar_path = AVATAR_UPLOAD_ROOT / filename
    avatar_path.write_bytes(body)
    avatar_url = str(request.url_for("static", path=f"avatars/{filename}"))
    updated = store.update_user_profile(user_id=user_id, avatar_url=avatar_url)
    _append_audit_log_safe(
        user_id=user_id,
        action="user.avatar.upload",
        resource_type="user",
        resource_id=user_id,
        detail_json={"avatar_url": avatar_url, "content_type": content_type.split(";")[0].strip().lower(), "size": len(body)},
        ip_address=_request_ip(request),
    )
    return _success_response(_decorate_user_payload(updated), code="USER_AVATAR_UPLOADED", message="avatar uploaded")


@app.get("/api/projects", response_model=ApiResponse)
def list_projects(current_user: dict[str, Any] = Depends(_require_current_user)):
    store = _db_store_or_503()
    return _success_response(
        store.list_projects_for_user(str(current_user["user"]["id"])),
        code="PROJECTS_OK",
        message="projects listed",
    )


@app.post("/api/projects", response_model=ApiResponse)
def create_project(
    payload: CreateProjectRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    store = _db_store_or_503()
    project = store.create_project(
        user_id=str(current_user["user"]["id"]),
        name=payload.name.strip(),
        description=payload.description,
    )
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="project.create",
        resource_type="project",
        resource_id=str(project["id"]),
        detail_json={"name": project["name"]},
        ip_address=_request_ip(request),
    )
    return _success_response(project, code="PROJECT_CREATED", message="project created", status_code=201)


@app.get("/api/projects/{project_id}", response_model=ApiResponse)
def get_project(project_id: str, current_user: dict[str, Any] = Depends(_require_current_user)):
    store = _db_store_or_503()
    project = _ensure_project_access(project_id, current_user)
    members = store.list_project_members(project_id)
    return _success_response(
        {"project": project, "members": members},
        code="PROJECT_OK",
        message="project fetched",
    )


@app.post("/api/projects/{project_id}/members", response_model=ApiResponse)
def add_project_member(
    project_id: str,
    payload: AddProjectMemberRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    store = _db_store_or_503()
    project = _ensure_project_access(project_id, current_user)
    if project.get("role") not in {"owner", "editor"}:
        raise HTTPException(status_code=403, detail="Only owner/editor can manage members")
    target_user = store.get_user_by_username(payload.username.strip())
    if target_user is None:
        raise HTTPException(status_code=404, detail=f"User not found: {payload.username}")
    member = store.add_project_member(project_id=project_id, user_id=str(target_user["id"]), role=payload.role)
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="project.member.save",
        resource_type="project_member",
        resource_id=f"{project_id}:{target_user['id']}",
        detail_json={"project_id": project_id, "target_user": payload.username.strip(), "role": payload.role},
        ip_address=_request_ip(request),
    )
    return _success_response(member, code="PROJECT_MEMBER_SAVED", message="project member saved", status_code=201)


@app.get("/api/defects", response_model=ApiResponse)
def list_defects(
    project_id: str,
    status: str | None = None,
    severity: str | None = None,
    keyword: str | None = None,
    task_id: str | None = None,
    assignee_user_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    _ensure_project_access(project_id, current_user)
    store = _db_store_or_503()
    payload = store.list_defects(
        project_id=project_id,
        status=_normalize_defect_status(status) if status else None,
        severity=_normalize_defect_severity(severity) if severity else None,
        keyword=keyword,
        task_uid=_validate_defect_task_reference(task_id, project_id=project_id) if task_id else None,
        assignee_user_id=_validate_defect_assignee(
            assignee_user_id=assignee_user_id,
            project_id=project_id,
            current_user=current_user,
        )
        if assignee_user_id
        else None,
        page=page,
        page_size=page_size,
    )
    return _success_response(payload, code="DEFECTS_OK", message="defects listed")


@app.post("/api/defects", response_model=ApiResponse)
def create_defect(
    payload: CreateDefectRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="title is required")
    _ensure_project_access(payload.project_id, current_user)
    store = _db_store_or_503()
    try:
        defect = store.create_defect(
            project_id=payload.project_id,
            reporter_user_id=str(current_user["user"]["id"]),
            title=payload.title.strip(),
            description=str(payload.description or "").strip() or None,
            severity=_normalize_defect_severity(payload.severity),
            status=_normalize_defect_status(payload.status),
            source=str(payload.source or "manual").strip() or "manual",
            task_uid=_validate_defect_task_reference(payload.task_id, project_id=payload.project_id),
            assignee_user_id=_validate_defect_assignee(
                assignee_user_id=payload.assignee_user_id,
                project_id=payload.project_id,
                current_user=current_user,
            ),
            reproduction_steps=str(payload.reproduction_steps or "").strip() or None,
            expected_result=str(payload.expected_result or "").strip() or None,
            actual_result=str(payload.actual_result or "").strip() or None,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="defect.create",
        resource_type="defect",
        resource_id=str(defect["id"]),
        detail_json={
            "defect_key": defect["defect_key"],
            "project_id": defect["project_id"],
            "task_id": defect.get("task_id"),
            "severity": defect["severity"],
            "status": defect["status"],
        },
        ip_address=_request_ip(request),
    )
    return _success_response(defect, code="DEFECT_CREATED", message="defect created", status_code=201)


@app.get("/api/defects/{defect_id}", response_model=ApiResponse)
def get_defect(defect_id: str, current_user: dict[str, Any] = Depends(_require_current_user)):
    store = _db_store_or_503()
    defect = store.get_defect(defect_id)
    if defect is None:
        raise HTTPException(status_code=404, detail=f"Defect not found: {defect_id}")
    _ensure_project_access(str(defect["project_id"]), current_user)
    return _success_response(defect, code="DEFECT_OK", message="defect fetched")


@app.patch("/api/defects/{defect_id}", response_model=ApiResponse)
def update_defect(
    defect_id: str,
    payload: UpdateDefectRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    store = _db_store_or_503()
    existing = store.get_defect(defect_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Defect not found: {defect_id}")
    if payload.title is not None and not payload.title.strip():
        raise HTTPException(status_code=400, detail="title cannot be empty")
    project_id = str(existing["project_id"])
    _ensure_project_access(project_id, current_user)
    try:
        defect = store.update_defect(
            defect_id,
            task_uid=_validate_defect_task_reference(payload.task_id, project_id=project_id) if payload.task_id is not None else None,
            clear_task=bool(payload.clear_task),
            title=payload.title.strip() if payload.title is not None else None,
            description=str(payload.description or "").strip() if payload.description is not None else None,
            severity=_normalize_defect_severity(payload.severity) if payload.severity is not None else None,
            status=_normalize_defect_status(payload.status) if payload.status is not None else None,
            source=str(payload.source or "").strip() if payload.source is not None else None,
            assignee_user_id=_validate_defect_assignee(
                assignee_user_id=payload.assignee_user_id,
                project_id=project_id,
                current_user=current_user,
            )
            if payload.assignee_user_id is not None and str(payload.assignee_user_id).strip()
            else None,
            clear_assignee=bool(payload.clear_assignee),
            reproduction_steps=str(payload.reproduction_steps or "").strip() if payload.reproduction_steps is not None else None,
            expected_result=str(payload.expected_result or "").strip() if payload.expected_result is not None else None,
            actual_result=str(payload.actual_result or "").strip() if payload.actual_result is not None else None,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="defect.update",
        resource_type="defect",
        resource_id=str(defect["id"]),
        detail_json={
            "defect_key": defect["defect_key"],
            "status": defect["status"],
            "severity": defect["severity"],
            "assignee_user_id": defect.get("assignee_user_id"),
            "task_id": defect.get("task_id"),
        },
        ip_address=_request_ip(request),
    )
    return _success_response(defect, code="DEFECT_UPDATED", message="defect updated")


@app.get("/api/interface-assets", response_model=ApiResponse)
def list_interface_assets(
    project_id: str,
    method: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    _ensure_project_access(project_id, current_user)
    store = _db_store_or_503()
    payload = store.list_interface_assets(
        project_id=project_id,
        method=_normalize_interface_method(method) if method else None,
        status=_normalize_interface_status(status) if status else None,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return _success_response(payload, code="INTERFACE_ASSETS_OK", message="interface assets listed")


@app.post("/api/interface-assets", response_model=ApiResponse)
def create_interface_asset(
    payload: CreateInterfaceAssetRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    _ensure_project_editor(payload.project_id, current_user)
    store = _db_store_or_503()
    asset = store.upsert_interface_asset(
        project_id=payload.project_id,
        method=_normalize_interface_method(payload.method),
        path=_normalize_interface_path(payload.path),
        name=payload.name.strip() or None,
        description=payload.description.strip() or None,
        source=str(payload.source or "manual").strip() or "manual",
        status=_normalize_interface_status(payload.status),
        version=str(payload.version or "default").strip() or "default",
        tags=_clean_interface_tags(payload.tags),
        request_example=payload.request_example,
        response_example=payload.response_example,
        schema=payload.schema,
        created_by=str(current_user["user"]["id"]),
    )
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="interface_asset.upsert",
        resource_type="interface_asset",
        resource_id=str(asset["id"]),
        detail_json={"project_id": payload.project_id, "method": asset["method"], "path": asset["path"]},
        ip_address=_request_ip(request),
    )
    return _success_response(asset, code="INTERFACE_ASSET_SAVED", message="interface asset saved", status_code=201)


@app.patch("/api/interface-assets/{asset_id}", response_model=ApiResponse)
def update_interface_asset(
    asset_id: str,
    payload: UpdateInterfaceAssetRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    store = _db_store_or_503()
    existing = store.get_interface_asset(asset_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Interface asset not found: {asset_id}")
    _ensure_project_editor(str(existing["project_id"]), current_user)
    changes: dict[str, Any] = {}
    if payload.name is not None:
        changes["name"] = payload.name.strip()
    if payload.description is not None:
        changes["description"] = payload.description.strip()
    if payload.source is not None:
        changes["source"] = str(payload.source or "manual").strip() or "manual"
    if payload.status is not None:
        changes["status"] = _normalize_interface_status(payload.status)
    if payload.version is not None:
        changes["version"] = str(payload.version or "default").strip() or "default"
    if payload.tags is not None:
        changes["tags"] = _clean_interface_tags(payload.tags)
    explicit_fields = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))
    for key in ("request_example", "response_example", "schema"):
        if key in explicit_fields:
            changes[key] = getattr(payload, key)
    asset = store.update_interface_asset(asset_id, **changes)
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="interface_asset.update",
        resource_type="interface_asset",
        resource_id=asset_id,
        detail_json={"project_id": existing["project_id"], "changed": sorted(changes.keys())},
        ip_address=_request_ip(request),
    )
    return _success_response(asset, code="INTERFACE_ASSET_UPDATED", message="interface asset updated")


@app.get("/api/test-case-assets", response_model=ApiResponse)
def list_test_case_assets(
    project_id: str,
    status: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    _ensure_project_access(project_id, current_user)
    store = _db_store_or_503()
    payload = store.list_test_case_assets(
        project_id=project_id,
        status=_normalize_test_case_status(status) if status else None,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return _success_response(payload, code="TEST_CASE_ASSETS_OK", message="test case assets listed")


@app.post("/api/test-case-assets", response_model=ApiResponse)
def create_test_case_asset(
    payload: CreateTestCaseAssetRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    _ensure_project_editor(payload.project_id, current_user)
    store = _db_store_or_503()
    case_key = _normalize_test_case_key(payload.case_key, f"case-{int(time.time())}")
    dsl_scenario = payload.dsl_scenario if isinstance(payload.dsl_scenario, dict) else {}
    assertions = payload.assertions or _assertions_from_dsl_scenario(dsl_scenario)
    asset = store.upsert_test_case_asset(
        project_id=payload.project_id,
        case_key=case_key,
        name=payload.name.strip(),
        description=payload.description.strip() or None,
        priority=_normalize_test_case_priority(payload.priority),
        status=_normalize_test_case_status(payload.status),
        source=str(payload.source or "manual").strip() or "manual",
        tags=_clean_test_case_tags(payload.tags),
        dsl_scenario=dsl_scenario,
        assertions=assertions,
        created_by=str(current_user["user"]["id"]),
    )
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="test_case_asset.upsert",
        resource_type="test_case_asset",
        resource_id=str(asset["id"]),
        detail_json={"project_id": payload.project_id, "case_key": asset["case_key"]},
        ip_address=_request_ip(request),
    )
    return _success_response(asset, code="TEST_CASE_ASSET_SAVED", message="test case asset saved", status_code=201)


@app.patch("/api/test-case-assets/{case_id}", response_model=ApiResponse)
def update_test_case_asset(
    case_id: str,
    payload: UpdateTestCaseAssetRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    store = _db_store_or_503()
    existing = store.get_test_case_asset(case_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Test case asset not found: {case_id}")
    _ensure_project_editor(str(existing["project_id"]), current_user)
    changes: dict[str, Any] = {}
    if payload.name is not None:
        changes["name"] = payload.name.strip()
    if payload.description is not None:
        changes["description"] = payload.description.strip()
    if payload.priority is not None:
        changes["priority"] = _normalize_test_case_priority(payload.priority)
    if payload.status is not None:
        changes["status"] = _normalize_test_case_status(payload.status)
    if payload.source is not None:
        changes["source"] = str(payload.source or "manual").strip() or "manual"
    if payload.tags is not None:
        changes["tags"] = _clean_test_case_tags(payload.tags)
    explicit_fields = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))
    if "dsl_scenario" in explicit_fields:
        changes["dsl_scenario"] = payload.dsl_scenario if isinstance(payload.dsl_scenario, dict) else {}
    if payload.assertions is not None:
        changes["assertions"] = payload.assertions
    asset = store.update_test_case_asset(case_id, **changes)
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="test_case_asset.update",
        resource_type="test_case_asset",
        resource_id=case_id,
        detail_json={"project_id": existing["project_id"], "changed": sorted(changes.keys())},
        ip_address=_request_ip(request),
    )
    return _success_response(asset, code="TEST_CASE_ASSET_UPDATED", message="test case asset updated")


@app.delete("/api/test-case-assets/{case_id}", response_model=ApiResponse)
def delete_test_case_asset(
    case_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    store = _db_store_or_503()
    existing = store.get_test_case_asset(case_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Test case asset not found: {case_id}")
    _ensure_project_editor(str(existing["project_id"]), current_user)
    deleted = store.delete_test_case_asset(case_id)
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="test_case_asset.delete",
        resource_type="test_case_asset",
        resource_id=case_id,
        detail_json={"project_id": existing["project_id"], "case_key": existing["case_key"]},
        ip_address=_request_ip(request),
    )
    return _success_response({"id": case_id, "deleted": deleted}, code="TEST_CASE_ASSET_DELETED", message="test case asset deleted")


@app.post("/api/tasks/{task_id}/test-case-assets/import", response_model=ApiResponse)
def import_test_case_assets_from_task(
    task_id: str,
    payload: ImportTestCaseAssetsFromTaskRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    task = _must_get_task(task_id)
    _ensure_task_visible_to_user(task, current_user)
    project_id = str(payload.project_id or task.project_id or "").strip()
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    _ensure_project_editor(project_id, current_user)
    dsl = (task.pipeline_result or {}).get("test_case_dsl") or {}
    scenarios = dsl.get("scenarios") if isinstance(dsl, dict) else []
    if not isinstance(scenarios, list):
        scenarios = []
    store = _db_store_or_503()
    imported: list[dict[str, Any]] = []
    for index, scenario in enumerate(scenarios, start=1):
        if not isinstance(scenario, dict):
            continue
        scenario_id = str(scenario.get("scenario_id") or f"scenario-{index:03d}")
        case_key = _normalize_test_case_key(f"{task.task_id}:{scenario_id}", f"{task.task_id}-{index:03d}")
        imported.append(
            store.upsert_test_case_asset(
                project_id=project_id,
                case_key=case_key,
                name=str(scenario.get("name") or scenario_id),
                description=str(scenario.get("goal") or ""),
                priority=_normalize_test_case_priority(str(scenario.get("priority") or "P1")),
                status="active",
                source="task_import",
                source_task_id=task.task_id,
                tags=["task-import"],
                dsl_scenario=scenario,
                assertions=_assertions_from_dsl_scenario(scenario),
                created_by=str(current_user["user"]["id"]),
            )
        )
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="test_case_asset.import_from_task",
        resource_type="task",
        resource_id=task.task_id,
        detail_json={"project_id": project_id, "imported_count": len(imported)},
        ip_address=_request_ip(request),
    )
    return _success_response(
        {"task_id": task.task_id, "project_id": project_id, "items": imported, "imported_count": len(imported)},
        code="TEST_CASE_ASSETS_IMPORTED",
        message="test case assets imported",
    )


@app.post("/api/test-case-assets/{case_id}/execute", response_model=ApiResponse)
def execute_test_case_asset(
    case_id: str,
    payload: ExecuteTestCaseAssetRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    store = _db_store_or_503()
    asset = store.get_test_case_asset(case_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Test case asset not found: {case_id}")
    _ensure_project_access(str(asset["project_id"]), current_user)
    execution_result = _execute_case_asset_payload(
        asset,
        execution_mode=payload.execution_mode,
        environment=payload.environment,
        base_url=payload.base_url,
    )
    result = {
        "case": asset,
        "execution_result": execution_result,
        "executed_at": _utc_now_iso(),
    }
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="test_case_asset.execute",
        resource_type="test_case_asset",
        resource_id=case_id,
        detail_json={
            "project_id": asset["project_id"],
            "case_key": asset["case_key"],
            "status": execution_result.get("status"),
            "environment": payload.environment,
        },
        ip_address=_request_ip(request),
    )
    return _success_response(result, code="TEST_CASE_ASSET_EXECUTED", message="test case asset executed")


@app.get("/api/test-suite-assets", response_model=ApiResponse)
def list_test_suite_assets(
    project_id: str,
    status: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    _ensure_project_access(project_id, current_user)
    store = _db_store_or_503()
    payload = store.list_test_suite_assets(
        project_id=project_id,
        status=_normalize_test_suite_status(status) if status else None,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return _success_response(payload, code="TEST_SUITE_ASSETS_OK", message="test suite assets listed")


@app.post("/api/test-suite-assets", response_model=ApiResponse)
def create_test_suite_asset(
    payload: CreateTestSuiteAssetRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    _ensure_project_editor(payload.project_id, current_user)
    store = _db_store_or_503()
    case_ids = _clean_case_ids(payload.case_ids)
    for case_id in case_ids:
        case = store.get_test_case_asset(case_id)
        if case is None or str(case["project_id"]) != str(payload.project_id):
            raise HTTPException(status_code=400, detail=f"invalid case_id for this project: {case_id}")
    suite = store.create_test_suite_asset(
        project_id=payload.project_id,
        name=payload.name.strip(),
        description=payload.description.strip() or None,
        status=_normalize_test_suite_status(payload.status),
        source=str(payload.source or "manual").strip() or "manual",
        case_ids=case_ids,
        tags=_clean_test_case_tags(payload.tags),
        created_by=str(current_user["user"]["id"]),
    )
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="test_suite_asset.create",
        resource_type="test_suite_asset",
        resource_id=str(suite["id"]),
        detail_json={"project_id": payload.project_id, "case_count": len(case_ids)},
        ip_address=_request_ip(request),
    )
    return _success_response(suite, code="TEST_SUITE_ASSET_CREATED", message="test suite asset created", status_code=201)


@app.patch("/api/test-suite-assets/{suite_id}", response_model=ApiResponse)
def update_test_suite_asset(
    suite_id: str,
    payload: UpdateTestSuiteAssetRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    store = _db_store_or_503()
    existing = store.get_test_suite_asset(suite_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Test suite asset not found: {suite_id}")
    _ensure_project_editor(str(existing["project_id"]), current_user)
    changes: dict[str, Any] = {}
    if payload.name is not None:
        changes["name"] = payload.name.strip()
    if payload.description is not None:
        changes["description"] = payload.description.strip()
    if payload.status is not None:
        changes["status"] = _normalize_test_suite_status(payload.status)
    if payload.source is not None:
        changes["source"] = str(payload.source or "manual").strip() or "manual"
    if payload.tags is not None:
        changes["tags"] = _clean_test_case_tags(payload.tags)
    if payload.case_ids is not None:
        case_ids = _clean_case_ids(payload.case_ids)
        for case_id in case_ids:
            case = store.get_test_case_asset(case_id)
            if case is None or str(case["project_id"]) != str(existing["project_id"]):
                raise HTTPException(status_code=400, detail=f"invalid case_id for this project: {case_id}")
        changes["case_ids"] = case_ids
    suite = store.update_test_suite_asset(suite_id, **changes)
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="test_suite_asset.update",
        resource_type="test_suite_asset",
        resource_id=suite_id,
        detail_json={"project_id": existing["project_id"], "changed": sorted(changes.keys())},
        ip_address=_request_ip(request),
    )
    return _success_response(suite, code="TEST_SUITE_ASSET_UPDATED", message="test suite asset updated")


@app.delete("/api/test-suite-assets/{suite_id}", response_model=ApiResponse)
def delete_test_suite_asset(
    suite_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    store = _db_store_or_503()
    existing = store.get_test_suite_asset(suite_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Test suite asset not found: {suite_id}")
    _ensure_project_editor(str(existing["project_id"]), current_user)
    deleted = store.delete_test_suite_asset(suite_id)
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="test_suite_asset.delete",
        resource_type="test_suite_asset",
        resource_id=suite_id,
        detail_json={"project_id": existing["project_id"], "name": existing["name"]},
        ip_address=_request_ip(request),
    )
    return _success_response({"id": suite_id, "deleted": deleted}, code="TEST_SUITE_ASSET_DELETED", message="test suite asset deleted")


@app.post("/api/test-suite-assets/{suite_id}/execute", response_model=ApiResponse)
def execute_test_suite_asset(
    suite_id: str,
    payload: ExecuteTestSuiteAssetRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    store = _db_store_or_503()
    suite = store.get_test_suite_asset(suite_id)
    if suite is None:
        raise HTTPException(status_code=404, detail=f"Test suite asset not found: {suite_id}")
    _ensure_project_access(str(suite["project_id"]), current_user)
    case_results: list[dict[str, Any]] = []
    overall_status = "passed"
    started_at = time.perf_counter()
    for case_id in suite.get("case_ids") or []:
        case = store.get_test_case_asset(str(case_id))
        if case is None:
            case_results.append({"case_id": case_id, "status": "failed", "error": "case not found"})
            overall_status = "failed"
            if payload.stop_on_failure:
                break
            continue
        try:
            execution_result = _execute_case_asset_payload(
                case,
                execution_mode=payload.execution_mode,
                environment=payload.environment,
                base_url=payload.base_url,
            )
            status = str(execution_result.get("status") or "failed")
            if status != "passed":
                overall_status = "failed"
            case_results.append({"case": case, "status": status, "execution_result": execution_result})
            if status != "passed" and payload.stop_on_failure:
                break
        except HTTPException as exc:
            overall_status = "failed"
            case_results.append({"case": case, "status": "failed", "error": exc.detail})
            if payload.stop_on_failure:
                break
    result = {
        "suite": suite,
        "status": overall_status,
        "case_results": case_results,
        "metrics": {
            "case_count": len(case_results),
            "passed": len([item for item in case_results if item.get("status") == "passed"]),
            "failed": len([item for item in case_results if item.get("status") != "passed"]),
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
        },
        "executed_at": _utc_now_iso(),
    }
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="test_suite_asset.execute",
        resource_type="test_suite_asset",
        resource_id=suite_id,
        detail_json={"project_id": suite["project_id"], "status": overall_status, "case_count": len(case_results)},
        ip_address=_request_ip(request),
    )
    return _success_response(result, code="TEST_SUITE_ASSET_EXECUTED", message="test suite asset executed")


@app.post("/api/interface-assets/{asset_id}/debug", response_model=ApiResponse)
def debug_interface_asset(
    asset_id: str,
    payload: DebugInterfaceAssetRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    store = _db_store_or_503()
    asset = store.get_interface_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Interface asset not found: {asset_id}")
    _ensure_project_access(str(asset["project_id"]), current_user)

    env_config: EnvironmentConfig | None = None
    if payload.environment:
        env_config = registry.get_environment(str(payload.environment), project_id=str(asset["project_id"]))
        if env_config is None:
            raise HTTPException(status_code=404, detail=f"Environment not found: {payload.environment}")

    base_url = str(payload.base_url or "").strip() or (env_config.base_url if env_config else "")
    headers = _safe_debug_headers(env_config.default_headers if env_config else {})
    headers.update(_safe_debug_headers(payload.headers))
    auth_obj = _ensure_json_dict(env_config.auth if env_config else {})
    cookies = _ensure_json_dict(env_config.cookies if env_config else {})
    headers, request_auth = _apply_debug_auth(headers, auth_obj)
    url = _resolve_interface_debug_url(asset, base_url=base_url, params=_ensure_json_dict(payload.params))
    method = str(asset["method"]).upper()
    started = time.perf_counter()
    error = ""
    status_code = 0
    response_headers: dict[str, str] = {}
    body_preview = ""
    response_json: Any = None
    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            cookies=cookies,
            json=payload.json_body if payload.json_body is not None else None,
            data=payload.raw_body if payload.json_body is None else None,
            timeout=(min(float(payload.timeout), 5.0), float(payload.timeout)),
            allow_redirects=True,
            auth=request_auth,
        )
        status_code = int(response.status_code)
        response_headers = dict(response.headers)
        body_preview = response.text[:4000]
        try:
            response_json = response.json()
        except ValueError:
            response_json = None
    except requests.RequestException as exc:
        error = str(exc)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    result = {
        "asset": asset,
        "request": {
            "method": method,
            "url": url,
            "headers": {key: value for key, value in headers.items() if key.lower() != "authorization"},
            "has_auth": bool(request_auth or any(key.lower() == "authorization" for key in headers)),
        },
        "response": {
            "status_code": status_code,
            "headers": response_headers,
            "json": response_json,
            "body_preview": body_preview,
            "elapsed_ms": elapsed_ms,
            "error": error,
            "ok": bool(status_code and status_code < 400 and not error),
        },
    }
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="interface_asset.debug",
        resource_type="interface_asset",
        resource_id=asset_id,
        detail_json={"project_id": asset["project_id"], "status_code": status_code, "elapsed_ms": elapsed_ms, "error": bool(error)},
        ip_address=_request_ip(request),
    )
    return _success_response(result, code="INTERFACE_ASSET_DEBUG_OK", message="interface asset debug completed")


@app.delete("/api/interface-assets/{asset_id}", response_model=ApiResponse)
def delete_interface_asset(
    asset_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    store = _db_store_or_503()
    existing = store.get_interface_asset(asset_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Interface asset not found: {asset_id}")
    _ensure_project_editor(str(existing["project_id"]), current_user)
    deleted = store.delete_interface_asset(asset_id)
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="interface_asset.delete",
        resource_type="interface_asset",
        resource_id=asset_id,
        detail_json={"project_id": existing["project_id"], "method": existing["method"], "path": existing["path"]},
        ip_address=_request_ip(request),
    )
    return _success_response({"id": asset_id, "deleted": deleted}, code="INTERFACE_ASSET_DELETED", message="interface asset deleted")


@app.post("/api/tasks/{task_id}/interface-assets/import", response_model=ApiResponse)
def import_interface_assets_from_task(
    task_id: str,
    payload: ImportInterfaceAssetsFromTaskRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    task = _must_get_task(task_id)
    _ensure_task_visible_to_user(task, current_user)
    project_id = str(payload.project_id or task.project_id or "").strip()
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    _ensure_project_editor(project_id, current_user)
    store = _db_store_or_503()
    imported: list[dict[str, Any]] = []
    for method, path in _extract_interface_signatures_from_task(task):
        imported.append(
            store.upsert_interface_asset(
                project_id=project_id,
                method=method,
                path=path,
                name=f"{method} {path}",
                source="task_import",
                status="active",
                version="default",
                tags=["task-import"],
                last_seen_task_id=task.task_id,
                created_by=str(current_user["user"]["id"]),
            )
        )
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="interface_asset.import_from_task",
        resource_type="task",
        resource_id=task.task_id,
        detail_json={"project_id": project_id, "imported_count": len(imported)},
        ip_address=_request_ip(request),
    )
    return _success_response(
        {"task_id": task.task_id, "project_id": project_id, "items": imported, "imported_count": len(imported)},
        code="INTERFACE_ASSETS_IMPORTED",
        message="interface assets imported",
    )


@app.post("/api/interface-assets/import/openapi", response_model=ApiResponse)
def import_interface_assets_from_openapi(
    payload: ImportOpenApiInterfaceAssetsRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(_require_current_user),
):
    _ensure_project_editor(payload.project_id, current_user)
    document = _parse_openapi_content(payload.content)
    candidates = _extract_openapi_interface_assets(document)
    store = _db_store_or_503()
    imported: list[dict[str, Any]] = []
    for item in candidates:
        existing = store.get_interface_asset_by_signature(
            project_id=payload.project_id,
            method=item["method"],
            path=item["path"],
            version=str(payload.version or "default").strip() or "default",
        )
        request_example = item.get("request_example") if payload.overwrite_examples or existing is None else None
        response_example = item.get("response_example") if payload.overwrite_examples or existing is None else None
        imported.append(
            store.upsert_interface_asset(
                project_id=payload.project_id,
                method=item["method"],
                path=item["path"],
                name=item.get("name"),
                description=item.get("description"),
                source=str(payload.source_name or "openapi").strip() or "openapi",
                status="active",
                version=str(payload.version or "default").strip() or "default",
                tags=item.get("tags") or ["openapi"],
                request_example=request_example,
                response_example=response_example,
                schema=item.get("schema") if payload.overwrite_examples or existing is None else None,
                created_by=str(current_user["user"]["id"]),
            )
        )
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]),
        action="interface_asset.import_openapi",
        resource_type="interface_asset",
        resource_id=payload.project_id,
        detail_json={"project_id": payload.project_id, "source_name": payload.source_name, "imported_count": len(imported)},
        ip_address=_request_ip(request),
    )
    return _success_response(
        {
            "project_id": payload.project_id,
            "source_name": payload.source_name,
            "items": imported,
            "imported_count": len(imported),
            "endpoint_count": len(candidates),
        },
        code="INTERFACE_ASSETS_OPENAPI_IMPORTED",
        message="openapi interface assets imported",
    )


@app.api_route("/mock/{project_id}/{mock_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
def serve_interface_asset_mock(project_id: str, mock_path: str, request: Request):
    method = _normalize_interface_method(request.method)
    path = _normalize_interface_path(mock_path)
    store = _db_store_or_503()
    asset = store.get_interface_asset_by_signature(project_id=project_id, method=method, path=path)
    if asset is None:
        return JSONResponse(
            {
                "mock": True,
                "matched": False,
                "method": method,
                "path": path,
                "message": "No interface asset matched this mock request.",
            },
            status_code=404,
        )
    payload, status_code = _build_mock_payload(asset)
    return JSONResponse(payload, status_code=max(100, min(int(status_code), 599)))


@app.post("/api/tasks", response_model=ApiResponse)
def create_task(
    payload: CreateTaskRequest,
    request: Request,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
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
    assigned_project_id = payload.project_id
    created_by = None
    if current_user is not None:
        created_by = str(current_user["user"]["id"])
        if assigned_project_id:
            _ensure_project_access(assigned_project_id, current_user)
        else:
            store = _db_store_or_503()
            default_project = store.ensure_default_workspace_and_project(
                user_id=created_by,
                username=str(current_user["user"]["username"]),
            )
            assigned_project_id = str(default_project["id"])
    record = registry.create_task(
        task_id=context["task_id"],
        task_name=context["task_name"],
        source_type=payload.source_type,
        requirement_text=payload.requirement_text,
        source_path=payload.source_path,
        target_system=payload.target_system,
        environment=payload.environment,
        project_id=assigned_project_id,
        created_by=created_by,
        task_context=context,
    )
    _append_audit_log_safe(
        user_id=created_by,
        action="task.create",
        resource_type="task",
        resource_id=record.task_id,
        detail_json={"task_name": record.task_name, "project_id": record.project_id, "source_type": record.source_type},
        ip_address=_request_ip(request),
    )
    analysis_progress: dict[str, Any] | None = None
    try:
        analysis_progress = _submit_analysis_job_if_needed(record.task_id)
    except Exception:
        analysis_progress = None
    return _success_response(
        {
            "task_id": record.task_id,
            "task_context": record.task_context,
            "project_id": record.project_id,
            "created_by": record.created_by,
            "analysis_progress": analysis_progress,
        },
        code="TASK_CREATED",
        message="task created",
        status_code=201,
    )


@app.post("/api/tasks/agent/draft", response_model=ApiResponse)
def suggest_task_draft(
    payload: TaskDraftAgentRequest,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    project_id = str(payload.project_id or "").strip() or None
    if project_id:
        if current_user is None:
            raise HTTPException(status_code=401, detail="project-scoped task draft suggestions require authenticated access")
        _ensure_project_access(project_id, current_user)
    result = _build_task_draft_agent_payload(payload, project_id=project_id)
    return _success_response(result, code="TASK_DRAFT_AGENT_OK", message="task draft suggestions ready")


@app.post("/api/tasks/agent/chat", response_model=ApiResponse)
def chat_with_task_agent(
    payload: TaskAgentChatRequest,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    project_id = str(payload.project_id or "").strip() or None
    if project_id:
        if current_user is None:
            raise HTTPException(status_code=401, detail="project-scoped task agent chat requires authenticated access")
        _ensure_project_access(project_id, current_user)
    agent_payload = _build_task_draft_agent_payload(payload, project_id=project_id)
    reply = _build_task_agent_chat_reply(payload.message, agent_payload)
    return _success_response(
        {
            "reply": reply,
            "agent_payload": agent_payload,
        },
        code="TASK_AGENT_CHAT_OK",
        message="task agent chat reply ready",
    )


@app.get("/api/tasks", response_model=ApiResponse)
def list_tasks(
    status: TaskStatus | None = None,
    keyword: str | None = None,
    environment: str | None = None,
    project_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    items = registry.list(status=status.value if status else None, keyword=keyword)
    if current_user is not None:
        visible_project_ids = set(_current_user_project_ids(str(current_user["user"]["id"])))
        visible_user_id = str(current_user["user"]["id"])
        items = [
            item
            for item in items
            if (item.created_by and str(item.created_by) == visible_user_id)
            or (item.project_id and str(item.project_id) in visible_project_ids)
        ]
    if environment:
        items = [item for item in items if item.environment == environment]
    if project_id:
        items = [item for item in items if item.project_id == project_id]
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
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    task = _must_get_task(task_id)
    _ensure_task_visible_to_user(task, current_user)
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
def delete_task(
    task_id: str,
    request: Request,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    task = _must_get_task(task_id)
    _ensure_task_visible_to_user(task, current_user)
    if not registry.archive(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]) if current_user is not None else None,
        action="task.archive",
        resource_type="task",
        resource_id=task_id,
        detail_json={"project_id": task.project_id, "task_name": task.task_name},
        ip_address=_request_ip(request),
    )
    return _success_response({"task_id": task_id, "archived": True}, code="TASK_ARCHIVED", message="task archived")


@app.post("/api/tasks/{task_id}/parse", response_model=ApiResponse)
def parse_task(
    task_id: str,
    payload: TaskParseRequest | None = None,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    task = _must_get_visible_task(task_id, current_user)
    parse_options = _resolve_parse_options(payload)
    result = _ensure_pipeline(task, parse_options=parse_options)
    return _success_response({
        "task_id": task_id,
        "status": task.status,
        "parsed_requirement": result.get("parsed_requirement"),
        "parse_metadata": _parse_metadata_payload(result.get("parse_metadata", {})),
    }, code="TASK_PARSED", message="task parsed")


@app.post("/api/tasks/{task_id}/analysis/start", response_model=ApiResponse)
def start_task_analysis(
    task_id: str,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    task = _must_get_visible_task(task_id, current_user)
    progress = _resolve_analysis_progress(task)
    if progress.get("status") == "completed":
        return _success_response(progress, code="TASK_ANALYSIS_READY", message="analysis already completed")
    progress = _submit_analysis_job_if_needed(task_id)
    code = "TASK_ANALYSIS_STARTED" if progress.get("stage") == "queued" else "TASK_ANALYSIS_RUNNING"
    message = "analysis started" if code == "TASK_ANALYSIS_STARTED" else "analysis running"
    return _success_response(progress, code=code, message=message)


@app.get("/api/tasks/{task_id}/analysis/progress", response_model=ApiResponse)
def get_task_analysis_progress(
    task_id: str,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    task = _must_get_visible_task(task_id, current_user)
    return _success_response(
        _resolve_analysis_progress(task),
        code="TASK_ANALYSIS_PROGRESS_OK",
        message="analysis progress",
    )


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
def get_parsed_requirement(task_id: str, current_user: dict[str, Any] | None = Depends(_optional_current_user)):
    task = _must_get_visible_task(task_id, current_user)
    result = _ensure_pipeline(task)
    return _success_response(result.get("parsed_requirement", {}), code="PARSED_REQUIREMENT_OK", message="parsed requirement")


@app.get("/api/tasks/{task_id}/retrieved-context", response_model=ApiResponse)
def get_retrieved_context(task_id: str, current_user: dict[str, Any] | None = Depends(_optional_current_user)):
    task = _must_get_visible_task(task_id, current_user)
    result = _ensure_pipeline(task)
    return _success_response(result.get("retrieved_context", []), code="RETRIEVED_CONTEXT_OK", message="retrieved context")


@app.post("/api/tasks/{task_id}/scenarios/generate", response_model=ApiResponse)
def generate_scenarios(task_id: str, current_user: dict[str, Any] | None = Depends(_optional_current_user)):
    task = _must_get_visible_task(task_id, current_user)
    result = _ensure_pipeline(task)
    task.status = TaskStatus.GENERATED.value
    registry.save(task)
    return _success_response({
        "task_id": task_id,
        "scenario_count": len(result.get("scenarios", [])),
        "scenarios": result.get("scenarios", []),
    }, code="SCENARIOS_READY", message="scenarios generated")


@app.get("/api/tasks/{task_id}/scenarios", response_model=ApiResponse)
def get_scenarios(task_id: str, current_user: dict[str, Any] | None = Depends(_optional_current_user)):
    task = _must_get_visible_task(task_id, current_user)
    result = _ensure_pipeline(task)
    return _success_response(result.get("scenarios", []), code="SCENARIOS_OK", message="scenarios fetched")


@app.get("/api/tasks/{task_id}/dsl", response_model=ApiResponse)
def get_dsl(task_id: str, current_user: dict[str, Any] | None = Depends(_optional_current_user)):
    task = _must_get_visible_task(task_id, current_user)
    result = _ensure_pipeline(task)
    return _success_response(result.get("test_case_dsl", {}), code="DSL_OK", message="dsl fetched")


@app.get("/api/tasks/{task_id}/feature", response_model=ApiResponse)
def get_feature(task_id: str, current_user: dict[str, Any] | None = Depends(_optional_current_user)):
    task = _must_get_visible_task(task_id, current_user)
    result = _ensure_pipeline(task)
    return _success_response({"feature_text": result.get("feature_text", "")}, code="FEATURE_OK", message="feature fetched")


@app.post("/api/tasks/{task_id}/preflight-check", response_model=ApiResponse)
def preflight_check(
    task_id: str,
    payload: PreflightCheckRequest | None = None,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    task = _must_get_visible_task(task_id, current_user)
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
        cookies=(environment_config.cookies if environment_config else {}) or {},
        latency_threshold_ms=body.latency_threshold_ms,
        checks=body.checks,
    )
    return _success_response(data, code="PREFLIGHT_OK", message="preflight complete")


@app.post("/api/tasks/{task_id}/execute", response_model=ApiResponse)
def execute_task(
    task_id: str,
    payload: ExecuteTaskRequest,
    request: Request,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    task = _must_get_visible_task(task_id, current_user)
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
                running_payload = _build_running_execution_result(
                    task_id,
                    payload.execution_mode,
                    selected_environment,
                )
                if task.execution_result and task.execution_result.get("logs"):
                    running_payload["logs"] = list(task.execution_result.get("logs") or [])
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
        future = _EXECUTION_EXECUTOR.submit(
            _run_async_execution_job,
            task_id,
            dsl,
            payload.execution_mode,
            selected_environment,
            environment_config,
        )
        with _RUNNING_EXECUTION_LOCK:
            _RUNNING_EXECUTION_FUTURES[task_id] = future
        _append_audit_log_safe(
            user_id=str(current_user["user"]["id"]) if current_user is not None else None,
            action="task.execute.start",
            resource_type="task",
            resource_id=task_id,
            detail_json={"environment": selected_environment, "execution_mode": payload.execution_mode, "async_mode": True},
            ip_address=_request_ip(request),
        )
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
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]) if current_user is not None else None,
        action="task.execute.finish",
        resource_type="task_run",
        resource_id=task_id,
        detail_json={
            "environment": selected_environment,
            "execution_mode": payload.execution_mode,
            "status": execution_result.get("status"),
        },
        ip_address=_request_ip(request),
    )
    return _success_response(execution_result, code="TASK_EXECUTED", message="task executed")


@app.get("/api/tasks/{task_id}/execution", response_model=ApiResponse)
def get_execution(task_id: str, current_user: dict[str, Any] | None = Depends(_optional_current_user)):
    task = _must_get_visible_task(task_id, current_user)
    if task.execution_result is None:
        payload = {"task_id": task_id, "executor": None, "status": "not_started", "scenario_results": [], "metrics": {}, "logs": []}
        return _success_response(payload, code="EXECUTION_OK", message="execution fetched")
    return _success_response(task.execution_result, code="EXECUTION_OK", message="execution fetched")


@app.get("/api/tasks/{task_id}/execution/stream")
async def stream_execution(
    task_id: str,
    interval_ms: int = Query(800, ge=200, le=5000),
    timeout_s: int = Query(60, ge=5, le=600),
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    _must_get_visible_task(task_id, current_user)

    async def _event_generator():
        started_at = datetime.now(timezone.utc)
        last_status: str | None = None
        last_log_index = 0

        yield _encode_sse({"task_id": task_id, "connected_at": _utc_now_iso()}, event="connected")

        while True:
            task = _must_get_visible_task(task_id, current_user)
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
def get_execution_explanations(
    task_id: str,
    top_n: int = Query(5, ge=1, le=20),
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    task = _must_get_visible_task(task_id, current_user)
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
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    _must_get_visible_task(task_id, current_user)
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
def get_execution_logs(task_id: str, current_user: dict[str, Any] | None = Depends(_optional_current_user)):
    task = _must_get_visible_task(task_id, current_user)
    payload = [] if task.execution_result is None else task.execution_result.get("logs", [])
    return _success_response(payload, code="EXECUTION_LOGS_OK", message="execution logs")


@app.post("/api/tasks/{task_id}/execution/stop", response_model=ApiResponse)
def stop_execution(task_id: str, current_user: dict[str, Any] | None = Depends(_optional_current_user)):
    task = _must_get_visible_task(task_id, current_user)
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
def get_validation_report(task_id: str, current_user: dict[str, Any] | None = Depends(_optional_current_user)):
    task = _must_get_visible_task(task_id, current_user)
    result = _ensure_pipeline(task)
    return _success_response(result.get("validation_report", {}), code="VALIDATION_REPORT_OK", message="validation report")


@app.get("/api/tasks/{task_id}/analysis-report", response_model=ApiResponse)
def get_analysis_report(task_id: str, current_user: dict[str, Any] | None = Depends(_optional_current_user)):
    task = _must_get_visible_task(task_id, current_user)
    return _success_response(_build_task_analysis_report(task), code="ANALYSIS_REPORT_OK", message="analysis report")


@app.get("/api/tasks/{task_id}/dashboard", response_model=ApiResponse)
def get_dashboard(task_id: str, current_user: dict[str, Any] | None = Depends(_optional_current_user)):
    task = _must_get_visible_task(task_id, current_user)
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
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    task = _must_get_visible_task(task_id, current_user)
    result = _ensure_pipeline(task)
    artifacts: list[dict[str, Any]] = []
    for artifact_type, resolver in DEFAULT_ARTIFACT_TYPES.items():
        if shallow:
            artifacts.append({"type": artifact_type})
        else:
            artifacts.append({"type": artifact_type, "content": resolver(result)})
    return _success_response({"task_id": task_id, "artifacts": artifacts}, code="ARTIFACTS_OK", message="artifacts fetched")


@app.get("/api/tasks/{task_id}/artifacts/{artifact_type}", response_model=ApiResponse)
def get_artifact_content(
    task_id: str,
    artifact_type: str,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    task = _must_get_visible_task(task_id, current_user)
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
    project_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    items = registry.list(status=status.value if status else None, keyword=keyword, include_archived=True)
    if current_user is not None:
        visible_project_ids = set(_current_user_project_ids(str(current_user["user"]["id"])))
        visible_user_id = str(current_user["user"]["id"])
        items = [
            item
            for item in items
            if (item.created_by and str(item.created_by) == visible_user_id)
            or (item.project_id and str(item.project_id) in visible_project_ids)
        ]
    if environment:
        items = [item for item in items if item.environment == environment]
    if project_id:
        items = [item for item in items if item.project_id == project_id]
    items = _filter_tasks_by_time(items, start_time, end_time)
    payload = _paginate([item.to_summary() for item in items], page, page_size)
    return _success_response(payload, code="TASK_HISTORY_OK", message="task history")


def _resolve_environment_scope(
    *,
    project_id: str | None,
    current_user: dict[str, Any] | None,
) -> str | None:
    normalized = str(project_id or "").strip() or None
    if normalized is None:
        return None
    if current_user is None:
        raise HTTPException(status_code=401, detail="project-scoped environments require authenticated access")
    _ensure_project_access(normalized, current_user)
    return normalized


def _normalize_defect_status(raw_status: str | None) -> str:
    normalized = str(raw_status or "").strip().lower() or "open"
    if normalized not in VALID_DEFECT_STATUSES:
        raise HTTPException(status_code=400, detail=f"invalid defect status: {normalized}")
    return normalized


def _normalize_defect_severity(raw_severity: str | None) -> str:
    normalized = str(raw_severity or "").strip().lower() or "medium"
    if normalized not in VALID_DEFECT_SEVERITIES:
        raise HTTPException(status_code=400, detail=f"invalid defect severity: {normalized}")
    return normalized


def _normalize_interface_method(raw_method: str | None) -> str:
    normalized = str(raw_method or "").strip().upper()
    if normalized not in VALID_INTERFACE_METHODS:
        raise HTTPException(status_code=400, detail=f"invalid interface method: {normalized}")
    return normalized


def _normalize_interface_status(raw_status: str | None) -> str:
    normalized = str(raw_status or "").strip().lower() or "active"
    if normalized not in VALID_INTERFACE_STATUSES:
        raise HTTPException(status_code=400, detail=f"invalid interface status: {normalized}")
    return normalized


def _normalize_interface_path(raw_path: str | None) -> str:
    normalized = _normalize_endpoint_token(str(raw_path or ""))
    if not normalized:
        raise HTTPException(status_code=400, detail="path is required")
    parsed = urlparse(normalized)
    if parsed.scheme and parsed.netloc:
        normalized = parsed.path or "/"
        if parsed.query:
            normalized = f"{normalized}?{parsed.query}"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized


def _clean_interface_tags(tags: list[str] | None) -> list[str]:
    output: list[str] = []
    for item in tags or []:
        normalized = str(item or "").strip()
        if normalized and normalized not in output:
            output.append(normalized[:64])
    return output[:20]


def _ensure_project_editor(project_id: str, current_user: dict[str, Any]) -> dict[str, Any]:
    project = _ensure_project_access(project_id, current_user)
    if project.get("role") not in {"owner", "editor"}:
        raise HTTPException(status_code=403, detail="Only owner/editor can manage interface assets")
    return project


def _extract_interface_signatures_from_task(task) -> list[tuple[str, str]]:
    signatures = list(_extract_requirement_endpoint_signatures(task.requirement_text or ""))
    pipeline = task.pipeline_result or {}
    dsl = pipeline.get("test_case_dsl") or {}
    for scenario in dsl.get("scenarios") or []:
        if not isinstance(scenario, dict):
            continue
        for step in scenario.get("steps") or []:
            if not isinstance(step, dict):
                continue
            request_spec = step.get("request") or {}
            if not isinstance(request_spec, dict):
                continue
            method = str(request_spec.get("method") or "").strip().upper()
            raw_url = str(request_spec.get("url") or "").strip()
            if not method or not raw_url:
                continue
            try:
                signatures.append((_normalize_interface_method(method), _normalize_interface_path(raw_url)))
            except HTTPException:
                continue
    seen: set[tuple[str, str]] = set()
    output: list[tuple[str, str]] = []
    for method, path in signatures:
        key = (method, path)
        if key in seen:
            continue
        seen.add(key)
        output.append(key)
    return output


def _resolve_interface_debug_url(asset: dict[str, Any], *, base_url: str | None, params: dict[str, Any]) -> str:
    raw_base = str(base_url or "").strip()
    raw_path = str(asset.get("path") or "").strip()
    if not raw_base:
        raise HTTPException(status_code=400, detail="base_url or environment is required")
    if urlparse(raw_path).scheme:
        url = raw_path
    else:
        url = urljoin(raw_base.rstrip("/") + "/", raw_path.lstrip("/"))
    if params:
        query = urlencode(params, doseq=True)
        url = f"{url}{'&' if '?' in url else '?'}{query}"
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="resolved request URL is not a valid http(s) URL")
    return url


def _apply_debug_auth(headers: dict[str, str], auth: dict[str, Any]) -> tuple[dict[str, str], Any]:
    auth_type = str(auth.get("type") or "").strip().lower()
    if not auth_type:
        return headers, None
    if auth_type in {"bearer", "token"}:
        token = str(auth.get("token") or auth.get("access_token") or "").strip()
        if token and "authorization" not in {key.lower() for key in headers}:
            headers["Authorization"] = f"Bearer {token}"
        return headers, None
    if auth_type in {"api_key", "apikey"}:
        key = str(auth.get("key") or auth.get("name") or "X-API-Key").strip()
        value = str(auth.get("value") or auth.get("token") or "").strip()
        location = str(auth.get("in") or "header").strip().lower()
        if key and value and location == "header":
            headers.setdefault(key, value)
        return headers, None
    if auth_type == "basic":
        username = str(auth.get("username") or "").strip()
        password = str(auth.get("password") or "")
        if username:
            return headers, (username, password)
    return headers, None


def _safe_debug_headers(headers: dict[str, Any]) -> dict[str, str]:
    blocked = {"host", "content-length", "connection"}
    output: dict[str, str] = {}
    for key, value in headers.items():
        normalized_key = str(key or "").strip()
        if not normalized_key or normalized_key.lower() in blocked:
            continue
        output[normalized_key] = str(value)
    return output


def _build_mock_payload(asset: dict[str, Any]) -> tuple[Any, int]:
    example = asset.get("response_example")
    if isinstance(example, dict):
        status_code = int(example.get("status_code") or example.get("status") or 200)
        if "body" in example:
            return example["body"], status_code
        if "json" in example:
            return example["json"], status_code
        return example, status_code
    if example is not None:
        return example, 200
    return {
        "mock": True,
        "method": asset.get("method"),
        "path": asset.get("path"),
        "name": asset.get("name") or "",
        "message": "No response example configured; returning generated mock payload.",
    }, 200


def _parse_openapi_content(content: str) -> dict[str, Any]:
    text = str(content or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="OpenAPI content is empty")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except Exception as exc:
            raise HTTPException(status_code=400, detail="OpenAPI content is not valid JSON; YAML support requires PyYAML") from exc
        try:
            parsed = yaml.safe_load(text)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"OpenAPI YAML parse failed: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="OpenAPI content must be an object")
    return parsed


def _openapi_example_from_media(media: Any) -> Any:
    if not isinstance(media, dict):
        return None
    if "example" in media:
        return media.get("example")
    examples = media.get("examples")
    if isinstance(examples, dict):
        for item in examples.values():
            if isinstance(item, dict) and "value" in item:
                return item.get("value")
            if item is not None:
                return item
    schema = media.get("schema")
    if isinstance(schema, dict):
        return {"schema": schema}
    return None


def _openapi_request_example(operation: dict[str, Any]) -> Any:
    request_body = operation.get("requestBody")
    if not isinstance(request_body, dict):
        return None
    content = request_body.get("content")
    if not isinstance(content, dict):
        return None
    for media_type in ("application/json", "application/*+json"):
        example = _openapi_example_from_media(content.get(media_type))
        if example is not None:
            return example
    for media in content.values():
        example = _openapi_example_from_media(media)
        if example is not None:
            return example
    return None


def _openapi_response_example(operation: dict[str, Any]) -> Any:
    responses = operation.get("responses")
    if not isinstance(responses, dict):
        return None
    for status_key in ("200", "201", "202", "204", "default"):
        response = responses.get(status_key)
        if not isinstance(response, dict):
            continue
        content = response.get("content")
        if isinstance(content, dict):
            for media_type in ("application/json", "application/*+json"):
                example = _openapi_example_from_media(content.get(media_type))
                if example is not None:
                    return {"status_code": int(status_key) if status_key.isdigit() else 200, "body": example}
            for media in content.values():
                example = _openapi_example_from_media(media)
                if example is not None:
                    return {"status_code": int(status_key) if status_key.isdigit() else 200, "body": example}
        description = str(response.get("description") or "").strip()
        if description:
            return {"status_code": int(status_key) if status_key.isdigit() else 200, "body": {"description": description}}
    return None


def _extract_openapi_interface_assets(openapi_doc: dict[str, Any]) -> list[dict[str, Any]]:
    paths = openapi_doc.get("paths")
    if not isinstance(paths, dict):
        raise HTTPException(status_code=400, detail="OpenAPI paths object is required")
    assets: list[dict[str, Any]] = []
    for raw_path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        path_tags = path_item.get("tags") if isinstance(path_item.get("tags"), list) else []
        for raw_method, operation in path_item.items():
            method = str(raw_method or "").strip().upper()
            if method not in VALID_INTERFACE_METHODS:
                continue
            if not isinstance(operation, dict):
                continue
            operation_tags = operation.get("tags") if isinstance(operation.get("tags"), list) else []
            name = str(operation.get("summary") or operation.get("operationId") or f"{method} {raw_path}").strip()
            description = str(operation.get("description") or "").strip()
            assets.append(
                {
                    "method": method,
                    "path": _normalize_interface_path(str(raw_path)),
                    "name": name,
                    "description": description,
                    "tags": _clean_interface_tags([str(item) for item in [*path_tags, *operation_tags]]),
                    "request_example": _openapi_request_example(operation),
                    "response_example": _openapi_response_example(operation),
                    "schema": operation,
                }
            )
    return assets


def _normalize_test_case_status(raw_status: str | None) -> str:
    normalized = str(raw_status or "").strip().lower() or "active"
    if normalized not in VALID_TEST_CASE_STATUSES:
        raise HTTPException(status_code=400, detail=f"invalid test case status: {normalized}")
    return normalized


def _normalize_test_case_priority(raw_priority: str | None) -> str:
    normalized = str(raw_priority or "").strip().upper() or "P1"
    if normalized not in VALID_TEST_CASE_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"invalid test case priority: {normalized}")
    return normalized


def _normalize_test_case_key(raw_key: str | None, fallback: str) -> str:
    value = str(raw_key or "").strip() or fallback
    value = re.sub(r"[^A-Za-z0-9_.:-]+", "-", value).strip("-_.:")
    return value[:120] or fallback


def _assertions_from_dsl_scenario(scenario: dict[str, Any]) -> list[Any]:
    assertions: list[Any] = []
    for step in scenario.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for assertion in step.get("assertions") or []:
            assertions.append(assertion)
    return assertions


def _clean_test_case_tags(tags: list[str] | None) -> list[str]:
    return _clean_interface_tags(tags)


def _normalize_test_suite_status(raw_status: str | None) -> str:
    normalized = str(raw_status or "").strip().lower() or "active"
    if normalized not in VALID_TEST_SUITE_STATUSES:
        raise HTTPException(status_code=400, detail=f"invalid test suite status: {normalized}")
    return normalized


def _clean_case_ids(raw_case_ids: list[str] | None) -> list[str]:
    output: list[str] = []
    for item in raw_case_ids or []:
        normalized = str(item or "").strip()
        if normalized and normalized not in output:
            output.append(normalized)
    return output


def _execute_case_asset_payload(
    asset: dict[str, Any],
    *,
    execution_mode: str,
    environment: str | None,
    base_url: str | None,
) -> dict[str, Any]:
    scenario = asset.get("dsl_scenario")
    if not isinstance(scenario, dict) or not scenario:
        raise HTTPException(status_code=400, detail="test case asset has no executable dsl_scenario")
    environment_config = _resolve_project_environment_config(str(asset["project_id"]), environment)
    dsl = {
        "dsl_version": "1.0",
        "task_id": f"case_asset:{asset['id']}",
        "task_name": asset["name"],
        "feature_name": asset["name"],
        "execution_mode": execution_mode,
        "scenarios": [scenario],
        "metadata": {
            "execution": {
                "base_url": str(base_url or "").strip(),
                "environment": environment or "",
                "context": {"case_id": asset["id"], "case_key": asset["case_key"]},
            }
        },
    }
    dsl = _inject_environment_into_dsl(
        dsl,
        environment,
        environment_config,
        fallback_base_url=str(base_url or "").strip(),
    )
    resolved_base_url = str((dsl.get("metadata") or {}).get("execution", {}).get("base_url", "")).strip()
    if execution_mode == "api" and not resolved_base_url:
        raise HTTPException(status_code=400, detail="Missing base_url. Select an environment or provide base_url.")
    execution_result = _run_dsl_with_timeout(dsl, execution_mode)
    return _apply_execution_metadata(
        execution_result,
        selected_environment=environment or "",
        execution_mode=execution_mode,
        environment_config=environment_config,
        dsl=dsl,
    )


def _validate_defect_task_reference(task_id: str | None, *, project_id: str) -> str | None:
    normalized = str(task_id or "").strip()
    if not normalized:
        return None
    task = registry.get(normalized)
    if task is None or task.archived:
        raise HTTPException(status_code=404, detail=f"Task not found: {normalized}")
    if str(task.project_id or "") != str(project_id):
        raise HTTPException(status_code=400, detail="task_id does not belong to the selected project")
    return normalized


def _validate_defect_assignee(
    *,
    assignee_user_id: str | None,
    project_id: str,
    current_user: dict[str, Any],
) -> str | None:
    normalized = str(assignee_user_id or "").strip()
    if not normalized:
        return None
    store = _db_store_or_503()
    user = store.get_user_by_id(normalized)
    if user is None:
        raise HTTPException(status_code=404, detail=f"Assignee not found: {normalized}")
    if not store.is_project_member(project_id=project_id, user_id=normalized):
        raise HTTPException(status_code=400, detail="assignee_user_id is not a member of the selected project")
    return normalized


def _environment_payload_to_config(
    payload: UpsertEnvironmentRequest,
    *,
    project_id: str | None,
    existing_config: EnvironmentConfig | None = None,
) -> EnvironmentConfig:
    candidate = EnvironmentConfig(
        name=payload.name,
        base_url=payload.base_url,
        default_headers=dict(payload.default_headers or {}),
        auth=dict(payload.auth or {}),
        cookies=dict(payload.cookies or {}),
        description=payload.description,
    )
    return merge_masked_environment_config(candidate, existing_config)


def _serialize_environment_response(config: EnvironmentConfig) -> dict[str, Any]:
    return mask_environment_config(config)


@app.get("/api/environments", response_model=ApiResponse)
def list_environments(
    project_id: str | None = None,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    scoped_project_id = _resolve_environment_scope(project_id=project_id, current_user=current_user)
    payload = [
        _serialize_environment_response(item)
        for item in registry.list_environments(
            project_id=scoped_project_id,
            include_global=scoped_project_id is not None,
        )
    ]
    return _success_response(payload, code="ENVIRONMENTS_OK", message="environments listed")


@app.post("/api/environments", response_model=ApiResponse)
def create_or_update_environment(
    payload: UpsertEnvironmentRequest,
    request: Request,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    scoped_project_id = _resolve_environment_scope(project_id=payload.project_id, current_user=current_user)
    existing_config = registry.get_environment(payload.name, project_id=scoped_project_id)
    config = _environment_payload_to_config(
        payload,
        project_id=scoped_project_id,
        existing_config=existing_config,
    )
    registry.save_environment(
        config,
        project_id=scoped_project_id,
        created_by=str(current_user["user"]["id"]) if current_user is not None else None,
    )
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]) if current_user is not None else None,
        action="environment.save",
        resource_type="environment",
        resource_id=f"{scoped_project_id or 'global'}:{payload.name}",
        detail_json={"project_id": scoped_project_id, "name": payload.name, "base_url": payload.base_url},
        ip_address=_request_ip(request),
    )
    return _success_response(_serialize_environment_response(config), code="ENVIRONMENT_SAVED", message="environment saved", status_code=201)


@app.get("/api/environments/{environment_name}", response_model=ApiResponse)
def get_environment(
    environment_name: str,
    project_id: str | None = None,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    scoped_project_id = _resolve_environment_scope(project_id=project_id, current_user=current_user)
    config = registry.get_environment(environment_name, project_id=scoped_project_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Environment not found: {environment_name}")
    return _success_response(_serialize_environment_response(config), code="ENVIRONMENT_OK", message="environment fetched")


@app.put("/api/environments/{environment_name}", response_model=ApiResponse)
def update_environment(
    environment_name: str,
    payload: UpsertEnvironmentRequest,
    request: Request,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    scoped_project_id = _resolve_environment_scope(project_id=payload.project_id, current_user=current_user)
    existing_config = registry.get_environment(environment_name, project_id=scoped_project_id)
    config = _environment_payload_to_config(
        UpsertEnvironmentRequest(
            name=environment_name,
            base_url=payload.base_url,
            default_headers=payload.default_headers,
            auth=payload.auth,
            cookies=payload.cookies,
            description=payload.description,
            project_id=payload.project_id,
        ),
        project_id=scoped_project_id,
        existing_config=existing_config,
    )
    registry.save_environment(
        config,
        project_id=scoped_project_id,
        created_by=str(current_user["user"]["id"]) if current_user is not None else None,
    )
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]) if current_user is not None else None,
        action="environment.update",
        resource_type="environment",
        resource_id=f"{scoped_project_id or 'global'}:{environment_name}",
        detail_json={"project_id": scoped_project_id, "name": environment_name, "base_url": payload.base_url},
        ip_address=_request_ip(request),
    )
    return _success_response(_serialize_environment_response(config), code="ENVIRONMENT_UPDATED", message="environment updated")


@app.delete("/api/environments/{environment_name}", response_model=ApiResponse)
def delete_environment(
    environment_name: str,
    request: Request,
    project_id: str | None = None,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    scoped_project_id = _resolve_environment_scope(project_id=project_id, current_user=current_user)
    if not registry.delete_environment(environment_name, project_id=scoped_project_id):
        raise HTTPException(status_code=404, detail=f"Environment not found: {environment_name}")
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]) if current_user is not None else None,
        action="environment.delete",
        resource_type="environment",
        resource_id=f"{scoped_project_id or 'global'}:{environment_name}",
        detail_json={"project_id": scoped_project_id, "name": environment_name},
        ip_address=_request_ip(request),
    )
    return _success_response({"name": environment_name, "deleted": True}, code="ENVIRONMENT_DELETED", message="environment deleted")


@app.post("/api/environments/probe", response_model=ApiResponse)
def probe_environment(
    payload: UpsertEnvironmentRequest,
    request: Request,
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    scoped_project_id = _resolve_environment_scope(project_id=payload.project_id, current_user=current_user)
    existing_config = registry.get_environment(payload.name, project_id=scoped_project_id)
    config = _environment_payload_to_config(
        payload,
        project_id=scoped_project_id,
        existing_config=existing_config,
    )
    result = run_preflight_check(
        task_id=f"environment-probe:{config.name}",
        base_url=config.base_url,
        default_headers=config.default_headers,
        auth=config.auth,
        cookies=config.cookies,
        latency_threshold_ms=1500.0,
        checks=["base_url_reachable", "auth_config_valid"],
    )
    result["environment_name"] = config.name
    result["project_id"] = scoped_project_id
    _append_audit_log_safe(
        user_id=str(current_user["user"]["id"]) if current_user is not None else None,
        action="environment.probe",
        resource_type="environment",
        resource_id=f"{scoped_project_id or 'global'}:{config.name}",
        detail_json={
            "project_id": scoped_project_id,
            "name": config.name,
            "base_url": config.base_url,
            "overall_status": result.get("overall_status"),
            "blocking": result.get("blocking"),
        },
        ip_address=_request_ip(request),
    )
    return _success_response(result, code="ENVIRONMENT_PROBE_OK", message="environment probe completed")


@app.get("/api/audit/logs", response_model=ApiResponse)
def get_audit_logs(
    action: str | None = None,
    resource_type: str | None = None,
    keyword: str | None = None,
    user_id: str | None = None,
    actor: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: dict[str, Any] = Depends(_require_platform_admin),
):
    store = _db_store_or_503()
    payload = store.list_audit_logs(
        action=action,
        resource_type=resource_type,
        keyword=keyword,
        user_id=user_id,
        actor=actor,
        start_time=_parse_iso_timestamp(start_time),
        end_time=_parse_iso_timestamp(end_time),
        page=page,
        page_size=page_size,
    )
    return _success_response(payload, code="AUDIT_LOGS_OK", message="audit logs")


@app.get("/api/history/executions", response_model=ApiResponse)
def get_execution_history(
    task_id: str | None = None,
    status: TaskStatus | None = None,
    keyword: str | None = None,
    environment: str | None = None,
    project_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: dict[str, Any] | None = Depends(_optional_current_user),
):
    items = registry.list_execution_history(
        task_id=task_id,
        status=status.value if status else None,
        keyword=keyword,
        environment=environment,
    )
    if current_user is not None:
        visible_task_ids = {
            item.task_id
            for item in registry.list(include_archived=True)
            if (
                (item.created_by and str(item.created_by) == str(current_user["user"]["id"]))
                or (item.project_id and item.project_id in set(_current_user_project_ids(str(current_user["user"]["id"]))))
            )
        }
        items = [item for item in items if str(item.get("task_id") or "") in visible_task_ids]
    if project_id:
        visible_project_task_ids = {
            item.task_id
            for item in registry.list(include_archived=True)
            if item.project_id == project_id
        }
        items = [item for item in items if str(item.get("task_id") or "") in visible_project_task_ids]
    items = _filter_dict_items_by_time(items, "executed_at", start_time, end_time)
    payload = _paginate(items, page, page_size)
    return _success_response(payload, code="EXECUTION_HISTORY_OK", message="execution history")
