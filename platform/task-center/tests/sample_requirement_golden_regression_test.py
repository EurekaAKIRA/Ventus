"""Golden regression for sample requirement parse -> scenarios -> DSL."""

from __future__ import annotations

import sys
from pathlib import Path


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[3]
    additions = [
        root / "platform" / "shared" / "src",
        root / "platform" / "requirement-analysis" / "src",
        root / "platform" / "case-generation" / "src",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


_extend_path()

from case_generation import build_scenarios, build_test_case_dsl
from platform_shared.models import ScenarioModel, TaskContext
from requirement_analysis.service import AnalysisParseOptions, parse_requirement_bundle


def test_sample_requirement_golden_regression() -> None:
    root = Path(__file__).resolve().parents[3]
    sample_path = root / "docs" / "sample_requirement.md"
    requirement_text = sample_path.read_text(encoding="utf-8")

    bundle = parse_requirement_bundle(
        requirement_text=requirement_text,
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=False,
            retrieval_top_k=5,
            rerank_enabled=False,
        ),
    )
    parsed = bundle["parsed_requirement"]
    scenarios = [ScenarioModel(**item) for item in build_scenarios(parsed)]
    dsl = build_test_case_dsl(
        TaskContext(task_id="golden_task", task_name="golden", source_type="text"),
        scenarios,
        parsed_requirement=parsed,
    )

    endpoint_pairs = [(item["method"], item["path"], item.get("description", "")) for item in parsed["api_endpoints"]]
    assert ("POST", "/api/auth/login", "用户登录") in endpoint_pairs
    assert ("GET", "/api/user/profile", "获取个人中心") in endpoint_pairs
    assert ("PUT", "/api/user/profile", "修改昵称") in endpoint_pairs

    assert len(scenarios) >= 3
    assert any("POST /api/auth/login" in step["text"] for s in scenarios for step in s.steps if step["type"] in {"when", "and"})
    assert any("GET /api/user/profile" in step["text"] for s in scenarios for step in s.steps if step["type"] in {"when", "and"})
    assert any("PUT /api/user/profile" in step["text"] for s in scenarios for step in s.steps if step["type"] in {"when", "and"})

    dsl_steps = [step for scenario in dsl["scenarios"] for step in scenario["steps"]]
    login_steps = [step for step in dsl_steps if step.get("request", {}).get("url") == "/api/auth/login"]
    assert login_steps, "expected login request in DSL"
    assert login_steps[0]["request"].get("json", {}) == {"username": "demo_user", "password": "demo_pass"}

    expectation_status_steps = [step for step in dsl_steps if "返回 200 并刷新页面" in step.get("text", "")]
    assert expectation_status_steps
    assert expectation_status_steps[0]["request"] == {}
