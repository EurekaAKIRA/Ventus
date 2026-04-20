"""Task registry with DB-backed persistence and JSON compatibility mirror."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platform_shared.models import EnvironmentConfig

from .artifact_manager import load_pipeline_artifacts
from .db_store import DatabaseTaskStore
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
    project_id: str | None = None
    created_by: str | None = None
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
            "project_id": self.project_id,
            "created_by": self.created_by,
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
            "project_id": self.project_id,
            "created_by": self.created_by,
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
        self._backend_name = str(os.getenv("TASK_CENTER_PERSISTENCE_BACKEND", "db") or "db").strip().lower()
        self._json_mirror_enabled = (
            str(
                os.getenv(
                    "TASK_CENTER_JSON_MIRROR_ENABLED",
                    "false" if self._backend_name == "db" else "true",
                )
            )
            .strip()
            .lower()
            in {"1", "true", "yes", "on"}
        )
        self._db_store: DatabaseTaskStore | None = None
        if self._backend_name == "db":
            self._db_store = DatabaseTaskStore(database_url=os.getenv("TASK_CENTER_DATABASE_URL"))
        self._load_state()

    @property
    def db_store(self) -> DatabaseTaskStore | None:
        return self._db_store

    def _load_state(self) -> None:
        tasks: list[TaskRecord]
        if self._db_store is not None:
            tasks = [TaskRecord.from_dict(item) for item in self._db_store.load_tasks()]
            environments = self._db_store.load_environments()
            execution_history = self._db_store.list_execution_history()
            if not tasks and not environments and not execution_history:
                self._import_json_mirror_into_db()
                tasks = [TaskRecord.from_dict(item) for item in self._db_store.load_tasks()]
                environments = self._db_store.load_environments()
                execution_history = self._db_store.list_execution_history()
            self._environments = {item.name: item for item in environments} or dict(DEFAULT_ENVIRONMENTS)
            if not environments:
                self._persist_environments()
            self._execution_history = execution_history
        else:
            tasks = [TaskRecord.from_dict(item) for item in self.task_repository.load_tasks()]
            self._load_environments_from_json()
            self._execution_history = self.execution_history_repository.load_history()

        if not tasks:
            tasks = self._recover_tasks_from_artifacts()
            if tasks:
                for record in tasks:
                    self._save_record(record)

        executions = self.execution_repository.load_executions()
        for record in tasks:
            record.execution_result = executions.get(record.task_id, record.execution_result)
            self._hydrate_task(record)
            self._tasks[record.task_id] = record
        if tasks and self._json_mirror_enabled:
            self._persist_json_mirror()

    def _import_json_mirror_into_db(self) -> None:
        if self._db_store is None:
            return
        json_tasks = [TaskRecord.from_dict(item) for item in self.task_repository.load_tasks()]
        json_executions = self.execution_repository.load_executions()
        json_environments = self.environment_repository.load_environments()
        json_history = self.execution_history_repository.load_history()
        if not json_tasks:
            json_tasks = self._recover_tasks_from_artifacts()
        for record in json_tasks:
            record.execution_result = json_executions.get(record.task_id, record.execution_result)
            self._db_store.save_task(record.to_dict())
        for item in json_environments:
            if item.get("name"):
                self._db_store.save_environment(EnvironmentConfig(**item))
        for item in json_history:
            if item.get("task_id"):
                self._db_store.append_execution_history(item)

    def _recover_tasks_from_artifacts(self) -> list[TaskRecord]:
        recovered: list[TaskRecord] = []
        root = Path(self.artifacts_root)
        if not root.exists():
            return recovered
        for candidate in sorted(root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
            if not candidate.is_dir():
                continue
            pipeline_result = load_pipeline_artifacts(str(candidate))
            task_context = pipeline_result.get("task_context") or {}
            task_id = str(task_context.get("task_id") or "")
            task_name = str(task_context.get("task_name") or candidate.name)
            if not task_id:
                continue
            status = "parsed"
            execution = pipeline_result.get("execution_result") or {}
            if execution.get("status"):
                status = str(execution.get("status"))
            record = TaskRecord(
                task_id=task_id,
                task_name=task_name,
                source_type=str(task_context.get("source_type") or "text"),
                requirement_text=str(pipeline_result.get("raw_requirement") or ""),
                source_path=task_context.get("source_path"),
                created_at=str(task_context.get("created_at") or _utc_now_iso()),
                status=status,
                task_context=task_context,
                pipeline_result=pipeline_result,
                execution_result=execution if execution else None,
                artifact_dir=str(candidate),
            )
            recovered.append(record)
        return recovered

    def _load_environments_from_json(self) -> None:
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

    def _persist_tasks_json(self) -> None:
        items = [record.to_dict() for record in self._tasks.values()]
        self.task_repository.save_tasks(items)

    def _persist_executions_json(self) -> None:
        executions = {
            task_id: record.execution_result
            for task_id, record in self._tasks.items()
            if record.execution_result is not None
        }
        self.execution_repository.save_executions(executions)

    def _persist_execution_history_json(self) -> None:
        self.execution_history_repository.save_history(self._execution_history)

    def _persist_environments_json(self) -> None:
        items = [config.to_dict() for _, config in sorted(self._environments.items())]
        self.environment_repository.save_environments(items)

    def _persist_json_mirror(self) -> None:
        self._persist_tasks_json()
        self._persist_executions_json()
        self._persist_execution_history_json()
        self._persist_environments_json()

    def _save_record(self, record: TaskRecord) -> None:
        self._tasks[record.task_id] = record
        if self._db_store is not None:
            self._db_store.save_task(record.to_dict())
        if self._json_mirror_enabled:
            self._persist_tasks_json()
            self._persist_executions_json()

    def _persist_environments(self) -> None:
        if self._db_store is not None:
            for _, config in sorted(self._environments.items()):
                self._db_store.save_environment(config)
        if self._json_mirror_enabled:
            self._persist_environments_json()

    def create_task(
        self,
        task_id: str,
        task_name: str,
        source_type: str,
        requirement_text: str,
        source_path: str | None = None,
        target_system: str | None = None,
        environment: str | None = None,
        project_id: str | None = None,
        created_by: str | None = None,
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
            project_id=project_id,
            created_by=created_by,
            task_context=task_context or {},
        )
        self._save_record(record)
        return record

    def save(self, record: TaskRecord) -> TaskRecord:
        self._save_record(record)
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

    def list_environments(
        self,
        *,
        project_id: str | None = None,
        include_global: bool = False,
    ) -> list[EnvironmentConfig]:
        if self._db_store is not None and project_id is not None:
            merged: dict[str, EnvironmentConfig] = {}
            if include_global:
                for item in self._db_store.load_environments(project_id=None):
                    merged[item.name] = item
            for item in self._db_store.load_environments(project_id=project_id):
                merged[item.name] = item
            if include_global:
                for name, config in self._environments.items():
                    merged.setdefault(name, config)
            return [merged[name] for name in sorted(merged)]
        return [self._environments[name] for name in sorted(self._environments)]

    def get_environment(self, name: str | None, *, project_id: str | None = None) -> EnvironmentConfig | None:
        if not name:
            return None
        if self._db_store is not None:
            db_env = self._db_store.get_environment(name=name, project_id=project_id, allow_global_fallback=True)
            if db_env is not None:
                return db_env
        return self._environments.get(name)

    def save_environment(
        self,
        config: EnvironmentConfig,
        *,
        project_id: str | None = None,
        created_by: str | None = None,
    ) -> EnvironmentConfig:
        if project_id is None:
            self._environments[config.name] = config
        if self._db_store is not None:
            self._db_store.save_environment(config, project_id=project_id, created_by=created_by)
        if project_id is None and self._json_mirror_enabled:
            self._persist_environments_json()
        return config

    def delete_environment(self, name: str, *, project_id: str | None = None) -> bool:
        deleted = False
        if project_id is None and name in self._environments:
            del self._environments[name]
            deleted = True
        if self._db_store is not None:
            deleted = self._db_store.delete_environment(name, project_id=project_id) or deleted
        if deleted and project_id is None and self._json_mirror_enabled:
            self._persist_environments_json()
        return deleted

    def append_execution_history(self, record: dict[str, Any]) -> dict[str, Any]:
        self._execution_history.append(record)
        self._execution_history.sort(key=lambda item: item.get("executed_at", ""), reverse=True)
        if self._db_store is not None and record.get("task_id"):
            self._db_store.append_execution_history(record)
        if self._json_mirror_enabled:
            self._persist_execution_history_json()
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
                item
                for item in items
                if keyword_lower in str(item.get("task_name", "")).lower()
                or keyword_lower in str(item.get("task_id", "")).lower()
                or keyword_lower in str(item.get("environment", "")).lower()
            ]
        return items


DEFAULT_ARTIFACT_TYPES = {
    "raw": lambda result: result.get("raw_requirement"),
    "parse-metadata": lambda result: result.get("parse_metadata", {}),
    "parsed-requirement": lambda result: result.get("parsed_requirement"),
    "retrieved-context": lambda result: result.get("retrieved_context"),
    "scenarios": lambda result: result.get("scenarios"),
    "dsl": lambda result: result.get("test_case_dsl"),
    "feature": lambda result: result.get("feature_text"),
    "validation-report": lambda result: result.get("validation_report"),
    "analysis-report": lambda result: result.get("analysis_report"),
}
