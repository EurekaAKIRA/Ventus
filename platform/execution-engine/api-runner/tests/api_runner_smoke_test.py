"""Smoke test for the real HTTP-capable API runner."""

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
    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/session":
            self.send_error(404)
            return
        if self.headers.get("X-Test-Client") != "platform-api-runner":
            self._send_json(400, {"error": "missing-client-header"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self._send_json(200, {"token": "token-123", "user": payload.get("name", "unknown")})

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/profile":
            self.send_error(404)
            return
        auth = self.headers.get("Authorization")
        if auth != "Bearer token-123":
            self._send_json(401, {"error": "unauthorized"})
            return
        self._send_json(200, {"user": "demo-user", "roles": ["admin", "editor"]})

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

    server = HTTPServer(("127.0.0.1", 8010), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        sample_path = Path(__file__).resolve().parents[1] / "examples" / "sample_test_case_dsl.json"
        payload = json.loads(sample_path.read_text(encoding="utf-8"))
        result = execute_test_case_dsl(payload)
        assert result["status"] == "passed"
        assert result["metrics"]["scenario_count"] == 1
        assert result["metrics"]["step_count"] == 2
        assert result["metrics"]["avg_elapsed_ms"] >= 0
        print("api runner smoke test passed")
        return 0
    finally:
        server.shutdown()
        thread.join()


if __name__ == "__main__":
    raise SystemExit(main())
