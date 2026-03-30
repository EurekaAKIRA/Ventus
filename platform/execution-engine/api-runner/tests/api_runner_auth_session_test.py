"""Auth and session regression tests for the API runner."""

from __future__ import annotations

import base64
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[4]
    additions = [
        root / "platform" / "shared" / "src",
        root / "platform" / "execution-engine" / "api-runner" / "src",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/login":
            payload = {"token": "token-456"}
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Set-Cookie", "session_id=session-123; Path=/")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return

        self.send_error(404)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/secure":
            if self.headers.get("Authorization") != "Bearer token-456":
                self._send_json(401, {"error": "bad bearer"})
                return
            if "session_id=session-123" not in (self.headers.get("Cookie") or ""):
                self._send_json(401, {"error": "missing session"})
                return
            self._send_json(200, {"items": [{"id": "item-001"}], "user": "demo-user"})
            return

        if self.path == "/basic":
            expected = "Basic " + base64.b64encode(b"demo:secret").decode("ascii")
            if self.headers.get("Authorization") != expected:
                self._send_json(401, {"error": "bad basic"})
                return
            self._send_json(200, {"authenticated": True})
            return

        self.send_error(404)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _send_json(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> int:
    _extend_path()
    from api_runner import execute_test_case_dsl

    server = HTTPServer(("127.0.0.1", 8012), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)
    try:
        payload = {
            "dsl_version": "0.2.0",
            "task_id": "auth_session_demo",
            "task_name": "auth_session_demo",
            "feature_name": "auth_session_demo",
            "execution_mode": "api",
            "metadata": {
                "execution": {
                    "base_url": "http://127.0.0.1:8012",
                    "default_headers": {"X-Test-Client": "platform-api-runner"},
                }
            },
            "scenarios": [
                {
                    "scenario_id": "s1",
                    "name": "bearer and session",
                    "steps": [
                        {
                            "step_id": "s1_01",
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
                            "step_id": "s1_02",
                            "step_type": "when",
                            "text": "access secure endpoint",
                            "uses_context": ["token"],
                            "request": {
                                "method": "GET",
                                "url": "/secure",
                                "auth": {"type": "bearer", "token_context": "token"},
                            },
                            "assertions": [
                                {"source": "status_code", "op": "eq", "expected": 200},
                                {"source": "json.items[0].id", "op": "eq", "expected": "item-001"},
                            ],
                        },
                    ],
                },
                {
                    "scenario_id": "s2",
                    "name": "basic auth",
                    "steps": [
                        {
                            "step_id": "s2_01",
                            "step_type": "when",
                            "text": "basic auth request",
                            "request": {
                                "method": "GET",
                                "url": "/basic",
                                "auth": {"type": "basic", "username": "demo", "password": "secret"},
                            },
                            "assertions": [
                                {"source": "status_code", "op": "eq", "expected": 200},
                                {"source": "json.authenticated", "op": "eq", "expected": True},
                            ],
                        }
                    ],
                },
            ],
        }

        result = execute_test_case_dsl(payload)
        assert result["status"] == "passed"
        assert result["metrics"]["cookie_count"] >= 1
        secure_step = result["scenario_results"][0]["steps"][1]
        assert secure_step["request_summary"]["auth_type"] == "bearer"
        assert secure_step["request_summary"]["headers"]["Authorization"] == "***"
        assert secure_step["response_summary"]["json_keys"] == ["items", "user"]
        assert secure_step["assertion_summary"]["passed"] == 2
        basic_step = result["scenario_results"][1]["steps"][0]
        assert basic_step["request"]["auth_type"] == "basic"
        events = [log["event"] for log in result["logs"]]
        assert "step_start" in events
        assert "request_prepared" in events
        assert "response_received" in events
        assert "context_saved" in events
        assert "assertions_evaluated" in events
        print("api runner auth/session test passed")
        return 0
    finally:
        server.shutdown()
        thread.join()


if __name__ == "__main__":
    raise SystemExit(main())
