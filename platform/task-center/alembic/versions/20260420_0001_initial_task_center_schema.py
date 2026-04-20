"""Initial task-center metadata schema.

Revision ID: 20260420_0001
Revises:
Create Date: 2026-04-20 03:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260420_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_index("ux_users_email", "users", ["email"], unique=True)
    op.create_index("ux_users_username", "users", ["username"], unique=True)

    op.create_table(
        "workspaces",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.CHAR(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_workspaces_owner_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
        sa.UniqueConstraint("slug", name=op.f("uq_workspaces_slug")),
    )

    op.create_table(
        "user_credentials",
        sa.Column("user_id", sa.CHAR(length=36), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("password_algo", sa.String(length=32), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("password_updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_credentials_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_credentials")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_credentials_user_id")),
    )

    op.create_table(
        "user_sessions",
        sa.Column("user_id", sa.CHAR(length=36), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=255), nullable=False),
        sa.Column("client_type", sa.String(length=32), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_sessions_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
        sa.UniqueConstraint("refresh_token_hash", name=op.f("uq_user_sessions_refresh_token_hash")),
    )
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"], unique=False)
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("user_id", sa.CHAR(length=36), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_audit_logs_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )

    op.create_table(
        "projects",
        sa.Column("workspace_id", sa.CHAR(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.CHAR(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_projects_created_by_users")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name=op.f("fk_projects_workspace_id_workspaces")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_index("ix_projects_created_by", "projects", ["created_by"], unique=False)
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"], unique=False)

    op.create_table(
        "project_members",
        sa.Column("project_id", sa.CHAR(length=36), nullable=False),
        sa.Column("user_id", sa.CHAR(length=36), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_project_members_project_id_projects")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_project_members_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_members")),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
    )

    op.create_table(
        "tasks",
        sa.Column("task_uid", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.CHAR(length=36), nullable=True),
        sa.Column("created_by", sa.CHAR(length=36), nullable=True),
        sa.Column("task_name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_path", sa.String(length=1024), nullable=True),
        sa.Column("target_system", sa.String(length=512), nullable=True),
        sa.Column("environment_name", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("artifact_dir", sa.String(length=1024), nullable=True),
        sa.Column("current_run_id", sa.CHAR(length=36), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_tasks_created_by_users")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_tasks_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
        sa.UniqueConstraint("task_uid", name=op.f("uq_tasks_task_uid")),
    )
    op.create_index("ix_tasks_created_by_created_at", "tasks", ["created_by", "created_at"], unique=False)
    op.create_index("ix_tasks_project_id_created_at", "tasks", ["project_id", "created_at"], unique=False)
    op.create_index("ix_tasks_status_created_at", "tasks", ["status", "created_at"], unique=False)
    op.create_index("ux_tasks_task_uid", "tasks", ["task_uid"], unique=True)

    op.create_table(
        "task_inputs",
        sa.Column("task_id", sa.CHAR(length=36), nullable=False),
        sa.Column("requirement_text", sa.Text(), nullable=True),
        sa.Column("source_file_sha256", sa.String(length=64), nullable=True),
        sa.Column("analysis_options_json", sa.JSON(), nullable=True),
        sa.Column("execution_options_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_task_inputs_task_id_tasks")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_inputs")),
    )

    op.create_table(
        "task_runs",
        sa.Column("task_id", sa.CHAR(length=36), nullable=False),
        sa.Column("run_no", sa.Integer(), nullable=False),
        sa.Column("triggered_by", sa.CHAR(length=36), nullable=True),
        sa.Column("execution_mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("parse_mode", sa.String(length=32), nullable=True),
        sa.Column("llm_used", sa.Boolean(), nullable=False),
        sa.Column("rag_enabled", sa.Boolean(), nullable=False),
        sa.Column("rag_used", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("progress_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("runtime_context_snapshot_path", sa.String(length=1024), nullable=True),
        sa.Column("analysis_report_path", sa.String(length=1024), nullable=True),
        sa.Column("execution_result_path", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_task_runs_task_id_tasks")),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"], name=op.f("fk_task_runs_triggered_by_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_runs")),
        sa.UniqueConstraint("task_id", "run_no", name="uq_task_runs_task_run_no"),
    )
    op.create_index("ix_task_runs_status_started_at", "task_runs", ["status", "started_at"], unique=False)
    op.create_index("ix_task_runs_task_id_run_no", "task_runs", ["task_id", "run_no"], unique=False)
    op.create_index("ix_task_runs_triggered_by_started_at", "task_runs", ["triggered_by", "started_at"], unique=False)

    op.create_table(
        "task_status_events",
        sa.Column("task_id", sa.CHAR(length=36), nullable=False),
        sa.Column("run_id", sa.CHAR(length=36), nullable=True),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("operator_user_id", sa.CHAR(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"], name=op.f("fk_task_status_events_operator_user_id_users")),
        sa.ForeignKeyConstraint(["run_id"], ["task_runs.id"], name=op.f("fk_task_status_events_run_id_task_runs")),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_task_status_events_task_id_tasks")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_status_events")),
    )

    op.create_table(
        "environments",
        sa.Column("project_id", sa.CHAR(length=36), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("default_headers_json", sa.JSON(), nullable=True),
        sa.Column("auth_json", sa.JSON(), nullable=True),
        sa.Column("cookies_json", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.CHAR(length=36), nullable=True),
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_environments_created_by_users")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_environments_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_environments")),
        sa.UniqueConstraint("project_id", "name", name="uq_environments_project_name"),
    )


def downgrade() -> None:
    op.drop_table("environments")
    op.drop_table("task_status_events")
    op.drop_index("ix_task_runs_triggered_by_started_at", table_name="task_runs")
    op.drop_index("ix_task_runs_task_id_run_no", table_name="task_runs")
    op.drop_index("ix_task_runs_status_started_at", table_name="task_runs")
    op.drop_table("task_runs")
    op.drop_table("task_inputs")
    op.drop_index("ux_tasks_task_uid", table_name="tasks")
    op.drop_index("ix_tasks_status_created_at", table_name="tasks")
    op.drop_index("ix_tasks_project_id_created_at", table_name="tasks")
    op.drop_index("ix_tasks_created_by_created_at", table_name="tasks")
    op.drop_table("tasks")
    op.drop_table("project_members")
    op.drop_index("ix_projects_workspace_id", table_name="projects")
    op.drop_index("ix_projects_created_by", table_name="projects")
    op.drop_table("projects")
    op.drop_table("audit_logs")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_table("user_credentials")
    op.drop_table("workspaces")
    op.drop_index("ux_users_username", table_name="users")
    op.drop_index("ux_users_email", table_name="users")
    op.drop_table("users")
