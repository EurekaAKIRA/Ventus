"""Add test case assets for maintainable API test suites.

Revision ID: 20260428_0005
Revises: 20260428_0004
Create Date: 2026-04-28 19:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260428_0005"
down_revision = "20260428_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "test_case_assets",
        sa.Column("project_id", sa.CHAR(length=36), nullable=False),
        sa.Column("case_key", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_task_uid", sa.String(length=128), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=True),
        sa.Column("dsl_scenario_json", sa.JSON(), nullable=True),
        sa.Column("assertions_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.CHAR(length=36), nullable=True),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_test_case_assets_created_by_users")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_test_case_assets_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_case_assets")),
        sa.UniqueConstraint("project_id", "case_key", name="uq_test_case_assets_project_case_key"),
    )
    op.create_index("ix_test_case_assets_project_id", "test_case_assets", ["project_id"], unique=False)
    op.create_index("ix_test_case_assets_status", "test_case_assets", ["status"], unique=False)
    op.create_index("ix_test_case_assets_source_task_uid", "test_case_assets", ["source_task_uid"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_test_case_assets_source_task_uid", table_name="test_case_assets")
    op.drop_index("ix_test_case_assets_status", table_name="test_case_assets")
    op.drop_index("ix_test_case_assets_project_id", table_name="test_case_assets")
    op.drop_table("test_case_assets")
