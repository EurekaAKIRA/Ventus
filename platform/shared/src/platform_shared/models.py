"""Unified platform data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    """Return an ISO timestamp for task metadata."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class TaskContext:
    """Task-scoped metadata for the platform pipeline."""

    task_id: str
    task_name: str
    source_type: str
    source_path: str | None = None
    created_at: str = field(default_factory=_utc_now_iso)
    language: str = "zh-CN"
    status: str = "received"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class DocumentChunk:
    """Traceable document chunk for retrieval."""

    chunk_id: str
    content: str
    section_title: str = ""
    source_file: str = ""
    source_block: str = ""
    tokens_estimate: int = 0
    keywords: list[str] = field(default_factory=list)
    doc_type: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class RetrievedChunk:
    """Retrieved chunk result."""

    chunk_id: str
    content: str
    score: float
    section_title: str = ""
    source_file: str = ""
    doc_type: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class FieldSpec:
    """Describes a single request-body or response field."""

    name: str
    field_type: str = "string"
    required: bool = False
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FieldSpec":
        return cls(
            name=str(data.get("name", "")),
            field_type=str(data.get("field_type", data.get("type", "string"))),
            required=bool(data.get("required", False)),
            description=str(data.get("description", "")),
        )


@dataclass(slots=True)
class EndpointSpec:
    """Rich endpoint descriptor extracted from requirement documents."""

    method: str
    path: str
    description: str = ""
    group: str = ""
    request_body_fields: list[FieldSpec] = field(default_factory=list)
    response_fields: list[FieldSpec] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "path": self.path,
            "description": self.description,
            "group": self.group,
            "request_body_fields": [f.to_dict() for f in self.request_body_fields],
            "response_fields": [f.to_dict() for f in self.response_fields],
            "depends_on": self.depends_on,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EndpointSpec":
        return cls(
            method=str(data.get("method", "")).strip().upper(),
            path=str(data.get("path", "")).strip(),
            description=str(data.get("description", "")).strip(),
            group=str(data.get("group", "")).strip(),
            request_body_fields=[
                FieldSpec.from_dict(f) if isinstance(f, dict) else FieldSpec(name=str(f))
                for f in (data.get("request_body_fields") or [])
            ],
            response_fields=[
                FieldSpec.from_dict(f) if isinstance(f, dict) else FieldSpec(name=str(f))
                for f in (data.get("response_fields") or [])
            ],
            depends_on=list(data.get("depends_on") or []),
        )


@dataclass(slots=True)
class ParsedRequirement:
    """Structured requirement representation."""

    objective: str
    actors: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    expected_results: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    source_chunks: list[str] = field(default_factory=list)
    api_endpoints: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ScenarioStep:
    """Single scenario step."""

    type: str
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ScenarioModel:
    """Structured test scenario."""

    scenario_id: str
    name: str
    goal: str
    steps: list[ScenarioStep]
    assertions: list[str]
    source_chunks: list[str]
    priority: str = "P1"
    preconditions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["steps"] = [step.to_dict() if hasattr(step, "to_dict") else dict(step) for step in self.steps]
        return payload


@dataclass(slots=True)
class TestCaseStep:
    """Unified executable DSL step."""

    step_id: str
    step_type: str
    text: str
    request: dict = field(default_factory=dict)
    load_profile: dict = field(default_factory=dict)
    assertions: list = field(default_factory=list)
    uses_context: list[str] = field(default_factory=list)
    saves_context: list[str] = field(default_factory=list)
    save_context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class TestCaseDSL:
    """Unified platform test-case protocol."""

    dsl_version: str
    task_id: str
    task_name: str
    feature_name: str
    execution_mode: str
    scenarios: list[dict]
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ExecutionResult:
    """Standardized execution result."""

    task_id: str
    executor: str
    status: str
    scenario_results: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    logs: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class EnvironmentConfig:
    """Execution environment configuration."""

    name: str
    base_url: str = ""
    default_headers: dict = field(default_factory=dict)
    auth: dict = field(default_factory=dict)
    cookies: dict = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ValidationReport:
    """Feature validation report."""

    feature_name: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class AnalysisReport:
    """Aggregated analysis report for display."""

    task_id: str
    task_name: str
    quality_status: str
    report_version: str = "1.0.0"
    generated_at: str = field(default_factory=_utc_now_iso)
    summary: dict = field(default_factory=dict)
    dashboard: dict = field(default_factory=dict)
    dashboard_summary: dict = field(default_factory=dict)
    task_summary: dict = field(default_factory=dict)
    execution_overview: dict = field(default_factory=dict)
    performance_stats: dict = field(default_factory=dict)
    failed_steps: list[dict] = field(default_factory=list)
    failure_reasons: list[dict] = field(default_factory=list)
    assertion_stats: dict = field(default_factory=dict)
    step_assertion_quality: list[dict] = field(default_factory=list)
    context_stats: dict = field(default_factory=dict)
    task_summary_text: str = ""
    findings: list[str] = field(default_factory=list)
    chart_data: dict = field(default_factory=dict)
    report_sections: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class PipelineResult:
    """Aggregated pipeline result for the new platform."""

    task_context: TaskContext
    raw_requirement: str
    cleaned_text: str
    outline: list[dict]
    chunks: list[DocumentChunk]
    retrieved_context: list[RetrievedChunk]
    parsed_requirement: ParsedRequirement
    scenarios: list[ScenarioModel]
    test_case_dsl: TestCaseDSL
    feature_text: str
    validation_report: ValidationReport
    analysis_report: AnalysisReport

    def to_dict(self) -> dict:
        return {
            "task_context": self.task_context.to_dict(),
            "raw_requirement": self.raw_requirement,
            "cleaned_text": self.cleaned_text,
            "outline": self.outline,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "retrieved_context": [chunk.to_dict() for chunk in self.retrieved_context],
            "parsed_requirement": self.parsed_requirement.to_dict(),
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
            "test_case_dsl": self.test_case_dsl.to_dict(),
            "feature_text": self.feature_text,
            "validation_report": self.validation_report.to_dict(),
            "analysis_report": self.analysis_report.to_dict(),
        }
