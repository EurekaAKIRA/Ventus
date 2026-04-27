"""Database-backed persistence for task-center registry state."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from platform_shared.models import EnvironmentConfig
from sqlalchemy import select
from sqlalchemy import or_
from sqlalchemy.orm import Session, aliased, sessionmaker

from task_center.db import (
    AuditLog,
    Base,
    Defect,
    Environment,
    Project,
    ProjectMember,
    Task,
    TaskInput,
    TaskRun,
    User,
    UserCredential,
    UserSession,
    Workspace,
    create_task_center_engine,
)
from task_center.secure_config import decrypt_json_payload, encrypt_json_payload


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_json_dict(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return dict(payload)
    return {}


class DatabaseTaskStore:
    """Persistence adapter over SQLAlchemy models."""

    def __init__(self, database_url: str | None = None):
        self.engine = create_task_center_engine(database_url=database_url)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _task_to_record(self, task_row: Task, input_row: TaskInput | None) -> dict[str, Any]:
        task_context = {}
        requirement_text = ""
        if input_row is not None:
            requirement_text = input_row.requirement_text or ""
            analysis_options = _ensure_json_dict(input_row.analysis_options_json)
            task_context = _ensure_json_dict(analysis_options.get("task_context"))
        created_at = task_row.created_at.isoformat() if task_row.created_at else _utc_now().isoformat()
        if not task_context:
            task_context = {
                "task_id": task_row.task_uid,
                "task_name": task_row.task_name,
                "source_type": task_row.source_type,
                "source_path": task_row.source_path,
                "created_at": created_at,
                "status": task_row.status,
            }
        else:
            task_context.setdefault("task_id", task_row.task_uid)
            task_context.setdefault("task_name", task_row.task_name)
            task_context.setdefault("source_type", task_row.source_type)
            task_context.setdefault("source_path", task_row.source_path)
            task_context.setdefault("created_at", created_at)
            task_context["status"] = task_row.status
        return {
            "task_id": task_row.task_uid,
            "task_name": task_row.task_name,
            "source_type": task_row.source_type,
            "requirement_text": requirement_text,
            "source_path": task_row.source_path,
            "target_system": task_row.target_system,
            "environment": task_row.environment_name,
            "project_id": str(task_row.project_id) if task_row.project_id else None,
            "created_by": str(task_row.created_by) if task_row.created_by else None,
            "created_at": created_at,
            "status": task_row.status,
            "task_context": task_context,
            "pipeline_result": None,
            "execution_result": None,
            "artifact_dir": task_row.artifact_dir,
            "archived": bool(task_row.archived),
        }

    def load_tasks(self) -> list[dict[str, Any]]:
        with self.session() as session:
            tasks = session.scalars(select(Task).order_by(Task.created_at.desc())).all()
            if not tasks:
                return []
            task_ids = [task.id for task in tasks]
            inputs = session.scalars(select(TaskInput).where(TaskInput.task_id.in_(task_ids))).all()
            input_map: dict[uuid.UUID, TaskInput] = {}
            for item in inputs:
                current = input_map.get(item.task_id)
                if current is None or (item.created_at and current.created_at and item.created_at >= current.created_at):
                    input_map[item.task_id] = item
            return [self._task_to_record(task, input_map.get(task.id)) for task in tasks]

    def save_task(self, record: dict[str, Any]) -> None:
        with self.session() as session:
            task_row = session.scalar(select(Task).where(Task.task_uid == record["task_id"]))
            if task_row is None:
                task_row = Task(
                    task_uid=record["task_id"],
                    task_name=record["task_name"],
                    source_type=record["source_type"],
                    created_at=self._parse_dt(record.get("created_at")),
                    updated_at=_utc_now(),
                )
                session.add(task_row)
                session.flush()

            task_row.task_name = record["task_name"]
            task_row.source_type = record["source_type"]
            task_row.source_path = record.get("source_path")
            task_row.target_system = record.get("target_system")
            task_row.environment_name = record.get("environment")
            task_row.project_id = self._parse_uuid(record.get("project_id"))
            task_row.created_by = self._parse_uuid(record.get("created_by"))
            task_row.status = record.get("status") or "received"
            task_row.artifact_dir = record.get("artifact_dir")
            task_row.archived = bool(record.get("archived", False))
            task_row.updated_at = _utc_now()
            if record.get("created_at") and task_row.created_at is None:
                task_row.created_at = self._parse_dt(record.get("created_at"))

            input_row = session.scalar(select(TaskInput).where(TaskInput.task_id == task_row.id))
            if input_row is None:
                input_row = TaskInput(
                    task_id=task_row.id,
                    created_at=self._parse_dt(record.get("created_at")) or _utc_now(),
                )
                session.add(input_row)
            input_row.requirement_text = record.get("requirement_text") or ""
            input_row.analysis_options_json = {
                "task_context": _ensure_json_dict(record.get("task_context")),
            }

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self.session() as session:
            task_row = session.scalar(select(Task).where(Task.task_uid == task_id))
            if task_row is None:
                return None
            input_row = session.scalar(select(TaskInput).where(TaskInput.task_id == task_row.id))
            return self._task_to_record(task_row, input_row)

    def save_environment(
        self,
        config: EnvironmentConfig,
        *,
        project_id: str | None = None,
        created_by: str | None = None,
    ) -> None:
        with self.session() as session:
            row = session.scalar(
                select(Environment).where(
                    Environment.project_id == self._parse_uuid(project_id),
                    Environment.name == config.name,
                )
            )
            if row is None:
                row = Environment(
                    project_id=self._parse_uuid(project_id),
                    name=config.name,
                    created_by=self._parse_uuid(created_by),
                    created_at=_utc_now(),
                    updated_at=_utc_now(),
                )
                session.add(row)
            if created_by and row.created_by is None:
                row.created_by = self._parse_uuid(created_by)
            row.base_url = config.base_url
            row.default_headers_json = encrypt_json_payload(dict(config.default_headers or {}))
            row.auth_json = encrypt_json_payload(dict(config.auth or {}))
            row.cookies_json = encrypt_json_payload(dict(config.cookies or {}))
            row.description = config.description
            row.updated_at = _utc_now()

    def load_environments(self, *, project_id: str | None = None, include_global: bool = False) -> list[EnvironmentConfig]:
        with self.session() as session:
            project_uuid = self._parse_uuid(project_id)
            stmt = select(Environment)
            if project_uuid is None:
                stmt = stmt.where(Environment.project_id.is_(None))
            elif include_global:
                stmt = stmt.where(or_(Environment.project_id == project_uuid, Environment.project_id.is_(None)))
            else:
                stmt = stmt.where(Environment.project_id == project_uuid)
            rows = session.scalars(stmt.order_by(Environment.name.asc(), Environment.created_at.asc())).all()
            return [
                EnvironmentConfig(
                    name=row.name,
                    base_url=row.base_url or "",
                    default_headers=_ensure_json_dict(decrypt_json_payload(row.default_headers_json)),
                    auth=_ensure_json_dict(decrypt_json_payload(row.auth_json)),
                    cookies=_ensure_json_dict(decrypt_json_payload(row.cookies_json)),
                    description=row.description or "",
                )
                for row in rows
            ]

    def get_environment(self, *, name: str, project_id: str | None = None, allow_global_fallback: bool = True) -> EnvironmentConfig | None:
        with self.session() as session:
            project_uuid = self._parse_uuid(project_id)
            if project_uuid is not None:
                row = session.scalar(
                    select(Environment).where(Environment.project_id == project_uuid, Environment.name == name)
                )
                if row is not None:
                    return EnvironmentConfig(
                        name=row.name,
                        base_url=row.base_url or "",
                        default_headers=_ensure_json_dict(decrypt_json_payload(row.default_headers_json)),
                        auth=_ensure_json_dict(decrypt_json_payload(row.auth_json)),
                        cookies=_ensure_json_dict(decrypt_json_payload(row.cookies_json)),
                        description=row.description or "",
                    )
            if not allow_global_fallback:
                return None
            row = session.scalar(select(Environment).where(Environment.project_id.is_(None), Environment.name == name))
            if row is None:
                return None
            return EnvironmentConfig(
                name=row.name,
                base_url=row.base_url or "",
                default_headers=_ensure_json_dict(decrypt_json_payload(row.default_headers_json)),
                auth=_ensure_json_dict(decrypt_json_payload(row.auth_json)),
                cookies=_ensure_json_dict(decrypt_json_payload(row.cookies_json)),
                description=row.description or "",
            )

    def delete_environment(self, name: str, *, project_id: str | None = None) -> bool:
        with self.session() as session:
            row = session.scalar(
                select(Environment).where(
                    Environment.project_id == self._parse_uuid(project_id),
                    Environment.name == name,
                )
            )
            if row is None:
                return False
            session.delete(row)
            return True

    def append_execution_history(self, record: dict[str, Any]) -> dict[str, Any]:
        with self.session() as session:
            task_row = session.scalar(select(Task).where(Task.task_uid == record["task_id"]))
            if task_row is None:
                return dict(record)
            latest = session.scalar(
                select(TaskRun)
                .where(TaskRun.task_id == task_row.id)
                .order_by(TaskRun.run_no.desc())
                .limit(1)
            )
            run_no = 1 if latest is None else latest.run_no + 1
            executed_at = self._parse_dt(record.get("executed_at")) or _utc_now()
            run = TaskRun(
                task_id=task_row.id,
                run_no=run_no,
                execution_mode=str(record.get("execution_mode") or "api"),
                status=str(record.get("status") or task_row.status or "unknown"),
                parse_mode=str(record.get("parse_mode") or "") or None,
                llm_used=bool(record.get("llm_used", False)),
                rag_enabled=bool(record.get("rag_enabled", False)),
                rag_used=bool(record.get("rag_used", False)),
                started_at=executed_at,
                finished_at=executed_at,
                duration_ms=self._to_int(record.get("duration_ms")),
                summary_json=dict(record),
                progress_snapshot_json=_ensure_json_dict(record.get("progress_snapshot")),
                runtime_context_snapshot_path=record.get("runtime_context_snapshot_path"),
                analysis_report_path=record.get("analysis_report_path"),
                execution_result_path=record.get("execution_result_path"),
                created_at=executed_at,
            )
            session.add(run)
            session.flush()
            task_row.current_run_id = run.id
            task_row.status = str(record.get("status") or task_row.status)
            task_row.updated_at = _utc_now()
            return dict(record)

    def list_execution_history(self) -> list[dict[str, Any]]:
        with self.session() as session:
            rows = session.execute(
                select(TaskRun, Task)
                .join(Task, Task.id == TaskRun.task_id)
                .order_by(TaskRun.created_at.desc(), TaskRun.run_no.desc())
            ).all()
            output: list[dict[str, Any]] = []
            for run, task in rows:
                summary = _ensure_json_dict(run.summary_json)
                output.append(
                    {
                        "task_id": task.task_uid,
                        "task_name": task.task_name,
                        "environment": summary.get("environment") or task.environment_name,
                        "execution_mode": run.execution_mode,
                        "status": run.status,
                        "executor": summary.get("executor"),
                        "executed_at": (
                            run.finished_at.isoformat()
                            if run.finished_at
                            else run.created_at.isoformat() if run.created_at else _utc_now().isoformat()
                        ),
                        "metrics": _ensure_json_dict(summary.get("metrics")),
                        "analysis_summary": _ensure_json_dict(summary.get("analysis_summary")),
                        "parse_mode": run.parse_mode,
                        "llm_used": bool(run.llm_used),
                        "rag_enabled": bool(run.rag_enabled),
                        "rag_used": bool(run.rag_used),
                        "runtime_context_snapshot_path": run.runtime_context_snapshot_path,
                        "analysis_report_path": run.analysis_report_path,
                        "execution_result_path": run.execution_result_path,
                    }
                )
            return output

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        with self.session() as session:
            row = session.scalar(select(User).where(User.username == username))
            return self._user_to_payload(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self.session() as session:
            row = session.scalar(select(User).where(User.id == self._parse_uuid(user_id)))
            return self._user_to_payload(row) if row else None

    def create_user(
        self,
        *,
        username: str,
        email: str | None,
        display_name: str,
        password_hash: str,
        password_algo: str = "bcrypt",
    ) -> dict[str, Any]:
        with self.session() as session:
            if session.scalar(select(User).where(User.username == username)) is not None:
                raise ValueError(f"username already exists: {username}")
            if email and session.scalar(select(User).where(User.email == email)) is not None:
                raise ValueError(f"email already exists: {email}")
            user = User(
                username=username,
                email=email,
                display_name=display_name,
                status="active",
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            session.add(user)
            session.flush()
            cred = UserCredential(
                user_id=user.id,
                password_hash=password_hash,
                password_algo=password_algo,
                must_change_password=False,
                password_updated_at=_utc_now(),
                created_at=_utc_now(),
            )
            session.add(cred)
            session.flush()
            return self._user_to_payload(user)

    def update_user_profile(
        self,
        *,
        user_id: str,
        display_name: str | None = None,
        avatar_url: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        with self.session() as session:
            row = session.scalar(select(User).where(User.id == self._parse_uuid(user_id)))
            if row is None:
                raise KeyError(f"unknown user_id: {user_id}")
            if email and email != row.email:
                exists = session.scalar(select(User).where(User.email == email))
                if exists is not None:
                    raise ValueError(f"email already exists: {email}")
                row.email = email
            if display_name is not None:
                row.display_name = display_name
            if avatar_url is not None:
                row.avatar_url = avatar_url
            row.updated_at = _utc_now()
            session.flush()
            return self._user_to_payload(row)

    def list_users(self, *, keyword: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        with self.session() as session:
            stmt = select(User).order_by(User.created_at.desc()).limit(max(1, min(limit, 100)))
            kw = str(keyword or "").strip()
            if kw:
                pattern = f"%{kw}%"
                stmt = (
                    select(User)
                    .where(
                        or_(
                            User.username.ilike(pattern),
                            User.display_name.ilike(pattern),
                            User.email.ilike(pattern),
                        )
                    )
                    .order_by(User.created_at.desc())
                    .limit(max(1, min(limit, 100)))
                )
            rows = session.scalars(stmt).all()
            return [self._user_to_payload(row) for row in rows]

    def get_user_credential_by_username(self, username: str) -> dict[str, Any] | None:
        with self.session() as session:
            row = session.execute(
                select(User, UserCredential)
                .join(UserCredential, UserCredential.user_id == User.id)
                .where(User.username == username)
            ).first()
            if row is None:
                return None
            user, cred = row
            payload = self._user_to_payload(user)
            payload["password_hash"] = cred.password_hash
            payload["password_algo"] = cred.password_algo
            return payload

    def touch_user_login(self, user_id: str) -> None:
        with self.session() as session:
            row = session.scalar(select(User).where(User.id == self._parse_uuid(user_id)))
            if row is None:
                return
            row.last_login_at = _utc_now()
            row.updated_at = _utc_now()

    def create_user_session(
        self,
        *,
        user_id: str,
        refresh_token_hash: str,
        expires_at: datetime,
        client_type: str | None,
        user_agent: str | None,
        ip_address: str | None,
    ) -> dict[str, Any]:
        with self.session() as session:
            row = UserSession(
                user_id=self._parse_uuid(user_id),
                refresh_token_hash=refresh_token_hash,
                client_type=client_type,
                user_agent=user_agent,
                ip_address=ip_address,
                expires_at=expires_at,
                revoked_at=None,
                created_at=_utc_now(),
            )
            session.add(row)
            session.flush()
            return self._user_session_to_payload(row)

    def get_user_session_by_id(self, session_id: str) -> dict[str, Any] | None:
        with self.session() as session:
            row = session.scalar(select(UserSession).where(UserSession.id == self._parse_uuid(session_id)))
            return self._user_session_to_payload(row) if row else None

    def get_user_session_by_refresh_token_hash(self, refresh_token_hash: str) -> dict[str, Any] | None:
        with self.session() as session:
            row = session.scalar(select(UserSession).where(UserSession.refresh_token_hash == refresh_token_hash))
            return self._user_session_to_payload(row) if row else None

    def revoke_user_session(self, session_id: str) -> dict[str, Any] | None:
        with self.session() as session:
            row = session.scalar(select(UserSession).where(UserSession.id == self._parse_uuid(session_id)))
            if row is None:
                return None
            row.revoked_at = _utc_now()
            session.flush()
            return self._user_session_to_payload(row)

    def ensure_default_workspace_and_project(self, *, user_id: str, username: str) -> dict[str, Any]:
        with self.session() as session:
            workspace = session.scalar(select(Workspace).where(Workspace.owner_user_id == self._parse_uuid(user_id)))
            if workspace is None:
                workspace = Workspace(
                    name=f"{username} Workspace",
                    slug=f"{username}-workspace",
                    owner_user_id=self._parse_uuid(user_id),
                    status="active",
                    created_at=_utc_now(),
                    updated_at=_utc_now(),
                )
                session.add(workspace)
                session.flush()
            project = session.scalar(
                select(Project)
                .where(Project.workspace_id == workspace.id, Project.created_by == self._parse_uuid(user_id))
                .order_by(Project.created_at.asc())
            )
            if project is None:
                project = Project(
                    workspace_id=workspace.id,
                    name="Default Project",
                    description="Auto-created default project",
                    created_by=self._parse_uuid(user_id),
                    status="active",
                    created_at=_utc_now(),
                    updated_at=_utc_now(),
                )
                session.add(project)
                session.flush()
                member = ProjectMember(
                    project_id=project.id,
                    user_id=self._parse_uuid(user_id),
                    role="owner",
                    joined_at=_utc_now(),
                )
                session.add(member)
                session.flush()
            return self._project_to_payload(project, role="owner")

    def list_projects_for_user(self, user_id: str) -> list[dict[str, Any]]:
        with self.session() as session:
            rows = session.execute(
                select(Project, ProjectMember)
                .join(ProjectMember, ProjectMember.project_id == Project.id)
                .where(ProjectMember.user_id == self._parse_uuid(user_id))
                .order_by(Project.created_at.desc())
            ).all()
            return [self._project_to_payload(project, role=member.role) for project, member in rows]

    def create_project(
        self,
        *,
        user_id: str,
        name: str,
        description: str | None,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        with self.session() as session:
            owner_workspace = None
            if workspace_id:
                owner_workspace = session.scalar(select(Workspace).where(Workspace.id == self._parse_uuid(workspace_id)))
            if owner_workspace is None:
                owner_workspace = session.scalar(select(Workspace).where(Workspace.owner_user_id == self._parse_uuid(user_id)))
            if owner_workspace is None:
                owner_workspace = Workspace(
                    name="Default Workspace",
                    slug=f"workspace-{str(user_id)[:8]}",
                    owner_user_id=self._parse_uuid(user_id),
                    status="active",
                    created_at=_utc_now(),
                    updated_at=_utc_now(),
                )
                session.add(owner_workspace)
                session.flush()
            project = Project(
                workspace_id=owner_workspace.id,
                name=name,
                description=description,
                created_by=self._parse_uuid(user_id),
                status="active",
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            session.add(project)
            session.flush()
            member = ProjectMember(
                project_id=project.id,
                user_id=self._parse_uuid(user_id),
                role="owner",
                joined_at=_utc_now(),
            )
            session.add(member)
            session.flush()
            return self._project_to_payload(project, role="owner")

    def get_project_for_user(self, *, project_id: str, user_id: str) -> dict[str, Any] | None:
        with self.session() as session:
            row = session.execute(
                select(Project, ProjectMember)
                .join(ProjectMember, ProjectMember.project_id == Project.id)
                .where(Project.id == self._parse_uuid(project_id), ProjectMember.user_id == self._parse_uuid(user_id))
            ).first()
            if row is None:
                return None
            project, member = row
            return self._project_to_payload(project, role=member.role)

    def add_project_member(
        self,
        *,
        project_id: str,
        user_id: str,
        role: str,
    ) -> dict[str, Any]:
        with self.session() as session:
            existing = session.scalar(
                select(ProjectMember).where(
                    ProjectMember.project_id == self._parse_uuid(project_id),
                    ProjectMember.user_id == self._parse_uuid(user_id),
                )
            )
            if existing is None:
                existing = ProjectMember(
                    project_id=self._parse_uuid(project_id),
                    user_id=self._parse_uuid(user_id),
                    role=role,
                    joined_at=_utc_now(),
                )
                session.add(existing)
            else:
                existing.role = role
            session.flush()
            return {
                "project_id": project_id,
                "user_id": user_id,
                "role": existing.role,
                "joined_at": existing.joined_at.isoformat() if existing.joined_at else None,
            }

    def list_project_members(self, project_id: str) -> list[dict[str, Any]]:
        with self.session() as session:
            rows = session.execute(
                select(ProjectMember, User)
                .join(User, User.id == ProjectMember.user_id)
                .where(ProjectMember.project_id == self._parse_uuid(project_id))
                .order_by(ProjectMember.joined_at.asc())
            ).all()
            return [
                {
                    "project_id": str(member.project_id),
                    "user_id": str(member.user_id),
                    "username": user.username,
                    "display_name": user.display_name,
                    "role": member.role,
                    "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                }
                for member, user in rows
            ]

    def is_project_member(self, *, project_id: str, user_id: str) -> bool:
        with self.session() as session:
            row = session.scalar(
                select(ProjectMember).where(
                    ProjectMember.project_id == self._parse_uuid(project_id),
                    ProjectMember.user_id == self._parse_uuid(user_id),
                )
            )
            return row is not None

    def create_defect(
        self,
        *,
        project_id: str,
        reporter_user_id: str,
        title: str,
        description: str | None = None,
        severity: str = "medium",
        status: str = "open",
        source: str = "manual",
        task_uid: str | None = None,
        assignee_user_id: str | None = None,
        reproduction_steps: str | None = None,
        expected_result: str | None = None,
        actual_result: str | None = None,
    ) -> dict[str, Any]:
        with self.session() as session:
            task_row = self._resolve_task_row_by_uid(session, task_uid, project_id=project_id)
            defect = Defect(
                defect_key=self._build_defect_key(),
                project_id=self._parse_uuid(project_id),
                task_id=task_row.id if task_row is not None else None,
                reporter_user_id=self._parse_uuid(reporter_user_id),
                assignee_user_id=self._parse_uuid(assignee_user_id),
                title=title,
                description=description,
                severity=severity,
                status=status,
                source=source,
                reproduction_steps=reproduction_steps,
                expected_result=expected_result,
                actual_result=actual_result,
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            session.add(defect)
            session.flush()
            return self._load_defect_payload(session, defect.id)

    def get_defect(self, defect_id: str) -> dict[str, Any] | None:
        with self.session() as session:
            try:
                parsed_id = self._parse_uuid(defect_id)
            except Exception:
                return None
            row = session.scalar(select(Defect).where(Defect.id == parsed_id))
            if row is None:
                return None
            return self._load_defect_payload(session, row.id)

    def update_defect(
        self,
        defect_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        source: str | None = None,
        task_uid: str | None = None,
        clear_task: bool = False,
        assignee_user_id: str | None = None,
        clear_assignee: bool = False,
        reproduction_steps: str | None = None,
        expected_result: str | None = None,
        actual_result: str | None = None,
    ) -> dict[str, Any]:
        with self.session() as session:
            defect = session.scalar(select(Defect).where(Defect.id == self._parse_uuid(defect_id)))
            if defect is None:
                raise KeyError(f"unknown defect_id: {defect_id}")
            project_id = str(defect.project_id)
            if clear_task:
                defect.task_id = None
            elif task_uid is not None:
                task_row = self._resolve_task_row_by_uid(session, task_uid, project_id=project_id)
                defect.task_id = task_row.id if task_row is not None else None
            if title is not None:
                defect.title = title
            if description is not None:
                defect.description = description
            if severity is not None:
                defect.severity = severity
            if status is not None:
                defect.status = status
            if source is not None:
                defect.source = source
            if clear_assignee:
                defect.assignee_user_id = None
            elif assignee_user_id is not None:
                defect.assignee_user_id = self._parse_uuid(assignee_user_id)
            if reproduction_steps is not None:
                defect.reproduction_steps = reproduction_steps
            if expected_result is not None:
                defect.expected_result = expected_result
            if actual_result is not None:
                defect.actual_result = actual_result
            defect.updated_at = _utc_now()
            session.flush()
            return self._load_defect_payload(session, defect.id)

    def list_defects(
        self,
        *,
        project_id: str,
        status: str | None = None,
        severity: str | None = None,
        keyword: str | None = None,
        task_uid: str | None = None,
        assignee_user_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        with self.session() as session:
            reporter = aliased(User)
            assignee = aliased(User)
            stmt = (
                select(Defect, Task, reporter, assignee)
                .outerjoin(Task, Task.id == Defect.task_id)
                .outerjoin(reporter, reporter.id == Defect.reporter_user_id)
                .outerjoin(assignee, assignee.id == Defect.assignee_user_id)
                .where(Defect.project_id == self._parse_uuid(project_id))
                .order_by(Defect.created_at.desc(), Defect.defect_key.desc())
            )
            if status:
                stmt = stmt.where(Defect.status == status)
            if severity:
                stmt = stmt.where(Defect.severity == severity)
            if task_uid:
                stmt = stmt.where(Task.task_uid == task_uid)
            if assignee_user_id:
                stmt = stmt.where(Defect.assignee_user_id == self._parse_uuid(assignee_user_id))

            rows = session.execute(stmt).all()
            payload = [self._defect_to_payload(defect, task_row, reporter_row, assignee_row) for defect, task_row, reporter_row, assignee_row in rows]
            kw = str(keyword or "").strip().lower()
            if kw:
                payload = [
                    item
                    for item in payload
                    if kw in str(item.get("defect_key", "")).lower()
                    or kw in str(item.get("title", "")).lower()
                    or kw in str(item.get("description", "")).lower()
                    or kw in str(item.get("task_id", "")).lower()
                    or kw in str(item.get("task_name", "")).lower()
                    or kw in str(item.get("assignee_username", "")).lower()
                    or kw in str(item.get("reporter_username", "")).lower()
                ]
            safe_page = max(1, int(page))
            safe_page_size = max(1, min(int(page_size), 200))
            start = (safe_page - 1) * safe_page_size
            end = start + safe_page_size
            return {
                "items": payload[start:end],
                "total": len(payload),
                "page": safe_page,
                "page_size": safe_page_size,
            }

    def append_audit_log(
        self,
        *,
        user_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str | None,
        detail_json: dict[str, Any] | list[Any] | None,
        ip_address: str | None,
    ) -> None:
        with self.session() as session:
            row = AuditLog(
                user_id=self._parse_uuid(user_id),
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail_json=detail_json,  # type: ignore[arg-type]
                ip_address=ip_address,
                created_at=_utc_now(),
            )
            session.add(row)

    def list_audit_logs(
        self,
        *,
        action: str | None = None,
        resource_type: str | None = None,
        keyword: str | None = None,
        user_id: str | None = None,
        actor: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        with self.session() as session:
            stmt = select(AuditLog, User).outerjoin(User, User.id == AuditLog.user_id).order_by(AuditLog.created_at.desc())
            if action:
                stmt = stmt.where(AuditLog.action == action)
            if resource_type:
                stmt = stmt.where(AuditLog.resource_type == resource_type)
            if user_id:
                try:
                    stmt = stmt.where(AuditLog.user_id == self._parse_uuid(user_id))
                except Exception:
                    safe_page = max(1, int(page))
                    safe_page_size = max(1, min(int(page_size), 200))
                    return {"items": [], "total": 0, "page": safe_page, "page_size": safe_page_size}
            if start_time is not None:
                stmt = stmt.where(AuditLog.created_at >= start_time)
            if end_time is not None:
                stmt = stmt.where(AuditLog.created_at <= end_time)
            rows = session.execute(stmt).all()
            payload = [
                {
                    "id": str(row.id),
                    "user_id": str(row.user_id) if row.user_id else None,
                    "username": user.username if user is not None else None,
                    "display_name": user.display_name if user is not None else None,
                    "action": row.action,
                    "resource_type": row.resource_type,
                    "resource_id": row.resource_id,
                    "detail_json": row.detail_json,
                    "ip_address": row.ip_address,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row, user in rows
            ]
            actor_kw = str(actor or "").strip().lower()
            if actor_kw:
                payload = [
                    item
                    for item in payload
                    if actor_kw in str(item.get("user_id", "")).lower()
                    or actor_kw in str(item.get("username", "")).lower()
                    or actor_kw in str(item.get("display_name", "")).lower()
                ]
            kw = str(keyword or "").strip().lower()
            if kw:
                payload = [
                    item
                    for item in payload
                    if kw in str(item.get("action", "")).lower()
                    or kw in str(item.get("resource_type", "")).lower()
                    or kw in str(item.get("resource_id", "")).lower()
                    or kw in str(item.get("username", "")).lower()
                    or kw in str(item.get("display_name", "")).lower()
                    or kw in str(item.get("detail_json", "")).lower()
                ]
            safe_page = max(1, int(page))
            safe_page_size = max(1, min(int(page_size), 200))
            start = (safe_page - 1) * safe_page_size
            end = start + safe_page_size
            return {
                "items": payload[start:end],
                "total": len(payload),
                "page": safe_page,
                "page_size": safe_page_size,
            }

    @staticmethod
    def _parse_dt(raw: Any) -> datetime | None:
        if raw is None:
            return None
        if isinstance(raw, datetime):
            return raw
        text = str(raw).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            if value is None or value == "":
                return None
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _parse_uuid(raw: Any) -> uuid.UUID | None:
        if raw is None or raw == "":
            return None
        if isinstance(raw, uuid.UUID):
            return raw
        return uuid.UUID(str(raw))

    @staticmethod
    def _user_to_payload(row: User) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "username": row.username,
            "email": row.email,
            "display_name": row.display_name,
            "avatar_url": row.avatar_url,
            "status": row.status,
            "last_login_at": row.last_login_at.isoformat() if row.last_login_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def _user_session_to_payload(row: UserSession) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "user_id": str(row.user_id),
            "refresh_token_hash": row.refresh_token_hash,
            "client_type": row.client_type,
            "user_agent": row.user_agent,
            "ip_address": row.ip_address,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _project_to_payload(project: Project, *, role: str | None) -> dict[str, Any]:
        return {
            "id": str(project.id),
            "workspace_id": str(project.workspace_id),
            "name": project.name,
            "description": project.description,
            "created_by": str(project.created_by) if project.created_by else None,
            "status": project.status,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None,
            "role": role,
        }

    @staticmethod
    def _build_defect_key() -> str:
        return f"DEF-{_utc_now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    @staticmethod
    def _resolve_task_row_by_uid(session: Session, task_uid: str | None, *, project_id: str) -> Task | None:
        normalized_task_uid = str(task_uid or "").strip()
        if not normalized_task_uid:
            return None
        row = session.scalar(
            select(Task).where(
                Task.task_uid == normalized_task_uid,
                Task.project_id == DatabaseTaskStore._parse_uuid(project_id),
            )
        )
        if row is None:
            raise KeyError(f"unknown task_uid for project: {normalized_task_uid}")
        return row

    def _load_defect_payload(self, session: Session, defect_id: uuid.UUID) -> dict[str, Any]:
        reporter = aliased(User)
        assignee = aliased(User)
        row = session.execute(
            select(Defect, Task, reporter, assignee)
            .outerjoin(Task, Task.id == Defect.task_id)
            .outerjoin(reporter, reporter.id == Defect.reporter_user_id)
            .outerjoin(assignee, assignee.id == Defect.assignee_user_id)
            .where(Defect.id == defect_id)
        ).first()
        if row is None:
            raise KeyError(f"unknown defect_id: {defect_id}")
        defect, task_row, reporter_row, assignee_row = row
        return self._defect_to_payload(defect, task_row, reporter_row, assignee_row)

    @staticmethod
    def _defect_to_payload(
        defect: Defect,
        task_row: Task | None,
        reporter_row: User | None,
        assignee_row: User | None,
    ) -> dict[str, Any]:
        return {
            "id": str(defect.id),
            "defect_key": defect.defect_key,
            "project_id": str(defect.project_id),
            "task_id": task_row.task_uid if task_row is not None else None,
            "task_name": task_row.task_name if task_row is not None else None,
            "reporter_user_id": str(defect.reporter_user_id),
            "reporter_username": reporter_row.username if reporter_row is not None else None,
            "reporter_display_name": reporter_row.display_name if reporter_row is not None else None,
            "assignee_user_id": str(defect.assignee_user_id) if defect.assignee_user_id else None,
            "assignee_username": assignee_row.username if assignee_row is not None else None,
            "assignee_display_name": assignee_row.display_name if assignee_row is not None else None,
            "title": defect.title,
            "description": defect.description or "",
            "severity": defect.severity,
            "status": defect.status,
            "source": defect.source,
            "reproduction_steps": defect.reproduction_steps or "",
            "expected_result": defect.expected_result or "",
            "actual_result": defect.actual_result or "",
            "created_at": defect.created_at.isoformat() if defect.created_at else None,
            "updated_at": defect.updated_at.isoformat() if defect.updated_at else None,
        }
