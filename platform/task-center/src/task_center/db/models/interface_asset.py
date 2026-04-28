"""Interface asset ORM models."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from task_center.db.base import Base, GUID, IdMixin, TimestampMixin


class InterfaceAsset(IdMixin, TimestampMixin, Base):
    __tablename__ = "interface_assets"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    name: Mapped[str | None] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    tags_json: Mapped[list | None] = mapped_column(JSON)
    request_example_json: Mapped[dict | list | None] = mapped_column(JSON)
    response_example_json: Mapped[dict | list | None] = mapped_column(JSON)
    schema_json: Mapped[dict | list | None] = mapped_column(JSON)
    last_seen_task_uid: Mapped[str | None] = mapped_column(String(128))
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))

    __table_args__ = (
        UniqueConstraint("project_id", "method", "path", "version", name="uq_interface_assets_project_method_path_version"),
        Index("ix_interface_assets_project_id", "project_id"),
        Index("ix_interface_assets_method", "method"),
        Index("ix_interface_assets_status", "status"),
    )
