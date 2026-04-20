"""Task-domain ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from task_center.db.base import Base, GUID, IdMixin, TimestampMixin


class Task(IdMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    task_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_path: Mapped[str | None] = mapped_column(String(1024))
    target_system: Mapped[str | None] = mapped_column(String(512))
    environment_name: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    artifact_dir: Mapped[str | None] = mapped_column(String(1024))
    current_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ux_tasks_task_uid", "task_uid", unique=True),
        Index("ix_tasks_project_id_created_at", "project_id", "created_at"),
        Index("ix_tasks_created_by_created_at", "created_by", "created_at"),
        Index("ix_tasks_status_created_at", "status", "created_at"),
    )


class TaskInput(IdMixin, Base):
    __tablename__ = "task_inputs"

    task_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tasks.id"), nullable=False)
    requirement_text: Mapped[str | None] = mapped_column(Text)
    source_file_sha256: Mapped[str | None] = mapped_column(String(64))
    analysis_options_json: Mapped[dict | list | None] = mapped_column(JSON)
    execution_options_json: Mapped[dict | list | None] = mapped_column(JSON)
    created_at: Mapped[datetime]


class TaskRun(IdMixin, Base):
    __tablename__ = "task_runs"

    task_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tasks.id"), nullable=False)
    run_no: Mapped[int] = mapped_column(Integer, nullable=False)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    execution_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    parse_mode: Mapped[str | None] = mapped_column(String(32))
    llm_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rag_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rag_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    duration_ms: Mapped[int | None]
    summary_json: Mapped[dict | list | None] = mapped_column(JSON)
    progress_snapshot_json: Mapped[dict | list | None] = mapped_column(JSON)
    runtime_context_snapshot_path: Mapped[str | None] = mapped_column(String(1024))
    analysis_report_path: Mapped[str | None] = mapped_column(String(1024))
    execution_result_path: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime]

    __table_args__ = (
        UniqueConstraint("task_id", "run_no", name="uq_task_runs_task_run_no"),
        Index("ix_task_runs_task_id_run_no", "task_id", "run_no"),
        Index("ix_task_runs_triggered_by_started_at", "triggered_by", "started_at"),
        Index("ix_task_runs_status_started_at", "status", "started_at"),
    )


class TaskStatusEvent(IdMixin, Base):
    __tablename__ = "task_status_events"

    task_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tasks.id"), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("task_runs.id"))
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    operator_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    created_at: Mapped[datetime]
