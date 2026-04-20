"""Tests for runtime-state store selection and behavior."""

from __future__ import annotations

import sys
from pathlib import Path


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[3]
    additions = [
        root / "platform" / "task-center" / "src",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


_extend_path()


def test_runtime_store_falls_back_to_memory_when_redis_not_configured(monkeypatch) -> None:
    from task_center.runtime_store import InMemoryRuntimeStateStore, build_runtime_state_store

    monkeypatch.delenv("TASK_CENTER_REDIS_URL", raising=False)
    store = build_runtime_state_store()
    assert isinstance(store, InMemoryRuntimeStateStore)


def test_in_memory_runtime_store_roundtrip() -> None:
    from task_center.runtime_store import InMemoryRuntimeStateStore

    store = InMemoryRuntimeStateStore()
    store.save_context("task_1", {"status": "running"})
    store.save_progress("task_1", {"scenario_done": 1, "scenario_total": 3})

    assert store.load_context("task_1") == {"status": "running"}
    assert store.load_progress("task_1") == {"scenario_done": 1, "scenario_total": 3}

    store.clear_task("task_1")
    assert store.load_context("task_1") is None
    assert store.load_progress("task_1") is None
