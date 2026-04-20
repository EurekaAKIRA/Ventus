"""Authentication helpers for task-center user module."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class AuthConfig:
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14


def load_auth_config() -> AuthConfig:
    return AuthConfig(
        jwt_secret=str(os.getenv("TASK_CENTER_JWT_SECRET", "task-center-dev-secret-change-me")),
        jwt_algorithm=str(os.getenv("TASK_CENTER_JWT_ALGORITHM", "HS256")),
        access_token_ttl_minutes=int(os.getenv("TASK_CENTER_ACCESS_TOKEN_TTL_MINUTES", "30")),
        refresh_token_ttl_days=int(os.getenv("TASK_CENTER_REFRESH_TOKEN_TTL_DAYS", "14")),
    )


def hash_password(raw_password: str) -> str:
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(raw_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def build_access_token(
    *,
    user_id: str,
    username: str,
    session_id: str,
    project_ids: list[str],
    config: AuthConfig,
) -> tuple[str, dict[str, Any]]:
    now = _utc_now()
    expires_at = now + timedelta(minutes=max(config.access_token_ttl_minutes, 1))
    jti = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "username": username,
        "session_id": session_id,
        "project_ids": project_ids,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, config.jwt_secret, algorithm=config.jwt_algorithm)
    return token, payload


def decode_access_token(token: str, config: AuthConfig) -> dict[str, Any]:
    return jwt.decode(token, config.jwt_secret, algorithms=[config.jwt_algorithm])


def build_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return _hash_token(token)


def verify_refresh_token(token: str, hashed_token: str) -> bool:
    return hmac.compare_digest(hash_refresh_token(token), hashed_token)
