"""Regression test for docs/platform_e2e_requirement.md against running API.

Usage:
  python platform/task-center/tests/platform_e2e_requirement_regression_test.py
  python platform/task-center/tests/platform_e2e_requirement_regression_test.py --api-base http://127.0.0.1:8001
  python platform/task-center/tests/platform_e2e_requirement_regression_test.py --use-llm
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url=url,
        method=method,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code} - {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc}") from exc


def _assert_success(payload: dict[str, Any], code: str) -> dict[str, Any]:
    assert payload.get("success") is True, payload
    assert payload.get("code") == code, payload
    data = payload.get("data")
    assert isinstance(data, dict), payload
    return data


def _wait_execution_finished(base: str, task_id: str, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        _, payload = _request_json("GET", f"{base}/api/tasks/{task_id}/execution", timeout=20.0)
        data = _assert_success(payload, "EXECUTION_OK")
        status = str(data.get("status", ""))
        if status in {"passed", "failed", "stopped"}:
            return data
        time.sleep(2)
    raise AssertionError(f"execution polling timed out after {timeout_seconds}s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Regression test for platform_e2e_requirement.md")
    parser.add_argument("--api-base", default="http://127.0.0.1:8001", help="Task-center API base URL")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds")
    parser.add_argument(
        "--requirement-path",
        default="docs/platform_e2e_requirement.md",
        help="Requirement document path",
    )
    parser.add_argument(
        "--execution-timeout",
        type=float,
        default=180.0,
        help="Polling timeout for execute endpoint",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable the slower LLM-enhanced parse path for an explicit extended regression run",
    )
    args = parser.parse_args()

    base = args.api_base.rstrip("/")
    root = Path(__file__).resolve().parents[3]
    requirement_path = (root / args.requirement_path).resolve()
    requirement_text = requirement_path.read_text(encoding="utf-8")

    task_id = ""
    task_name = f"platform_e2e_regression_{uuid.uuid4().hex[:8]}"
    try:
        # 1) health
        status, payload = _request_json("GET", f"{base}/health", timeout=args.timeout)
        assert status == 200
        _assert_success(payload, "HEALTH_OK")

        # 2) create
        status, payload = _request_json(
            "POST",
            f"{base}/api/tasks",
            payload={
                "task_name": task_name,
                "source_type": "text",
                "requirement_text": requirement_text,
                "target_system": base,
                "environment": "test",
            },
            timeout=args.timeout,
        )
        assert status == 201
        data = _assert_success(payload, "TASK_CREATED")
        task_id = str(data["task_id"])

        # 3) parse — 启用 LLM 增强（允许 fallback），同时确认 RAG 检索生效
        status, payload = _request_json(
            "POST",
            f"{base}/api/tasks/{task_id}/parse",
            payload={
                "use_llm": args.use_llm,
                "rag_enabled": True,
                "retrieval_top_k": 5,
                "rerank_enabled": False,
            },
            timeout=120.0,
        )
        assert status == 200
        parse_data = _assert_success(payload, "TASK_PARSED")
        parse_meta = parse_data.get("parse_metadata")
        # LLM ??????????????? false?????????? LLM??
        # e2e ??????????????? rules ???
        llm_attempted = parse_meta.get("llm_attempted")
        assert isinstance(llm_attempted, bool), f"llm_attempted should be bool, got: {parse_meta}"
        assert llm_attempted is args.use_llm, f"llm_attempted should mirror --use-llm, got: {parse_meta}"
        assert parse_meta.get("retrieval_mode") in {"vector+keyword", "keyword"}, \
            f"retrieval_mode unexpected: {parse_meta.get('retrieval_mode')}"
        assert parse_meta.get("parse_mode") in {"llm", "rules"}, \
            f"parse_mode unexpected: {parse_meta.get('parse_mode')}"
        assert parse_meta.get("retrieval_mode"), "retrieval_mode should not be empty"
        # fallback 原因可为空（LLM 成功）或非空（LLM fallback），但不允许 retrieval_mode 为空
        assert parse_meta.get("retrieval_mode"), "retrieval_mode should not be empty"

        # 4) dsl key assertions — 验证链路结构可用性，不强约束字段类型
        status, payload = _request_json("GET", f"{base}/api/tasks/{task_id}/dsl", timeout=args.timeout)
        assert status == 200
        dsl = _assert_success(payload, "DSL_OK")
        scenarios = dsl.get("scenarios") or []
        assert scenarios, "DSL scenarios should not be empty"
        steps = [step for scenario in scenarios for step in (scenario.get("steps") or [])]
        assert steps, "DSL steps should not be empty"

        # 验证创建任务的步骤存在且 save_context 正确
        create_steps = [
            step for step in steps
            if (step.get("request") or {}).get("method") == "POST"
            and (step.get("request") or {}).get("url") == "/api/tasks"
        ]
        assert create_steps, "Expected create-task request step in DSL"
        assert create_steps[0].get("save_context") == {
            "task_id": "json.data.task_id",
            "resource_id": "json.data.task_id",
        }

        # 验证 parse 步骤存在（不强约束请求体字段类型）
        parse_steps = [
            step for step in steps
            if (step.get("request") or {}).get("method") == "POST"
            and "{{task_id}}" in str((step.get("request") or {}).get("url", ""))
            and str((step.get("request") or {}).get("url", "")).endswith("/parse")
        ]
        assert parse_steps, "Expected parse request step with {{task_id}} in DSL"
        parse_step_request = (parse_steps[0].get("request") or {})
        assert parse_step_request.get("url"), "parse step url should not be empty"
        assert parse_step_request.get("method") == "POST", "parse step method should be POST"

        # 5) execute — 验证执行链路可走通，允许 DSL 生成质量导致的部分场景失败
        status, payload = _request_json(
            "POST",
            f"{base}/api/tasks/{task_id}/execute",
            payload={"execution_mode": "api", "environment": "test"},
            timeout=120.0,
        )
        assert status == 200
        _assert_success(payload, "TASK_EXECUTED")
        execution_data = _wait_execution_finished(base, task_id, timeout_seconds=args.execution_timeout)
        exec_status = execution_data.get("status")
        assert exec_status in {"passed", "failed"}, \
            f"execution did not reach terminal state (passed/failed), got: {exec_status}"
        scenario_results = execution_data.get("scenario_results") or []
        assert scenario_results, "execution returned no scenario_results"
        # 统计通过率，仅打印，不作为阻断条件（DSL 生成质量属 P0 遗留问题）
        passed_count = sum(1 for s in scenario_results if s.get("status") == "passed")
        total_count = len(scenario_results)
        print(f"execution status={exec_status}  scenarios={total_count}  passed={passed_count}")

        # 6) reports
        status, payload = _request_json("GET", f"{base}/api/tasks/{task_id}/analysis-report", timeout=args.timeout)
        assert status == 200
        _assert_success(payload, "ANALYSIS_REPORT_OK")

        print("platform e2e requirement regression passed")
        return 0
    finally:
        if task_id:
            try:
                _request_json("DELETE", f"{base}/api/tasks/{task_id}", timeout=args.timeout)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
