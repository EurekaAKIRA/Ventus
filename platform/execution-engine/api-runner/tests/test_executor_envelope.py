"""Tests for envelope JSON fallback and default timeout/retries wiring."""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[4]
    for rel in (
        "platform/shared/src",
        "platform/execution-engine/api-runner/src",
    ):
        p = str(root / rel)
        if p not in sys.path:
            sys.path.insert(0, p)


@pytest.fixture()
def envelope_server():
    _extend_path()

    class H(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            body = {"success": True, "code": "OK", "data": {"task_id": "t-env-1"}}
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
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.shutdown()


def test_exists_assertion_reads_envelope_data(envelope_server):
    from api_runner.executor import execute_test_case_dsl

    dsl = {
        "dsl_version": "0.2.0",
        "task_id": "t1",
        "task_name": "t1",
        "feature_name": "t1",
        "execution_mode": "api",
        "metadata": {"execution": {"base_url": envelope_server}},
        "scenarios": [
            {
                "scenario_id": "s1",
                "name": "get",
                "steps": [
                    {
                        "step_id": "s1_1",
                        "step_type": "when",
                        "text": "get",
                        "request": {"method": "GET", "url": "/x", "retries": 0},
                        "assertions": [
                            {"source": "status_code", "op": "eq", "expected": 200},
                            {"source": "json.task_id", "op": "exists"},
                        ],
                    }
                ],
            }
        ],
    }
    result = execute_test_case_dsl(dsl)
    assert result["status"] == "passed"


def test_save_context_reads_envelope_data(envelope_server):
    from api_runner.executor import execute_test_case_dsl

    dsl = {
        "dsl_version": "0.2.0",
        "task_id": "t2",
        "task_name": "t2",
        "feature_name": "t2",
        "execution_mode": "api",
        "metadata": {"execution": {"base_url": envelope_server}},
        "scenarios": [
            {
                "scenario_id": "s1",
                "name": "get",
                "steps": [
                    {
                        "step_id": "s1_1",
                        "step_type": "when",
                        "text": "get",
                        "request": {"method": "GET", "url": "/x", "retries": 0},
                        "save_context": {"tid": "json.task_id"},
                        "assertions": [{"source": "status_code", "op": "eq", "expected": 200}],
                    },
                    {
                        "step_id": "s1_2",
                        "step_type": "then",
                        "text": "ctx",
                        "uses_context": ["tid"],
                        "assertions": [],
                    },
                ],
            }
        ],
    }
    result = execute_test_case_dsl(dsl)
    assert result["status"] == "passed"
    step2 = result["scenario_results"][0]["steps"][1]
    assert step2["status"] == "passed"


