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
    rag_enabled: bool | None = None


class ExecuteTaskRequest(BaseModel):
    execution_mode: str = "api"
    environment: str | None = None
    async_mode: bool = False


class PreflightCheckRequest(BaseModel):
    """Optional body for POST /preflight-check."""

    environment: str | None = None
    checks: list[str] | None = None
    latency_threshold_ms: float = Field(default=1500.0, ge=100.0, le=60000.0)


class AnalysisEnhancementOptions(BaseModel):
    use_llm: bool | None = None
    rag_enabled: bool | None = None
    retrieval_top_k: int | None = Field(default=None, ge=1, le=20)
    rerank_enabled: bool | None = None
    model_profile: str | None = None


class ParsePerformance(BaseModel):
    elapsed_ms: float = 0.0
    target_ms: float = 0.0
    within_target: bool = True
    slow_reason: str = ""
    phase_timings_ms: dict[str, float] = Field(default_factory=dict)


class ParseRetrievalMetrics(BaseModel):
    returned_count: int = 0
    requested_top_k: int = 0
    coverage_ratio: float = 0.0
    duplicate_ratio: float = 0.0
    score_avg: float = 0.0
    rerank_applied: bool = False
    embedded_chunk_count: int = 0
    embedding_coverage: float = 0.0
    embedding_error: str = ""
    embedding_error_detail: str = ""


class ParseRetrievalScoring(BaseModel):
    lexical_weight: float = 4.0
    vector_weight: float = 6.0
    rerank_vector_weight: float = 7.0
    rerank_lexical_weight: float = 2.0
    rerank_title_boost: float = 0.2
    rerank_content_boost: float = 0.2


class ParseMetadata(BaseModel):
    parse_mode: str = "rules"
    llm_attempted: bool = False
    llm_used: bool = False
    rag_enabled: bool = False
    rag_used: bool = False
    rag_fallback_reason: str = ""
    fallback_reason: str = ""
    llm_error_type: str = ""
    llm_provider_profile: str = "tencent_hunyuan_openai_compat"
    model_profile: str = "default"
    retrieval_mode: str = "keyword"
    retrieval_top_k: int = 5
    rerank_enabled: bool = False
    document_char_count: int = 0
    cleaned_char_count: int = 0
    chunk_count: int = 0
    embedding_batch_size: int = 32
    estimated_embedding_calls: int = 0
    processing_tier: str = "realtime"
    large_document_warning: str = ""
    retrieval_metrics: ParseRetrievalMetrics = Field(default_factory=ParseRetrievalMetrics)
    retrieval_scoring: ParseRetrievalScoring = Field(default_factory=ParseRetrievalScoring)
    performance: ParsePerformance = Field(default_factory=ParsePerformance)


class TaskParseRequest(AnalysisEnhancementOptions):
    pass


class AnalysisParseRequest(AnalysisEnhancementOptions):
    task_name: str = "analysis_parse_demo"
    source_type: str = "text"
    requirement_text: str = ""
    source_path: str | None = None


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
