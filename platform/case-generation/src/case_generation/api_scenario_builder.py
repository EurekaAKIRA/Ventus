"""Scenario construction helpers with API dependency grouping."""

from __future__ import annotations

import re

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


_COMMON_ENDPOINT_SEGMENTS = {
    "api",
    "task",
    "tasks",
    "task_id",
    "{task_id}",
    "id",
    "data",
    "history",
}


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
    path_lower = str(path or "").lower()
    return bool((method_lower and path_lower and f"{method_lower} {path_lower}" in lowered) or (path_lower and path_lower in lowered))


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


def _select_expectations_for_endpoint(endpoint: dict, expectations: list[str], scenario_index: int) -> list[str]:
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
    if matched:
        return matched[:2]
    return []


def _build_goal_for_endpoint(endpoint: dict, action: str, parsed_requirement: dict) -> str:
    method = str(endpoint.get("method", "")).upper().strip()
    path = str(endpoint.get("path", "")).strip()
    description = str(endpoint.get("description", "")).strip()
    if description and not description.startswith("/") and not description.startswith("###"):
        return description
    if method and path:
        return f"{method} {path}"
    if path:
        return path
    return parsed_requirement.get("objective", action)


_MAX_ENDPOINT_SCENARIOS = 25


def _group_endpoints_by_section(endpoints: list[dict]) -> dict[str, list[dict]]:
    """Group endpoints by their ``group`` field (falls back to first path segment)."""
    groups: dict[str, list[dict]] = {}
    for ep in endpoints:
        group = str(ep.get("group", "")).strip()
        if not group:
            parts = [s for s in str(ep.get("path", "")).strip("/").split("/") if s and not s.startswith("{")]
            group = parts[1] if len(parts) > 1 else (parts[0] if parts else "default")
        groups.setdefault(group, []).append(ep)
    return groups


def _build_endpoint_scenarios(parsed_requirement: dict, actions: list[str], expectations: list[str]) -> list[dict]:
    endpoints = [endpoint for endpoint in (parsed_requirement.get("api_endpoints") or []) if endpoint.get("path")]
    if not endpoints:
        return []
    scenarios: list[dict] = []
    for index, endpoint in enumerate(endpoints[:_MAX_ENDPOINT_SCENARIOS], start=1):
        endpoint_action = _build_action_for_endpoint(endpoint, actions)
        endpoint_expectations = _select_expectations_for_endpoint(endpoint, expectations, index)
        endpoint_goal = _build_goal_for_endpoint(endpoint, endpoint_action, parsed_requirement)
        scenarios.append(_build_scenario(index, [endpoint_action], endpoint_expectations, parsed_requirement, goal=endpoint_goal))
    return scenarios


def _path_is_child(parent: str, child: str) -> bool:
    """Return True if *child* path is a sub-resource of *parent* (e.g. /api/tasks → /api/tasks/{task_id}/parse)."""
    parent_norm = parent.rstrip("/")
    child_norm = child.rstrip("/")
    if not parent_norm or not child_norm:
        return False
    return child_norm.startswith(parent_norm + "/") and child_norm != parent_norm


def _detect_endpoint_chains(endpoints: list[dict]) -> list[list[dict]]:
    """Detect dependency chains among endpoints.

    A chain is formed when later endpoints' paths are sub-resources of earlier ones
    (e.g. POST /api/tasks → POST /api/tasks/{task_id}/parse → POST .../execute).
    """
    if len(endpoints) < 2:
        return []

    post_endpoints = [ep for ep in endpoints if str(ep.get("method", "")).upper() == "POST"]
    if len(post_endpoints) < 2:
        return []

    sorted_eps = sorted(post_endpoints, key=lambda ep: len(str(ep.get("path", ""))))

    chains: list[list[dict]] = []
    used: set[str] = set()

    for root in sorted_eps:
        root_path = str(root.get("path", "")).rstrip("/")
        if root_path in used:
            continue
        chain = [root]
        for candidate in sorted_eps:
            cand_path = str(candidate.get("path", "")).rstrip("/")
            if cand_path == root_path:
                continue
            if _path_is_child(root_path, cand_path):
                chain.append(candidate)
        if len(chain) >= 2:
            chains.append(chain)
            for ep in chain:
                used.add(str(ep.get("path", "")).rstrip("/"))

    return chains


def _build_chained_scenarios(
    parsed_requirement: dict,
    actions: list[str],
    expectations: list[str],
    start_index: int,
) -> list[dict]:
    """Build multi-step scenarios from detected endpoint dependency chains."""
    endpoints = [ep for ep in (parsed_requirement.get("api_endpoints") or []) if ep.get("path")]
    chains = _detect_endpoint_chains(endpoints)
    if not chains:
        return []

    preconditions = _normalize_preconditions(parsed_requirement)
    scenarios: list[dict] = []

    for chain_offset, chain in enumerate(chains[:5]):
        idx = start_index + chain_offset
        steps: list[ScenarioStep] = [ScenarioStep(type="given", text=preconditions[0])]

        for step_i, ep in enumerate(chain):
            method = str(ep.get("method", "POST")).upper()
            path = str(ep.get("path", ""))
            desc = str(ep.get("description", "")).strip()
            action_text = desc if desc and not desc.startswith("/") else f"调用 {method} {path}"
            step_type = "when" if step_i == 0 else "and"
            steps.append(ScenarioStep(type=step_type, text=action_text))

        chain_expectations = _select_expectations_for_endpoint(chain[-1], expectations, idx)
        if chain_expectations:
            steps.append(ScenarioStep(type="then", text=chain_expectations[0]))
        else:
            steps.append(ScenarioStep(type="then", text="系统返回符合需求的可观察结果"))

        chain_names = [str(ep.get("description") or ep.get("path", ""))[:30] for ep in chain]
        scenario_name = " -> ".join(chain_names)[:80]
        goal = f"端到端链路: {scenario_name}"

        scenario = ScenarioModel(
            scenario_id=f"scenario_{idx:03d}",
            name=scenario_name,
            goal=goal,
            preconditions=preconditions,
            steps=steps,
            assertions=chain_expectations or ["系统返回符合需求的可观察结果"],
            source_chunks=parsed_requirement.get("source_chunks", []),
            priority="P0",
        )
        scenarios.append(scenario.to_dict())

    return scenarios


def _is_narrative_action(text: str) -> bool:
    """Return True if the action looks like a high-level business narrative rather than a direct endpoint call."""
    lowered = text.lower()
    if re.match(r"^调用\s+(get|post|put|patch|delete)\s+/", lowered):
        return False
    narrative_keywords = (
        "主链路", "流程", "用户", "前端", "页面", "完成", "确认",
        "提交", "登录", "结束", "开始", "进入", "退出",
        "workflow", "flow", "journey", "scenario", "process",
    )
    return any(kw in lowered for kw in narrative_keywords)


def _build_narrative_scenarios(
    parsed_requirement: dict,
    actions: list[str],
    expectations: list[str],
    start_index: int,
) -> list[dict]:
    """Build scenarios from high-level narrative/business-flow actions."""
    narrative_actions = [a for a in actions if _is_narrative_action(a)]
    if not narrative_actions:
        return []
    grouped = _group_actions(narrative_actions[:8])
    scenarios: list[dict] = []
    for offset, action_group in enumerate(grouped[:5], start=0):
        idx = start_index + offset
        if len(grouped) == 1:
            scenario_expectations = expectations
        else:
            scenario_expectations = [expectations[min(offset, len(expectations) - 1)]]
        scenarios.append(_build_scenario(idx, action_group, scenario_expectations, parsed_requirement))
    return scenarios


def build_scenarios(parsed_requirement: dict, use_llm: bool = False) -> list[dict]:
    """Build scenario list from parsed requirement.

    Generates both endpoint-level scenarios (one per API endpoint) and
    narrative/main-flow scenarios (from business actions) when applicable.
    """
    actions = parsed_requirement.get("actions") or [parsed_requirement.get("objective", "执行核心业务动作")]
    expectations = parsed_requirement.get("expected_results") or ["系统返回符合需求的可观察结果"]

    endpoint_scenarios = _build_endpoint_scenarios(parsed_requirement, actions, expectations)

    chained_start = len(endpoint_scenarios) + 1
    chained_scenarios = _build_chained_scenarios(parsed_requirement, actions, expectations, chained_start)

    narrative_start = chained_start + len(chained_scenarios)
    narrative_scenarios = _build_narrative_scenarios(parsed_requirement, actions, expectations, narrative_start)

    if endpoint_scenarios or chained_scenarios or narrative_scenarios:
        combined = endpoint_scenarios + chained_scenarios + narrative_scenarios
        if combined:
            return combined

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
