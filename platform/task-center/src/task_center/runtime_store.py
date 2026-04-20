"""Runtime-state storage for task execution progress and context."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

try:
    import redis
except Exception:  # pragma: no cover - optional import guard
    redis = None  # type: ignore[assignment]


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class RuntimeStateStore:
    """Abstract runtime-state store."""

    def save_context(self, task_id: str, payload: dict[str, Any], *, ttl_seconds: int = 86400) -> None:
        raise NotImplementedError

    def load_context(self, task_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def save_progress(self, task_id: str, payload: dict[str, Any], *, ttl_seconds: int = 86400) -> None:
        raise NotImplementedError

    def load_progress(self, task_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def clear_task(self, task_id: str) -> None:
        raise NotImplementedError


class InMemoryRuntimeStateStore(RuntimeStateStore):
    """Process-local fallback store when Redis is unavailable."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, tuple[float, dict[str, Any]]] = {}

    def _save(self, key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        expires_at = time.time() + max(ttl_seconds, 1)
        with self._lock:
            self._state[key] = (expires_at, dict(payload))

    def _load(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._state.get(key)
            if item is None:
                return None
            expires_at, payload = item
            if expires_at < time.time():
                self._state.pop(key, None)
                return None
            return dict(payload)

    def _delete(self, key: str) -> None:
        with self._lock:
            self._state.pop(key, None)

    def save_context(self, task_id: str, payload: dict[str, Any], *, ttl_seconds: int = 86400) -> None:
        self._save(f"{task_id}:context", payload, ttl_seconds)

    def load_context(self, task_id: str) -> dict[str, Any] | None:
        return self._load(f"{task_id}:context")

    def save_progress(self, task_id: str, payload: dict[str, Any], *, ttl_seconds: int = 86400) -> None:
        self._save(f"{task_id}:progress", payload, ttl_seconds)

    def load_progress(self, task_id: str) -> dict[str, Any] | None:
        return self._load(f"{task_id}:progress")

    def clear_task(self, task_id: str) -> None:
        self._delete(f"{task_id}:context")
        self._delete(f"{task_id}:progress")


class RedisRuntimeStateStore(RuntimeStateStore):
    """Redis-backed runtime-state store."""

    def __init__(self, redis_url: str) -> None:
        if redis is None:  # pragma: no cover - guarded by caller in practice
            raise RuntimeError("redis package is not available")
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    @staticmethod
    def _context_key(task_id: str) -> str:
        return f"task_runtime:{task_id}:current:context"

    @staticmethod
    def _progress_key(task_id: str) -> str:
        return f"task_runtime:{task_id}:current:progress"

    def save_context(self, task_id: str, payload: dict[str, Any], *, ttl_seconds: int = 86400) -> None:
        self._client.set(self._context_key(task_id), _json_dumps(payload), ex=max(ttl_seconds, 1))

    def load_context(self, task_id: str) -> dict[str, Any] | None:
        raw = self._client.get(self._context_key(task_id))
        return json.loads(raw) if raw else None

    def save_progress(self, task_id: str, payload: dict[str, Any], *, ttl_seconds: int = 86400) -> None:
        self._client.set(self._progress_key(task_id), _json_dumps(payload), ex=max(ttl_seconds, 1))

    def load_progress(self, task_id: str) -> dict[str, Any] | None:
        raw = self._client.get(self._progress_key(task_id))
        return json.loads(raw) if raw else None

    def clear_task(self, task_id: str) -> None:
        self._client.delete(self._context_key(task_id), self._progress_key(task_id))


def build_runtime_state_store() -> RuntimeStateStore:
    """Build a runtime-state store, preferring Redis when configured."""
    redis_url = str(os.getenv("TASK_CENTER_REDIS_URL", "") or "").strip()
    if redis_url and redis is not None:
        try:
            return RedisRuntimeStateStore(redis_url)
        except Exception:
            return InMemoryRuntimeStateStore()
    return InMemoryRuntimeStateStore()
