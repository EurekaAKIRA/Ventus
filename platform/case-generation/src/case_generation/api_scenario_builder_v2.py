"""Scenario construction helpers with API dependency grouping."""

from __future__ import annotations

import re
from typing import Iterable

from platform_shared.models import ScenarioModel, ScenarioStep

DEFAULT_PRECONDITION = "Start from a valid API entrypoint"
DEFAULT_ASSERTION_TEXT = "系统返回符合需求的可观察结果"
DEFAULT_RESULT_TEXT = "System returns an observable result"
MAX_ENDPOINT_SCENARIOS = 25
MAX_DEPENDENCY_SCENARIOS = 6

_COMMON_ENDPOINT_SEGMENTS = {"api", "task", "tasks", "task_id", "{task_id}", "id", "data", "history"}
_META_ACTION_PREFIXES = (
    "scenario:",
    "scenario ",
    "scen:",
    "step ",
    "request:**",
    "expected:**",
    "goal:",
    "场景:",
    "场景 ",
    "步骤 ",
    "请求:",
    "预期:",
    "统一目标:",
    "统一目标 ",
)
_GENERIC_EXPECTATION_HINTS = (
    "统一使用如下响应结构",
    "不应把任务详情查询接口当作列表接口",
    "不应假设存在",
    "联调和断言设计",
    "响应结构",
    "主链路联调需求说明",
    "当前实现对齐版",
)
_NARRATIVE_KEYWORDS = (
    "main flow",
    "workflow",
    "flow",
    "journey",
    "scenario",
    "process",
    "user",
    "page",
    "页面",
    "用户",
    "流程",
    "主链路",
    "完成",
    "确认",
)
_FLOW_SUMMARY_HINTS = (
    "闭环",
    "主链路",
    "全链路",
    "端到端",
    "e2e",
    "end-to-end",
    "workflow",
    "journey",
)
_VERIFICATION_PREFIXES = (
    "验证",
    "校验",
    "检查",
    "确认",
    "确保",
    "verify",
    "validate",
    "check",
    "ensure",
    "confirm",
)
_ACTION_CLASS_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("auth", ("auth", "login", "token", "鉴权", "登录", "令牌")),
    ("create", ("create", "post", "创建", "新增")),
    ("query", ("query", "fetch", "get", "read", "查询", "读取", "查看")),
    ("update", ("update", "put", "patch", "更新", "修改")),
    ("delete", ("delete", "remove", "删除", "取消")),
)
_EXPLICIT_HTTP_SURFACE_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+/[\w/\-{}:.]+", re.IGNORECASE)


def _normalize_preconditions(parsed_requirement: dict) -> list[str]:
    return parsed_requirement.get("preconditions") or [DEFAULT_PRECONDITION]


def _priority_from_text(text: str) -> str:
    lowered = text.lower()
    if any(
        keyword in lowered
        for keyword in ("login", "auth", "pay", "submit", "create", "delete", "登录", "鉴权", "创建", "删除")
    ):
        return "P0"
    if any(keyword in lowered for keyword in ("display", "search", "view", "query", "查看", "查询")):
        return "P1"
    return "P2"


def _is_auth_action(text: str) -> bool:
    lowered = text.lower()
    return any(
        keyword in lowered
        for keyword in ("login", "auth", "token", "bearer", "session", "cookie", "登录", "鉴权", "会话")
    )


def _is_create_action(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ("create", "submit", "add", "register", "post", "创建", "新增", "提交"))


def _depends_on_previous(text: str) -> bool:
    lowered = text.lower()
    return any(
        keyword in lowered
        for keyword in ("previous", "prior", "token", "session", "cookie", "id", "detail", "profile", "上一步", "返回值", "详情")
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
        steps.append(ScenarioStep(type="then", text=DEFAULT_ASSERTION_TEXT))

    scenario = ScenarioModel(
        scenario_id=f"scenario_{scenario_index:03d}",
        name=" -> ".join(actions)[:80],
        goal=goal or parsed_requirement.get("objective", primary_action),
        preconditions=preconditions,
        steps=steps,
        assertions=expected_results or [DEFAULT_ASSERTION_TEXT],
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
    return any(hint in lowered for hint in _GENERIC_EXPECTATION_HINTS)


def _select_expectations_for_endpoint(endpoint: dict, expectations: list[str]) -> list[str]:
    if not expectations:
        return [DEFAULT_ASSERTION_TEXT]
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


def _select_expectations_for_chain(chain: list[dict], expectations: list[str]) -> list[str]:
    matched: list[str] = []
    for endpoint in reversed(chain):
        for expectation in _select_expectations_for_endpoint(endpoint, expectations):
            if expectation not in matched:
                matched.append(expectation)
            if len(matched) >= 2:
                return matched
    return matched or [DEFAULT_ASSERTION_TEXT]


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


def _normalize_meta_text(text: str) -> str:
    return str(text or "").strip().lower().replace("：", ":")


def _looks_like_flow_summary_action(text: str) -> bool:
    normalized = _normalize_meta_text(text)
    if not normalized or _EXPLICIT_HTTP_SURFACE_RE.search(text):
        return False
    if any(hint in normalized for hint in _FLOW_SUMMARY_HINTS):
        return True
    if not any(normalized.startswith(prefix) for prefix in _VERIFICATION_PREFIXES):
        return False
    matched_classes = 0
    for _, keywords in _ACTION_CLASS_HINTS:
        if any(keyword in normalized for keyword in keywords):
            matched_classes += 1
    return matched_classes >= 2


def _is_meta_action(text: str) -> bool:
    normalized = _normalize_meta_text(text)
    if not normalized:
        return True
    if any(normalized.startswith(prefix) for prefix in _META_ACTION_PREFIXES):
        return True
    return _looks_like_flow_summary_action(text)


def _filter_actions(actions: list[str]) -> list[str]:
    return [action for action in actions if not _is_meta_action(action)]


def _endpoint_requires_context(endpoint: dict) -> bool:
    depends_on = endpoint.get("depends_on") or []
    return bool(depends_on)


def _ordered_endpoints(parsed_requirement: dict) -> list[dict]:
    endpoints = [endpoint for endpoint in (parsed_requirement.get("api_endpoints") or []) if endpoint.get("path")]
    return sorted(endpoints, key=_endpoint_flow_rank)


def _build_endpoint_scenarios(parsed_requirement: dict, actions: list[str], expectations: list[str]) -> list[dict]:
    scenarios: list[dict] = []
    listed_endpoints = [endpoint for endpoint in (parsed_requirement.get("api_endpoints") or []) if endpoint.get("path")]
    for index, endpoint in enumerate(listed_endpoints[:MAX_ENDPOINT_SCENARIOS], start=1):
        if _endpoint_requires_context(endpoint):
            continue
        endpoint_action = _build_action_for_endpoint(endpoint, actions)
        endpoint_expectations = _select_expectations_for_endpoint(endpoint, expectations)
        endpoint_goal = _build_goal_for_endpoint(endpoint, endpoint_action, parsed_requirement)
        scenarios.append(_build_scenario(index, [endpoint_action], endpoint_expectations, parsed_requirement, goal=endpoint_goal))
    return scenarios


def _endpoint_key(endpoint: dict) -> tuple[str, str]:
    return (str(endpoint.get("method", "")).upper().strip(), str(endpoint.get("path", "")).strip())


def _dedupe_endpoints(endpoints: Iterable[dict]) -> list[dict]:
    unique: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for endpoint in endpoints:
        key = _endpoint_key(endpoint)
        if key in seen:
            continue
        seen.add(key)
        unique.append(endpoint)
    return unique


def _is_auth_endpoint(endpoint: dict) -> bool:
    method = str(endpoint.get("method", "")).upper().strip()
    path = str(endpoint.get("path", "")).lower()
    description = str(endpoint.get("description", "")).lower()
    if any(token in path for token in ("/auth", "/login", "/session")):
        return True
    return method == "POST" and any(token in description for token in ("auth", "login", "token", "session"))


def _endpoint_needs_auth_context(endpoint: dict) -> bool:
    text = " ".join(
        [
            str(endpoint.get("path", "")),
            str(endpoint.get("description", "")),
            " ".join(str((field or {}).get("name", "")) for field in (endpoint.get("request_body_fields") or [])),
        ]
    ).lower()
    return any(token in text for token in ("cookie", "token", "bearer", "auth", "session"))


def _find_endpoint_by_path(path: str, endpoints: list[dict]) -> dict | None:
    normalized = str(path or "").strip()
    for endpoint in endpoints:
        if str(endpoint.get("path", "")).strip() == normalized:
            return endpoint
    return None


def _resolve_dependency_chain(target: dict, ordered_endpoints: list[dict]) -> list[dict]:
    chain: list[dict] = []
    visiting: set[tuple[str, str]] = set()

    def visit(endpoint: dict) -> None:
        key = _endpoint_key(endpoint)
        if key in visiting:
            return
        visiting.add(key)
        for dependency_path in endpoint.get("depends_on") or []:
            dependency = _find_endpoint_by_path(str(dependency_path), ordered_endpoints)
            if dependency is not None:
                visit(dependency)
        chain.append(endpoint)

    visit(target)
    if _endpoint_needs_auth_context(target) and not any(_is_auth_endpoint(endpoint) for endpoint in chain):
        auth_roots = [endpoint for endpoint in ordered_endpoints if _is_auth_endpoint(endpoint) and not _endpoint_requires_context(endpoint)]
        if auth_roots:
            chain = auth_roots[:1] + chain
    return _dedupe_endpoints(chain)


def _build_dependency_chain_scenarios(
    parsed_requirement: dict,
    actions: list[str],
    expectations: list[str],
    start_index: int,
) -> list[dict]:
    ordered_endpoints = _ordered_endpoints(parsed_requirement)
    dependent_endpoints = [endpoint for endpoint in ordered_endpoints if _endpoint_requires_context(endpoint)]
    scenarios: list[dict] = []
    seen_chains: set[tuple[tuple[str, str], ...]] = set()

    for endpoint in dependent_endpoints:
        chain = _resolve_dependency_chain(endpoint, ordered_endpoints)
        if len(chain) < 2:
            continue
        chain_key = tuple(_endpoint_key(item) for item in chain)
        if chain_key in seen_chains:
            continue
        seen_chains.add(chain_key)
        scenario_index = start_index + len(scenarios)
        chain_actions = [_build_action_for_endpoint(item, actions) for item in chain]
        chain_expectations = _select_expectations_for_chain(chain, expectations)
        endpoint_goal = _build_goal_for_endpoint(endpoint, chain_actions[-1], parsed_requirement)
        scenarios.append(_build_scenario(scenario_index, chain_actions, chain_expectations, parsed_requirement, goal=endpoint_goal))
        if len(scenarios) >= MAX_DEPENDENCY_SCENARIOS:
            break
    return scenarios


def _build_full_flow_scenario(
    parsed_requirement: dict,
    actions: list[str],
    expectations: list[str],
    start_index: int,
) -> list[dict]:
    ordered_endpoints = _ordered_endpoints(parsed_requirement)
    dependent_count = len([endpoint for endpoint in ordered_endpoints if _endpoint_requires_context(endpoint)])
    if len(ordered_endpoints) < 3 or dependent_count < 2:
        return []
    flow_actions = [_build_action_for_endpoint(endpoint, actions) for endpoint in ordered_endpoints[:8]]
    flow_expectations = _select_expectations_for_chain(ordered_endpoints[:8], expectations)
    scenario = _build_scenario(
        start_index,
        flow_actions,
        flow_expectations,
        parsed_requirement,
        goal=parsed_requirement.get("objective", "dependent api flow"),
    )
    return [scenario]


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
    normalized = _normalize_meta_text(text)
    if not normalized or _is_meta_action(text):
        return False
    if re.match(r"^调用\s+(get|post|put|patch|delete)\s+/", text.lower()):
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in _NARRATIVE_KEYWORDS)


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
    expectations = parsed_requirement.get("expected_results") or [DEFAULT_RESULT_TEXT]

    endpoint_scenarios = _build_endpoint_scenarios(parsed_requirement, actions, expectations)
    dependency_scenarios = _build_dependency_chain_scenarios(parsed_requirement, actions, expectations, len(endpoint_scenarios) + 1)
    full_flow_start = len(endpoint_scenarios) + len(dependency_scenarios) + 1
    full_flow_scenarios = _build_full_flow_scenario(parsed_requirement, actions, expectations, full_flow_start)
    narrative_start = len(endpoint_scenarios) + len(dependency_scenarios) + len(full_flow_scenarios) + 1
    narrative_scenarios = _build_narrative_scenarios(parsed_requirement, actions, expectations, narrative_start)

    combined = endpoint_scenarios + dependency_scenarios + full_flow_scenarios + narrative_scenarios
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
