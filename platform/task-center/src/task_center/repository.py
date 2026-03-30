"""Persistent repositories for task-center state."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any


def _utc_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


class JsonRepository:
    """Small JSON-backed repository helper."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except JSONDecodeError:
            corrupt_path = self.path.with_suffix(f"{self.path.suffix}.corrupt.{_utc_suffix()}")
            self.path.replace(corrupt_path)
            return {}

    def save(self, payload: dict[str, Any]) -> None:
        temp_path = self.path.with_suffix(f"{self.path.suffix}.{os.getpid()}.{_utc_suffix()}.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.path)


class TaskRepository(JsonRepository):
    """Store task metadata and artifact references."""

    def load_tasks(self) -> list[dict[str, Any]]:
        payload = self.load()
        return list(payload.get("tasks", []))

    def save_tasks(self, tasks: list[dict[str, Any]]) -> None:
        self.save({"tasks": tasks})


class ExecutionRepository(JsonRepository):
    """Store execution snapshots keyed by task id."""

    def load_executions(self) -> dict[str, dict[str, Any]]:
        payload = self.load()
        return dict(payload.get("executions", {}))

    def save_executions(self, executions: dict[str, dict[str, Any]]) -> None:
        self.save({"executions": executions})


class ExecutionHistoryRepository(JsonRepository):
    """Store execution history records."""

    def load_history(self) -> list[dict[str, Any]]:
        payload = self.load()
        return list(payload.get("history", []))

    def save_history(self, history: list[dict[str, Any]]) -> None:
        self.save({"history": history})


class EnvironmentRepository(JsonRepository):
    """Store named execution environments."""

    def load_environments(self) -> list[dict[str, Any]]:
        payload = self.load()
        return list(payload.get("environments", []))

    def save_environments(self, environments: list[dict[str, Any]]) -> None:
        self.save({"environments": environments})
