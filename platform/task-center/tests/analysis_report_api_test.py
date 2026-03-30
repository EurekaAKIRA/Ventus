"""Regression checks for analysis report and dashboard payloads."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[3]
    legacy = root / "legacy"
    additions = [
        root / "platform" / "shared" / "src",
        root / "platform" / "requirement-analysis" / "src",
        root / "platform" / "case-generation" / "src",
        root / "platform" / "result-analysis" / "src",
        root / "platform" / "execution-engine" / "api-runner" / "src",
        root / "platform" / "execution-engine" / "core" / "src",
        root / "platform" / "task-center" / "src",
        legacy / "lavague-core",
        legacy / "lavague-integrations" / "drivers" / "lavague-drivers-selenium",
        legacy / "lavague-integrations" / "drivers" / "lavague-drivers-playwright",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


def main() -> int:
    _extend_path()
    import task_center.api as api_module
    from task_center.registry import TaskRegistry

    temp_dir = tempfile.TemporaryDirectory()
    api_module.registry = TaskRegistry(temp_dir.name)
    client = TestClient(api_module.app)

    create_resp = client.post(
        "/api/tasks",
        json={
            "task_name": "analysis_api_demo",
            "source_type": "text",
            "requirement_text": "用户登录后访问个人资料，并校验昵称与订单入口。",
        },
    )
    assert create_resp.status_code == 201
    create_payload = create_resp.json()
    assert create_payload["success"] is True
    task_id = create_payload["data"]["task_id"]
    assert client.post(f"/api/tasks/{task_id}/parse").status_code == 200

    task = api_module.registry.get(task_id)
    assert task is not None
    assert task.pipeline_result is not None
    task.execution_result = {
        "executor": "api",
        "status": "failed",
        "metrics": {
            "step_count": 2,
            "passed_step_count": 0,
            "failed_step_count": 2,
            "avg_elapsed_ms": 108,
            "max_elapsed_ms": 121,
            "context_keys": ["token"],
            "total_requests": 2,
            "success_count": 0,
            "failure_count": 2,
            "throughput": 9.8,
        },
        "scenario_results": [
            {
                "scenario_id": "scenario_001",
                "name": "登录后访问资料",
                "steps": [
                    {
                        "step_id": "step_login",
                        "step_type": "when",
                        "text": "调用登录接口",
                        "status": "failed",
                        "message": "Assertion failed: status_code eq 200, actual=401",
                        "request": {"method": "POST", "url": "/login"},
                        "response": {"status_code": 401, "elapsed_ms": 95, "body_preview": "unauthorized"},
                    },
                    {
                        "step_id": "step_profile",
                        "step_type": "then",
                        "text": "调用资料接口",
                        "status": "failed",
                        "message": "Missing context: token",
                        "response": {"elapsed_ms": 121},
                    },
                ],
            }
        ],
        "logs": [{"level": "error", "message": "login failed"}],
    }
    task.pipeline_result["validation_report"] = {
        "feature_name": "analysis_api_demo",
        "passed": False,
        "errors": ["Feature validation failed"],
        "warnings": ["Missing optional tag"],
        "metrics": {},
    }
    api_module.registry.save(task)

    analysis_resp = client.get(f"/api/tasks/{task_id}/analysis-report")
    assert analysis_resp.status_code == 200
    analysis_envelope = analysis_resp.json()
    assert analysis_envelope["success"] is True
    analysis_payload = analysis_envelope["data"]
    assert analysis_payload["report_version"] == "1.1.0"
    assert analysis_payload["summary"]["total_steps"] == 2
    assert analysis_payload["summary"]["failed_steps"] == 2
    assert analysis_payload["summary"]["avg_elapsed_ms"] == 108.0
    assert analysis_payload["dashboard_summary"]["failed_steps"] == 2
    assert analysis_payload["task_summary"]["next_action"] == "优先处理失败步骤与失败原因分类"
    assert analysis_payload["report_sections"][1]["key"] == "failures"
    assert analysis_payload["failed_steps"][0]["request_summary"]["method"] == "POST"
    assert any(item["category"] == "validation_error" for item in analysis_payload["failure_reasons"])
    assert analysis_payload["dashboard"]["assertion_summary"]["failed"] >= 0
    assert analysis_payload["dashboard"]["context_summary"]["extracted_keys"] == 1
    assert analysis_payload["task_summary_text"].startswith("任务 analysis_api_demo")

    dashboard_resp = client.get(f"/api/tasks/{task_id}/dashboard")
    assert dashboard_resp.status_code == 200
    dashboard_envelope = dashboard_resp.json()
    assert dashboard_envelope["success"] is True
    dashboard_payload = dashboard_envelope["data"]
    assert dashboard_payload["dashboard_summary"]["failed_steps"] == 2
    assert dashboard_payload["dashboard_summary"]["failed_scenarios"] == 1
    assert dashboard_payload["dashboard_summary"]["total_requests"] == 2
    assert isinstance(dashboard_payload["dashboard_summary"]["assertion_total"], int)
    assert isinstance(dashboard_payload["dashboard_summary"]["context_used_keys"], int)
    assert dashboard_payload["task_summary"]["next_action"] == "优先处理失败步骤与失败原因分类"
    assert dashboard_payload["performance_stats"]["throughput"] == 9.8
    assert dashboard_payload["report_sections"][0]["key"] == "overview"
    assert dashboard_payload["dashboard"]["top_failure_reason"]["category"] in {"assertion_failed", "missing_context"}
    assert dashboard_payload["dashboard"]["performance_summary"]["total_requests"] == 2
    assert dashboard_payload["failed_steps"][1]["category"] == "missing_context"
    assert dashboard_payload["task_summary_text"].startswith("任务 analysis_api_demo")
    assert dashboard_payload["execution_overview"]["status"] == "failed"
    assert dashboard_payload["context_stats"]["extracted_key_count"] == 1

    temp_dir.cleanup()
    print("analysis report api test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
