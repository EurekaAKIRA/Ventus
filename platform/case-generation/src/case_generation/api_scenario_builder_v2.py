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
_NON_PERSISTENT_HINTS = (
    "fake rest api",
    "fake success",
    "not persistent",
    "non-persistent",
    "不会真正写入服务器",
    "不会真正写入",
    "不真正写入服务器",
    "不真正写入",
    "不真正改写服务器状态",
    "不应作为真实持久化断言依据",
    "不应期望真实改变",
    "不应期望真实删除",
)
_PRELOADED_RESOURCE_HINTS = (
    "preloaded",
    "pre-existing",
    "preexisting",
    "preset resource",
    "official preset",
    "existing resource",
    "资源来源",
    "官方预置",
    "预置",
    "预先存在",
    "已存在",
    "默认使用",
    "建议使用",
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
_EXPLICIT_HTTP_SURFACE_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+/[\w/\-{}:.?=&%]+", re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r"\{\{?\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}?\}")


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


def _iter_requirement_texts(parsed_requirement: dict) -> list[str]:
    texts: list[str] = []
    objective = str(parsed_requirement.get("objective", "")).strip()
    if objective:
        texts.append(objective)
    for key in ("preconditions", "actions", "expected_results", "constraints"):
        for item in parsed_requirement.get(key) or []:
            text = str(item or "").strip()
            if text:
                texts.append(text)
    for endpoint in parsed_requirement.get("api_endpoints") or []:
        for key in ("path", "description", "group"):
            text = str((endpoint or {}).get(key, "")).strip()
            if text:
                texts.append(text)
    return texts


def _resource_related_texts(parsed_requirement: dict, resource: str) -> list[str]:
    normalized_resource = str(resource or "").strip().lower()
    if not normalized_resource:
        return []
    aliases = {
        normalized_resource,
        normalized_resource.rstrip("s"),
        f"{normalized_resource}_id",
        f"/{normalized_resource}",
    }
    return [text for text in _iter_requirement_texts(parsed_requirement) if any(alias and alias in text.lower() for alias in aliases)]


def _resource_is_non_persistent(parsed_requirement: dict, resource: str) -> bool:
    haystack = " ".join(_resource_related_texts(parsed_requirement, resource)).lower()
    return bool(haystack) and any(hint in haystack for hint in _NON_PERSISTENT_HINTS)


def _endpoint_has_preloaded_resource_source(endpoint: dict, parsed_requirement: dict) -> bool:
    capability = _endpoint_capability(endpoint)
    path = _canonicalize_endpoint_path(str(endpoint.get("path", "")))
    if capability not in {"detail", "replace", "patch", "delete"} and not _is_querystring_filter_endpoint(endpoint):
        return False
    if "{" not in path or "}" not in path:
        return False
    if _is_querystring_filter_endpoint(endpoint):
        return True
    haystack = " ".join(_resource_related_texts(parsed_requirement, _resource_key(endpoint))).lower()
    return bool(haystack) and any(hint in haystack for hint in _PRELOADED_RESOURCE_HINTS)


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
        if lowered_method and re.search(rf"\b{re.escape(lowered_method)}\b", lowered_action) and lowered_path and lowered_path in lowered_action:
            return action

    for action in actions:
        lowered_action = action.lower()
        if lowered_method and re.search(rf"\b{re.escape(lowered_method)}\b", lowered_action) and any(segment in lowered_action for segment in path_segments):
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
    endpoint_key = _endpoint_key(endpoint)
    path_segments = _extract_significant_path_segments(path)
    matched = []
    for expectation in expectations:
        lowered_expectation = expectation.lower()
        if _is_generic_expectation_text(expectation):
            continue
        explicit_refs = []
        for match in _EXPLICIT_HTTP_SURFACE_RE.finditer(expectation):
            token = match.group(0).strip()
            method_part, _, path_part = token.partition(" ")
            if method_part and path_part:
                explicit_refs.append((method_part.upper(), _canonicalize_endpoint_path(path_part)))
        if explicit_refs:
            if endpoint_key in explicit_refs:
                matched.append(expectation)
            continue
        bare_refs = [_canonicalize_endpoint_path(match.group(0)) for match in re.finditer(r"/[\w/\-{}:.?=&%]+", expectation)]
        if bare_refs and _canonicalize_endpoint_path(path) not in bare_refs:
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
    capability = _endpoint_capability(endpoint)
    path = _canonicalize_endpoint_path(str(endpoint.get("path", "")))
    has_placeholder = "{" in path and "}" in path
    return (
        bool(depends_on)
        or capability == "detail"
        or (capability in {"replace", "patch", "delete"} and has_placeholder)
        or (_endpoint_needs_auth_context(endpoint) and not _is_auth_root_endpoint(endpoint))
    )


def _ordered_endpoints(parsed_requirement: dict, actions: list[str] | None = None) -> list[dict]:
    endpoints = _filtered_endpoints(parsed_requirement, actions=actions)
    return sorted(endpoints, key=_endpoint_flow_rank)


def _build_endpoint_scenarios(parsed_requirement: dict, actions: list[str], expectations: list[str]) -> list[dict]:
    scenarios: list[dict] = []
    listed_endpoints = _filtered_endpoints(parsed_requirement, actions=actions)
    for index, endpoint in enumerate(listed_endpoints[:MAX_ENDPOINT_SCENARIOS], start=1):
        if _endpoint_effectively_requires_context(endpoint, listed_endpoints, parsed_requirement):
            continue
        endpoint_action = _build_action_for_endpoint(endpoint, actions)
        endpoint_expectations = _select_expectations_for_endpoint(endpoint, expectations)
        endpoint_goal = _build_goal_for_endpoint(endpoint, endpoint_action, parsed_requirement)
        scenarios.append(_build_scenario(index, [endpoint_action], endpoint_expectations, parsed_requirement, goal=endpoint_goal))
    return scenarios


def _endpoint_key(endpoint: dict) -> tuple[str, str]:
    return (str(endpoint.get("method", "")).upper().strip(), _canonicalize_endpoint_path(str(endpoint.get("path", ""))))


def _canonical_placeholder_name(name: str) -> str:
    lowered = str(name or "").strip().lower()
    if lowered in {"bookingid", "booking_id", "id"}:
        return "booking_id"
    if lowered in {"taskid", "task_id"}:
        return "task_id"
    return lowered


def _canonicalize_endpoint_path(path: str) -> str:
    normalized = str(path or "").strip()
    if not normalized:
        return normalized
    if "://" in normalized:
        after = normalized.split("://", 1)[1]
        slash = after.find("/")
        normalized = after[slash:] if slash >= 0 else "/"
    if normalized != "/" and normalized.endswith("/"):
        normalized = normalized[:-1]
    query = ""
    if "?" in normalized:
        normalized, query = normalized.split("?", 1)

    def repl(match: re.Match[str]) -> str:
        return "{" + _canonical_placeholder_name(match.group(1)) + "}"

    canonical = _PLACEHOLDER_RE.sub(repl, normalized)
    return canonical if not query else f"{canonical}?{query}"


def _dedupe_endpoints(endpoints: Iterable[dict]) -> list[dict]:
    best_by_key: dict[tuple[str, str], dict] = {}
    for endpoint in endpoints:
        key = _endpoint_key(endpoint)
        current = best_by_key.get(key)
        if current is None or _endpoint_confidence_rank(endpoint) > _endpoint_confidence_rank(current):
            best_by_key[key] = endpoint
    return list(best_by_key.values())


def _endpoint_meta_text(endpoint: dict) -> str:
    return " ".join(
        [
            str(endpoint.get("description", "")),
            str(endpoint.get("group", "")),
        ]
    ).strip()


def _is_low_confidence_endpoint(endpoint: dict) -> bool:
    description = str(endpoint.get("description", "")).strip()
    group = str(endpoint.get("group", "")).strip()
    meta_text = _normalize_meta_text(_endpoint_meta_text(endpoint))
    if not str(endpoint.get("path", "")).strip():
        return True
    if description == "**Request:**":
        return True
    if description.startswith("|") and description.endswith("|"):
        return True
    if group.startswith("断言摘要"):
        return True
    if any(meta_text.startswith(prefix) for prefix in _META_ACTION_PREFIXES):
        return True
    if any(token in meta_text for token in ("**request:**", "scenario:", "断言摘要", "统一目标", "step ")):
        return True
    return False


def _endpoint_confidence_rank(endpoint: dict) -> tuple[int, int, int]:
    method = str(endpoint.get("method", "")).upper().strip()
    description = str(endpoint.get("description", "")).strip()
    group = str(endpoint.get("group", "")).strip()
    capability = _endpoint_capability(endpoint)
    has_dependency = 1 if (endpoint.get("depends_on") or []) else 0
    group_preference = 0 if group.startswith("断言摘要") else 1
    return (
        has_dependency,
        group_preference,
        0 if _is_low_confidence_endpoint(endpoint) else 1,
        1 if capability != "other" else 0,
        1 if description and description != "**Request:**" else 0,
    )


def _is_querystring_filter_endpoint(endpoint: dict) -> bool:
    method = str(endpoint.get("method", "")).upper().strip()
    path = str(endpoint.get("path", "")).strip()
    return method == "GET" and "?" in path and "=" in path


def _is_placeholder_querystring_endpoint(endpoint: dict) -> bool:
    if not _is_querystring_filter_endpoint(endpoint):
        return False
    path = str(endpoint.get("path", "")).strip().lower()
    return "..." in path or "、" in path


def _endpoint_has_action_support(endpoint: dict, actions: list[str]) -> bool:
    if not actions:
        return False
    method = str(endpoint.get("method", "")).upper().strip()
    path = str(endpoint.get("path", "")).strip()
    return any(_contains_explicit_endpoint_reference(action, method, path) for action in actions)


def _filtered_endpoints(parsed_requirement: dict, actions: list[str] | None = None) -> list[dict]:
    endpoints = [
        endpoint
        for endpoint in (parsed_requirement.get("api_endpoints") or [])
        if endpoint.get("path") and not _is_placeholder_querystring_endpoint(endpoint)
    ]
    if actions:
        dependency_paths = {
            str(dependency_path)
            for endpoint in endpoints
            for dependency_path in (endpoint.get("depends_on") or [])
            if str(dependency_path).strip()
        }
        auth_needed = any(_endpoint_needs_auth_context(endpoint) for endpoint in endpoints)
        endpoints = [
            endpoint
            for endpoint in endpoints
            if (
                not _is_low_confidence_endpoint(endpoint)
                or _endpoint_has_action_support(endpoint, actions)
                or _is_querystring_filter_endpoint(endpoint)
                or _endpoint_requires_context(endpoint)
                or any(
                    _canonicalize_endpoint_path(str(endpoint.get("path", ""))) == _canonicalize_endpoint_path(dependency_path)
                    for dependency_path in dependency_paths
                )
                or (_is_auth_endpoint(endpoint) and auth_needed)
            )
            and not _is_unlikely_auth_root_variant(endpoint, actions)
        ]
    return _dedupe_endpoints(endpoints)


def _is_auth_endpoint(endpoint: dict) -> bool:
    method = str(endpoint.get("method", "")).upper().strip()
    path = str(endpoint.get("path", "")).lower()
    description = str(endpoint.get("description", "")).lower()
    if any(token in path for token in ("/auth", "/login", "/session", "/challenger", "/token")):
        return True
    return method == "POST" and any(token in description for token in ("auth", "login", "token", "session", "令牌"))


def _is_auth_root_endpoint(endpoint: dict) -> bool:
    path = str(endpoint.get("path", "")).lower()
    return any(token in path for token in ("/auth", "/login", "/session", "/challenger"))


def _is_unlikely_auth_root_variant(endpoint: dict, actions: list[str]) -> bool:
    method = str(endpoint.get("method", "")).upper().strip()
    if method == "POST" or not _is_auth_root_endpoint(endpoint):
        return False
    if _endpoint_has_action_support(endpoint, actions):
        return False
    return not bool(endpoint.get("response_fields") or endpoint.get("request_body_fields"))


def _endpoint_request_field_names(endpoint: dict) -> list[str]:
    fields = endpoint.get("request_body_fields") or []
    return [str((field or {}).get("name", "")).strip().lower() for field in fields if str((field or {}).get("name", "")).strip()]


def _endpoint_needs_auth_context(endpoint: dict) -> bool:
    request_fields = _endpoint_request_field_names(endpoint)
    text = " ".join(
        [
            str(endpoint.get("path", "")),
            str(endpoint.get("description", "")),
            " ".join(request_fields),
        ]
    ).lower()
    return any(
        token in text
        for token in (
            "cookie",
            "token",
            "bearer",
            "auth",
            "session",
            "authorization",
            "x-auth-token",
            "x-challenger",
        )
    )


def _endpoint_requires_token_provider(endpoint: dict) -> bool:
    request_fields = set(_endpoint_request_field_names(endpoint))
    return "x-auth-token" in request_fields or "authorization" in request_fields


def _find_token_provider_endpoint(target: dict, ordered_endpoints: list[dict]) -> dict | None:
    target_key = _endpoint_key(target)
    target_resource = _resource_key(target)
    candidates: list[dict] = []
    for endpoint in ordered_endpoints:
        if _endpoint_key(endpoint) == target_key:
            continue
        if not _is_auth_endpoint(endpoint):
            continue
        path = str(endpoint.get("path", "")).lower()
        description = str(endpoint.get("description", "")).lower()
        if "token" not in path and "token" not in description:
            continue
        candidates.append(endpoint)
    if not candidates:
        return None
    for endpoint in candidates:
        if _resource_key(endpoint) == target_resource:
            return endpoint
    return candidates[0]


def _find_resource_provider_endpoint(
    target: dict,
    ordered_endpoints: list[dict],
    parsed_requirement: dict | None = None,
) -> dict | None:
    target_key = _endpoint_key(target)
    target_resource = _resource_key(target)
    target_capability = _endpoint_capability(target)
    target_path = _canonicalize_endpoint_path(str(target.get("path", "")))
    has_placeholder = "{" in target_path and "}" in target_path
    if target_capability not in {"detail", "replace", "patch", "delete"}:
        return None
    if target_capability in {"replace", "patch", "delete"} and not has_placeholder:
        return None
    candidates: list[dict] = []
    for endpoint in ordered_endpoints:
        if _endpoint_key(endpoint) == target_key:
            continue
        if _resource_key(endpoint) != target_resource:
            continue
        capability = _endpoint_capability(endpoint)
        if parsed_requirement and capability == "create" and _resource_is_non_persistent(parsed_requirement, target_resource):
            continue
        if capability in {"create", "list", "auth"}:
            candidates.append(endpoint)
    if not candidates:
        return None
    priority = {"create": 0, "list": 1, "auth": 2}
    candidates.sort(key=lambda item: (priority.get(_endpoint_capability(item), 9), _endpoint_flow_rank(item)))
    return candidates[0]


def _endpoint_effectively_requires_context(
    endpoint: dict,
    ordered_endpoints: list[dict],
    parsed_requirement: dict | None = None,
) -> bool:
    if _endpoint_needs_auth_context(endpoint) and not _is_auth_root_endpoint(endpoint):
        return True
    if parsed_requirement and _endpoint_has_preloaded_resource_source(endpoint, parsed_requirement):
        return False
    if _endpoint_requires_context(endpoint):
        return True
    if _find_resource_provider_endpoint(endpoint, ordered_endpoints, parsed_requirement) is not None:
        return True
    token_provider = _find_token_provider_endpoint(endpoint, ordered_endpoints)
    if token_provider is not None and not _is_auth_endpoint(endpoint) and _resource_key(token_provider) == _resource_key(endpoint):
        return True
    return False


def _find_endpoint_by_path(path: str, endpoints: list[dict]) -> dict | None:
    dependency = str(path or "").strip()
    normalized = _canonicalize_endpoint_path(dependency)
    dependency_method = ""
    method_match = re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s+(.+)$", dependency, re.IGNORECASE)
    if method_match:
        dependency_method = method_match.group(1).upper().strip()
        normalized = _canonicalize_endpoint_path(method_match.group(2).strip())
    for endpoint in endpoints:
        endpoint_method = str(endpoint.get("method", "")).upper().strip()
        if dependency_method and endpoint_method != dependency_method:
            continue
        if _canonicalize_endpoint_path(str(endpoint.get("path", ""))) == normalized:
            return endpoint
    return None


def _resource_key(endpoint: dict) -> str:
    path = _canonicalize_endpoint_path(str(endpoint.get("path", ""))).lower()
    segments = _extract_significant_path_segments(path)
    return segments[0] if segments else path.strip("/") or "root"


def _endpoint_capability(endpoint: dict) -> str:
    method = str(endpoint.get("method", "")).upper().strip()
    path = _canonicalize_endpoint_path(str(endpoint.get("path", ""))).lower()
    if any(token in path for token in ("/ping", "/health", "/ready", "/version")):
        return "health"
    has_placeholder = bool(_PLACEHOLDER_RE.search(path))
    if method == "GET" and has_placeholder:
        return "detail"
    if _is_auth_endpoint(endpoint):
        return "auth"
    if method == "GET" and not has_placeholder:
        return "list"
    if method == "POST":
        return "create"
    if method == "PUT":
        return "replace"
    if method == "PATCH":
        return "patch"
    if method == "DELETE":
        return "delete"
    return "other"


def _resolve_dependency_chain(
    target: dict,
    ordered_endpoints: list[dict],
    parsed_requirement: dict | None = None,
) -> list[dict]:
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
    resource_provider = _find_resource_provider_endpoint(target, ordered_endpoints, parsed_requirement)
    if resource_provider is not None and resource_provider not in chain:
        provider_chain = _resolve_dependency_chain(resource_provider, ordered_endpoints, parsed_requirement)
        chain = provider_chain + chain
    if _endpoint_requires_token_provider(target):
        token_provider = _find_token_provider_endpoint(target, ordered_endpoints)
        if token_provider is not None and token_provider not in chain:
            provider_chain = _resolve_dependency_chain(token_provider, ordered_endpoints, parsed_requirement)
            chain = provider_chain + chain
    elif _find_token_provider_endpoint(target, ordered_endpoints) is not None and not _is_auth_endpoint(target):
        token_provider = _find_token_provider_endpoint(target, ordered_endpoints)
        if token_provider is not None and token_provider not in chain and _resource_key(token_provider) == _resource_key(target):
            provider_chain = _resolve_dependency_chain(token_provider, ordered_endpoints, parsed_requirement)
            chain = provider_chain + chain
    if _endpoint_needs_auth_context(target) and not any(_is_auth_root_endpoint(endpoint) for endpoint in chain):
        auth_roots = [
            endpoint
            for endpoint in ordered_endpoints
            if _is_auth_root_endpoint(endpoint) and not _endpoint_requires_context(endpoint)
        ]
        if auth_roots:
            chain = auth_roots[:1] + chain
    return _dedupe_endpoints(chain)


def _build_dependency_chain_scenarios(
    parsed_requirement: dict,
    actions: list[str],
    expectations: list[str],
    start_index: int,
) -> list[dict]:
    ordered_endpoints = _ordered_endpoints(parsed_requirement, actions)
    dependent_endpoints = [
        endpoint
        for endpoint in ordered_endpoints
        if _endpoint_effectively_requires_context(endpoint, ordered_endpoints, parsed_requirement)
    ]
    scenarios: list[dict] = []
    seen_chains: set[tuple[tuple[str, str], ...]] = set()

    for endpoint in dependent_endpoints:
        chain = _resolve_dependency_chain(endpoint, ordered_endpoints, parsed_requirement)
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
    ordered_endpoints = _ordered_endpoints(parsed_requirement, actions)
    dependent_count = len(
        [
            endpoint
            for endpoint in ordered_endpoints
            if _endpoint_effectively_requires_context(endpoint, ordered_endpoints, parsed_requirement)
        ]
    )
    if len(ordered_endpoints) < 3 or dependent_count < 2:
        return []
    primary_resource = next((_resource_key(endpoint) for endpoint in ordered_endpoints if _endpoint_capability(endpoint) == "create"), "")
    if primary_resource and _resource_is_non_persistent(parsed_requirement, primary_resource):
        return []
    selected: list[dict] = []

    def add_first(capability: str) -> None:
        for endpoint in ordered_endpoints:
            if _endpoint_capability(endpoint) != capability:
                continue
            if primary_resource and capability not in {"auth", "health"} and _resource_key(endpoint) != primary_resource:
                continue
            if endpoint not in selected:
                selected.append(endpoint)
            return

    add_first("auth")
    add_first("create")
    add_first("detail")
    add_first("delete")
    if len(selected) < 3:
        add_first("replace")
    if len(selected) < 3:
        add_first("patch")

    selected = [endpoint for endpoint in selected if _endpoint_capability(endpoint) not in {"health", "list"}]
    if len(selected) < 3:
        return []

    flow_actions = [_build_action_for_endpoint(endpoint, actions) for endpoint in selected[:5]]
    flow_expectations = _select_expectations_for_chain(selected[:5], expectations)
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


def _scenario_step_texts(scenario: dict) -> list[str]:
    texts: list[str] = []
    for step in scenario.get("steps", []):
        if step.get("type") in {"when", "and"}:
            text = str(step.get("text", "")).strip()
            if text:
                texts.append(text)
    return texts


def _endpoint_matches_text(endpoint: dict, text: str) -> bool:
    method = str(endpoint.get("method", "")).upper().strip()
    path = str(endpoint.get("path", "")).strip()
    lowered = text.lower()
    if _EXPLICIT_HTTP_SURFACE_RE.search(text):
        return bool(method and method.lower() in lowered and _contains_explicit_endpoint_reference(text, method, path))
    path_segments = _extract_significant_path_segments(path)
    if not path_segments:
        return False
    if method and method.lower() not in lowered:
        return False
    return any(re.search(rf"\b{re.escape(segment)}\b", lowered) for segment in path_segments)


def _scenario_signature(scenario: dict, ordered_endpoints: list[dict]) -> tuple[tuple[str, str], ...]:
    signature: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for text in _scenario_step_texts(scenario):
        for endpoint in ordered_endpoints:
            key = _endpoint_key(endpoint)
            if key in seen:
                continue
            if _endpoint_matches_text(endpoint, text):
                seen.add(key)
                signature.append(key)
    return tuple(signature)


def _filter_supplemental_scenarios(
    *,
    base_scenarios: list[dict],
    candidate_scenarios: list[dict],
    ordered_endpoints: list[dict],
) -> list[dict]:
    retained: list[dict] = []
    covered_signatures = {
        signature
        for scenario in base_scenarios
        if (signature := _scenario_signature(scenario, ordered_endpoints))
    }
    covered_endpoint_sets = {frozenset(signature) for signature in covered_signatures}

    for scenario in candidate_scenarios:
        signature = _scenario_signature(scenario, ordered_endpoints)
        if not signature:
            continue
        endpoint_set = frozenset(signature)
        if signature in covered_signatures or any(endpoint_set.issubset(covered) for covered in covered_endpoint_sets):
            continue
        retained.append(scenario)
        covered_signatures.add(signature)
        covered_endpoint_sets.add(endpoint_set)
    return retained


def _scenario_has_explicit_preloaded_resource(scenario: dict, parsed_requirement: dict) -> bool:
    texts = _scenario_step_texts(scenario)
    preconditions = [str(item) for item in (scenario.get("preconditions") or parsed_requirement.get("preconditions") or [])]
    haystack = " ".join(texts + preconditions).lower()
    preload_markers = (
        "preloaded",
        "pre-existing",
        "preexisting",
        "existing_",
        "existing ",
        "预置",
        "预先存在",
        "已有",
        "已存在",
        "existing_booking_id",
        "existing resource id",
    )
    return any(marker in haystack for marker in preload_markers)


def _scenario_mentions_saved_resource(texts: list[str], resource: str) -> bool:
    haystack = " ".join(texts).lower()
    resource_markers = {
        resource,
        f"{resource}_id",
        "bookingid" if resource == "booking" else "",
        "resource_id",
        "id",
    }
    return (
        any(marker and marker in haystack for marker in resource_markers)
        and any(token in haystack for token in ("save", "saved", "保存", "existing_", "existing "))
    )


def _scenario_satisfies_resource_lifecycle(
    scenario: dict,
    ordered_endpoints: list[dict],
    parsed_requirement: dict,
) -> bool:
    signature = _scenario_signature(scenario, ordered_endpoints)
    if not signature:
        return True
    endpoints_by_key = {_endpoint_key(endpoint): endpoint for endpoint in ordered_endpoints}
    capabilities: dict[str, set[str]] = {}
    texts = _scenario_step_texts(scenario)

    for key in signature:
        endpoint = endpoints_by_key.get(key)
        if endpoint is None:
            continue
        resource = _resource_key(endpoint)
        capabilities.setdefault(resource, set()).add(_endpoint_capability(endpoint))

    for resource, caps in capabilities.items():
        if not caps.intersection({"detail", "replace", "patch", "delete"}):
            continue
        if "create" in caps:
            continue
        if caps.intersection({"list", "detail"}) and _scenario_mentions_saved_resource(texts, resource):
            continue
        if _scenario_has_explicit_preloaded_resource(scenario, parsed_requirement):
            continue
        return False
    return True


def _filter_resource_lifecycle_scenarios(
    scenarios: list[dict],
    *,
    ordered_endpoints: list[dict],
    parsed_requirement: dict,
) -> list[dict]:
    return [
        scenario
        for scenario in scenarios
        if _scenario_satisfies_resource_lifecycle(scenario, ordered_endpoints, parsed_requirement)
    ]


def _renumber_scenarios(scenarios: list[dict]) -> list[dict]:
    for index, scenario in enumerate(scenarios, start=1):
        scenario["scenario_id"] = f"scenario_{index:03d}"
    return scenarios


def build_scenarios(parsed_requirement: dict, use_llm: bool = False) -> list[dict]:
    actions = _filter_actions(parsed_requirement.get("actions") or [parsed_requirement.get("objective", "Execute core action")])
    expectations = parsed_requirement.get("expected_results") or [DEFAULT_RESULT_TEXT]
    ordered_endpoints = _ordered_endpoints(parsed_requirement, actions)

    endpoint_scenarios = _build_endpoint_scenarios(parsed_requirement, actions, expectations)
    dependency_scenarios = _build_dependency_chain_scenarios(parsed_requirement, actions, expectations, len(endpoint_scenarios) + 1)
    full_flow_start = len(endpoint_scenarios) + len(dependency_scenarios) + 1
    full_flow_scenarios = _build_full_flow_scenario(parsed_requirement, actions, expectations, full_flow_start)
    narrative_start = len(endpoint_scenarios) + len(dependency_scenarios) + len(full_flow_scenarios) + 1
    narrative_scenarios = _filter_resource_lifecycle_scenarios(
        _filter_supplemental_scenarios(
        base_scenarios=endpoint_scenarios + dependency_scenarios + full_flow_scenarios,
        candidate_scenarios=_build_narrative_scenarios(parsed_requirement, actions, expectations, narrative_start),
        ordered_endpoints=ordered_endpoints,
        ),
        ordered_endpoints=ordered_endpoints,
        parsed_requirement=parsed_requirement,
    )

    combined = endpoint_scenarios + dependency_scenarios + full_flow_scenarios + narrative_scenarios
    if combined:
        return _renumber_scenarios(combined)

    scenarios: list[dict] = []
    grouped_actions = _group_actions(actions[:6])
    for index, action_group in enumerate(grouped_actions[:5], start=1):
        scenario_expectations = expectations if len(grouped_actions) == 1 else [expectations[min(index - 1, len(expectations) - 1)]]
        scenarios.append(_build_scenario(index, action_group, scenario_expectations, parsed_requirement))

    if use_llm:
        parsed_requirement.setdefault("ambiguities", []).append("LLM scenario enhancement is not wired in yet.")

    return _renumber_scenarios(scenarios)
