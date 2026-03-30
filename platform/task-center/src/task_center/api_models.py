"""Pydantic API models for the task-center service."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    RECEIVED = "received"
    PARSED = "parsed"
    GENERATED = "generated"
    PASSED = "passed"
    FAILED = "failed"
    STOPPED = "stopped"
    ARCHIVED = "archived"


class CreateTaskRequest(BaseModel):
    task_name: str
    source_type: str = "text"
    requirement_text: str = ""
    source_path: str | None = None
    target_system: str | None = None
    environment: str | None = None


class ExecuteTaskRequest(BaseModel):
    execution_mode: str = "api"
    environment: str | None = None


class UpsertEnvironmentRequest(BaseModel):
    name: str
    base_url: str = ""
    default_headers: dict[str, Any] = Field(default_factory=dict)
    auth: dict[str, Any] = Field(default_factory=dict)
    cookies: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class ApiResponse(BaseModel):
    success: bool = True
    code: str = "OK"
    message: str = "success"
    data: Any = None
    timestamp: str


class ErrorDetail(BaseModel):
    detail: Any = None


class ErrorResponse(BaseModel):
    success: bool = False
    code: str
    message: str
    data: ErrorDetail = Field(default_factory=ErrorDetail)
    timestamp: str


class PageMeta(BaseModel):
    page: int
    page_size: int
    items: list[dict[str, Any]]
    total: int


class TaskListResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


class HistoryTaskQuery(BaseModel):
    status: str | None = None
    keyword: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    page: int = 1
    page_size: int = 20


class VersionInfo(BaseModel):
    service: str
    version: str
    api_version: str


class HealthInfo(BaseModel):
    status: str
    service: str
    version: str


class StopExecutionResponse(BaseModel):
    task_id: str
    stopped: bool
    message: str
