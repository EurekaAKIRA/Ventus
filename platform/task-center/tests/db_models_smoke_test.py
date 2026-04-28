"""Smoke tests for the task-center database scaffolding."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


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
pytest.importorskip("sqlalchemy")


def test_task_center_db_models_create_tables_in_sqlite_memory() -> None:
    from sqlalchemy import inspect

    from task_center.db import Base, create_task_center_engine

    engine = create_task_center_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    assert {
        "users",
        "user_credentials",
        "user_sessions",
        "workspaces",
        "projects",
        "project_members",
        "tasks",
        "task_inputs",
        "task_runs",
        "task_status_events",
        "environments",
        "audit_logs",
    }.issubset(table_names)


def test_task_runs_table_contains_snapshot_columns() -> None:
    from sqlalchemy import inspect

    from task_center.db import Base, create_task_center_engine

    engine = create_task_center_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("task_runs")}

    assert "progress_snapshot_json" in columns
    assert "runtime_context_snapshot_path" in columns


def test_users_table_contains_profile_and_role_columns() -> None:
    from sqlalchemy import inspect

    from task_center.db import Base, create_task_center_engine

    engine = create_task_center_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("users")}

    assert "avatar_url" in columns
    assert "platform_role" in columns
