"""Aggregate assertion totals from execution results (per-step truth)."""

from __future__ import annotations

from typing import Any


def dsl_assertion_count_by_step_id(test_case_dsl: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for scenario in test_case_dsl.get("scenarios") or []:
        if not isinstance(scenario, dict):
            continue
        for step in scenario.get("steps") or []:
            if not isinstance(step, dict):
                continue
            sid = str(step.get("step_id") or "").strip()
            if sid:
                out[sid] = len(step.get("assertions") or [])
    return out


def compute_assertion_execution_stats(
    scenario_results: list[dict[str, Any]],
    test_case_dsl: dict[str, Any],
) -> tuple[int, int, int]:
    """Return (total, passed, failed) for executed steps.

    Prefer each step's ``assertion_summary`` when ``total > 0`` (runner truth).
    Otherwise fall back to DSL assertion count per ``step_id``: passed steps
    credit all their DSL assertions; failed steps count them as failed.
    If there are no executed scenario steps, return ``(dsl_total, 0, 0)``.
    """
    dsl_by_id = dsl_assertion_count_by_step_id(test_case_dsl)
    dsl_total = sum(dsl_by_id.values())

    if not _execution_has_scenario_steps(scenario_results):
        return dsl_total, 0, 0

    total = 0
    passed = 0
    failed = 0
    for scenario in scenario_results or []:
        if not isinstance(scenario, dict):
            continue
        for step in scenario.get("steps") or []:
            if not isinstance(step, dict):
                continue
            sid = str(step.get("step_id") or "").strip()
            n = dsl_by_id.get(sid, 0)
            summ = step.get("assertion_summary")
            if isinstance(summ, dict) and int(summ.get("total") or 0) > 0:
                total += int(summ.get("total") or 0)
                passed += int(summ.get("passed") or 0)
                failed += int(summ.get("failed") or 0)
                continue
            total += n
            if step.get("status") == "passed":
                passed += n
            else:
                failed += n
    return total, passed, failed


def _execution_has_scenario_steps(scenario_results: list[dict[str, Any]]) -> bool:
    for scenario in scenario_results or []:
        if not isinstance(scenario, dict):
            continue
        if scenario.get("steps"):
            return True
    return False
