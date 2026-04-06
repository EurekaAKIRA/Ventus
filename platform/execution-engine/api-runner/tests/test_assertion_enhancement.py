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
        path = str(root / rel)
        if path not in sys.path:
            sys.path.insert(0, path)


@pytest.fixture()
def assertion_server():
    _extend_path()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/profile":
                payload = {"active": True, "items": [{"id": "item-001"}], "user": {"nickname": "demo"}}
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
                return
            self.send_error(404)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join()


def test_executor_supports_extended_assertion_ops(assertion_server):
    from api_runner.executor import execute_test_case_dsl

    dsl = {
        "dsl_version": "0.2.0",
        "task_id": "assertion_ops_demo",
        "task_name": "assertion_ops_demo",
        "feature_name": "assertion_ops_demo",
        "execution_mode": "api",
        "metadata": {"execution": {"base_url": assertion_server}},
        "scenarios": [
            {
                "scenario_id": "scenario_001",
                "name": "extended assertions",
                "steps": [
                    {
                        "step_id": "step_01",
                        "step_type": "when",
                        "text": "query profile",
                        "request": {"method": "GET", "url": "/profile"},
                        "assertions": [
                            {"assertion_id": "a1", "source": "status_code", "op": "in", "expected": [200, 204], "category": "status", "severity": "critical", "confidence": 0.99, "generated_by": "rules"},
                            {"assertion_id": "a2", "source": "json.active", "op": "is_true", "category": "field_value", "severity": "major", "confidence": 0.9, "generated_by": "llm"},
                            {"assertion_id": "a3", "source": "json.items", "op": "len_ge", "expected": 1, "category": "collection", "severity": "major", "confidence": 0.88, "generated_by": "llm_repair"},
                            {"assertion_id": "a4", "source": "json.missing", "op": "not_exists", "category": "field_presence", "severity": "minor", "confidence": 0.7, "generated_by": "rules", "fallback_used": True},
                            {"assertion_id": "a5", "source": "json.user.nickname", "op": "not_in", "expected": ["other"], "category": "field_value", "severity": "major", "confidence": 0.8, "generated_by": "rules"},
                        ],
                    }
                ],
            }
        ],
    }

    result = execute_test_case_dsl(dsl)
    assert result["status"] == "passed"
    step = result["scenario_results"][0]["steps"][0]
    assert step["assertion_summary"]["category_counts"]["status"] == 1
    assert step["assertion_summary"]["generated_by_counts"]["llm"] == 1
    assert step["assertion_summary"]["generated_by_counts"]["llm_repair"] == 1
    assert step["assertion_summary"]["fallback_count"] == 1
    assert result["metrics"]["assertion_generated_by_counts"]["llm_repair"] == 1


def test_executor_failure_details_include_assertion_metadata(assertion_server):
    from api_runner.executor import execute_test_case_dsl

    dsl = {
        "dsl_version": "0.2.0",
        "task_id": "assertion_failure_demo",
        "task_name": "assertion_failure_demo",
        "feature_name": "assertion_failure_demo",
        "execution_mode": "api",
        "metadata": {"execution": {"base_url": assertion_server}},
        "scenarios": [
            {
                "scenario_id": "scenario_001",
                "name": "failing assertion",
                "steps": [
                    {
                        "step_id": "step_01",
                        "step_type": "when",
                        "text": "query profile",
                        "request": {"method": "GET", "url": "/profile"},
                        "assertions": [
                            {"assertion_id": "nickname_check", "source": "json.user.nickname", "op": "eq", "expected": "other", "category": "field_value", "severity": "major", "confidence": 0.84, "generated_by": "llm"},
                        ],
                    }
                ],
            }
        ],
    }

    result = execute_test_case_dsl(dsl)
    assert result["status"] == "failed"
    step = result["scenario_results"][0]["steps"][0]
    assert step["assertion_failures"][0]["assertion_id"] == "nickname_check"
    assert step["assertion_failures"][0]["generated_by"] == "llm"
    assert step["assertion_summary"]["failure_details"][0]["category"] == "field_value"


def test_executor_treats_empty_error_string_as_absent(assertion_server):
    from api_runner.executor import execute_test_case_dsl

    dsl = {
        "dsl_version": "0.2.0",
        "task_id": "assertion_error_absent_demo",
        "task_name": "assertion_error_absent_demo",
        "feature_name": "assertion_error_absent_demo",
        "execution_mode": "api",
        "metadata": {"execution": {"base_url": assertion_server}},
        "scenarios": [
            {
                "scenario_id": "scenario_001",
                "name": "empty error is absent",
                "steps": [
                    {
                        "step_id": "step_01",
                        "step_type": "when",
                        "text": "query profile",
                        "request": {"method": "GET", "url": "/profile"},
                        "assertions": [
                            {"assertion_id": "status_ok", "source": "status_code", "op": "eq", "expected": 200, "category": "status", "severity": "critical", "confidence": 0.99, "generated_by": "rules"},
                            {"assertion_id": "no_runtime_error", "source": "error", "op": "not_exists", "category": "business", "severity": "major", "confidence": 0.75, "generated_by": "rules"},
                        ],
                    }
                ],
            }
        ],
    }

    result = execute_test_case_dsl(dsl)
    assert result["status"] == "passed"
