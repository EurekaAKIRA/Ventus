"""Minimal smoke test for the new platform pipeline."""

from __future__ import annotations

import sys
from pathlib import Path


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[3]
    additions = [
        root / "platform" / "shared" / "src",
        root / "platform" / "requirement-analysis" / "src",
        root / "platform" / "case-generation" / "src",
        root / "platform" / "result-analysis" / "src",
        root / "platform" / "task-center" / "src",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


def main() -> int:
    """Run a minimal end-to-end smoke test."""
    _extend_path()
    from task_center.pipeline import run_analysis_pipeline

    artifacts_dir = Path(__file__).resolve().parents[1] / "artifacts"
    result = run_analysis_pipeline(
        task_name="smoke_test",
        requirement_text="用户打开首页后应看到搜索框和标题",
        artifacts_base_dir=str(artifacts_dir),
    )

    assert result["task_context"]["task_name"] == "smoke_test"
    assert result["scenarios"], "未生成任何场景"
    assert result["validation_report"]["passed"] is True, "最小 feature 校验未通过"
    assert result["feature_text"].startswith("Feature: smoke_test")

    print("smoke test passed")
    print("scenario_count =", len(result["scenarios"]))
    print("feature_name =", result["validation_report"]["feature_name"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
