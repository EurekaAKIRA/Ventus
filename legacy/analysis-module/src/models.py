"""analysis-module 统一中间结构定义。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    """Return an ISO timestamp for task metadata."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class TaskContext:
    """任务级上下文。"""

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
    """可追踪的文档片段。"""

    chunk_id: str
    content: str
    section_title: str = ""
    source_file: str = ""
    source_block: str = ""
    tokens_estimate: int = 0
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class RetrievedChunk:
    """检索命中的片段结构。"""

    chunk_id: str
    content: str
    score: float
    section_title: str = ""
    source_file: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ParsedRequirement:
    """需求解析结果。"""

    objective: str
    actors: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    expected_results: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    source_chunks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ScenarioStep:
    """单个 Gherkin 步骤。"""

    type: str
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ScenarioModel:
    """结构化测试场景。"""

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
        payload["steps"] = [step.to_dict() for step in self.steps]
        return payload


@dataclass(slots=True)
class ValidationReport:
    """产物校验报告。"""

    feature_name: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class PipelineResult:
    """最小流水线聚合结果。"""

    task_context: TaskContext
    raw_requirement: str
    cleaned_text: str
    outline: list[dict]
    chunks: list[DocumentChunk]
    retrieved_context: list[RetrievedChunk]
    parsed_requirement: ParsedRequirement
    scenarios: list[ScenarioModel]
    feature_text: str
    validation_report: ValidationReport

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
            "feature_text": self.feature_text,
            "validation_report": self.validation_report.to_dict(),
        }
