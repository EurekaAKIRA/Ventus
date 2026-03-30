"""Input handling for analysis-module."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .models import TaskContext


def normalize_input(
    task_name: str,
    requirement_text: str,
    source_type: str = "text",
    source_path: str | None = None,
    language: str = "zh-CN",
) -> dict:
    """Normalize raw input and build a task context payload."""
    normalized_name = task_name.strip() or "analysis_task"
    task_id = f"{normalized_name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    context = TaskContext(
        task_id=task_id,
        task_name=normalized_name,
        source_type=source_type,
        source_path=source_path,
        language=language,
        status="received",
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
