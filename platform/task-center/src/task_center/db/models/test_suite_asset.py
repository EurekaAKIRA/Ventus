"""Test suite asset ORM models."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from task_center.db.base import Base, GUID, IdMixin, TimestampMixin


class TestSuiteAsset(IdMixin, TimestampMixin, Base):
    __tablename__ = "test_suite_assets"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    case_ids_json: Mapped[list | None] = mapped_column(JSON)
    tags_json: Mapped[list | None] = mapped_column(JSON)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))

    __table_args__ = (
        Index("ix_test_suite_assets_project_id", "project_id"),
        Index("ix_test_suite_assets_status", "status"),
    )
