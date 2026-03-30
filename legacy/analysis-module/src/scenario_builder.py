"""Scenario construction helpers."""

from __future__ import annotations

from .models import ScenarioModel, ScenarioStep


def _normalize_preconditions(parsed_requirement: dict) -> list[str]:
    return parsed_requirement.get("preconditions") or ["用户已进入需求对应页面或流程入口"]


def _priority_from_text(text: str) -> str:
    if any(keyword in text for keyword in ("登录", "支付", "提交", "下单", "创建")):
        return "P0"
    if any(keyword in text for keyword in ("显示", "搜索", "查看", "打开")):
        return "P1"
    return "P2"


def _build_scenario(
    scenario_index: int,
    action: str,
    expected_results: list[str],
    parsed_requirement: dict,
) -> dict:
    preconditions = _normalize_preconditions(parsed_requirement)
    steps = [ScenarioStep(type="given", text=preconditions[0]), ScenarioStep(type="when", text=action)]
    if expected_results:
        steps.append(ScenarioStep(type="then", text=expected_results[0]))
        for extra_expectation in expected_results[1:3]:
            steps.append(ScenarioStep(type="and", text=extra_expectation))
    else:
        steps.append(ScenarioStep(type="then", text="系统返回符合需求的可观察结果"))

    scenario = ScenarioModel(
        scenario_id=f"scenario_{scenario_index:03d}",
        name=action[:80],
        goal=parsed_requirement.get("objective", action),
        preconditions=preconditions,
        steps=steps,
        assertions=expected_results or ["系统返回符合需求的可观察结果"],
        source_chunks=parsed_requirement.get("source_chunks", []),
        priority=_priority_from_text(action),
    )
    return scenario.to_dict()


def build_scenarios(parsed_requirement: dict, use_llm: bool = False) -> list[dict]:
    """Build scenario list from parsed requirement."""
    actions = parsed_requirement.get("actions") or [parsed_requirement.get("objective", "执行核心业务动作")]
    expectations = parsed_requirement.get("expected_results") or ["系统返回符合需求的可观察结果"]
    scenarios: list[dict] = []

    for index, action in enumerate(actions[:5], start=1):
        if len(actions) == 1:
            scenario_expectations = expectations
        else:
            scenario_expectations = [expectations[min(index - 1, len(expectations) - 1)]]
        scenarios.append(_build_scenario(index, action, scenario_expectations, parsed_requirement))

    if use_llm:
        parsed_requirement.setdefault("ambiguities", []).append("LLM 场景增强尚未接入，本次使用规则拆分结果")

    return scenarios
