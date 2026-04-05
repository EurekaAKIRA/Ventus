"""Unit tests for execution assertion aggregation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for rel in ("platform/shared/src", "platform/result-analysis/src"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from result_analysis.assertion_stats import compute_assertion_execution_stats


def test_rollup_from_assertion_summary() -> None:
    dsl = {
        "scenarios": [
            {
                "steps": [
                    {"step_id": "s1", "assertions": [{"source": "status_code"}] * 6},
                ],
            },
        ],
    }
    scenario_results = [
        {
            "steps": [
                {
                    "step_id": "s1",
                    "status": "failed",
                    "assertion_summary": {"total": 6, "passed": 1, "failed": 5},
                },
            ],
        },
    ]
    total, passed, failed = compute_assertion_execution_stats(scenario_results, dsl)
    assert (total, passed, failed) == (6, 1, 5)


def test_fallback_dsl_counts_per_step_when_no_summary() -> None:
    dsl = {
        "scenarios": [
            {
                "steps": [
                    {"step_id": "a", "assertions": [{}]},
                    {"step_id": "b", "assertions": [{}]},
                ],
            },
        ],
    }
    scenario_results = [
        {
            "steps": [
                {"step_id": "a", "status": "failed", "message": "Assertion failed: x"},
                {"step_id": "b", "status": "failed", "message": "Missing context"},
            ],
        },
    ]
    total, passed, failed = compute_assertion_execution_stats(scenario_results, dsl)
    assert (total, passed, failed) == (2, 0, 2)


def test_pending_no_execution_steps_uses_dsl_total_zero_pass() -> None:
    dsl = {"scenarios": [{"steps": [{"step_id": "x", "assertions": [{}]}]}]}
    total, passed, failed = compute_assertion_execution_stats([], dsl)
    assert (total, passed, failed) == (1, 0, 0)
