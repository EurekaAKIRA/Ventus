"""Rebuild and replay API task artifacts with current parser/generator/executor.

Examples:
  python replay_api_artifact_compare.py --recent 3
  python replay_api_artifact_compare.py --task-id g_20260417093452762415
  python replay_api_artifact_compare.py --task-id g_20260417093452762415 --write-json tmp/report.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for extra in (
    ROOT / "shared" / "src",
    ROOT / "requirement-analysis" / "src",
    ROOT / "case-generation" / "src",
    ROOT / "execution-engine" / "api-runner" / "src",
):
    sys.path.insert(0, str(extra))

from api_runner import execute_test_case_dsl  # noqa: E402
from case_generation import build_scenarios, build_test_case_dsl  # noqa: E402
from platform_shared.models import ScenarioModel, TaskContext  # noqa: E402
from requirement_analysis.service import AnalysisParseOptions, parse_requirement_bundle  # noqa: E402


ARTIFACT_ROOT = ROOT / "task-center" / "api_artifacts"
BASE_URL_RE = re.compile(r"https?://[^\s)`>\"']+")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _old_summary(execution_result: dict[str, Any]) -> dict[str, Any]:
    scenario_results = execution_result.get("scenario_results") or []
    passed = sum(1 for item in scenario_results if item.get("status") == "passed")
    failed = sum(1 for item in scenario_results if item.get("status") != "passed")
    total_assertions = 0
    passed_assertions = 0
    failures: list[dict[str, Any]] = []
    for scenario in scenario_results:
        for step in scenario.get("steps") or []:
            summary = step.get("assertion_summary") or {}
            total_assertions += int(summary.get("total") or 0)
            passed_assertions += int(summary.get("passed") or 0)
            if step.get("status") != "passed":
                failures.append(
                    {
                        "scenario_name": scenario.get("name"),
                        "step_name": step.get("text"),
                        "error_message": step.get("message") or step.get("error_category") or "",
                    }
                )
    rate = round((passed_assertions / total_assertions) * 100, 2) if total_assertions else None
    return {
        "status": execution_result.get("status"),
        "scenario_count": len(scenario_results),
        "passed_scenarios": passed,
        "failed_scenarios": failed,
        "assertion_pass_rate": rate,
        "failed_results": failures,
    }


def _new_summary(execution_result: dict[str, Any]) -> dict[str, Any]:
    summary = _old_summary(execution_result)
    if execution_result.get("passed_scenarios") is not None:
        summary["passed_scenarios"] = execution_result.get("passed_scenarios")
    if execution_result.get("failed_scenarios") is not None:
        summary["failed_scenarios"] = execution_result.get("failed_scenarios")
    if execution_result.get("assertion_pass_rate") is not None:
        summary["assertion_pass_rate"] = execution_result.get("assertion_pass_rate")
    if execution_result.get("failed_results"):
        summary["failed_results"] = execution_result.get("failed_results") or []
    return summary


def _extract_base_url(old_dsl: dict[str, Any], raw_requirement: str) -> str | None:
    metadata_url = (((old_dsl.get("metadata") or {}).get("execution") or {}).get("base_url"))
    if metadata_url:
        return str(metadata_url)
    candidates = BASE_URL_RE.findall(raw_requirement or "")
    for candidate in candidates:
        if "{BASE_URL}" not in candidate:
            return candidate.rstrip("/")
    return None


def _inject_execution_metadata(new_dsl: dict[str, Any], old_dsl: dict[str, Any], raw_requirement: str) -> None:
    metadata = dict(new_dsl.get("metadata") or {})
    old_metadata = old_dsl.get("metadata") or {}
    execution_meta = dict((metadata.get("execution") or {}))
    execution_meta.update(old_metadata.get("execution") or {})

    base_url = execution_meta.get("base_url") or _extract_base_url(old_dsl, raw_requirement)
    if base_url:
        execution_meta["base_url"] = base_url
    if not execution_meta.get("default_headers"):
        execution_meta["default_headers"] = {"Content-Type": "application/json"}
    metadata["execution"] = execution_meta
    new_dsl["metadata"] = metadata


def _task_dirs_from_args(task_ids: list[str], recent: int) -> list[Path]:
    if task_ids:
        return [ARTIFACT_ROOT / task_id for task_id in task_ids]
    return sorted(
        [path for path in ARTIFACT_ROOT.iterdir() if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:recent]


def _rebuild_and_replay(task_dir: Path) -> dict[str, Any]:
    raw_requirement = (task_dir / "raw" / "requirement.txt").read_text(encoding="utf-8")
    task_context_payload = _read_json(task_dir / "metadata" / "task_context.json")
    old_dsl = _read_json(task_dir / "scenarios" / "test_case_dsl.json")
    old_execution = _read_json(task_dir / "execution" / "execution_result.json")
    parse_metadata_path = task_dir / "parsed" / "parse_metadata.json"
    parse_metadata = _read_json(parse_metadata_path) if parse_metadata_path.exists() else {}

    options = AnalysisParseOptions.resolve(
        {
            "use_llm": parse_metadata.get("llm_used") or parse_metadata.get("llm_attempted") or False,
            "rag_enabled": parse_metadata.get("rag_used", True),
            "retrieval_top_k": parse_metadata.get("retrieval_top_k", 5),
            "rerank_enabled": parse_metadata.get("rerank_enabled", False),
            "model_profile": parse_metadata.get("model_profile"),
        }
    )
    parse_bundle = parse_requirement_bundle(requirement_text=raw_requirement, options=options)
    parsed_requirement = parse_bundle["parsed_requirement"]
    scenarios = [
        ScenarioModel(**payload)
        for payload in build_scenarios(parsed_requirement, use_llm=options.use_llm)
    ]
    new_dsl = build_test_case_dsl(
        TaskContext(**task_context_payload),
        scenarios,
        parsed_requirement=parsed_requirement,
        enable_assertion_enhancement=options.use_llm,
    )
    _inject_execution_metadata(new_dsl, old_dsl, raw_requirement)
    replay_result = execute_test_case_dsl(new_dsl)
    return {
        "task_id": task_dir.name,
        "task_name": task_context_payload.get("task_name"),
        "parse_options": {
            "use_llm": options.use_llm,
            "rag_enabled": options.rag_enabled,
            "retrieval_top_k": options.retrieval_top_k,
            "rerank_enabled": options.rerank_enabled,
        },
        "old": _old_summary(old_execution),
        "new": _new_summary(replay_result),
        "replayed_dsl_scenarios": len(new_dsl.get("scenarios") or []),
        "replayed_parse_mode": (parse_bundle.get("parse_metadata") or {}).get("parse_mode"),
        "replayed_llm_used": (parse_bundle.get("parse_metadata") or {}).get("llm_used"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay recent API artifact tasks with current code")
    parser.add_argument("--task-id", action="append", dest="task_ids", default=[], help="Specific task id to replay")
    parser.add_argument("--recent", type=int, default=3, help="Replay latest N tasks when no --task-id is given")
    parser.add_argument("--write-json", type=Path, default=None, help="Optional path to write full comparison json")
    args = parser.parse_args()

    reports = [_rebuild_and_replay(task_dir) for task_dir in _task_dirs_from_args(args.task_ids, args.recent)]
    text = json.dumps(reports, ensure_ascii=False, indent=2)
    if args.write_json is not None:
        args.write_json.parent.mkdir(parents=True, exist_ok=True)
        args.write_json.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
