"""Shared context bus for multi-step execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ContextBus:
    """Store and resolve step-to-step execution data."""

    values: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        if "." not in key:
            return self.values.get(key, default)
        head, _, tail = key.partition(".")
        return self._read_dotted_path(self.values.get(head), tail, default)

    def set(self, key: str, value: Any) -> None:
        if "." not in key:
            self.values[key] = value
            return
        head, _, tail = key.partition(".")
        current = self.values.setdefault(head, {})
        if not isinstance(current, dict):
            current = {}
            self.values[head] = current
        self._write_dotted_path(current, tail, value)

    def require(self, keys: list[str]) -> list[str]:
        missing: list[str] = []
        for key in keys:
            if self.get(key) is None:
                missing.append(key)
        return missing

    def snapshot(self) -> dict[str, Any]:
        return dict(self.values)

    def _read_dotted_path(self, payload: Any, path: str, default: Any = None) -> Any:
        current = payload
        if path == "":
            return current
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part, default)
            elif isinstance(current, list) and part.isdigit():
                index = int(part)
                current = current[index] if 0 <= index < len(current) else default
            else:
                return default
        return current

    def _write_dotted_path(self, payload: dict[str, Any], path: str, value: Any) -> None:
        current = payload
        parts = path.split(".")
        for part in parts[:-1]:
            next_value = current.get(part)
            if not isinstance(next_value, dict):
                next_value = {}
                current[part] = next_value
            current = next_value
        current[parts[-1]] = value
