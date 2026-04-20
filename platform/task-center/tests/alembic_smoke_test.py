"""Smoke test for task-center Alembic migrations."""

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
pytest.importorskip("alembic")
pytest.importorskip("sqlalchemy")


def test_alembic_upgrade_builds_expected_tables(tmp_path: Path) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    task_center_dir = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "task_center_alembic.db"

    config = Config(str(task_center_dir / "alembic.ini"))
    config.set_main_option("script_location", str(task_center_dir / "alembic"))
    config.set_main_option("prepend_sys_path", str(task_center_dir / "src"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{db_path.as_posix()}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    assert {
        "users",
        "projects",
        "tasks",
        "task_runs",
        "environments",
    }.issubset(table_names)
