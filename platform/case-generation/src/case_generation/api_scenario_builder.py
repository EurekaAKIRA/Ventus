"""Scenario construction helpers with API dependency grouping."""

from __future__ import annotations

from platform_shared.models import ScenarioModel, ScenarioStep


def _normalize_preconditions(parsed_requirement: dict) -> list[str]:
    return parsed_requirement.get("preconditions") or ["从有效的 API 入口开始执行"]


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
        steps.append(ScenarioStep(type="then", text="系统返回符合需求的可观察结果"))

    scenario = ScenarioModel(
        scenario_id=f"scenario_{scenario_index:03d}",
        name=" -> ".join(actions)[:80],
        goal=parsed_requirement.get("objective", primary_action),
        preconditions=preconditions,
        steps=steps,
        assertions=expected_results or ["系统返回符合需求的可观察结果"],
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


def _build_action_for_endpoint(endpoint: dict, actions: list[str]) -> str:
    method = str(endpoint.get("method", "")).upper()
    path = str(endpoint.get("path", "")).strip()
    lowered_method = method.lower()
    lowered_path = path.lower()
    path_segments = [segment for segment in lowered_path.split("/") if segment]

    for action in actions:
        lowered_action = action.lower()
        if lowered_method and lowered_method in lowered_action and lowered_path and lowered_path in lowered_action:
            return action

    for action in actions:
        lowered_action = action.lower()
        if lowered_method and lowered_method in lowered_action:
            if any(segment in lowered_action for segment in path_segments):
                return action

    has_path_match = False
    for action in actions:
        lowered_action = action.lower()
        if lowered_path and lowered_path in lowered_action:
            has_path_match = True
            break
    if has_path_match and method and path:
        # Avoid mapping GET endpoint to a PUT action when path is shared.
        return f"调用 {method} {path}"

    for action in actions:
        lowered_action = action.lower()
        if any(segment in lowered_action for segment in path_segments):
            return action

    if method and path:
        return f"调用 {method} {path}"
    if path:
        return f"调用接口 {path}"
    return actions[0] if actions else "执行核心业务动作"


def _select_expectations_for_endpoint(endpoint: dict, expectations: list[str], scenario_index: int) -> list[str]:
    if not expectations:
        return ["系统返回符合需求的可观察结果"]
    path = str(endpoint.get("path", "")).lower()
    path_segments = [segment for segment in path.split("/") if segment]
    matched = []
    for expectation in expectations:
        lowered_expectation = expectation.lower()
        if path and path in lowered_expectation:
            matched.append(expectation)
            continue
        if any(segment in lowered_expectation for segment in path_segments):
            matched.append(expectation)
    if matched:
        return matched[:2]
    return [expectations[min(scenario_index - 1, len(expectations) - 1)]]


def _build_endpoint_scenarios(parsed_requirement: dict, actions: list[str], expectations: list[str]) -> list[dict]:
    endpoints = [endpoint for endpoint in (parsed_requirement.get("api_endpoints") or []) if endpoint.get("path")]
    if not endpoints:
        return []
    scenarios: list[dict] = []
    for index, endpoint in enumerate(endpoints[:8], start=1):
        endpoint_action = _build_action_for_endpoint(endpoint, actions)
        endpoint_expectations = _select_expectations_for_endpoint(endpoint, expectations, index)
        scenarios.append(_build_scenario(index, [endpoint_action], endpoint_expectations, parsed_requirement))
    return scenarios


def build_scenarios(parsed_requirement: dict, use_llm: bool = False) -> list[dict]:
    """Build scenario list from parsed requirement."""
    actions = parsed_requirement.get("actions") or [parsed_requirement.get("objective", "执行核心业务动作")]
    expectations = parsed_requirement.get("expected_results") or ["系统返回符合需求的可观察结果"]
    endpoint_scenarios = _build_endpoint_scenarios(parsed_requirement, actions, expectations)
    if endpoint_scenarios:
        return endpoint_scenarios

    scenarios: list[dict] = []

    grouped_actions = _group_actions(actions[:6])
    for index, action_group in enumerate(grouped_actions[:5], start=1):
        if len(grouped_actions) == 1:
            scenario_expectations = expectations
        else:
            scenario_expectations = [expectations[min(index - 1, len(expectations) - 1)]]
        scenarios.append(_build_scenario(index, action_group, scenario_expectations, parsed_requirement))

    if use_llm:
        parsed_requirement.setdefault("ambiguities", []).append("LLM 场景增强尚未接入，本次使用规则拆分结果")

    return scenarios
