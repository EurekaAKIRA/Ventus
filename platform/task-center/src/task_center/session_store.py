"""Session and token-revocation cache with Redis-first fallback."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

try:
    import redis
except Exception:  # pragma: no cover
    redis = None  # type: ignore[assignment]


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class SessionStateStore:
    def set_session(self, session_id: str, payload: dict[str, Any], *, ttl_seconds: int) -> None:
        raise NotImplementedError

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def clear_session(self, session_id: str) -> None:
        raise NotImplementedError

    def revoke_token_jti(self, jti: str, *, ttl_seconds: int) -> None:
        raise NotImplementedError

    def is_token_jti_revoked(self, jti: str) -> bool:
        raise NotImplementedError


class InMemorySessionStateStore(SessionStateStore):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, tuple[float, dict[str, Any]]] = {}
        self._revoked: dict[str, float] = {}

    def _cleanup(self) -> None:
        now = time.time()
        expired_sessions = [key for key, (expires_at, _) in self._sessions.items() if expires_at < now]
        for key in expired_sessions:
            self._sessions.pop(key, None)
        expired_revocations = [key for key, expires_at in self._revoked.items() if expires_at < now]
        for key in expired_revocations:
            self._revoked.pop(key, None)

    def set_session(self, session_id: str, payload: dict[str, Any], *, ttl_seconds: int) -> None:
        with self._lock:
            self._cleanup()
            self._sessions[session_id] = (time.time() + max(ttl_seconds, 1), dict(payload))

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._cleanup()
            item = self._sessions.get(session_id)
            return dict(item[1]) if item else None

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def revoke_token_jti(self, jti: str, *, ttl_seconds: int) -> None:
        with self._lock:
            self._cleanup()
            self._revoked[jti] = time.time() + max(ttl_seconds, 1)

    def is_token_jti_revoked(self, jti: str) -> bool:
        with self._lock:
            self._cleanup()
            return jti in self._revoked


class RedisSessionStateStore(SessionStateStore):
    def __init__(self, redis_url: str) -> None:
        if redis is None:  # pragma: no cover
            raise RuntimeError("redis package is not available")
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"session:{session_id}"

    @staticmethod
    def _revocation_key(jti: str) -> str:
        return f"token_revocation:{jti}"

    def set_session(self, session_id: str, payload: dict[str, Any], *, ttl_seconds: int) -> None:
        self._client.set(self._session_key(session_id), _json_dumps(payload), ex=max(ttl_seconds, 1))

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        raw = self._client.get(self._session_key(session_id))
        return json.loads(raw) if raw else None

    def clear_session(self, session_id: str) -> None:
        self._client.delete(self._session_key(session_id))

    def revoke_token_jti(self, jti: str, *, ttl_seconds: int) -> None:
        self._client.set(self._revocation_key(jti), "1", ex=max(ttl_seconds, 1))

    def is_token_jti_revoked(self, jti: str) -> bool:
        return bool(self._client.exists(self._revocation_key(jti)))


def build_session_state_store() -> SessionStateStore:
    redis_url = str(os.getenv("TASK_CENTER_REDIS_URL", "") or "").strip()
    if redis_url and redis is not None:
        try:
            return RedisSessionStateStore(redis_url)
        except Exception:
            return InMemorySessionStateStore()
    return InMemorySessionStateStore()
