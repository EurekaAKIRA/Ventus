"""Scenario construction helpers with API dependency grouping."""

from __future__ import annotations

import re

from platform_shared.models import ScenarioModel, ScenarioStep


def _normalize_preconditions(parsed_requirement: dict) -> list[str]:
    return parsed_requirement.get("preconditions") or ["从有效的 API 入口开始执行"]


def _priority_from_text(text: str) -> str:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("login", "pay", "submit", "create", "delete", "登录", "鉴权", "创建", "删除")):
        return "P0"
    if any(keyword in lowered for keyword in ("display", "search", "view", "query", "查看", "查询")):
        return "P1"
    return "P2"


def _is_auth_action(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ("login", "auth", "token", "bearer", "session", "登录", "鉴权", "会话"))


def _is_create_action(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ("create", "submit", "add", "register", "post", "创建", "新增", "提交"))


def _depends_on_previous(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ("previous", "prior", "token", "session", "id", "detail", "profile", "上一步", "返回值", "详情"))


def _build_scenario(
    scenario_index: int,
    actions: list[str],
    expected_results: list[str],
    parsed_requirement: dict,
    goal: str | None = None,
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
        goal=goal or parsed_requirement.get("objective", primary_action),
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
        if lowered_method and lowered_method in lowered_action and any(segment in lowered_action for segment in path_segments):
            return action

    if method and path:
        return f"调用 {method} {path}"
    if path:
        return f"调用接口 {path}"
    return actions[0] if actions else "执行核心业务动作"


_COMMON_ENDPOINT_SEGMENTS = {"api", "task", "tasks", "task_id", "{task_id}", "id", "data", "history"}


def _extract_significant_path_segments(path: str) -> list[str]:
    segments: list[str] = []
    for segment in str(path or "").lower().split("/"):
        normalized = segment.strip("{} ").strip()
        if not normalized or normalized in _COMMON_ENDPOINT_SEGMENTS:
            continue
        segments.append(normalized)
    return segments


def _contains_explicit_endpoint_reference(text: str, method: str, path: str) -> bool:
    lowered = text.lower()
    method_lower = str(method or "").lower()
    path_lower = str(path or "").lower().rstrip("/")
    if not path_lower:
        return False
    if method_lower:
        needle = f"{method_lower} {path_lower}"
        search_from = 0
        while True:
            pos = lowered.find(needle, search_from)
            if pos < 0:
                break
            end = pos + len(needle)
            if lowered[end : end + 1] != "/":
                return True
            search_from = pos + 1
    search_from = 0
    while True:
        pos = lowered.find(path_lower, search_from)
        if pos < 0:
            return False
        end = pos + len(path_lower)
        if lowered[end : end + 1] != "/":
            return True
        search_from = pos + 1


def _is_generic_expectation_text(text: str) -> bool:
    lowered = text.lower()
    generic_hints = (
        "统一使用如下响应结构",
        "不应把任务详情查询接口当作列表接口",
        "不应假设存在",
        "联调和断言设计",
        "响应结构",
        "主链路联调需求说明",
        "当前实现对齐版",
    )
    return any(hint in lowered for hint in generic_hints)


def _select_expectations_for_endpoint(endpoint: dict, expectations: list[str]) -> list[str]:
    if not expectations:
        return ["系统返回符合需求的可观察结果"]
    path = str(endpoint.get("path", "")).lower()
    method = str(endpoint.get("method", "")).upper()
    path_segments = _extract_significant_path_segments(path)
    matched = []
    for expectation in expectations:
        lowered_expectation = expectation.lower()
        if _is_generic_expectation_text(expectation):
            continue
        if _contains_explicit_endpoint_reference(expectation, method, path):
            matched.append(expectation)
            continue
        if path_segments and any(re.search(rf"\b{re.escape(segment)}\b", lowered_expectation) for segment in path_segments):
            matched.append(expectation)
    return matched[:2]


def _build_goal_for_endpoint(endpoint: dict, action: str, parsed_requirement: dict) -> str:
    method = str(endpoint.get("method", "")).upper().strip()
    path = str(endpoint.get("path", "")).strip()
    description = str(endpoint.get("description", "")).strip()
    if description and not description.startswith("/") and not description.startswith("###") and description != "**Request:**":
        return description
    if method and path:
        return f"{method} {path}"
    if path:
        return path
    return parsed_requirement.get("objective", action)


def _is_meta_action(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return True
    return (
        lowered.startswith("scenario:")
        or lowered.startswith("step ")
        or lowered.startswith("request:**")
        or lowered.startswith("expected:**")
        or lowered.startswith("统一目标：")
    )


def _filter_actions(actions: list[str]) -> list[str]:
    return [action for action in actions if not _is_meta_action(action)]


def _endpoint_requires_context(endpoint: dict) -> bool:
    depends_on = endpoint.get("depends_on") or []
    return bool(depends_on)


def _build_endpoint_scenarios(parsed_requirement: dict, actions: list[str], expectations: list[str]) -> list[dict]:
    endpoints = [endpoint for endpoint in (parsed_requirement.get("api_endpoints") or []) if endpoint.get("path")]
    scenarios: list[dict] = []
    for index, endpoint in enumerate(endpoints[:25], start=1):
        if _endpoint_requires_context(endpoint):
            continue
        endpoint_action = _build_action_for_endpoint(endpoint, actions)
        endpoint_expectations = _select_expectations_for_endpoint(endpoint, expectations)
        endpoint_goal = _build_goal_for_endpoint(endpoint, endpoint_action, parsed_requirement)
        scenarios.append(_build_scenario(index, [endpoint_action], endpoint_expectations, parsed_requirement, goal=endpoint_goal))
    return scenarios


def _build_dependency_flow_scenarios(
    parsed_requirement: dict,
    actions: list[str],
    expectations: list[str],
    start_index: int,
) -> list[dict]:
    endpoints = [endpoint for endpoint in (parsed_requirement.get("api_endpoints") or []) if endpoint.get("path")]
    if len(endpoints) < 2 or not any(_endpoint_requires_context(endpoint) for endpoint in endpoints):
        return []
    endpoints = sorted(endpoints, key=_endpoint_flow_rank)

    preconditions = _normalize_preconditions(parsed_requirement)
    steps: list[ScenarioStep] = [ScenarioStep(type="given", text=preconditions[0])]
    for step_index, endpoint in enumerate(endpoints[:8]):
        action_text = _build_action_for_endpoint(endpoint, actions)
        steps.append(ScenarioStep(type="when" if step_index == 0 else "and", text=action_text))

    scenario = ScenarioModel(
        scenario_id=f"scenario_{start_index:03d}",
        name=" -> ".join(_build_action_for_endpoint(endpoint, actions) for endpoint in endpoints[:4])[:80],
        goal=parsed_requirement.get("objective", "dependent api flow"),
        preconditions=preconditions,
        steps=steps + [ScenarioStep(type="then", text=(expectations[0] if expectations else "System returns an observable result"))],
        assertions=expectations[:2] or ["System returns an observable result"],
        source_chunks=parsed_requirement.get("source_chunks", []),
        priority="P0",
    )
    return [scenario.to_dict()]


def _endpoint_flow_rank(endpoint: dict) -> tuple[int, str]:
    method = str(endpoint.get("method", "")).upper().strip()
    path = str(endpoint.get("path", "")).lower()
    if "/auth" in path or "/login" in path:
        return (0, path)
    if method == "POST" and not endpoint.get("depends_on"):
        return (1, path)
    if method == "GET":
        return (2, path)
    if method in {"PUT", "PATCH"}:
        return (3, path)
    if method == "DELETE":
        return (4, path)
    return (5, path)


def _is_narrative_action(text: str) -> bool:
    lowered = text.lower()
    if re.match(r"^调用\s+(get|post|put|patch|delete)\s+/", lowered):
        return False
    narrative_keywords = (
        "主链路",
        "流程",
        "用户",
        "前端",
        "页面",
        "完成",
        "确认",
        "workflow",
        "flow",
        "journey",
        "scenario",
        "process",
    )
    return any(keyword in lowered for keyword in narrative_keywords)


def _build_narrative_scenarios(
    parsed_requirement: dict,
    actions: list[str],
    expectations: list[str],
    start_index: int,
) -> list[dict]:
    narrative_actions = [action for action in actions if _is_narrative_action(action)]
    if not narrative_actions:
        return []
    working_actions = list(actions[:8]) if len(narrative_actions) < len(actions) else narrative_actions[:8]
    grouped = _group_actions(working_actions)
    scenarios: list[dict] = []
    for offset, action_group in enumerate(grouped[:5]):
        idx = start_index + offset
        scenario_expectations = expectations if len(grouped) == 1 else [expectations[min(offset, len(expectations) - 1)]]
        scenarios.append(_build_scenario(idx, action_group, scenario_expectations, parsed_requirement))
    return scenarios


def build_scenarios(parsed_requirement: dict, use_llm: bool = False) -> list[dict]:
    actions = _filter_actions(parsed_requirement.get("actions") or [parsed_requirement.get("objective", "Execute core action")])
    expectations = parsed_requirement.get("expected_results") or ["System returns an observable result"]

    endpoint_scenarios = _build_endpoint_scenarios(parsed_requirement, actions, expectations)
    dependency_scenarios = _build_dependency_flow_scenarios(parsed_requirement, actions, expectations, len(endpoint_scenarios) + 1)
    narrative_start = len(endpoint_scenarios) + len(dependency_scenarios) + 1
    narrative_scenarios = _build_narrative_scenarios(parsed_requirement, actions, expectations, narrative_start)

    combined = endpoint_scenarios + dependency_scenarios + narrative_scenarios
    if combined:
        return combined

    scenarios: list[dict] = []
    grouped_actions = _group_actions(actions[:6])
    for index, action_group in enumerate(grouped_actions[:5], start=1):
        scenario_expectations = expectations if len(grouped_actions) == 1 else [expectations[min(index - 1, len(expectations) - 1)]]
        scenarios.append(_build_scenario(index, action_group, scenario_expectations, parsed_requirement))

    if use_llm:
        parsed_requirement.setdefault("ambiguities", []).append("LLM scenario enhancement is not wired in yet.")

    return scenarios
