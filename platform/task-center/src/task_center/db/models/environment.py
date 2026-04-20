"""Environment-domain ORM models."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from task_center.db.base import Base, GUID, IdMixin, TimestampMixin


class Environment(IdMixin, TimestampMixin, Base):
    __tablename__ = "environments"

    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(512))
    default_headers_json: Mapped[dict | list | None] = mapped_column(JSON)
    auth_json: Mapped[dict | list | None] = mapped_column(JSON)
    cookies_json: Mapped[dict | list | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_environments_project_name"),
    )
