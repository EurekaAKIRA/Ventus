"""Add interface assets for API inventory management.

Revision ID: 20260428_0004
Revises: 20260428_0003
Create Date: 2026-04-28 19:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260428_0004"
down_revision = "20260428_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interface_assets",
        sa.Column("project_id", sa.CHAR(length=36), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=True),
        sa.Column("request_example_json", sa.JSON(), nullable=True),
        sa.Column("response_example_json", sa.JSON(), nullable=True),
        sa.Column("schema_json", sa.JSON(), nullable=True),
        sa.Column("last_seen_task_uid", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.CHAR(length=36), nullable=True),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_interface_assets_created_by_users")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_interface_assets_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interface_assets")),
        sa.UniqueConstraint("project_id", "method", "path", "version", name="uq_interface_assets_project_method_path_version"),
    )
    op.create_index("ix_interface_assets_project_id", "interface_assets", ["project_id"], unique=False)
    op.create_index("ix_interface_assets_method", "interface_assets", ["method"], unique=False)
    op.create_index("ix_interface_assets_status", "interface_assets", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_interface_assets_status", table_name="interface_assets")
    op.drop_index("ix_interface_assets_method", table_name="interface_assets")
    op.drop_index("ix_interface_assets_project_id", table_name="interface_assets")
    op.drop_table("interface_assets")
