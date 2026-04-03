"""API tests for /api/analysis/parse and parse option priority."""

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

        response = client.post(
            "/api/analysis/parse",
            json={
                "requirement_text": "用户登录后进入个人中心并看到昵称",
                "use_llm": False,
                "rag_enabled": True,
                "retrieval_top_k": 3,
                "rerank_enabled": False,
                "model_profile": "low_cost",
            },
        )
        assert response.status_code == 200
        payload = response.json()["data"]
        metadata = payload["parse_metadata"]
        assert isinstance(metadata.get("llm_attempted"), bool)
        assert isinstance(metadata.get("llm_used"), bool)
        assert metadata["retrieval_top_k"] == 3
        assert metadata["rerank_enabled"] is False
        assert metadata["rag_used"] is True
        assert metadata["model_profile"] == "low_cost"
        assert metadata["document_char_count"] > 0
        assert metadata["chunk_count"] > 0
        assert metadata["processing_tier"] in {"realtime", "batch", "large_document"}
        assert "embedding_error_detail" in metadata["retrieval_metrics"]
        assert "performance" in metadata
        assert "retrieval_metrics" in metadata
        # request-level options should override module defaults
        assert metadata["parse_mode"] == "rules"

    print("analysis parse api test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
