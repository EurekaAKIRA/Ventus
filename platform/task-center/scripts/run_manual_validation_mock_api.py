"""Local mock API for manual validation from the task creation page.

Usage:
  python platform\task-center\scripts\run_manual_validation_mock_api.py --mode buggy --port 18080
  python platform\task-center\scripts\run_manual_validation_mock_api.py --mode healthy --port 18080
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def _read_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    raw = handler.rfile.read(length) if length else b"{}"
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    return handler.headers.get("Authorization") == "Bearer valid-token"


def _make_handler(mode: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/ping":
                _send_json(self, 200, {"status": "ok", "mode": mode})
                return

            if self.path == "/profile":
                if mode == "buggy":
                    _send_json(self, 401, {"error": "token rejected"})
                    return
                if not _authorized(self):
                    _send_json(self, 401, {"error": "unauthorized"})
                    return
                _send_json(self, 200, {"id": "user-1", "role": "admin"})
                return

            if self.path.startswith("/orders/"):
                if not _authorized(self):
                    _send_json(self, 401, {"error": "unauthorized"})
                    return
                status = "pending" if mode == "buggy" else "confirmed"
                _send_json(self, 200, {"id": self.path.rsplit("/", 1)[-1], "status": status, "item": "book"})
                return

            self.send_error(404)

        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/login":
                if mode == "buggy":
                    _send_json(self, 200, {"user": "demo-admin"})
                    return
                _send_json(self, 200, {"token": "valid-token", "user": "demo-admin"})
                return

            if self.path == "/orders":
                if not _authorized(self):
                    _send_json(self, 401, {"error": "unauthorized"})
                    return
                body = _read_body(self)
                order_id: str | int = 1001 if mode == "buggy" else "order-1001"
                status = "pending" if mode == "buggy" else "confirmed"
                _send_json(self, 201, {"id": order_id, "item": body.get("item", "book"), "status": status})
                return

            self.send_error(404)

        def do_DELETE(self) -> None:  # noqa: N802
            if self.path.startswith("/orders/"):
                if not _authorized(self):
                    _send_json(self, 401, {"error": "unauthorized"})
                    return
                if mode == "buggy":
                    _send_json(self, 500, {"error": "delete failed"})
                    return
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            self.send_error(404)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run manual validation mock API.")
    parser.add_argument("--mode", choices=["healthy", "buggy"], default="buggy")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), _make_handler(args.mode))
    print(f"manual validation mock api running: mode={args.mode} url=http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
