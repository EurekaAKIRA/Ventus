"""Tests for Apifox-like automatic request header defaults."""

from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[4]
    for rel in (
        "platform/shared/src",
        "platform/execution-engine/api-runner/src",
    ):
        p = str(root / rel)
        if p not in sys.path:
            sys.path.insert(0, p)


def _run_header_echo_case(assertions: list[dict], request_headers: dict | None = None) -> dict:
    _extend_path()

    class H(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            body = {
                "success": True,
                "code": "OK",
                "data": {
                    "content_type": self.headers.get("Content-Type"),
                    "accept": self.headers.get("Accept"),
                },
            }
            raw = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, fmt: str, *args) -> None:  # noqa: A003
            return

    srv = HTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)
    try:
        from api_runner.executor import execute_test_case_dsl

        payload = {
            "dsl_version": "0.2.0",
            "task_id": "t-header",
            "task_name": "t-header",
            "feature_name": "t-header",
            "execution_mode": "api",
            "metadata": {"execution": {"base_url": f"http://127.0.0.1:{port}"}},
            "scenarios": [
                {
                    "scenario_id": "s1",
                    "name": "post-json-header-echo",
                    "steps": [
                        {
                            "step_id": "s1_1",
                            "step_type": "when",
                            "text": "post",
                            "request": {
                                "method": "POST",
                                "url": "/x",
                                "json": {"k": 1},
                                "headers": request_headers or {},
                            },
                            "assertions": assertions,
                        }
                    ],
                }
            ],
        }
        return execute_test_case_dsl(payload)
    finally:
        srv.shutdown()
        thread.join()


def test_runner_auto_adds_default_headers_for_json():
    result = _run_header_echo_case(
        assertions=[
            {"source": "json.content_type", "op": "eq", "expected": "application/json"},
            {"source": "json.accept", "op": "eq", "expected": "application/json"},
        ],
    )
    assert result["status"] == "passed", result


def test_runner_keeps_user_accept_header_override():
    result = _run_header_echo_case(
        assertions=[
            {"source": "json.content_type", "op": "eq", "expected": "application/json"},
            {"source": "json.accept", "op": "eq", "expected": "application/vnd.custom+json"},
        ],
        request_headers={"accept": "application/vnd.custom+json"},
    )
    assert result["status"] == "passed", result
