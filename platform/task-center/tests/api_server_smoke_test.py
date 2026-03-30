"""Smoke test for the FastAPI task-center API."""

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
            "task_name": "api_server_demo",
            "source_type": "text",
            "requirement_text": "用户登录后进入用户中心并看到昵称",
            "target_system": "http://127.0.0.1:8010",
            "environment": "test",
        },
    )
    assert create_resp.status_code == 201
    create_payload = create_resp.json()
    assert create_payload["success"] is True
    assert create_payload["code"] == "TASK_CREATED"
    task_id = create_payload["data"]["task_id"]

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["data"]["status"] == "ok"

    version_resp = client.get("/version")
    assert version_resp.status_code == 200
    assert version_resp.json()["data"]["service"] == "platform-task-center"

    environments_resp = client.get("/api/environments")
    assert environments_resp.status_code == 200
    assert any(item["name"] == "test" for item in environments_resp.json()["data"])

    task_list_resp = client.get("/api/tasks?page=1&page_size=10")
    assert task_list_resp.status_code == 200
    assert task_list_resp.json()["data"]["total"] == 1

    detail_resp = client.get(f"/api/tasks/{task_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["data"]["task_id"] == task_id

    parse_resp = client.post(f"/api/tasks/{task_id}/parse")
    assert parse_resp.status_code == 200
    assert parse_resp.json()["data"]["status"] == "parsed"

    assert client.get(f"/api/tasks/{task_id}/parsed-requirement").status_code == 200
    assert client.get(f"/api/tasks/{task_id}/retrieved-context").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/scenarios/generate").status_code == 200
    assert client.get(f"/api/tasks/{task_id}/scenarios").status_code == 200
    assert client.get(f"/api/tasks/{task_id}/dsl").status_code == 200
    assert client.get(f"/api/tasks/{task_id}/feature").status_code == 200
    execute_resp = client.post(
        f"/api/tasks/{task_id}/execute",
        json={"execution_mode": "api", "environment": "test"},
    )
    assert execute_resp.status_code == 200
    assert execute_resp.json()["success"] is True
    assert client.get(f"/api/tasks/{task_id}/validation-report").status_code == 200
    analysis_report_resp = client.get(f"/api/tasks/{task_id}/analysis-report")
    assert analysis_report_resp.status_code == 200
    analysis_report = analysis_report_resp.json()["data"]
    assert "summary" in analysis_report
    assert "dashboard" in analysis_report
    assert "execution_overview" in analysis_report
    assert "assertion_stats" in analysis_report
    assert "context_stats" in analysis_report
    assert "task_summary_text" in analysis_report
    assert "report_version" in analysis_report
    assert analysis_report["report_version"] == "1.1.0"
    assert "generated_at" in analysis_report
    assert "failure_reasons" in analysis_report
    dashboard_resp = client.get(f"/api/tasks/{task_id}/dashboard")
    assert dashboard_resp.status_code == 200
    dashboard_payload = dashboard_resp.json()["data"]
    assert "dashboard" in dashboard_payload
    assert "analysis_report" in dashboard_payload
    assert "summary" in dashboard_payload
    assert "failed_steps" in dashboard_payload
    assert "failure_reasons" in dashboard_payload
    assert "summary" in dashboard_payload["dashboard"]
    assert "totals" in dashboard_payload["dashboard"]
    assert client.get(f"/api/tasks/{task_id}/artifacts").status_code == 200
    assert client.get(f"/api/tasks/{task_id}/artifacts/dsl").status_code == 200
    history_resp = client.get("/api/history/tasks?page=1&page_size=10&keyword=api_server_demo")
    assert history_resp.status_code == 200
    assert history_resp.json()["data"]["total"] == 1
    execution_history_resp = client.get("/api/history/executions?page=1&page_size=10")
    assert execution_history_resp.status_code == 200
    assert execution_history_resp.json()["data"]["total"] >= 1
    assert client.get(f"/api/tasks/{task_id}/execution").status_code == 200
    assert client.get(f"/api/tasks/{task_id}/execution/logs").status_code == 200
    stop_resp = client.post(f"/api/tasks/{task_id}/execution/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["data"]["stopped"] is False
    delete_resp = client.delete(f"/api/tasks/{task_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["data"]["archived"] is True
    missing_resp = client.get("/api/tasks/not-found")
    assert missing_resp.status_code == 404
    assert missing_resp.json()["success"] is False
    assert missing_resp.json()["code"] == "TASK_NOT_FOUND"
    temp_dir.cleanup()

    print("api server smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
