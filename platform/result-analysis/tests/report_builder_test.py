"""Smoke tests for the formal analysis report builder."""

from __future__ import annotations

import json
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
    validation_report = ValidationReport(feature_name="demo_task", passed=True)
    dsl = _build_sample_dsl()

    passed_report = build_analysis_report(
        task_context=task_context,
        validation_report=validation_report,
        scenario_count=1,
        execution_result={
            "status": "passed",
            "metrics": {"context_key_count": 1},
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
                            "message": "POST /login -> 200",
                            "response": {"status_code": 200, "elapsed_ms": 120},
                        },
                        {
                            "step_id": "step_profile",
                            "step_type": "then",
                            "text": "Call profile API",
                            "status": "passed",
                            "message": "GET /profile -> 200",
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
    assert passed_report["generated_at"]
    assert passed_report["summary"]["total_steps"] == 2
    assert passed_report["summary"]["success_rate"] == 100.0
    assert passed_report["summary"]["passed_scenarios"] == 1
    assert passed_report["summary"]["assertion_total"] == 2
    assert passed_report["assertion_stats"]["total"] == 2
    assert passed_report["assertion_stats"]["pass_rate"] == 100.0
    assert passed_report["context_stats"]["defined_key_count"] == 1
    assert passed_report["context_stats"]["extracted_keys"] == ["token"]
    assert passed_report["dashboard"]["totals"]["assertions"] == 2
    assert passed_report["dashboard_summary"]["assertion_passed"] == 2
    assert passed_report["dashboard_summary"]["context_extracted_keys"] == 1
    assert passed_report["task_summary"]["next_action"] == "可进入联调或演示环节"
    assert len(passed_report["report_sections"]) == 4
    assert passed_report["report_sections"][0]["key"] == "overview"
    assert passed_report["dashboard"]["status_breakdown"]["passed_scenarios"] == 1
    assert passed_report["dashboard"]["summary"]["scenario_count"] == 1
    assert passed_report["dashboard"]["summary"]["passed_scenarios"] == 1
    assert passed_report["dashboard"]["summary"]["assertion_total"] == 2
    assert passed_report["dashboard"]["summary"]["context_defined_keys"] == 1
    assert passed_report["dashboard"]["context_summary"]["defined_key_names"] == ["token"]
    assert passed_report["dashboard"]["context_summary"]["extracted_key_names"] == ["token"]
    assert passed_report["execution_overview"]["status"] == "passed"
    assert passed_report["dashboard"]["headline"] == "2/2 steps passed"
    assert "平均耗时" in passed_report["task_summary_text"]
    schema_path = Path(__file__).resolve().parents[2] / "shared" / "schemas" / "analysis_report.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for key in schema["required"]:
        assert key in passed_report
    for key in schema["properties"]["summary"]["required"]:
        assert key in passed_report["summary"]

    failed_report = build_analysis_report(
        task_context=task_context,
        validation_report=ValidationReport(
            feature_name="demo_task",
            passed=False,
            errors=["Feature validation failed", "Scenario tag missing"],
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
    assert failed_report["failed_steps"][0]["step_index"] == 1
    assert failed_report["failure_reasons"][0]["category"] == "validation_error"
    assert failed_report["dashboard"]["top_failure_reason"]["category"] == "validation_error"
    assert failed_report["failure_reasons"][0]["label"]
    assert failed_report["dashboard"]["failure_reason_breakdown"]
    assert failed_report["dashboard_summary"]["failure_rate"] == 100.0
    assert failed_report["task_summary"]["next_action"] == "优先处理失败步骤与失败原因分类"
    assert failed_report["report_sections"][1]["key"] == "failures"
    assert failed_report["dashboard"]["summary"]["failed_scenarios"] == 1
    assert failed_report["dashboard"]["summary"]["context_used_keys"] == 1
    assert failed_report["context_stats"]["unused_defined_keys"] == []
    assert failed_report["context_stats"]["undefined_used_keys"] == []
    assert any(item["category"] == "validation_warning" for item in failed_report["failure_reasons"])
    assert failed_report["task_summary_text"]

    pending_report = build_analysis_report(
        task_context=task_context,
        validation_report=validation_report,
        scenario_count=1,
        execution_result={"status": "not_started", "metrics": {}, "scenario_results": []},
        test_case_dsl=dsl,
    )
    assert pending_report["summary"]["total_steps"] == 2
    assert pending_report["summary"]["failed_steps"] == 0
    assert pending_report["summary"]["success_rate"] == 0.0
    assert pending_report["task_summary"]["next_action"] == "执行任务以生成运行报告"
    assert "尚未开始执行" in pending_report["task_summary_text"]

    print("report builder smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
