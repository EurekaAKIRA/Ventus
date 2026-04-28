"""Add test suite assets for regression suites.

Revision ID: 20260428_0006
Revises: 20260428_0005
Create Date: 2026-04-28 20:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260428_0006"
down_revision = "20260428_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "test_suite_assets",
        sa.Column("project_id", sa.CHAR(length=36), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("case_ids_json", sa.JSON(), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.CHAR(length=36), nullable=True),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_test_suite_assets_created_by_users")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_test_suite_assets_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_suite_assets")),
    )
    op.create_index("ix_test_suite_assets_project_id", "test_suite_assets", ["project_id"], unique=False)
    op.create_index("ix_test_suite_assets_status", "test_suite_assets", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_test_suite_assets_status", table_name="test_suite_assets")
    op.drop_index("ix_test_suite_assets_project_id", table_name="test_suite_assets")
    op.drop_table("test_suite_assets")
