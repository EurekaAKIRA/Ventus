"""Add persistent platform role to users.

Revision ID: 20260428_0003
Revises: 20260421_0002
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260428_0003"
down_revision = "20260421_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("platform_role", sa.String(length=32), nullable=False, server_default="user"))
    op.execute("UPDATE users SET platform_role = 'admin' WHERE username = 'admin'")


def downgrade() -> None:
    op.drop_column("users", "platform_role")
