"""Environment switching and execution history regression test."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
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


def _build_dsl(task_id: str, task_name: str) -> dict:
    return {
        "dsl_version": "0.2.0",
        "task_id": task_id,
        "task_name": task_name,
        "feature_name": task_name,
        "execution_mode": "api",
        "metadata": {},
        "scenarios": [
            {
                "scenario_id": "scenario_auth_profile",
                "name": "auth and profile",
                "steps": [
                    {
                        "step_id": "step_login",
                        "step_type": "when",
                        "text": "login",
                        "request": {"method": "POST", "url": "/login", "json": {"username": "demo"}},
                        "assertions": [
                            {"source": "status_code", "op": "eq", "expected": 200},
                            {"source": "json.token", "op": "exists"},
                        ],
                        "save_context": {"token": "json.token"},
                    },
                    {
                        "step_id": "step_profile",
                        "step_type": "when",
                        "text": "profile",
                        "uses_context": ["token"],
                        "request": {
                            "method": "GET",
                            "url": "/profile",
                            "auth": {"type": "bearer", "token_context": "token"},
                        },
                        "assertions": [
                            {"source": "status_code", "op": "eq", "expected": 200},
                            {"source": "json.environment", "op": "exists"},
                        ],
                    },
                ],
            }
        ],
    }


class _EnvHandler(BaseHTTPRequestHandler):
    environment = "unknown"

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/login":
            self.send_error(404)
            return
        payload = json.dumps({"token": f"token-{self.environment}"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/profile":
            self.send_error(404)
            return
        auth = self.headers.get("Authorization")
        if auth != f"Bearer token-{self.environment}":
            self._send_json(401, {"error": "unauthorized"})
            return
        self._send_json(200, {"environment": self.environment, "client": self.headers.get("X-Env-Name")})

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _send_json(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _make_handler(environment_name: str):
    class Handler(_EnvHandler):
        environment = environment_name

    return Handler


def main() -> int:
    _extend_path()
    import task_center.api as api_module
    from platform_shared.models import EnvironmentConfig
    from task_center.registry import TaskRegistry

    with tempfile.TemporaryDirectory() as temp_dir:
        api_module.registry = TaskRegistry(temp_dir)
        server_dev = HTTPServer(("127.0.0.1", 0), _make_handler("dev"))
        server_test = HTTPServer(("127.0.0.1", 0), _make_handler("test"))
        dev_port = server_dev.server_port
        test_port = server_test.server_port
        api_module.registry.save_environment(
            EnvironmentConfig(
                name="dev",
                base_url=f"http://127.0.0.1:{dev_port}",
                default_headers={"X-Env-Name": "dev"},
                description="dev env",
            )
        )
        api_module.registry.save_environment(
            EnvironmentConfig(
                name="test",
                base_url=f"http://127.0.0.1:{test_port}",
                default_headers={"X-Env-Name": "test"},
                description="test env",
            )
        )

        thread_dev = threading.Thread(target=server_dev.serve_forever, daemon=True)
        thread_test = threading.Thread(target=server_test.serve_forever, daemon=True)
        thread_dev.start()
        thread_test.start()
        time.sleep(0.15)
        try:
            client = TestClient(api_module.app)
            create_resp = client.post(
                "/api/tasks",
                json={
                    "task_name": "env_switch_demo",
                    "source_type": "text",
                    "requirement_text": "login and query profile api",
                },
            )
            assert create_resp.status_code == 201
            task_id = create_resp.json()["data"]["task_id"]
            assert client.post(f"/api/tasks/{task_id}/parse").status_code == 200

            task = api_module.registry.get(task_id)
            assert task is not None
            assert task.pipeline_result is not None
            task.pipeline_result["test_case_dsl"] = _build_dsl(task_id, task.task_name)
            api_module.registry.save(task)

            env_resp = client.get("/api/environments")
            assert env_resp.status_code == 200
            env_names = {item["name"] for item in env_resp.json()["data"]}
            assert {"dev", "test", "prod"}.issubset(env_names)

            staging_resp = client.post(
                "/api/environments",
                json={
                    "name": "staging",
                    "base_url": f"http://127.0.0.1:{test_port}",
                    "default_headers": {"X-Env-Name": "staging"},
                    "auth": {"type": "bearer", "token": "demo-token"},
                    "description": "staging env",
                },
            )
            assert staging_resp.status_code == 201
            assert staging_resp.json()["data"]["name"] == "staging"

            update_resp = client.put(
                "/api/environments/staging",
                json={
                    "name": "ignored",
                    "base_url": f"http://127.0.0.1:{dev_port}",
                    "default_headers": {"X-Env-Name": "staging-updated"},
                    "cookies": {"session": "abc123"},
                    "description": "staging env updated",
                },
            )
            assert update_resp.status_code == 200
            assert update_resp.json()["data"]["cookies"]["session"] == "abc123"

            staging_detail = client.get("/api/environments/staging")
            assert staging_detail.status_code == 200
            assert staging_detail.json()["data"]["default_headers"]["X-Env-Name"] == "staging-updated"

            dev_execute = client.post(
                f"/api/tasks/{task_id}/execute",
                json={"execution_mode": "api", "environment": "dev"},
            )
            assert dev_execute.status_code == 200
            dev_payload = dev_execute.json()["data"]
            assert dev_payload["status"] == "passed"
            assert dev_payload["metadata"]["execution"]["environment"] == "dev"
            assert dev_payload["metadata"]["execution"]["base_url"] == f"http://127.0.0.1:{dev_port}"

            test_execute = client.post(
                f"/api/tasks/{task_id}/execute",
                json={"execution_mode": "api", "environment": "test"},
            )
            assert test_execute.status_code == 200
            test_payload = test_execute.json()["data"]
            assert test_payload["status"] == "passed"
            assert test_payload["metadata"]["execution"]["environment"] == "test"
            assert test_payload["scenario_results"][0]["steps"][1]["response"]["json"]["environment"] == "test"

            task_list_resp = client.get("/api/tasks?environment=test")
            assert task_list_resp.status_code == 200
            assert task_list_resp.json()["data"]["items"][0]["environment"] == "test"

            history_resp = client.get("/api/history/tasks?environment=test")
            assert history_resp.status_code == 200
            assert history_resp.json()["data"]["items"][0]["environment"] == "test"

            execution_history_resp = client.get("/api/history/executions?environment=dev")
            assert execution_history_resp.status_code == 200
            execution_history = execution_history_resp.json()["data"]
            assert execution_history["total"] == 1
            assert execution_history["items"][0]["environment"] == "dev"
            assert execution_history["items"][0]["analysis_summary"]["success_rate"] == 100.0

            all_history_resp = client.get(f"/api/history/executions?task_id={task_id}")
            assert all_history_resp.status_code == 200
            assert all_history_resp.json()["data"]["total"] == 2

            delete_resp = client.delete("/api/environments/staging")
            assert delete_resp.status_code == 200
            missing_resp = client.get("/api/environments/staging")
            assert missing_resp.status_code == 404

        finally:
            server_dev.shutdown()
            server_test.shutdown()
            thread_dev.join()
            thread_test.join()

    print("environment history test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
