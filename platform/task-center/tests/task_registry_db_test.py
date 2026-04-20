"""Integration tests for DB-backed task registry."""

from __future__ import annotations

import sys
from pathlib import Path


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[3]
    additions = [
        root / "platform" / "shared" / "src",
        root / "platform" / "task-center" / "src",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


_extend_path()


def test_db_backed_registry_persists_tasks_and_history(tmp_path, monkeypatch) -> None:
    from platform_shared.models import EnvironmentConfig
    from task_center.registry import TaskRecord, TaskRegistry

    db_path = tmp_path / "registry.db"
    artifacts_root = tmp_path / "artifacts"
    monkeypatch.setenv("TASK_CENTER_PERSISTENCE_BACKEND", "db")
    monkeypatch.setenv("TASK_CENTER_DATABASE_URL", f"sqlite+pysqlite:///{db_path.as_posix()}")

    registry = TaskRegistry(str(artifacts_root))
    assert registry.list_environments()

    record = registry.create_task(
        task_id="task_demo_001",
        task_name="Demo Task",
        source_type="text",
        requirement_text="test requirement",
        source_path=None,
        target_system="https://example.com",
        environment="test",
        task_context={"task_id": "task_demo_001", "task_name": "Demo Task", "status": "received"},
    )
    record.status = "parsed"
    record.artifact_dir = str(artifacts_root / "task_demo_001")
    registry.save(record)
    registry.save_environment(EnvironmentConfig(name="qa", base_url="https://qa.example.com"))
    registry.append_execution_history(
        {
            "task_id": "task_demo_001",
            "task_name": "Demo Task",
            "environment": "qa",
            "execution_mode": "api",
            "status": "passed",
            "executed_at": "2026-04-20T03:30:00+00:00",
            "metrics": {"duration_ms": 1200},
            "analysis_summary": {"success_rate": 1.0, "failed_steps": 0, "avg_elapsed_ms": 1200},
        }
    )

    reloaded = TaskRegistry(str(artifacts_root))
    task = reloaded.get("task_demo_001")
    assert task is not None
    assert task.task_name == "Demo Task"
    assert task.status == "passed"
    assert any(item.name == "qa" for item in reloaded.list_environments())
    history = reloaded.list_execution_history(task_id="task_demo_001")
    assert len(history) == 1
    assert history[0]["status"] == "passed"
    assert history[0]["execution_mode"] == "api"


def test_db_backed_registry_archive_roundtrip(tmp_path, monkeypatch) -> None:
    from task_center.registry import TaskRegistry

    db_path = tmp_path / "archive.db"
    artifacts_root = tmp_path / "artifacts"
    monkeypatch.setenv("TASK_CENTER_PERSISTENCE_BACKEND", "db")
    monkeypatch.setenv("TASK_CENTER_DATABASE_URL", f"sqlite+pysqlite:///{db_path.as_posix()}")

    registry = TaskRegistry(str(artifacts_root))
    registry.create_task(
        task_id="task_demo_002",
        task_name="Archive Task",
        source_type="text",
        requirement_text="archive me",
        task_context={"task_id": "task_demo_002", "task_name": "Archive Task", "status": "received"},
    )
    assert registry.archive("task_demo_002") is True

    reloaded = TaskRegistry(str(artifacts_root))
    task = reloaded.get("task_demo_002")
    assert task is not None
    assert task.archived is True
    visible_ids = [item.task_id for item in reloaded.list()]
    assert "task_demo_002" not in visible_ids


def test_db_backend_disables_json_mirror_by_default(tmp_path, monkeypatch) -> None:
    from task_center.registry import TaskRegistry

    db_path = tmp_path / "registry_no_mirror.db"
    artifacts_root = tmp_path / "artifacts"
    monkeypatch.setenv("TASK_CENTER_PERSISTENCE_BACKEND", "db")
    monkeypatch.setenv("TASK_CENTER_DATABASE_URL", f"sqlite+pysqlite:///{db_path.as_posix()}")
    monkeypatch.delenv("TASK_CENTER_JSON_MIRROR_ENABLED", raising=False)

    registry = TaskRegistry(str(artifacts_root))
    registry.create_task(
        task_id="task_demo_003",
        task_name="No Mirror Task",
        source_type="text",
        requirement_text="db only",
        task_context={"task_id": "task_demo_003", "task_name": "No Mirror Task", "status": "received"},
    )

    assert not (artifacts_root / "tasks.json").exists()
    assert not (artifacts_root / "executions.json").exists()
