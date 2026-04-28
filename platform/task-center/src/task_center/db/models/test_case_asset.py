"""Test case asset ORM models."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from task_center.db.base import Base, GUID, IdMixin, TimestampMixin


class TestCaseAsset(IdMixin, TimestampMixin, Base):
    __tablename__ = "test_case_assets"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    case_key: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="P1")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    source_task_uid: Mapped[str | None] = mapped_column(String(128))
    tags_json: Mapped[list | None] = mapped_column(JSON)
    dsl_scenario_json: Mapped[dict | list | None] = mapped_column(JSON)
    assertions_json: Mapped[list | dict | None] = mapped_column(JSON)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))

    __table_args__ = (
        UniqueConstraint("project_id", "case_key", name="uq_test_case_assets_project_case_key"),
        Index("ix_test_case_assets_project_id", "project_id"),
        Index("ix_test_case_assets_status", "status"),
        Index("ix_test_case_assets_source_task_uid", "source_task_uid"),
    )
