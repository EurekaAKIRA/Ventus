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


def _run_server(handler_cls):
    srv = HTTPServer(("127.0.0.1", 0), handler_cls)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)
    return srv, thread, port


def test_runner_retries_transient_502_then_passes():
    _extend_path()
    from api_runner.executor import execute_test_case_dsl

    class H(BaseHTTPRequestHandler):
        call_count = 0

        def do_GET(self) -> None:  # noqa: N802
            H.call_count += 1
            if H.call_count == 1:
                raw = json.dumps({"error": "temporary gateway issue"}).encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

            raw = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, fmt: str, *args) -> None:  # noqa: A003
            return

    srv, thread, port = _run_server(H)
    try:
        payload = {
            "dsl_version": "0.2.0",
            "task_id": "retry-502-pass",
            "task_name": "retry-502-pass",
            "feature_name": "retry-502-pass",
            "execution_mode": "api",
            "metadata": {"execution": {"base_url": f"http://127.0.0.1:{port}"}},
            "scenarios": [
                {
                    "scenario_id": "s1",
                    "name": "retry once",
                    "steps": [
                        {
                            "step_id": "s1_1",
                            "step_type": "when",
                            "text": "get unstable",
                            "request": {"method": "GET", "url": "/unstable", "retries": 1},
                            "assertions": [
                                {"source": "status_code", "op": "eq", "expected": 200},
                                {"source": "json.ok", "op": "eq", "expected": True},
                            ],
                        }
                    ],
                }
            ],
        }
        result = execute_test_case_dsl(payload)
        assert result["status"] == "passed", result
        assert H.call_count == 2
    finally:
        srv.shutdown()
        thread.join()


def test_runner_marks_repeated_502_as_upstream_error():
    _extend_path()
    from api_runner.executor import execute_test_case_dsl

    class H(BaseHTTPRequestHandler):
        call_count = 0

        def do_GET(self) -> None:  # noqa: N802
            H.call_count += 1
            raw = json.dumps({"error": "temporary gateway issue"}).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, fmt: str, *args) -> None:  # noqa: A003
            return

    srv, thread, port = _run_server(H)
    try:
        payload = {
            "dsl_version": "0.2.0",
            "task_id": "retry-502-fail",
            "task_name": "retry-502-fail",
            "feature_name": "retry-502-fail",
            "execution_mode": "api",
            "metadata": {"execution": {"base_url": f"http://127.0.0.1:{port}"}},
            "scenarios": [
                {
                    "scenario_id": "s1",
                    "name": "retry and fail",
                    "steps": [
                        {
                            "step_id": "s1_1",
                            "step_type": "when",
                            "text": "get unstable",
                            "request": {"method": "GET", "url": "/unstable", "retries": 1},
                            "assertions": [{"source": "status_code", "op": "eq", "expected": 200}],
                        }
                    ],
                }
            ],
        }
        result = execute_test_case_dsl(payload)
        assert result["status"] == "failed", result
        step = result["scenario_results"][0]["steps"][0]
        assert step["response_summary"]["error_category"] == "upstream_error"
        assert H.call_count == 2
    finally:
        srv.shutdown()
        thread.join()
