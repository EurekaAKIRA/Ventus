"""Database engine and session helpers for task-center."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def default_sqlite_path() -> Path:
    """Return the default sqlite database file path."""
    root = Path(__file__).resolve().parents[3]
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "task_center.db"


def get_database_url() -> str:
    """Resolve the task-center database URL from env or fallback sqlite path."""
    return os.getenv("TASK_CENTER_DATABASE_URL", f"sqlite+pysqlite:///{default_sqlite_path().as_posix()}")


def create_task_center_engine(database_url: str | None = None, *, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine for task-center metadata storage."""
    return create_engine(database_url or get_database_url(), echo=echo, future=True)


def create_session_factory(database_url: str | None = None, *, echo: bool = False) -> sessionmaker[Session]:
    """Create a configured SQLAlchemy session factory."""
    engine = create_task_center_engine(database_url=database_url, echo=echo)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
