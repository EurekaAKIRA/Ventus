"""Defect-domain ORM models."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from task_center.db.base import Base, GUID, IdMixin, TimestampMixin


class Defect(IdMixin, TimestampMixin, Base):
    __tablename__ = "defects"

    defect_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("tasks.id"))
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    reproduction_steps: Mapped[str | None] = mapped_column(Text)
    expected_result: Mapped[str | None] = mapped_column(Text)
    actual_result: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ux_defects_defect_key", "defect_key", unique=True),
        Index("ix_defects_project_status_created_at", "project_id", "status", "created_at"),
        Index("ix_defects_task_id_created_at", "task_id", "created_at"),
        Index("ix_defects_assignee_status", "assignee_user_id", "status"),
    )
