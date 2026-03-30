"""Smoke tests for the minimal local cloud-load runner."""

from __future__ import annotations

import json
import importlib.util
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
        root / "platform" / "execution-engine" / "cloud-load-runner" / "src",
        root / "platform" / "execution-engine" / "core" / "src",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/load":
            self.send_error(404)
            return
        encoded = json.dumps({"ok": True, "path": self.path}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def _build_payload(port: int) -> dict:
    return {
        "dsl_version": "0.2.0",
        "task_id": "cloud_load_demo",
        "task_name": "cloud_load_demo",
        "feature_name": "cloud_load_demo",
        "execution_mode": "cloud-load",
        "metadata": {
            "execution": {
                "base_url": f"http://127.0.0.1:{port}",
                "default_headers": {"X-Test-Client": "platform-cloud-load-runner"},
            }
        },
        "scenarios": [
            {
                "scenario_id": "load_01",
                "name": "ping load",
                "steps": [
                    {
                        "step_id": "load_01_step_01",
                        "step_type": "when",
                        "text": "load /load endpoint",
                        "request": {"method": "GET", "url": "/load"},
                        "load_profile": {"concurrency": 4, "total_requests": 12},
                        "assertions": [
                            {"source": "status_code", "op": "eq", "expected": 200},
                            {"source": "json.ok", "op": "eq", "expected": True},
                        ],
                    }
                ],
            }
        ],
    }


def main() -> int:
    _extend_path()
    from cloud_load_runner import execute_load_test_case_dsl

    runtime_path = (
        Path(__file__).resolve().parents[2]
        / "core"
        / "src"
        / "execution_engine_core"
        / "dsl_runtime.py"
    )
    spec = importlib.util.spec_from_file_location("cloud_load_dsl_runtime", runtime_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run_dsl = module.run_dsl

    server = HTTPServer(("127.0.0.1", 8013), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)
    try:
        payload = _build_payload(8013)
        result = execute_load_test_case_dsl(payload)
        assert result["executor"] == "cloud-load-runner"
        assert result["status"] == "passed"
        assert result["metrics"]["total_requests"] == 12
        assert result["metrics"]["success_rate"] == 100.0
        assert result["metrics"]["avg_elapsed_ms"] >= 0
        assert result["metrics"]["max_elapsed_ms"] >= result["metrics"]["avg_elapsed_ms"]
        assert result["metrics"]["throughput"] > 0
        step_result = result["scenario_results"][0]["steps"][0]
        assert step_result["load_profile"]["concurrency"] == 4
        assert step_result["request_count"] == 12
        assert step_result["response"]["status_codes"] == [200]

        duration_payload = _build_payload(8013)
        duration_payload["task_id"] = "cloud_load_duration_demo"
        duration_payload["scenarios"][0]["steps"][0]["load_profile"] = {
            "concurrency": 2,
            "duration_seconds": 0.2,
        }
        duration_result = run_dsl(duration_payload)
        assert duration_result["executor"] == "cloud-load-runner"
        assert duration_result["metrics"]["total_requests"] > 0
        assert duration_result["metrics"]["throughput"] > 0
        print("cloud load runner smoke test passed")
        return 0
    finally:
        server.shutdown()
        thread.join()


if __name__ == "__main__":
    raise SystemExit(main())
