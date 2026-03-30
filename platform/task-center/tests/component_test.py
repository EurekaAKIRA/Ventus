"""Component-level checks for the new platform analysis pipeline."""

from __future__ import annotations

import importlib
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
    _extend_path()
    parser = importlib.import_module("requirement_analysis.document_parser")
    requirement_parser = importlib.import_module("requirement_analysis.requirement_parser")
    scenario_builder = importlib.import_module("case_generation.scenario_builder")

    sample_text = """# 用户中心
用户登录后进入用户中心。

- 页面应显示昵称。
- 页面应显示最近订单入口。

用户点击最近订单后，应跳转到订单列表页。"""
    parsed_document = parser.parse_document(sample_text)
    assert parsed_document["outline"], "未提取到文档结构"
    assert parsed_document["candidate_test_points"], "未提取到候选测试点"

    parsed_requirement = requirement_parser.parse_requirement(
        "用户登录后进入用户中心，点击最近订单后应跳转到订单列表页，并显示最近订单入口。",
        retrieved_context=[],
    )
    assert parsed_requirement["actions"], "未提取到动作"
    assert parsed_requirement["expected_results"], "未提取到断言"

    scenarios = scenario_builder.build_scenarios(parsed_requirement)
    assert scenarios, "未构建出场景"
    assert scenarios[0]["steps"][0]["type"] == "given"
    assert any(step["type"] == "then" for step in scenarios[0]["steps"])

    print("component test passed")
    print("scenario_count =", len(scenarios))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
