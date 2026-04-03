"""Edge case tests for the API runner."""

from __future__ import annotations

import json
import sys
import threading
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
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/text"):
            encoded = b"plain-text-response"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return

        if self.path.startswith("/items"):
            encoded = json.dumps({"items": [1, 2, 3]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return

        self.send_error(404)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> int:
    _extend_path()
    from api_runner import execute_test_case_dsl

    server = HTTPServer(("127.0.0.1", 8011), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        text_payload = {
            "dsl_version": "0.1.0",
            "task_id": "edge_text",
            "task_name": "edge_text",
            "feature_name": "edge_text",
            "execution_mode": "api",
            "metadata": {
                "execution": {
                    "base_url": "http://127.0.0.1:8011",
                    "default_headers": {"X-Edge-Test": "1"}
                }
            },
            "scenarios": [
                {
                    "scenario_id": "s1",
                    "name": "text response",
                    "steps": [
                        {
                            "step_id": "s1_01",
                            "step_type": "when",
                            "text": "get text",
                            "request": {"method": "GET", "url": "/text"},
                            "assertions": [
                                {"source": "body_text", "op": "contains", "expected": "plain-text"},
                                {"source": "body_text", "op": "matches", "expected": "response$"}
                            ]
                        }
                    ]
                }
            ]
        }
        items_payload = {
            "dsl_version": "0.1.0",
            "task_id": "edge_items",
            "task_name": "edge_items",
            "feature_name": "edge_items",
            "execution_mode": "api",
            "metadata": {
                "execution": {
                    "base_url": "http://127.0.0.1:8011"
                }
            },
            "scenarios": [
                {
                    "scenario_id": "s2",
                    "name": "items len",
                    "steps": [
                        {
                            "step_id": "s2_01",
                            "step_type": "when",
                            "text": "get items",
                            "request": {"method": "GET", "url": "/items"},
                            "assertions": [
                                {"source": "json.items", "op": "len_eq", "expected": 3},
                                {"source": "json.items[-1]", "op": "eq", "expected": 3},
                                {"source": "elapsed_ms", "op": "ge", "expected": 0}
                            ]
                        }
                    ]
                }
            ]
        }
        relative_items_payload = {
            "dsl_version": "0.1.0",
            "task_id": "edge_relative_items",
            "task_name": "edge_relative_items",
            "feature_name": "edge_relative_items",
            "execution_mode": "api",
            "metadata": {
                "execution": {
                    "base_url": "http://127.0.0.1:8011"
                }
            },
            "scenarios": [
                {
                    "scenario_id": "s2b",
                    "name": "items relative path",
                    "steps": [
                        {
                            "step_id": "s2b_01",
                            "step_type": "when",
                            "text": "get items relative",
                            "request": {"method": "GET", "url": "items"},
                            "assertions": [
                                {"source": "status_code", "op": "eq", "expected": 200},
                                {"source": "json.items", "op": "len_eq", "expected": 3},
                            ]
                        }
                    ]
                }
            ]
        }
        missing_context_payload = {
            "dsl_version": "0.1.0",
            "task_id": "edge_context",
            "task_name": "edge_context",
            "feature_name": "edge_context",
            "execution_mode": "api",
            "metadata": {
                "execution": {
                    "base_url": "http://127.0.0.1:8011"
                }
            },
            "scenarios": [
                {
                    "scenario_id": "s3",
                    "name": "missing context",
                    "steps": [
                        {
                            "step_id": "s3_01",
                            "step_type": "when",
                            "text": "needs token",
                            "uses_context": ["token"],
                            "request": {"method": "GET", "url": "/items"},
                            "assertions": []
                        }
                    ]
                }
            ]
        }
        network_failure_payload = {
            "dsl_version": "0.1.0",
            "task_id": "edge_network",
            "task_name": "edge_network",
            "feature_name": "edge_network",
            "execution_mode": "api",
            "scenarios": [
                {
                    "scenario_id": "s4",
                    "name": "network failure",
                    "steps": [
                        {
                            "step_id": "s4_01",
                            "step_type": "when",
                            "text": "bad url",
                            "request": {"method": "GET", "url": "http://127.0.0.1:65500/unreachable", "retries": 1, "timeout": 0.2},
                            "assertions": [
                                {"source": "status_code", "op": "eq", "expected": 0},
                                {"source": "error", "op": "exists"}
                            ]
                        }
                    ]
                }
            ]
        }
        seeded_context_payload = {
            "dsl_version": "0.2.0",
            "task_id": "edge_context_seed",
            "task_name": "edge_context_seed",
            "feature_name": "edge_context_seed",
            "execution_mode": "api",
            "metadata": {
                "execution": {
                    "base_url": "http://127.0.0.1:8011",
                    "context": {"task_id": "demo-task-id"},
                }
            },
            "scenarios": [
                {
                    "scenario_id": "s5",
                    "name": "seeded task id path",
                    "steps": [
                        {
                            "step_id": "s5_01",
                            "step_type": "when",
                            "text": "get task detail with seeded id",
                            "request": {"method": "GET", "url": "/items/{{task_id}}"},
                            "assertions": [{"source": "status_code", "op": "eq", "expected": 200}],
                        }
                    ],
                }
            ],
        }

        assert execute_test_case_dsl(text_payload)["status"] == "passed"
        items_result = execute_test_case_dsl(items_payload)
        assert items_result["status"] == "passed"
        relative_items_result = execute_test_case_dsl(relative_items_payload)
        assert relative_items_result["status"] == "passed"
        item_step = items_result["scenario_results"][0]["steps"][0]
        assert item_step["response_summary"]["body_size"] > 0
        missing_result = execute_test_case_dsl(missing_context_payload)
        assert missing_result["status"] == "failed"
        network_result = execute_test_case_dsl(network_failure_payload)
        assert network_result["status"] == "passed"
        network_step = network_result["scenario_results"][0]["steps"][0]
        assert network_step["response_summary"]["error_category"] in {"network_error", "timeout_error"}
        assert network_step["response_summary"]["parse_error"] == ""
        seeded_context_result = execute_test_case_dsl(seeded_context_payload)
        assert seeded_context_result["status"] == "passed"
        assert any(log["event"] == "assertions_evaluated" for log in items_result["logs"])
        print("api runner edge cases test passed")
        return 0
    finally:
        server.shutdown()
        thread.join()


if __name__ == "__main__":
    raise SystemExit(main())
