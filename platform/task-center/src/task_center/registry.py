"""Task registry with JSON-backed persistence and recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifact_manager import load_pipeline_artifacts
from platform_shared.models import EnvironmentConfig

from .repository import EnvironmentRepository, ExecutionHistoryRepository, ExecutionRepository, TaskRepository


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class TaskRecord:
    task_id: str
    task_name: str
    source_type: str
    requirement_text: str
    source_path: str | None = None
    target_system: str | None = None
    environment: str | None = None
    created_at: str = field(default_factory=_utc_now_iso)
    status: str = "received"
    task_context: dict[str, Any] = field(default_factory=dict)
    pipeline_result: dict[str, Any] | None = None
    execution_result: dict[str, Any] | None = None
    artifact_dir: str | None = None
    archived: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskRecord":
        return cls(**payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "source_type": self.source_type,
            "requirement_text": self.requirement_text,
            "source_path": self.source_path,
            "target_system": self.target_system,
            "environment": self.environment,
            "created_at": self.created_at,
            "status": self.status,
            "task_context": self.task_context,
            "pipeline_result": self.pipeline_result,
            "execution_result": self.execution_result,
            "artifact_dir": self.artifact_dir,
            "archived": self.archived,
        }

    def to_summary(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "source_type": self.source_type,
            "target_system": self.target_system,
            "environment": self.environment,
            "created_at": self.created_at,
            "status": self.status,
            "archived": self.archived,
        }


DEFAULT_ENVIRONMENTS = {
    "dev": EnvironmentConfig(name="dev", description="Local development environment"),
    "test": EnvironmentConfig(name="test", description="Integration test environment"),
    "prod": EnvironmentConfig(name="prod", description="Production-like environment"),
}


class TaskRegistry:
    """Registry that persists task metadata and recovers task artifacts."""

    def __init__(self, artifacts_root: str):
        self._tasks: dict[str, TaskRecord] = {}
        self.artifacts_root = artifacts_root
        Path(self.artifacts_root).mkdir(parents=True, exist_ok=True)
        self.task_repository = TaskRepository(str(Path(self.artifacts_root) / "tasks.json"))
        self.execution_repository = ExecutionRepository(str(Path(self.artifacts_root) / "executions.json"))
        self.execution_history_repository = ExecutionHistoryRepository(str(Path(self.artifacts_root) / "execution_history.json"))
        self.environment_repository = EnvironmentRepository(str(Path(self.artifacts_root) / "environments.json"))
        self._execution_history: list[dict[str, Any]] = []
        self._environments: dict[str, EnvironmentConfig] = {}
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        tasks = [TaskRecord.from_dict(item) for item in self.task_repository.load_tasks()]
        executions = self.execution_repository.load_executions()
        self._load_environments()
        self._execution_history = self.execution_history_repository.load_history()
        for record in tasks:
            record.execution_result = executions.get(record.task_id, record.execution_result)
            self._hydrate_task(record)
            self._tasks[record.task_id] = record

    def _load_environments(self) -> None:
        loaded = self.environment_repository.load_environments()
        if loaded:
            self._environments = {
                item["name"]: EnvironmentConfig(**item)
                for item in loaded
                if item.get("name")
            }
        else:
            self._environments = dict(DEFAULT_ENVIRONMENTS)

    def _hydrate_task(self, record: TaskRecord) -> None:
        if not record.artifact_dir:
            return
        artifact_dir = Path(record.artifact_dir)
        if not artifact_dir.exists():
            return
        pipeline_result = load_pipeline_artifacts(str(artifact_dir))
        if pipeline_result.get("task_context"):
            record.task_context = pipeline_result["task_context"]
        if any(pipeline_result.get(key) for key in ("parsed_requirement", "scenarios", "test_case_dsl", "validation_report", "analysis_report")):
            record.pipeline_result = pipeline_result
        if pipeline_result.get("execution_result"):
            record.execution_result = pipeline_result["execution_result"]

    def _persist_tasks(self) -> None:
        items = [record.to_dict() for record in self._tasks.values()]
        self.task_repository.save_tasks(items)

    def _persist_executions(self) -> None:
        executions = {
            task_id: record.execution_result
            for task_id, record in self._tasks.items()
            if record.execution_result is not None
        }
        self.execution_repository.save_executions(executions)

    def _persist_execution_history(self) -> None:
        self.execution_history_repository.save_history(self._execution_history)

    def _persist_environments(self) -> None:
        items = [config.to_dict() for _, config in sorted(self._environments.items())]
        self.environment_repository.save_environments(items)

    def create_task(
        self,
        task_id: str,
        task_name: str,
        source_type: str,
        requirement_text: str,
        source_path: str | None = None,
        target_system: str | None = None,
        environment: str | None = None,
        task_context: dict[str, Any] | None = None,
    ) -> TaskRecord:
        record = TaskRecord(
            task_id=task_id,
            task_name=task_name,
            source_type=source_type,
            requirement_text=requirement_text,
            source_path=source_path,
            target_system=target_system,
            environment=environment,
            task_context=task_context or {},
        )
        self._tasks[task_id] = record
        self._persist_tasks()
        return record

    def save(self, record: TaskRecord) -> TaskRecord:
        self._tasks[record.task_id] = record
        self._persist_tasks()
        self._persist_executions()
        return record

    def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def list(
        self,
        status: str | None = None,
        keyword: str | None = None,
        include_archived: bool = False,
    ) -> list[TaskRecord]:
        items = list(self._tasks.values())
        if not include_archived:
            items = [item for item in items if not item.archived]
        if status:
            items = [item for item in items if item.status == status]
        if keyword:
            keyword_lower = keyword.lower()
            items = [
                item
                for item in items
                if keyword_lower in item.task_name.lower()
                or keyword_lower in item.requirement_text.lower()
                or keyword_lower in (item.target_system or "").lower()
            ]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items

    def archive(self, task_id: str) -> bool:
        record = self.get(task_id)
        if record is None:
            return False
        record.archived = True
        record.status = "archived"
        self.save(record)
        return True

    def list_environments(self) -> list[EnvironmentConfig]:
        return [self._environments[name] for name in sorted(self._environments)]

    def get_environment(self, name: str | None) -> EnvironmentConfig | None:
        if not name:
            return None
        return self._environments.get(name)

    def save_environment(self, config: EnvironmentConfig) -> EnvironmentConfig:
        self._environments[config.name] = config
        self._persist_environments()
        return config

    def delete_environment(self, name: str) -> bool:
        if name not in self._environments:
            return False
        del self._environments[name]
        self._persist_environments()
        return True

    def append_execution_history(self, record: dict[str, Any]) -> dict[str, Any]:
        self._execution_history.append(record)
        self._execution_history.sort(key=lambda item: item.get("executed_at", ""), reverse=True)
        self._persist_execution_history()
        return record

    def list_execution_history(
        self,
        *,
        task_id: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        environment: str | None = None,
    ) -> list[dict[str, Any]]:
        items = list(self._execution_history)
        if task_id:
            items = [item for item in items if item.get("task_id") == task_id]
        if status:
            items = [item for item in items if item.get("status") == status]
        if environment:
            items = [item for item in items if item.get("environment") == environment]
        if keyword:
            keyword_lower = keyword.lower()
            items = [
                item for item in items
                if keyword_lower in str(item.get("task_name", "")).lower()
                or keyword_lower in str(item.get("task_id", "")).lower()
                or keyword_lower in str(item.get("environment", "")).lower()
            ]
        return items


DEFAULT_ARTIFACT_TYPES = {
    "raw": lambda result: result.get("raw_requirement"),
    "parsed-requirement": lambda result: result.get("parsed_requirement"),
    "retrieved-context": lambda result: result.get("retrieved_context"),
    "scenarios": lambda result: result.get("scenarios"),
    "dsl": lambda result: result.get("test_case_dsl"),
    "feature": lambda result: result.get("feature_text"),
    "validation-report": lambda result: result.get("validation_report"),
    "analysis-report": lambda result: result.get("analysis_report"),
}
