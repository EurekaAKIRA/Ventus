"""Regression checks for the formal analysis report builder."""

from __future__ import annotations

import sys
from pathlib import Path


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[3]
    additions = [
        root / "platform" / "shared" / "src",
        root / "platform" / "result-analysis" / "src",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


def _build_sample_dsl() -> dict:
    return {
        "task_id": "task_demo",
        "task_name": "demo_task",
        "scenarios": [
            {
                "scenario_id": "scenario_login",
                "name": "Login Success",
                "steps": [
                    {
                        "step_id": "step_login",
                        "step_type": "when",
                        "text": "Call login API",
                        "assertions": [{"source": "status_code", "op": "eq", "expected": 200}],
                        "save_context": {"token": "json.data.token"},
                    },
                    {
                        "step_id": "step_profile",
                        "step_type": "then",
                        "text": "Call profile API",
                        "assertions": [{"source": "json.code", "op": "eq", "expected": 0}],
                        "uses_context": ["token"],
                    },
                ],
            }
        ],
    }


def main() -> int:
    _extend_path()

    from platform_shared.models import TaskContext, ValidationReport
    from result_analysis import build_analysis_report

    task_context = TaskContext(task_id="task_demo", task_name="demo_task", source_type="text")
    dsl = _build_sample_dsl()

    passed_report = build_analysis_report(
        task_context=task_context,
        validation_report=ValidationReport(feature_name="demo_task", passed=True),
        scenario_count=1,
        execution_result={
            "status": "passed",
            "metrics": {"context_keys": ["token"]},
            "scenario_results": [
                {
                    "scenario_id": "scenario_login",
                    "name": "Login Success",
                    "steps": [
                        {
                            "step_id": "step_login",
                            "step_type": "when",
                            "text": "Call login API",
                            "status": "passed",
                            "response": {"status_code": 200, "elapsed_ms": 120},
                        },
                        {
                            "step_id": "step_profile",
                            "step_type": "then",
                            "text": "Call profile API",
                            "status": "passed",
                            "response": {"status_code": 200, "elapsed_ms": 80},
                        },
                    ],
                }
            ],
        },
        test_case_dsl=dsl,
    )
    assert passed_report["quality_status"] == "passed"
    assert passed_report["report_version"] == "1.1.0"
    assert passed_report["summary"]["total_steps"] == 2
    assert passed_report["summary"]["success_rate"] == 100.0
    assert passed_report["summary"]["avg_elapsed_ms"] == 100.0
    assert passed_report["assertion_stats"]["pass_rate"] == 100.0
    assert passed_report["context_stats"]["extracted_keys"] == ["token"]
    assert passed_report["dashboard"]["assertion_summary"]["pass_rate"] == 100.0
    assert passed_report["dashboard_summary"]["assertion_total"] == 2
    assert passed_report["task_summary"]["headline"] == passed_report["task_summary_text"]
    assert passed_report["dashboard"]["summary"]["executed_scenarios"] == 1
    assert passed_report["dashboard"]["summary"]["assertion_total"] == 2
    assert passed_report["dashboard"]["context_summary"]["extracted_keys"] == 1
    assert passed_report["dashboard"]["context_summary"]["defined_key_names"] == ["token"]
    assert passed_report["dashboard"]["context_summary"]["extracted_key_names"] == ["token"]
    assert "平均耗时" in passed_report["task_summary_text"]

    failed_report = build_analysis_report(
        task_context=task_context,
        validation_report=ValidationReport(
            feature_name="demo_task",
            passed=False,
            errors=["Feature validation failed"],
            warnings=["Missing optional tag"],
        ),
        scenario_count=1,
        execution_result={
            "status": "failed",
            "metrics": {"context_key_count": 0},
            "scenario_results": [
                {
                    "scenario_id": "scenario_login",
                    "name": "Login Success",
                    "steps": [
                        {
                            "step_id": "step_login",
                            "step_type": "when",
                            "text": "Call login API",
                            "status": "failed",
                            "message": "Assertion failed: status_code eq 200, actual=401",
                            "response": {"status_code": 401, "elapsed_ms": 95},
                            "request": {"method": "POST", "url": "/login"},
                        },
                        {
                            "step_id": "step_profile",
                            "step_type": "then",
                            "text": "Call profile API",
                            "status": "failed",
                            "message": "Missing context: token",
                        },
                    ],
                }
            ],
        },
        test_case_dsl=dsl,
    )
    assert failed_report["quality_status"] == "failed"
    assert failed_report["summary"]["failed_steps"] == 2
    assert failed_report["failed_steps"][0]["category"] == "assertion_failed"
    assert failed_report["failed_steps"][0]["request_summary"]["method"] == "POST"
    assert failed_report["dashboard"]["failure_reason_breakdown"]
    assert failed_report["dashboard_summary"]["failed_steps"] == 2
    assert failed_report["task_summary"]["top_failure_reason"]["category"] == "assertion_failed"
    assert failed_report["dashboard"]["summary"]["failed_scenarios"] == 1
    assert failed_report["dashboard"]["summary"]["context_used_keys"] == 1
    assert any(item["category"] == "validation_error" for item in failed_report["failure_reasons"])
    assert any(item["category"] == "validation_warning" for item in failed_report["failure_reasons"])
    assert failed_report["dashboard"]["top_failure_reason"]["category"] == "assertion_failed"
    assert failed_report["dashboard"]["context_summary"]["undefined_used_keys"] == []

    pending_report = build_analysis_report(
        task_context=task_context,
        validation_report=ValidationReport(feature_name="demo_task", passed=True),
        scenario_count=1,
        execution_result={"status": "not_started", "metrics": {}, "scenario_results": []},
        test_case_dsl=dsl,
    )
    assert pending_report["summary"]["total_steps"] == 2
    assert pending_report["summary"]["failed_steps"] == 0
    assert pending_report["summary"]["success_rate"] == 0.0
    assert pending_report["report_sections"][2]["key"] == "assertions"
    assert "尚未开始执行" in pending_report["task_summary_text"]

    load_report = build_analysis_report(
        task_context=task_context,
        validation_report=ValidationReport(feature_name="demo_task", passed=True),
        scenario_count=1,
        execution_result={
            "executor": "cloud-load-runner",
            "status": "passed",
            "metrics": {
                "step_count": 1,
                "passed_step_count": 1,
                "failed_step_count": 0,
                "total_requests": 24,
                "success_count": 24,
                "failure_count": 0,
                "avg_elapsed_ms": 18.5,
                "max_elapsed_ms": 31.0,
                "throughput": 120.5,
            },
            "scenario_results": [
                {
                    "scenario_id": "load_01",
                    "name": "Load Scenario",
                    "status": "passed",
                    "steps": [
                        {
                            "step_id": "load_step",
                            "step_type": "when",
                            "text": "Load endpoint",
                            "status": "passed",
                            "response": {"status_code": 200, "elapsed_ms": 18.5},
                        }
                    ],
                }
            ],
        },
        test_case_dsl={
            "task_id": "task_demo",
            "task_name": "demo_task",
            "scenarios": [
                {
                    "scenario_id": "load_01",
                    "steps": [
                        {
                            "step_id": "load_step",
                            "step_type": "when",
                            "text": "Load endpoint",
                            "request": {"method": "GET", "url": "/load"},
                            "assertions": [{"source": "status_code", "op": "eq", "expected": 200}],
                        }
                    ],
                }
            ],
        },
    )
    assert load_report["summary"]["total_requests"] == 24
    assert load_report["summary"]["throughput"] == 120.5
    assert load_report["performance_stats"]["is_load_test"] is True
    assert load_report["dashboard_summary"]["total_requests"] == 24
    assert load_report["dashboard"]["performance_summary"]["throughput"] == 120.5
    assert load_report["dashboard"]["totals"]["requests"] == 24
    assert load_report["report_sections"][4]["key"] == "performance"

    print("analysis report regression test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
