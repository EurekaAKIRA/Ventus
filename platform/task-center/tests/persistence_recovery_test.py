"""Persistence and recovery test for the task-center API."""

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

    with tempfile.TemporaryDirectory() as temp_dir:
        api_module.registry = TaskRegistry(temp_dir)
        client = TestClient(api_module.app)

        create_resp = client.post(
            "/api/tasks",
            json={
                "task_name": "persistence_demo",
                "source_type": "text",
                "requirement_text": "用户登录后访问个人中心并查看用户名",
                "target_system": "http://127.0.0.1:8010",
                "environment": "test",
            },
        )
        assert create_resp.status_code == 201
        create_payload = create_resp.json()
        assert create_payload["success"] is True
        task_id = create_payload["data"]["task_id"]

        assert client.post(f"/api/tasks/{task_id}/parse").status_code == 200
        execute_resp = client.post(
            f"/api/tasks/{task_id}/execute",
            json={"execution_mode": "api", "environment": "test"},
        )
        assert execute_resp.status_code == 200

        api_module.registry = TaskRegistry(temp_dir)
        recovered_client = TestClient(api_module.app)

        list_resp = recovered_client.get("/api/tasks")
        assert list_resp.status_code == 200
        list_payload = list_resp.json()
        assert list_payload["success"] is True
        assert list_payload["data"]["total"] == 1

        dsl_resp = recovered_client.get(f"/api/tasks/{task_id}/dsl")
        assert dsl_resp.status_code == 200
        assert dsl_resp.json()["data"]["task_id"] == task_id

        execution_resp = recovered_client.get(f"/api/tasks/{task_id}/execution")
        assert execution_resp.status_code == 200
        assert execution_resp.json()["data"]["status"] in {"passed", "success", "completed", "failed"}

        analysis_resp = recovered_client.get(f"/api/tasks/{task_id}/analysis-report")
        assert analysis_resp.status_code == 200
        assert "summary" in analysis_resp.json()["data"]

        delete_resp = recovered_client.delete(f"/api/tasks/{task_id}")
        assert delete_resp.status_code == 200

        history_resp = recovered_client.get("/api/history/tasks")
        assert history_resp.status_code == 200
        history_payload = history_resp.json()["data"]
        assert history_payload["total"] == 1
        assert history_payload["items"][0]["archived"] is True

        active_resp = recovered_client.get("/api/tasks")
        assert active_resp.status_code == 200
        assert active_resp.json()["data"]["total"] == 0

    print("persistence recovery test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
