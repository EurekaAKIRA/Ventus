"""Add defects table for project-scoped defect management.

Revision ID: 20260421_0002
Revises: 20260420_0001
Create Date: 2026-04-21 11:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260421_0002"
down_revision = "20260420_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "defects",
        sa.Column("defect_key", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.CHAR(length=36), nullable=False),
        sa.Column("task_id", sa.CHAR(length=36), nullable=True),
        sa.Column("reporter_user_id", sa.CHAR(length=36), nullable=False),
        sa.Column("assignee_user_id", sa.CHAR(length=36), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("reproduction_steps", sa.Text(), nullable=True),
        sa.Column("expected_result", sa.Text(), nullable=True),
        sa.Column("actual_result", sa.Text(), nullable=True),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"], name=op.f("fk_defects_assignee_user_id_users")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_defects_project_id_projects")),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"], name=op.f("fk_defects_reporter_user_id_users")),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_defects_task_id_tasks")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_defects")),
        sa.UniqueConstraint("defect_key", name=op.f("uq_defects_defect_key")),
    )
    op.create_index("ux_defects_defect_key", "defects", ["defect_key"], unique=True)
    op.create_index("ix_defects_project_status_created_at", "defects", ["project_id", "status", "created_at"], unique=False)
    op.create_index("ix_defects_task_id_created_at", "defects", ["task_id", "created_at"], unique=False)
    op.create_index("ix_defects_assignee_status", "defects", ["assignee_user_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_defects_assignee_status", table_name="defects")
    op.drop_index("ix_defects_task_id_created_at", table_name="defects")
    op.drop_index("ix_defects_project_status_created_at", table_name="defects")
    op.drop_index("ux_defects_defect_key", table_name="defects")
    op.drop_table("defects")
