"""Standard backend API test case against a running server.

Usage:
  python platform/task-center/tests/backend_standard_case.py
  python platform/task-center/tests/backend_standard_case.py --source-path docs/project_requirements.md
  python platform/task-center/tests/backend_standard_case.py --api-base http://127.0.0.1:8001 --use-llm
"""

from __future__ import annotations

import argparse
import json
import uuid
import urllib.error
import urllib.request
from typing import Any


def _request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url=url,
        method=method,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code} - {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Run standard backend API test case")
    parser.add_argument("--api-base", default="http://127.0.0.1:8001", help="Task-center API base URL")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout seconds")
    parser.add_argument("--use-llm", action="store_true", help="Enable LLM enhancement in parse request")
    parser.add_argument("--model-profile", default="default", help="Model profile for parse request")
    parser.add_argument("--source-path", default="", help="Requirement document path for server-side loading")
    parser.add_argument("--source-type", default="text", help="Source type, e.g. text/markdown")
    parser.add_argument("--requirement-text", default="", help="Inline requirement text (optional)")
    args = parser.parse_args()

    base = args.api_base.rstrip("/")
    suffix = uuid.uuid4().hex[:8]
    task_name = f"backend_standard_{suffix}"
    requirement_text = args.requirement_text.strip() or (
        "用户登录后进入个人中心并看到昵称。"
        "系统应返回200，并在响应中包含nickname字段。"
    )
    source_path = args.source_path.strip()
    source_type = args.source_type.strip() or "text"

    print(f"[1/5] health check: {base}/health")
    status, payload = _request_json("GET", f"{base}/health", timeout=args.timeout)
    assert status == 200 and payload.get("success") is True

    print(f"[2/5] create task: {task_name}")
    status, payload = _request_json(
        "POST",
        f"{base}/api/tasks",
        payload={
            "task_name": task_name,
            "source_type": source_type,
            "requirement_text": requirement_text if not source_path else "",
            "source_path": source_path or None,
            "target_system": "http://127.0.0.1:8010",
            "environment": "test",
        },
        timeout=args.timeout,
    )
    assert status == 201 and payload.get("success") is True
    task_id = payload["data"]["task_id"]

    print("[3/5] parse task (standard enhancement options)")
    status, payload = _request_json(
        "POST",
        f"{base}/api/tasks/{task_id}/parse",
        payload={
            "use_llm": args.use_llm,
            "rag_enabled": True,
            "retrieval_top_k": 5,
            "rerank_enabled": False,
            "model_profile": args.model_profile,
        },
        timeout=args.timeout,
    )
    assert status == 200 and payload.get("success") is True
    parse_metadata = payload["data"].get("parse_metadata") or {}
    print(
        "    parse_mode={parse_mode}, llm_attempted={llm_attempted}, rag_used={rag_used}, model_profile={model_profile}".format(
            parse_mode=parse_metadata.get("parse_mode"),
            llm_attempted=parse_metadata.get("llm_attempted"),
            rag_used=parse_metadata.get("rag_used"),
            model_profile=parse_metadata.get("model_profile"),
        )
    )

    print("[4/5] fetch task detail")
    status, payload = _request_json("GET", f"{base}/api/tasks/{task_id}", timeout=args.timeout)
    assert status == 200 and payload.get("success") is True
    detail = payload.get("data") or {}
    assert detail.get("task_id") == task_id
    assert detail.get("parsed_requirement") is not None

    print("[5/5] archive task")
    status, payload = _request_json("DELETE", f"{base}/api/tasks/{task_id}", timeout=args.timeout)
    assert status == 200 and payload.get("success") is True

    print("backend standard case passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
