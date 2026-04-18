"""Input handling for analysis-module."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from platform_shared.models import TaskContext


def _derive_task_name(task_name: str, source_path: str | None = None) -> str:
    explicit_name = str(task_name or "").strip()
    if explicit_name:
        return explicit_name

    if source_path:
        source_name = Path(source_path).stem.strip()
        if source_name:
            return source_name

    return "analysis_task"


def normalize_input(
    task_name: str,
    requirement_text: str,
    source_type: str = "text",
    source_path: str | None = None,
    language: str = "zh-CN",
    task_id: str | None = None,
    created_at: str | None = None,
    status: str = "received",
) -> dict:
    """Normalize raw input and build a task context payload."""
    normalized_name = _derive_task_name(task_name, source_path)
    resolved_task_id = task_id or f"{normalized_name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    context = TaskContext(
        task_id=resolved_task_id,
        task_name=normalized_name,
        source_type=source_type,
        source_path=source_path,
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
        language=language,
        status=status,
    )
    return {
        "task_context": context.to_dict(),
        "raw_requirement": requirement_text.strip(),
    }


def persist_raw_input(task_dir: str, requirement_text: str, filename: str = "requirement.txt") -> str:
    """Persist the raw requirement for traceability."""
    raw_dir = Path(task_dir) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / filename
    target.write_text(requirement_text, encoding="utf-8")
    return str(target)
