"""Tests for async execute mode and realtime status polling."""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

import pytest
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


@pytest.fixture()
def api_client(monkeypatch: pytest.MonkeyPatch):
    _extend_path()
    import task_center.api as api_module
    from task_center.registry import TaskRegistry

    temp_dir = tempfile.TemporaryDirectory()
    api_module.registry = TaskRegistry(temp_dir.name)

    def _fake_run_dsl(_dsl, execution_mode="api"):
        time.sleep(0.2)
        return {
            "task_id": str(_dsl.get("task_id") or ""),
            "executor": "api-runner",
            "status": "passed",
            "scenario_results": [],
            "metrics": {"avg_elapsed_ms": 120.0, "failed_step_count": 0},
            "logs": [{"time": "2026-04-03T00:00:00+00:00", "level": "INFO", "message": f"done:{execution_mode}"}],
        }

    monkeypatch.setattr(api_module, "run_dsl", _fake_run_dsl)
    client = TestClient(api_module.app)
    yield client, api_module.registry
    deadline = time.time() + 3
    while time.time() < deadline:
        with api_module._RUNNING_EXECUTION_LOCK:
            has_running = any(not fut.done() for fut in api_module._RUNNING_EXECUTION_FUTURES.values())
        if not has_running:
            break
        time.sleep(0.05)
    temp_dir.cleanup()


def test_async_execute_returns_running_then_final(api_client):
    client, registry = api_client
    create = client.post(
        "/api/tasks",
        json={
            "task_name": "async_exec_demo",
            "source_type": "text",
            "requirement_text": "demo",
            "target_system": "http://127.0.0.1:8001",
            "environment": "test",
        },
    )
    assert create.status_code == 201
    task_id = create.json()["data"]["task_id"]

    task = registry.get(task_id)
    assert task is not None
    task.pipeline_result = {
        "task_context": task.task_context,
        "validation_report": {"feature_name": task.task_name, "passed": True, "errors": [], "warnings": [], "metrics": {}},
        "test_case_dsl": {"task_id": task_id, "task_name": task.task_name, "metadata": {"execution": {"base_url": "http://127.0.0.1:8001"}}, "scenarios": []},
        "parse_metadata": {},
    }
    registry.save(task)

    execute = client.post(
        f"/api/tasks/{task_id}/execute",
        json={"execution_mode": "api", "environment": "test", "async_mode": True},
    )
    assert execute.status_code == 200
    assert execute.json()["code"] == "TASK_EXECUTION_STARTED"
    assert execute.json()["data"]["status"] == "running"

    execute_again = client.post(
        f"/api/tasks/{task_id}/execute",
        json={"execution_mode": "api", "environment": "test", "async_mode": True},
    )
    assert execute_again.status_code == 200
    assert execute_again.json()["code"] == "TASK_EXECUTION_ALREADY_RUNNING"
    assert execute_again.json()["data"]["status"] == "running"

    deadline = time.time() + 5
    final_status = "running"
    while time.time() < deadline:
        current = client.get(f"/api/tasks/{task_id}/execution")
        assert current.status_code == 200
        final_status = current.json()["data"]["status"]
        if final_status != "running":
            break
        time.sleep(0.2)

    assert final_status == "passed"
