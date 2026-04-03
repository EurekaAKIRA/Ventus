"""Tests for /api/tasks/{task_id}/regression-diff endpoint."""

from __future__ import annotations

import sys
import tempfile
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
def api_client():
    _extend_path()
    import task_center.api as api_module
    from task_center.registry import TaskRegistry

    temp_dir = tempfile.TemporaryDirectory()
    api_module.registry = TaskRegistry(temp_dir.name)
    client = TestClient(api_module.app)
    yield client, api_module.registry
    temp_dir.cleanup()


def _create_task(client: TestClient) -> str:
    resp = client.post(
        "/api/tasks",
        json={
            "task_name": "regression_diff_demo",
            "source_type": "text",
            "requirement_text": "demo",
            "target_system": "http://127.0.0.1:8001",
            "environment": "test",
        },
    )
    assert resp.status_code == 201
    return str(resp.json()["data"]["task_id"])


def test_regression_diff_ready_returns_payload(api_client):
    client, registry = api_client
    task_id = _create_task(client)
    registry.append_execution_history(
        {
            "task_id": task_id,
            "task_name": "regression_diff_demo",
            "environment": "test",
            "execution_mode": "api",
            "status": "failed",
            "executor": "api-runner",
            "executed_at": "2026-04-03T08:00:00+00:00",
            "metrics": {"avg_elapsed_ms": 320.0, "failed_step_count": 3},
            "analysis_summary": {"success_rate": 62.5, "failed_steps": 3, "avg_elapsed_ms": 320.0},
        }
    )
    registry.append_execution_history(
        {
            "task_id": task_id,
            "task_name": "regression_diff_demo",
            "environment": "test",
            "execution_mode": "api",
            "status": "passed",
            "executor": "api-runner",
            "executed_at": "2026-04-03T09:00:00+00:00",
            "metrics": {"avg_elapsed_ms": 210.0, "failed_step_count": 1},
            "analysis_summary": {"success_rate": 87.5, "failed_steps": 1, "avg_elapsed_ms": 210.0},
        }
    )

    resp = client.get(f"/api/tasks/{task_id}/regression-diff")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["code"] == "REGRESSION_DIFF_OK"
    data = payload["data"]
    assert data["task_id"] == task_id
    assert data["verdict"] == "improved"
    assert data["metrics_diff"]["failed_steps_delta"] == -2
    assert data["metrics_diff"]["success_rate_delta"] == 25.0


def test_regression_diff_not_ready_returns_409(api_client):
    client, registry = api_client
    task_id = _create_task(client)
    registry.append_execution_history(
        {
            "task_id": task_id,
            "task_name": "regression_diff_demo",
            "environment": "test",
            "execution_mode": "api",
            "status": "failed",
            "executor": "api-runner",
            "executed_at": "2026-04-03T08:00:00+00:00",
            "metrics": {"avg_elapsed_ms": 300.0, "failed_step_count": 2},
            "analysis_summary": {"success_rate": 70.0, "failed_steps": 2, "avg_elapsed_ms": 300.0},
        }
    )

    resp = client.get(f"/api/tasks/{task_id}/regression-diff")
    assert resp.status_code == 409
    payload = resp.json()
    assert payload["success"] is False
    assert payload["code"] == "REGRESSION_DIFF_NOT_READY"

