"""Tests for preflight-check and execution/explanations endpoints."""

from __future__ import annotations

import sys
import tempfile
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

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


@pytest.fixture()
def ping_only_server():
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/ping":
                body = b"pong"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join()


@pytest.fixture()
def root_only_server():
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/":
                body = b"ok"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join()


def test_preflight_unreachable_base(api_client):
    client, _registry = api_client
    r = client.post(
        "/api/tasks",
        json={
            "task_name": "preflight_demo",
            "source_type": "text",
            "requirement_text": "demo",
            "target_system": "http://127.0.0.1:1",
            "environment": "test",
        },
    )
    assert r.status_code == 201
    task_id = r.json()["data"]["task_id"]
    pre = client.post(f"/api/tasks/{task_id}/preflight-check", json={})
    assert pre.status_code == 200
    body = pre.json()
    assert body["success"] is True
    assert body["code"] == "PREFLIGHT_OK"
    data = body["data"]
    assert data["overall_status"] == "failed"
    assert data["blocking"] is True
    assert data["blocking_issues"]


def test_preflight_ping_fallback_marks_base_reachable(api_client, ping_only_server):
    client, _registry = api_client
    r = client.post(
        "/api/tasks",
        json={
            "task_name": "preflight_ping_fallback",
            "source_type": "text",
            "requirement_text": "demo",
            "target_system": ping_only_server,
            "environment": "test",
        },
    )
    assert r.status_code == 201
    task_id = r.json()["data"]["task_id"]
    pre = client.post(f"/api/tasks/{task_id}/preflight-check", json={})
    assert pre.status_code == 200
    data = pre.json()["data"]

    reachability = next(item for item in data["checks"] if item["name"] == "base_url_reachable")
    assert reachability["status"] == "passed"
    assert data["blocking"] is False


def test_preflight_root_fallback_avoids_false_blocking(api_client, root_only_server):
    client, _registry = api_client
    r = client.post(
        "/api/tasks",
        json={
            "task_name": "preflight_root_fallback",
            "source_type": "text",
            "requirement_text": "demo",
            "target_system": root_only_server,
            "environment": "test",
        },
    )
    assert r.status_code == 201
    task_id = r.json()["data"]["task_id"]
    pre = client.post(f"/api/tasks/{task_id}/preflight-check", json={})
    assert pre.status_code == 200
    data = pre.json()["data"]

    reachability = next(item for item in data["checks"] if item["name"] == "base_url_reachable")
    assert reachability["status"] == "passed"
    assert data["blocking"] is False


def test_explanations_requires_execution(api_client):
    client, _registry = api_client
    r = client.post(
        "/api/tasks",
        json={
            "task_name": "expl_demo",
            "source_type": "text",
            "requirement_text": "demo",
            "target_system": "http://127.0.0.1:8001",
            "environment": "test",
        },
    )
    task_id = r.json()["data"]["task_id"]
    ex = client.get(f"/api/tasks/{task_id}/execution/explanations")
    assert ex.status_code == 404


def test_explanations_with_stored_execution(api_client):
    client, registry = api_client
    r = client.post(
        "/api/tasks",
        json={
            "task_name": "expl_demo2",
            "source_type": "text",
            "requirement_text": "demo",
            "target_system": "http://127.0.0.1:8001",
            "environment": "test",
        },
    )
    task_id = r.json()["data"]["task_id"]
    task = registry.get(task_id)
    task.execution_result = {
        "task_id": task_id,
        "executor": "api-runner",
        "status": "failed",
        "scenario_results": [
            {
                "scenario_id": "s1",
                "name": "n",
                "status": "failed",
                "steps": [
                    {
                        "step_id": "s1_1",
                        "status": "failed",
                        "message": "Assertion failed: json.id exists None, actual=None",
                        "error_category": "assertion_error",
                    }
                ],
            }
        ],
        "metrics": {},
        "logs": [],
    }
    registry.save(task)

    ex = client.get(f"/api/tasks/{task_id}/execution/explanations?top_n=3")
    assert ex.status_code == 200
    payload = ex.json()
    assert payload["code"] == "EXECUTION_EXPLANATIONS_OK"
    data = payload["data"]
    assert data["summary"]["failed_steps"] == 1
    assert "field_mapping" in data["top_reasons"]


def test_execution_stream_with_stored_execution(api_client):
    client, registry = api_client
    r = client.post(
        "/api/tasks",
        json={
            "task_name": "stream_demo",
            "source_type": "text",
            "requirement_text": "demo",
            "target_system": "http://127.0.0.1:8001",
            "environment": "test",
        },
    )
    task_id = r.json()["data"]["task_id"]
    task = registry.get(task_id)
    task.execution_result = {
        "task_id": task_id,
        "executor": "api-runner",
        "status": "failed",
        "scenario_results": [],
        "metrics": {},
        "logs": [
            {"time": "2026-04-03T00:00:00+00:00", "level": "INFO", "message": "started"},
            {"time": "2026-04-03T00:00:01+00:00", "level": "ERROR", "message": "failed"},
        ],
    }
    registry.save(task)

    with client.stream("GET", f"/api/tasks/{task_id}/execution/stream?interval_ms=200&timeout_s=5") as stream_resp:
        assert stream_resp.status_code == 200
        stream_text = "".join(list(stream_resp.iter_text()))

    assert "event: connected" in stream_text
    assert "event: execution_done" in stream_text
    assert "failed" in stream_text
