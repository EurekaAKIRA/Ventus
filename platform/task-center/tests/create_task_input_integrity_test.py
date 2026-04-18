"""Regression tests for task creation input integrity handling."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[3]
    legacy = root / "legacy"
    additions = [
        root / "platform" / "shared" / "src",
        root / "platform" / "requirement-analysis" / "src",
        root / "platform" / "case-generation" / "src",
        root / "platform" / "result-analysis" / "src",
        root / "platform" / "execution-engine" / "api-runner" / "src",
        root / "platform" / "execution-engine" / "core" / "src",
        root / "platform" / "task-center" / "src",
        legacy / "lavague-core",
        legacy / "lavague-integrations" / "drivers" / "lavague-drivers-selenium",
        legacy / "lavague-integrations" / "drivers" / "lavague-drivers-playwright",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


def main() -> int:
    _extend_path()
    import task_center.api as api_module
    from task_center.registry import TaskRegistry

    with tempfile.TemporaryDirectory() as temp_dir:
        api_module.registry = TaskRegistry(temp_dir)
        client = TestClient(api_module.app)

        long_requirement = (
            "# API Requirement\n\n"
            "## Overview\n\n"
            + ("用户登录后查看个人中心，系统返回 200 并展示昵称、订单入口与账户摘要。\n" * 80)
        )
        ok_resp = client.post(
            "/api/tasks",
            json={
                "task_name": "long_inline_requirement",
                "source_type": "text",
                "requirement_text": long_requirement,
                "environment": "test",
            },
        )
        assert ok_resp.status_code == 201
        ok_task_id = ok_resp.json()["data"]["task_id"]
        saved = api_module.registry.get(ok_task_id)
        assert saved is not None
        assert saved.requirement_text == long_requirement
        assert len(saved.requirement_text) > 1024

        file_create_resp = client.post(
            "/api/tasks",
            json={
                "task_name": "",
                "source_type": "file",
                "source_path": r"D:\docs\restful_booker_e2e2_plus.md",
                "requirement_text": "",
                "environment": "test",
            },
        )
        assert file_create_resp.status_code == 201
        file_payload = file_create_resp.json()["data"]
        assert file_payload["task_context"]["task_name"] == "restful_booker_e2e2_plus"
        file_task_id = file_payload["task_id"]
        file_saved = api_module.registry.get(file_task_id)
        assert file_saved is not None
        assert file_saved.task_name == "restful_booker_e2e2_plus"

        truncated_requirement = (
            "# Restful Booker\n\n"
            "## Step 1\n\n"
            "**Request:** `POST /booking`\n\n"
            "**Body:**\n\n"
            "```json\n"
            "{\n"
            '  "firstname": "Jim",\n'
            '  "bookingdates": {\n'
            '    "checkin": "2026-0'
        )
        padded_requirement = truncated_requirement + ("x" * (1024 - len(truncated_requirement)))
        bad_resp = client.post(
            "/api/tasks",
            json={
                "task_name": "truncated_inline_requirement",
                "source_type": "text",
                "requirement_text": padded_requirement,
                "environment": "test",
            },
        )
        assert bad_resp.status_code == 400
        payload = bad_resp.json()
        assert payload["success"] is False
        assert "疑似在上传前被截断" in payload["message"]
        assert "文本长度为 1024" in payload["message"]

    print("create task input integrity test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
