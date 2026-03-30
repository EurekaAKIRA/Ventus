"""Scenario construction helpers with API dependency grouping."""

from __future__ import annotations

from platform_shared.models import ScenarioModel, ScenarioStep


def _normalize_preconditions(parsed_requirement: dict) -> list[str]:
    return parsed_requirement.get("preconditions") or ["Start from a valid API entry point"]


def _priority_from_text(text: str) -> str:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("login", "pay", "submit", "create", "delete", "登录", "支付", "提交", "创建")):
        return "P0"
    if any(keyword in lowered for keyword in ("display", "search", "view", "query", "查看", "查询", "搜索")):
        return "P1"
    return "P2"


def _is_auth_action(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ("login", "auth", "token", "bearer", "session", "登录", "鉴权", "会话"))


def _is_create_action(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ("create", "submit", "add", "register", "post", "创建", "新增", "提交", "下单"))


def _depends_on_previous(text: str) -> bool:
    lowered = text.lower()
    return any(
        keyword in lowered
        for keyword in ("previous", "prior", "token", "session", "id", "detail", "profile", "上一步", "返回值", "详情")
    )


def _build_scenario(
    scenario_index: int,
    actions: list[str],
    expected_results: list[str],
    parsed_requirement: dict,
) -> dict:
    preconditions = _normalize_preconditions(parsed_requirement)
    primary_action = actions[0]
    steps = [ScenarioStep(type="given", text=preconditions[0]), ScenarioStep(type="when", text=primary_action)]
    for chained_action in actions[1:]:
        steps.append(ScenarioStep(type="and", text=chained_action))
    if expected_results:
        steps.append(ScenarioStep(type="then", text=expected_results[0]))
        for extra_expectation in expected_results[1:3]:
            steps.append(ScenarioStep(type="and", text=extra_expectation))
    else:
        steps.append(ScenarioStep(type="then", text="System returns an observable result aligned with the requirement"))

    scenario = ScenarioModel(
        scenario_id=f"scenario_{scenario_index:03d}",
        name=" -> ".join(actions)[:80],
        goal=parsed_requirement.get("objective", primary_action),
        preconditions=preconditions,
        steps=steps,
        assertions=expected_results or ["System returns an observable result aligned with the requirement"],
        source_chunks=parsed_requirement.get("source_chunks", []),
        priority=_priority_from_text(" ".join(actions)),
    )
    return scenario.to_dict()


def _group_actions(actions: list[str]) -> list[list[str]]:
    grouped_actions: list[list[str]] = []
    index = 0
    while index < len(actions):
        current = actions[index]
        if index + 1 < len(actions):
            next_action = actions[index + 1]
            if _is_auth_action(current):
                grouped_actions.append([current, next_action])
                index += 2
                continue
            if _is_create_action(current) and _depends_on_previous(next_action):
                grouped_actions.append([current, next_action])
                index += 2
                continue
        grouped_actions.append([current])
        index += 1
    return grouped_actions


def build_scenarios(parsed_requirement: dict, use_llm: bool = False) -> list[dict]:
    """Build scenario list from parsed requirement."""
    actions = parsed_requirement.get("actions") or [parsed_requirement.get("objective", "Execute the core business action")]
    expectations = parsed_requirement.get("expected_results") or ["System returns an observable result aligned with the requirement"]
    scenarios: list[dict] = []

    grouped_actions = _group_actions(actions[:6])
    for index, action_group in enumerate(grouped_actions[:5], start=1):
        if len(grouped_actions) == 1:
            scenario_expectations = expectations
        else:
            scenario_expectations = [expectations[min(index - 1, len(expectations) - 1)]]
        scenarios.append(_build_scenario(index, action_group, scenario_expectations, parsed_requirement))

    if use_llm:
        parsed_requirement.setdefault("ambiguities", []).append("LLM enhancement is not wired yet; current scenarios come from rule-based grouping")

    return scenarios
