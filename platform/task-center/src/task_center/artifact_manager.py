"""Artifact writing helpers."""

from __future__ import annotations

import json
from pathlib import Path


def read_json_artifact(path: str) -> dict | list | None:
    """Read JSON artifact if it exists."""
    target = Path(path)
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


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
    for name in ("raw", "parsed", "retrieval", "scenarios", "validation", "metadata", "execution"):
        target = base / name
        target.mkdir(parents=True, exist_ok=True)
        subdirs[name] = str(target)
    return subdirs


def load_pipeline_artifacts(task_dir: str) -> dict:
    """Load persisted pipeline artifacts into the in-memory result shape."""
    base = Path(task_dir)
    raw_requirement = ""
    raw_path = base / "raw" / "requirement.txt"
    if raw_path.exists():
        raw_requirement = raw_path.read_text(encoding="utf-8")

    cleaned_document = read_json_artifact(str(base / "parsed" / "cleaned_document.json")) or {}
    parsed_requirement = read_json_artifact(str(base / "parsed" / "parsed_requirement.json")) or {}
    retrieved_context_bundle = read_json_artifact(str(base / "retrieval" / "retrieved_chunks.json")) or {}
    scenario_bundle = read_json_artifact(str(base / "scenarios" / "scenario_bundle.json")) or {}
    test_case_dsl = read_json_artifact(str(base / "scenarios" / "test_case_dsl.json")) or {}
    validation_report = read_json_artifact(str(base / "validation" / "validation_report.json")) or {}
    analysis_report = read_json_artifact(str(base / "validation" / "analysis_report.json")) or {}
    execution_result = read_json_artifact(str(base / "execution" / "execution_result.json")) or {}
    feature_path = base / "generated.feature"
    feature_text = feature_path.read_text(encoding="utf-8") if feature_path.exists() else ""

    return {
        "task_context": scenario_bundle.get("task_context")
        or read_json_artifact(str(base / "metadata" / "task_context.json"))
        or {},
        "raw_requirement": raw_requirement,
        "cleaned_text": cleaned_document.get("cleaned_text", ""),
        "outline": cleaned_document.get("outline", []),
        "chunks": cleaned_document.get("chunks", []),
        "retrieved_context": scenario_bundle.get("retrieved_context", retrieved_context_bundle.get("hits", [])),
        "parsed_requirement": scenario_bundle.get("parsed_requirement", parsed_requirement),
        "scenarios": scenario_bundle.get("scenarios", []),
        "test_case_dsl": scenario_bundle.get("test_case_dsl", test_case_dsl),
        "feature_text": feature_text,
        "validation_report": scenario_bundle.get("validation_report", validation_report),
        "analysis_report": scenario_bundle.get("analysis_report", analysis_report),
        "execution_result": execution_result,
    }
