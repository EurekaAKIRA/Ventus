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
        original_context_task_id = create_payload["data"]["task_context"]["task_id"]
        assert original_context_task_id == task_id

        second_create_resp = client.post(
            "/api/tasks",
            json={
                "task_name": "persistence_demo",
                "source_type": "text",
                "requirement_text": "再次创建同名任务，避免 artifact 串号。",
                "target_system": "http://127.0.0.1:8010",
                "environment": "test",
            },
        )
        assert second_create_resp.status_code == 201
        second_task_id = second_create_resp.json()["data"]["task_id"]
        assert second_task_id != task_id

        assert client.post(f"/api/tasks/{task_id}/parse").status_code == 200
        detail_resp = client.get(f"/api/tasks/{task_id}")
        assert detail_resp.status_code == 200
        detail_payload = detail_resp.json()["data"]
        assert detail_payload["task_id"] == task_id
        assert detail_payload["task_context"]["task_id"] == task_id
        assert detail_payload["test_case_dsl"]["task_id"] == task_id
        assert task_id in str(detail_payload["artifact_dir"])
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
        assert list_payload["data"]["total"] == 2
        recovered_task_ids = {item["task_id"] for item in list_payload["data"]["items"]}
        assert task_id in recovered_task_ids
        assert second_task_id in recovered_task_ids

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
        assert history_payload["total"] == 2
        archived_history = {item["task_id"]: item["archived"] for item in history_payload["items"]}
        assert archived_history[task_id] is True
        assert archived_history[second_task_id] is False

        active_resp = recovered_client.get("/api/tasks")
        assert active_resp.status_code == 200
        assert active_resp.json()["data"]["total"] == 1

    print("persistence recovery test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
