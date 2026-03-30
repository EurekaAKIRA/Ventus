"""Artifact writing helpers."""

from __future__ import annotations

import json
from pathlib import Path


def write_text_artifact(path: str, content: str) -> None:
    """Write text content to disk, creating parent directories when needed."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def write_json_artifact(path: str, payload: dict | list) -> None:
    """Write JSON artifact with UTF-8 encoding."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_task_artifact_dir(base_dir: str, task_name: str, timestamp: str) -> str:
    """Build a task-scoped artifact directory path."""
    safe_name = task_name.strip().replace(" ", "_") or "analysis_task"
    target = Path(base_dir) / f"{safe_name}_{timestamp}"
    target.mkdir(parents=True, exist_ok=True)
    return str(target)


def ensure_task_subdirs(task_dir: str) -> dict[str, str]:
    """Create standard subdirectories for a task artifact bundle."""
    base = Path(task_dir)
    subdirs = {}
    for name in ("raw", "parsed", "retrieval", "scenarios", "validation", "metadata"):
        target = base / name
        target.mkdir(parents=True, exist_ok=True)
        subdirs[name] = str(target)
    return subdirs
