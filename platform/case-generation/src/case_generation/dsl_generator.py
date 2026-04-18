"""Unified DSL generation for the platform."""

from __future__ import annotations

import re

from platform_shared.models import ScenarioModel, TaskContext, TestCaseDSL, TestCaseStep

from .assertion_planner import AssertionPlanner

API_HINTS = (
    "api",
    "http",
    "endpoint",
    "interface",
    "login",
    "token",
    "auth",
    "bearer",
    "session",
    "cookie",
    "request",
    "response",
    "接口",
    "鉴权",
    "登录",
    "令牌",
    "会话",
)
LOGIN_HINTS = ("login", "sign in", "signin", "authenticate", "登录", "会话", "鉴权")
AUTH_HINTS = ("auth", "token", "bearer", "session", "cookie", "basic auth", "authorization", "鉴权", "令牌", "会话")
BASIC_AUTH_HINTS = ("basic auth", "basic authentication", "basic authorization", "基础认证")
FORM_HINTS = ("form", "form-data", "x-www-form-urlencoded", "form urlencoded", "表单")
SESSION_HINTS = ("session", "cookie", "会话")
CREATE_HINTS = ("create", "submit", "add", "register", "post", "创建", "新增", "提交", "下单")
QUERY_HINTS = ("get", "query", "fetch", "list", "detail", "profile", "view", "查看", "查询", "详情", "获取")
UPDATE_HINTS = ("update", "edit", "put", "patch", "修改", "更新")
DELETE_HINTS = ("delete", "remove", "取消", "删除")
EXPECTATION_HINTS = ("should", "expect", "returns", "return", "expected", "成功", "失败", "返回", "提示")
VERIFICATION_HINTS = ("verify", "validate", "check", "ensure", "confirm", "验证", "校验", "检查", "确保", "确认")
FLOW_SUMMARY_HINTS = ("闭环", "主链路", "全链路", "端到端", "e2e", "end-to-end", "workflow", "journey", "flow")
PREVIOUS_CONTEXT_HINTS = (
    "previous",
    "prior",
    "from last",
    "from previous",
    "token",
    "session",
    "id",
    "上一步",
    "返回值",
    "会话",
    "详情",
)
RESOURCE_ALIASES = (
    ("profile", ("/profile", "profile", "user detail", "用户详情", "用户信息", "资料")),
    ("session", ("/session", "session", "会话")),
    ("order", ("/orders", "order", "订单", "下单")),
    ("user", ("/users", "user", "用户")),
    ("item", ("/items", "item", "商品", "条目")),
)
_EXPLICIT_PATH_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE|ANY)\s+(/[\w/\-{}:.?=&%]+)", re.IGNORECASE)
_BARE_PATH_RE = re.compile(r"(/[\w/\-{}:.?=&%]+)")
_PLACEHOLDER_RE = re.compile(r"\{\{?\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}?\}")
_STATUS_CODE_RE = re.compile(r"(?:status\s*code|http|返回|状态码)\s*[:：=]?\s*(\d{3})", re.IGNORECASE)
_FIELD_TOKEN_RE = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_]*)`|\"([a-zA-Z_][a-zA-Z0-9_]*)\"|'([a-zA-Z_][a-zA-Z0-9_]*)'")
_FIELD_LIST_RE = re.compile(
    r"(?:包含|include(?:s)?|with|携带)\s*([a-zA-Z0-9_,\s、，和and]+?)\s*(?:字段|参数|field|fields)",
    re.IGNORECASE,
)
_FIELD_STOPWORDS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "api",
    "http",
    "json",
    "body",
    "field",
    "fields",
    "request",
    "response",
    "and",
    "or",
    "with",
    "include",
    "includes",
    "from",
    "token",
    "bearer",
}
_IDENTIFIER_ALIASES: dict[str, tuple[str, ...]] = {
    "task_id": ("task_id", "taskid"),
    "booking_id": ("booking_id", "bookingid"),
    "todo_id": ("todo_id", "todoid"),
    "user_id": ("user_id", "userid"),
    "order_id": ("order_id", "orderid"),
    "pet_id": ("pet_id", "petid"),
    "username": ("username", "user_name"),
    "access_token": ("access_token", "accesstoken"),
    "refresh_token": ("refresh_token", "refreshtoken"),
    "challenger_guid": ("challenger_guid", "challengerguid", "guid"),
    "resource_id": ("resource_id", "resourceid"),
    "session_id": ("session_id", "sessionid"),
}

# 已知平台接口请求体字段白名单，key=(METHOD, path)，供 _extract_body_fields 失败时兜底使用
_KNOWN_ENDPOINT_BODY_FIELDS: dict[tuple[str, str], dict[str, object]] = {
    ("POST", "/challenger"): {},
    ("POST", "/auth"): {
        "username": "admin",
        "password": "password123",
    },
    ("POST", "/auth/login"): {
        "username": "emilys",
        "password": "emilyspass",
        "expiresInMins": 30,
    },
    ("POST", "/auth/refresh"): {
        "refreshToken": "{{refresh_token}}",
        "expiresInMins": 30,
    },
    ("POST", "/booking"): {
        "firstname": "Jim",
        "lastname": "Brown",
        "totalprice": 111,
        "depositpaid": True,
        "bookingdates": {
            "checkin": "2026-04-10",
            "checkout": "2026-04-12",
        },
        "additionalneeds": "Breakfast",
    },
    ("PUT", "/booking/{booking_id}"): {
        "firstname": "James",
        "lastname": "Brown",
        "totalprice": 222,
        "depositpaid": False,
        "bookingdates": {
            "checkin": "2026-04-11",
            "checkout": "2026-04-13",
        },
        "additionalneeds": "Lunch",
    },
    ("PATCH", "/booking/{booking_id}"): {
        "firstname": "Jamie",
        "additionalneeds": "Dinner",
    },
    ("POST", "/todos"): {
        "title": "write API test",
        "doneStatus": False,
        "description": "created by automated test",
    },
    ("POST", "/todos/add"): {
        "todo": "write API test",
        "completed": False,
        "userId": 5,
    },
    ("PUT", "/todos/{todo_id}"): {
        "todo": "write API test updated",
        "completed": True,
        "userId": 5,
    },
    ("PATCH", "/todos/{todo_id}"): {
        "completed": True,
    },
    ("POST", "/posts"): {
        "title": "write API test",
        "body": "created by automated test",
        "userId": 1,
    },
    ("POST", "/user"): {
        "id": 10001,
        "username": "demo_user",
        "firstName": "Demo",
        "lastName": "User",
        "email": "demo@example.com",
        "password": "demo_pass",
        "phone": "13800000000",
        "userStatus": 0,
    },
    ("POST", "/store/order"): {
        "id": 10001,
        "petId": 20001,
        "quantity": 1,
        "shipDate": "2026-04-17T10:00:00.000Z",
        "status": "placed",
        "complete": False,
    },
    ("POST", "/pet"): {
        "id": 20001,
        "category": {"id": 1, "name": "demo-category"},
        "name": "demo_pet",
        "photoUrls": ["https://example.com/pet.png"],
        "tags": [{"id": 1, "name": "demo-tag"}],
        "status": "available",
    },
    ("PUT", "/posts/{resource_id}"): {
        "id": 1,
        "title": "write API test updated",
        "body": "updated by automated test",
        "userId": 1,
    },
    ("PATCH", "/posts/{resource_id}"): {
        "title": "write API test updated",
    },
    ("POST", "/todos/{todo_id}"): {
        "title": "write API test updated",
        "doneStatus": True,
        "description": "updated by automated test",
    },
    ("PUT", "/todos/{todo_id}"): {
        "todo": "write API test updated",
        "completed": True,
        "userId": 5,
    },
    ("POST", "/secret/token"): {},
    ("POST", "/secret/note"): {
        "note": "updated by automated test",
    },
    ("POST", "/api/tasks"): {
        "task_name": "demo_task_name",
        "source_type": "text",
        "requirement_text": "demo requirement text",
        "target_system": "http://127.0.0.1:8001",
        "environment": "test",
    },
    ("POST", "/api/tasks/{task_id}/parse"): {
        "use_llm": False,
        "rag_enabled": False,
        "retrieval_top_k": 5,
        "rerank_enabled": False,
    },
    ("POST", "/api/tasks/{task_id}/scenarios/generate"): {},
    ("POST", "/api/tasks/{task_id}/execute"): {
        "execution_mode": "api",
        "environment": "test",
    },
    ("POST", "/api/analysis/parse"): {
        "requirement_text": "demo requirement text",
        "source_type": "text",
    },
}
_PREFER_KNOWN_FULL_BODY_ENDPOINTS: set[tuple[str, str]] = {
    ("POST", "/challenger"),
    ("POST", "/auth"),
    ("POST", "/auth/login"),
    ("POST", "/auth/refresh"),
    ("POST", "/booking"),
    ("POST", "/todos"),
    ("POST", "/todos/add"),
    ("POST", "/posts"),
    ("POST", "/user"),
    ("POST", "/store/order"),
    ("POST", "/pet"),
    ("PUT", "/todos/{todo_id}"),
    ("PATCH", "/todos/{todo_id}"),
    ("PUT", "/posts/{resource_id}"),
    ("PATCH", "/posts/{resource_id}"),
    ("POST", "/todos/{todo_id}"),
    ("PUT", "/todos/{todo_id}"),
    ("PUT", "/booking/{booking_id}"),
    ("PATCH", "/booking/{booking_id}"),
    ("POST", "/secret/token"),
    ("POST", "/secret/note"),
}


def _known_endpoint_body(method: str, endpoint_path: str) -> dict[str, object] | None:
    normalized_method = (method or "").upper().strip()
    normalized_path = _canonicalize_endpoint_path(endpoint_path)
    known = _KNOWN_ENDPOINT_BODY_FIELDS.get((normalized_method, normalized_path))
    if known is None:
        known = _KNOWN_ENDPOINT_BODY_FIELDS.get((normalized_method, _normalize_endpoint_path(endpoint_path)))
    return dict(known) if isinstance(known, dict) else None


def _is_synthetic_body_value(value: object) -> bool:
    if isinstance(value, str):
        return value.startswith("demo_")
    if isinstance(value, dict):
        return all(_is_synthetic_body_value(item) for item in value.values())
    if isinstance(value, list):
        return all(_is_synthetic_body_value(item) for item in value)
    return False


def _merge_extracted_with_known_body(
    extracted: dict[str, object],
    method: str,
    endpoint_path: str,
) -> dict[str, object]:
    normalized_key = ((method or "").upper().strip(), _normalize_endpoint_path(endpoint_path))
    canonical_key = ((method or "").upper().strip(), _canonicalize_endpoint_path(endpoint_path))
    known = _known_endpoint_body(method, endpoint_path)
    if not known:
        return extracted
    if not extracted:
        return known

    if normalized_key in _PREFER_KNOWN_FULL_BODY_ENDPOINTS or canonical_key in _PREFER_KNOWN_FULL_BODY_ENDPOINTS:
        merged = dict(known)
        for key, value in extracted.items():
            if key not in known or not _is_synthetic_body_value(value):
                merged[key] = value
        return merged

    merged = dict(extracted)
    for key, value in extracted.items():
        if key in known and _is_synthetic_body_value(value):
            merged[key] = known[key]
    return merged


def build_test_case_dsl(
    task_context: TaskContext,
    scenarios: list[ScenarioModel],
    execution_mode: str = "api",
    parsed_requirement: dict | None = None,
    enable_assertion_enhancement: bool | None = None,
) -> dict:
    """Convert structured scenarios into the platform DSL."""
    dsl_scenarios: list[dict] = []
    parsed_requirement = parsed_requirement or {}
    api_scenario_count = 0

    for scenario in scenarios:
        step_payloads: list[dict] = []
        scenario_state = {"saved_context": set()}
        scenario_is_api = _is_api_scenario(scenario, parsed_requirement, execution_mode)
        if scenario_is_api:
            api_scenario_count += 1

        for index, step in enumerate(scenario.steps, start=1):
            step_payload = step.to_dict() if hasattr(step, "to_dict") else dict(step)
            request, assertions, uses_context, save_context, assertion_quality = _build_step_payload(
                scenario=scenario,
                step=step_payload,
                index=index,
                task_context=task_context,
                parsed_requirement=parsed_requirement,
                scenario_state=scenario_state,
                enable_api_enrichment=scenario_is_api,
                enable_assertion_enhancement=enable_assertion_enhancement,
            )
            dsl_step = TestCaseStep(
                step_id=f"{scenario.scenario_id}_step_{index:02d}",
                step_type=step_payload.get("type", ""),
                text=step_payload.get("text", ""),
                request=request,
                assertions=assertions,
                uses_context=uses_context,
                saves_context=sorted(save_context.keys()),
                save_context=save_context,
            )
            step_payload_dict = dsl_step.to_dict()
            step_payload_dict["assertion_quality"] = assertion_quality
            scenario_state["saved_context"].update(save_context.keys())
            step_payloads.append(step_payload_dict)

        dsl_scenarios.append(
            {
                "scenario_id": scenario.scenario_id,
                "name": scenario.name,
                "goal": scenario.goal,
                "priority": scenario.priority,
                "preconditions": scenario.preconditions,
                "source_chunks": scenario.source_chunks,
                "steps": step_payloads,
            }
        )

    payload = TestCaseDSL(
        dsl_version="0.2.0",
        task_id=task_context.task_id,
        task_name=task_context.task_name,
        feature_name=task_context.task_name,
        execution_mode=execution_mode,
        scenarios=dsl_scenarios,
        metadata={
            "source_type": task_context.source_type,
            "language": task_context.language,
            "case_generation": {
                "api_scenario_count": api_scenario_count,
                "scenario_count": len(dsl_scenarios),
                "parsed_entities": parsed_requirement.get("entities", []),
            },
        },
    )
    return payload.to_dict()


def _build_step_payload(
    scenario: ScenarioModel,
    step: dict,
    index: int,
    task_context: TaskContext,
    parsed_requirement: dict,
    scenario_state: dict,
    enable_api_enrichment: bool,
    enable_assertion_enhancement: bool | None,
) -> tuple[dict, list[dict | str], list[str], dict[str, str], dict]:
    scenario_assertions = [str(item) for item in (scenario.assertions or [])]
    if (
        not enable_api_enrichment
        or step.get("type") == "given"
        or _is_expectation_step(step)
        or (
            _is_assertion_phase_step(scenario, index)
            and str(step.get("text", "")).strip() in scenario_assertions
        )
    ):
        fallback_assertions = _build_fallback_assertions(scenario, step)
        return {}, fallback_assertions, [], {}, {
            "llm_attempted": False,
            "fallback_reason": "",
            "invalid_assertion_count": 0,
            "generated_by_counts": {"rules": 0, "llm": 0, "llm_repair": 0, "manual": len(fallback_assertions)},
            "high_confidence_count": 0,
            "weak_assertion": True,
            "warning": "non_request_step",
        }

    intent = _infer_intent(step.get("text", ""))
    uses_context = _infer_uses_context(step.get("text", ""), intent, scenario_state)
    request = _build_request_template(step.get("text", ""), intent, parsed_requirement, uses_context)
    save_context = _build_save_context(step.get("text", ""), intent, request)
    request.pop("_matched_endpoint", None)
    planned = AssertionPlanner(
        task_context=task_context,
        parsed_requirement=parsed_requirement,
        scenario=scenario.to_dict(),
        step={
            "step_id": f"{scenario.scenario_id}_step_{index:02d}",
            "step_type": step.get("type", ""),
            "text": step.get("text", ""),
            "type": step.get("type", ""),
        },
        request=request,
        save_context=save_context,
        intent=intent,
        fallback_assertions=_build_fallback_assertions(scenario, step),
        enable_llm=enable_assertion_enhancement,
    ).build()
    return request, planned.assertions, uses_context, save_context, planned.quality


def _is_assertion_phase_step(scenario: ScenarioModel, index: int) -> bool:
    for position, candidate in enumerate(scenario.steps or [], start=1):
        candidate_type = ""
        if isinstance(candidate, dict):
            candidate_type = str(candidate.get("type", ""))
        else:
            candidate_type = str(getattr(candidate, "type", ""))
        if candidate_type.lower() == "then":
            return index >= position
    return False


def _is_api_scenario(scenario: ScenarioModel, parsed_requirement: dict, execution_mode: str) -> bool:
    if execution_mode == "api":
        return True
    text = " ".join(
        [
            scenario.name,
            scenario.goal,
            " ".join(scenario.preconditions),
            " ".join(step.text for step in scenario.steps),
            " ".join(parsed_requirement.get("actions", [])),
            " ".join(parsed_requirement.get("expected_results", [])),
        ]
    ).lower()
    return any(hint in text for hint in API_HINTS)


def _is_expectation_step(step: dict) -> bool:
    step_type = step.get("type")
    raw_text = step.get("text", "")
    text = raw_text.lower()
    if _STATUS_CODE_RE.search(raw_text):
        return True
    if step_type == "then":
        return True
    if _is_flow_summary_step(raw_text):
        return True
    if step_type != "and":
        return False
    if text.startswith("expected:"):
        return True
    return any(keyword in text for keyword in EXPECTATION_HINTS) and not any(
        keyword in text for keyword in QUERY_HINTS + AUTH_HINTS + CREATE_HINTS
    )


def _infer_intent(text: str) -> str:
    lowered = text.lower()
    if _is_flow_summary_step(text):
        return "action"
    explicit_match = _EXPLICIT_PATH_RE.search(text)
    if explicit_match:
        method = explicit_match.group(1).upper()
        if method == "GET":
            return "query"
        if method == "POST":
            if "/auth" in lowered or "/login" in lowered:
                return "login"
            return "create"
        if method == "PUT" or method == "PATCH":
            return "update"
        if method == "DELETE":
            return "delete"
    if any(keyword in lowered for keyword in LOGIN_HINTS):
        return "login"
    # CREATE_HINTS includes "post", which matches "POST /auth" and mis-classifies token/auth steps as create.
    if "/auth" in lowered or re.search(r"/\s*login\b", lowered):
        return "login"
    if any(keyword in lowered for keyword in CREATE_HINTS):
        return "create"
    if any(keyword in lowered for keyword in DELETE_HINTS):
        return "delete"
    if any(keyword in lowered for keyword in UPDATE_HINTS):
        return "update"
    if any(keyword in lowered for keyword in QUERY_HINTS):
        return "query"
    return "action"


def _is_flow_summary_step(text: str) -> bool:
    raw = str(text or "").strip()
    lowered = raw.lower()
    if not raw:
        return False
    if _EXPLICIT_PATH_RE.search(raw) or _BARE_PATH_RE.search(raw):
        return False
    if any(hint in lowered for hint in FLOW_SUMMARY_HINTS):
        return True
    if not any(hint in lowered for hint in VERIFICATION_HINTS):
        return False
    matched_classes = 0
    for keywords in (LOGIN_HINTS, CREATE_HINTS, QUERY_HINTS, UPDATE_HINTS, DELETE_HINTS):
        if any(keyword in lowered for keyword in keywords):
            matched_classes += 1
    return matched_classes >= 2


def _infer_uses_context(text: str, intent: str, scenario_state: dict) -> list[str]:
    lowered = text.lower()
    saved_context = scenario_state.get("saved_context", set())
    uses_context: list[str] = []
    if any(keyword in lowered for keyword in PREVIOUS_CONTEXT_HINTS):
        if "task_id" in saved_context:
            uses_context.append("task_id")
        if "access_token" in saved_context:
            uses_context.append("access_token")
        if "refresh_token" in saved_context:
            uses_context.append("refresh_token")
        if "token" in saved_context:
            uses_context.append("token")
        if "resource_id" in saved_context:
            uses_context.append("resource_id")
        if "order_id" in saved_context:
            uses_context.append("order_id")
        if "pet_id" in saved_context:
            uses_context.append("pet_id")
        if "username" in saved_context:
            uses_context.append("username")
        if "booking_id" in saved_context:
            uses_context.append("booking_id")
        if "todo_id" in saved_context:
            uses_context.append("todo_id")
        if "challenger_guid" in saved_context:
            uses_context.append("challenger_guid")
        if "auth_token" in saved_context:
            uses_context.append("auth_token")
        if "session_id" in saved_context:
            uses_context.append("session_id")
    if "task_id" in saved_context and ("task_id" in lowered or "{task_id}" in text):
        uses_context.append("task_id")
    if "access_token" in saved_context and ("access_token" in lowered or "bearer" in lowered or "auth/me" in lowered):
        uses_context.append("access_token")
    if "refresh_token" in saved_context and ("refresh_token" in lowered or "refresh" in lowered):
        uses_context.append("refresh_token")
    if "order_id" in saved_context and ("order_id" in lowered or "{orderid}" in lowered or "{order_id}" in text):
        uses_context.append("order_id")
    if "pet_id" in saved_context and ("pet_id" in lowered or "{petid}" in lowered or "{pet_id}" in text):
        uses_context.append("pet_id")
    if "username" in saved_context and ("username" in lowered or "{username}" in text):
        uses_context.append("username")
    if "booking_id" in saved_context and ("booking_id" in lowered or "{booking_id}" in text):
        uses_context.append("booking_id")
    if "todo_id" in saved_context and ("todo_id" in lowered or "{todo_id}" in text or "{id}" in text):
        uses_context.append("todo_id")
    if "challenger_guid" in saved_context and ("challenger_guid" in lowered or "{guid}" in text or "challenger" in lowered):
        uses_context.append("challenger_guid")
    if "challenger_guid" in saved_context and not re.search(r"\bpost\s+/challenger\b", lowered):
        uses_context.append("challenger_guid")
    if intent == "query" and "token" in saved_context and (
        "profile" in lowered or "鉴权" in text or "protected" in lowered
    ):
        uses_context.append("token")
    if "auth_token" in saved_context and ("auth_token" in lowered or "secret" in lowered or "token" in lowered):
        uses_context.append("auth_token")
    if "access_token" in saved_context and ("token" in lowered or "bearer" in lowered):
        uses_context.append("access_token")
    if "token" in saved_context and ("token" in lowered or "cookie" in lowered):
        uses_context.append("token")
    if any(keyword in lowered for keyword in SESSION_HINTS) and "session_id" in saved_context:
        uses_context.append("session_id")
    if intent in {"query", "update", "delete"} and "resource_id" in saved_context and _resource_needs_identifier(text):
        uses_context.append("resource_id")
    return sorted(set(uses_context))


def _build_request_template(text: str, intent: str, parsed_requirement: dict, uses_context: list[str]) -> dict:
    resource_name, resource_path, explicit_method = _infer_resource_with_method(text, parsed_requirement, intent)
    if _is_generic_unknown_resource(resource_name, resource_path, explicit_method, parsed_requirement):
        return {}
    lowered = text.lower()
    headers: dict[str, str] = {}
    params: dict[str, object] = {}
    json_body: dict[str, object] | None = None
    form_body: dict[str, object] | None = None
    method = "POST"
    url = resource_path
    auth: dict[str, object] | None = None
    cookies: dict[str, str] | None = None
    matched_endpoint: dict | None = None

    if intent == "login":
        method = "POST"
        url = "/login" if resource_name != "session" else "/session"
        credentials = _extract_body_fields(parsed_requirement, text, resource_path, method, intent)
        credentials = _merge_extracted_with_known_body(credentials, method, resource_path)
        if not credentials:
            credentials = {"username": "demo_user", "password": "demo_pass"}
        if any(keyword in lowered for keyword in FORM_HINTS):
            form_body = credentials
        else:
            json_body = credentials
        if resource_name == "session":
            if form_body is not None:
                form_body = {"name": "demo-user"}
            else:
                json_body = {"name": "demo-user"}
    elif intent == "create":
        method = "POST"
        extracted = _extract_body_fields(parsed_requirement, text, resource_path, method, intent)
        merged = _merge_extracted_with_known_body(extracted, method, resource_path)
        if merged:
            json_body = merged
        else:
            known = _known_endpoint_body(method, resource_path)
            if known is not None:
                json_body = known if known else None
            elif resource_name == "order":
                json_body = {"sku": "demo-sku", "quantity": 1}
            else:
                safe_name = resource_path.strip("/").split("/")[-1] or "resource"
                json_body = {"name": f"{safe_name}-demo"}
    elif intent == "query":
        method = "GET"
        identifier_context = _identifier_context_for_path(resource_path, uses_context)
        if identifier_context and _resource_needs_identifier(text):
            url = _apply_identifier_to_path(resource_path, identifier_context)
        elif any(keyword in lowered for keyword in ("list", "search", "query", "查询", "列表")):
            params = {"page": 1, "size": 20}
    elif intent == "update":
        method = "PUT"
        identifier_context = _identifier_context_for_path(resource_path, uses_context)
        if identifier_context:
            url = _apply_identifier_to_path(resource_path, identifier_context)
        extracted = _extract_body_fields(parsed_requirement, text, resource_path, method, intent)
        merged = _merge_extracted_with_known_body(extracted, method, resource_path)
        if merged:
            json_body = merged
        else:
            known = _known_endpoint_body(method, resource_path)
            if known is not None:
                json_body = known if known else None
            else:
                safe_name = resource_path.strip("/").split("/")[-1] or "resource"
                json_body = {"name": f"{safe_name}-updated"}
    elif intent == "delete":
        method = "DELETE"
        identifier_context = _identifier_context_for_path(resource_path, uses_context)
        if identifier_context:
            url = _apply_identifier_to_path(resource_path, identifier_context)
    else:
        method = "POST"
        json_body = {"input": text[:60]}

    if explicit_method:
        if explicit_method != "ANY":
            method = explicit_method
        url = resource_path  # explicit endpoint overrides hardcoded intent URL
        url = _normalize_path_placeholders(url, uses_context)
        if intent == "update":
            extracted = _extract_body_fields(parsed_requirement, text, resource_path, method, intent)
            merged = _merge_extracted_with_known_body(extracted, method, resource_path)
            if merged:
                json_body = merged
            else:
                known = _known_endpoint_body(method, resource_path)
                if known is not None:
                    json_body = known if known else None
    url = _apply_preloaded_identifier_defaults(url, parsed_requirement, uses_context)
    url = _apply_parameterized_path_defaults(url)
    matched_endpoint = _find_endpoint_spec(parsed_requirement, method, url)
    headers.update(_context_headers_for_request(url, uses_context))
    headers.update(_infer_fixed_headers(parsed_requirement, url, method, text))
    params.update(_infer_request_params(parsed_requirement, url, method, text))
    if _requires_basic_auth(text, matched_endpoint, parsed_requirement=parsed_requirement, method=method, path=url):
        auth = {"type": "basic", "username": "admin", "password": "password123"}
    if _requires_token_cookie(text, matched_endpoint, parsed_requirement=parsed_requirement, method=method, path=url):
        cookies = {"token": "{{token}}"}
    if cookies is None and "token" in uses_context and _canonicalize_endpoint_path(url).startswith("/booking/") and method in {"PUT", "PATCH", "DELETE"}:
        cookies = {"token": "{{token}}"}
    if cookies is not None:
        auth = None

    if any(keyword in lowered for keyword in BASIC_AUTH_HINTS):
        auth = {"type": "basic", "username": "demo", "password": "secret"}
    elif cookies is None and auth is None and intent != "login" and (
        "access_token" in uses_context
        or any(keyword in lowered for keyword in ("bearer", "token", "令牌"))
        or any(str(dep).lower() in {"accesstoken", "access_token"} for dep in ((matched_endpoint or {}).get("depends_on") or []))
    ):
        auth = {"type": "bearer", "token_context": "access_token" if "access_token" in uses_context else "token"}
    if "session_id" in uses_context:
        cookies = {"session_id": "{{session_id}}"}

    request = {"method": method, "url": url}
    matched_endpoint = _find_endpoint_spec(parsed_requirement, method, url)
    if matched_endpoint is not None:
        # internal planning hint (used by save_context/assertion shaping)
        request["_matched_endpoint"] = matched_endpoint
    if headers:
        request["headers"] = headers
    if params:
        request["params"] = params
    if json_body is not None and method not in {"GET", "DELETE"}:
        request["json"] = json_body
    if form_body is not None and method not in {"GET", "DELETE"}:
        request["data"] = form_body
    if auth is not None:
        request["auth"] = auth
    if cookies is not None:
        request["cookies"] = cookies
    if str(url).endswith("/parse"):
        request["timeout"] = 180
    return request


def _is_generic_unknown_resource(
    resource_name: str,
    resource_path: str,
    explicit_method: str | None,
    parsed_requirement: dict,
) -> bool:
    if explicit_method:
        return False
    if parsed_requirement.get("api_endpoints"):
        return False
    return resource_name == "resource" and resource_path == "/resource"


def _extract_body_fields(
    parsed_requirement: dict,
    step_text: str,
    endpoint_path: str,
    method: str,
    intent: str,
) -> dict[str, object]:
    corpus = [step_text]
    corpus.extend(parsed_requirement.get("actions", []))
    corpus.extend(parsed_requirement.get("expected_results", []))
    corpus.extend(parsed_requirement.get("constraints", []))
    candidates: list[str] = []
    for sentence in corpus:
        lowered = sentence.lower()
        if "字段" not in sentence and "field" not in lowered and "参数" not in sentence:
            continue
        if _sentence_matches_endpoint(sentence, endpoint_path, method):
            candidates.append(sentence)
            continue
        if intent == "login" and ("login" in lowered or "登录" in sentence):
            candidates.append(sentence)
    if not candidates:
        return {}

    ordered_fields: list[str] = []
    for sentence in candidates:
        fields = _extract_field_names_from_sentence(sentence)
        for field in fields:
            if field not in ordered_fields:
                ordered_fields.append(field)
    if not ordered_fields:
        return {}

    values: dict[str, object] = {}
    for field in ordered_fields[:8]:
        lowered = field.lower()
        if lowered in {"nickname", "nick_name"}:
            values[field] = "demo_nickname"
        elif lowered in {"avatar", "avatar_url"}:
            values[field] = "https://example.com/avatar.png"
        elif lowered in {"use_llm", "rag_enabled", "rerank_enabled"}:
            values[field] = False
        elif lowered in {"retrieval_top_k"}:
            values[field] = 5
        elif lowered in {"source_type"}:
            values[field] = "text"
        elif lowered in {"environment"}:
            values[field] = "test"
        elif lowered in {"task_name"}:
            values[field] = "demo_task_name"
        elif lowered in {"requirement_text"}:
            values[field] = "demo requirement text"
        elif lowered in {"execution_mode"}:
            values[field] = "api"
        else:
            values[field] = _default_value_for_field(field)
    if not values:
        return values
    endpoint_hints = _extract_endpoint_field_hints(parsed_requirement, endpoint_path, method)
    for field in endpoint_hints:
        if field not in values and len(values) < 10:
            values[field] = _default_value_for_field(field)
    return values


def _extract_field_names_from_sentence(sentence: str) -> list[str]:
    names: list[str] = []
    for groups in _FIELD_TOKEN_RE.findall(sentence):
        token = next((item for item in groups if item), "").strip()
        if token and token.lower() not in _FIELD_STOPWORDS and token not in names:
            names.append(token)
    if names:
        return names

    for match in _FIELD_LIST_RE.findall(sentence):
        for token in re.split(r"[,\s、，和]+|and", match):
            normalized = token.strip()
            if not normalized:
                continue
            if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", normalized):
                continue
            if normalized.lower() in _FIELD_STOPWORDS:
                continue
            if normalized.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            if normalized not in names:
                names.append(normalized)
    return names


def _extract_endpoint_field_hints(parsed_requirement: dict, endpoint_path: str, method: str) -> list[str]:
    hints: list[str] = []
    corpus = []
    corpus.extend(parsed_requirement.get("actions", []))
    corpus.extend(parsed_requirement.get("expected_results", []))
    corpus.extend(parsed_requirement.get("constraints", []))
    for sentence in corpus:
        if not _sentence_matches_endpoint(str(sentence), endpoint_path, method):
            continue
        for field in _extract_field_names_from_sentence(str(sentence)):
            if field not in hints:
                hints.append(field)
    return hints


def _default_value_for_field(field: str) -> object:
    lowered = str(field or "").strip().lower()
    if lowered in {"username", "user_name"}:
        return "demo_user"
    if lowered in {"password", "passwd", "pwd"}:
        return "demo_pass"
    if lowered in {"first_name", "firstname"}:
        return "Demo"
    if lowered in {"last_name", "lastname"}:
        return "User"
    if lowered == "email":
        return "demo@example.com"
    if lowered in {"phone", "mobile"}:
        return "13800000000"
    if lowered in {"name", "pet_name"}:
        return "demo_name"
    if lowered == "title":
        return "write API test"
    if lowered == "body":
        return "created by automated test"
    if lowered in {"quantity", "count"}:
        return 1
    if lowered in {"id", "order_id", "pet_id", "userid", "user_id", "petid"}:
        return 10001
    if lowered == "photourls":
        return ["https://example.com/pet.png"]
    if lowered == "status":
        return "available"
    if lowered == "complete":
        return False
    if lowered == "shipdate":
        return "2026-04-17T10:00:00.000Z"
    if lowered == "userstatus":
        return 0
    if lowered in {"category", "tag", "tags"}:
        return [{"id": 1, "name": "demo-tag"}] if lowered == "tags" else {"id": 1, "name": "demo-category"}
    if lowered in {"api_key", "apikey"}:
        return "special-key"
    return f"demo_{lowered}"


def _normalize_endpoint_path(path: str) -> str:
    normalized = (path or "").strip()
    if not normalized:
        return ""
    if "://" in normalized:
        after = normalized.split("://", 1)[1]
        slash = after.find("/")
        normalized = after[slash:] if slash >= 0 else "/"
    if normalized != "/" and normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def _canonical_placeholder_name(name: str) -> str:
    lowered = str(name or "").strip().lower()
    if lowered == "id":
        return "resource_id"
    for canonical, aliases in _IDENTIFIER_ALIASES.items():
        if lowered in aliases:
            return canonical
    return lowered


def _canonicalize_endpoint_path(path: str) -> str:
    normalized = _normalize_endpoint_path(path)
    if not normalized:
        return normalized
    query = ""
    if "?" in normalized:
        normalized, query = normalized.split("?", 1)

    def repl(match: re.Match[str]) -> str:
        return "{" + _canonical_placeholder_name(match.group(1)) + "}"

    canonical = _PLACEHOLDER_RE.sub(repl, normalized)
    canonical = canonical.replace("/booking/{resource_id}", "/booking/{booking_id}")
    canonical = canonical.replace("/todos/{resource_id}", "/todos/{todo_id}")
    canonical = canonical.replace("/tasks/{resource_id}", "/tasks/{task_id}")
    return canonical if not query else f"{canonical}?{query}"


def _sentence_matches_endpoint(sentence: str, endpoint_path: str, method: str) -> bool:
    expected_path = _canonicalize_endpoint_path(endpoint_path)
    expected_method = (method or "").upper().strip()
    if not expected_path:
        return False

    explicit_endpoints = [(m.group(1).upper(), _canonicalize_endpoint_path(m.group(2))) for m in _EXPLICIT_PATH_RE.finditer(sentence)]
    if explicit_endpoints:
        return any(m == expected_method and p == expected_path for m, p in explicit_endpoints)

    bare_paths = [_canonicalize_endpoint_path(m.group(1)) for m in _BARE_PATH_RE.finditer(sentence)]
    return any(path == expected_path for path in bare_paths)


def _find_endpoint_spec(parsed_requirement: dict, method: str, path: str) -> dict | None:
    normalized_method = str(method or "").upper().strip()
    normalized_path = _canonicalize_endpoint_path(path)
    if not normalized_method or not normalized_path:
        return None
    for endpoint in parsed_requirement.get("api_endpoints") or []:
        ep_method = str(endpoint.get("method", "")).upper().strip()
        ep_path = _canonicalize_endpoint_path(str(endpoint.get("path", "")))
        if ep_method == normalized_method and ep_path == normalized_path:
            return endpoint
    return None


def _requires_token_cookie(
    step_text: str,
    endpoint: dict | None,
    *,
    parsed_requirement: dict | None = None,
    method: str = "",
    path: str = "",
) -> bool:
    lowered = str(step_text or "").lower()
    if "cookie" in lowered and "token" in lowered:
        return True
    candidates: list[dict] = []
    if endpoint:
        candidates.append(endpoint)
    if parsed_requirement:
        target_method = str(method or "").upper().strip()
        target_path = _canonicalize_endpoint_path(path)
        for item in parsed_requirement.get("api_endpoints") or []:
            ep_method = str(item.get("method", "")).upper().strip()
            ep_path = _canonicalize_endpoint_path(str(item.get("path", "")))
            if ep_method == target_method and ep_path == target_path:
                candidates.append(item)

    for candidate in candidates:
        for field in candidate.get("request_body_fields") or []:
            name = str(field.get("name", "") if isinstance(field, dict) else field).lower()
            if "cookie" in name:
                return True
        description = str(candidate.get("description", "")).lower()
        if "cookie" in description and "token" in description:
            return True

    if parsed_requirement:
        target_path = _canonicalize_endpoint_path(path)
        target_method = str(method or "").upper().strip()
        corpus = []
        corpus.extend(parsed_requirement.get("actions", []))
        corpus.extend(parsed_requirement.get("expected_results", []))
        corpus.extend(parsed_requirement.get("constraints", []))
        for sentence in corpus:
            lowered_sentence = str(sentence).lower()
            if "cookie" not in lowered_sentence or "token" not in lowered_sentence:
                continue
            if _sentence_matches_endpoint(str(sentence), target_path, target_method):
                return True
    return False


def _requires_basic_auth(
    step_text: str,
    endpoint: dict | None,
    *,
    parsed_requirement: dict | None = None,
    method: str = "",
    path: str = "",
) -> bool:
    lowered = str(step_text or "").lower()
    if any(keyword in lowered for keyword in BASIC_AUTH_HINTS):
        return True
    candidates: list[dict] = []
    if endpoint:
        candidates.append(endpoint)
    if parsed_requirement:
        target_method = str(method or "").upper().strip()
        target_path = _canonicalize_endpoint_path(path)
        for item in parsed_requirement.get("api_endpoints") or []:
            ep_method = str(item.get("method", "")).upper().strip()
            ep_path = _canonicalize_endpoint_path(str(item.get("path", "")))
            if ep_method == target_method and ep_path == target_path:
                candidates.append(item)

    for candidate in candidates:
        description = str(candidate.get("description", "")).lower()
        if "basic auth" in description or "basic authentication" in description:
            return True

    if _canonicalize_endpoint_path(path).startswith("/basic-auth/"):
        return True
    if _canonicalize_endpoint_path(path) == "/secret/token":
        return True
    if _canonicalize_endpoint_path(path).startswith("/booking/") and str(method or "").upper().strip() in {"PUT", "PATCH", "DELETE"}:
        return True
    if parsed_requirement:
        target_path = _canonicalize_endpoint_path(path)
        target_method = str(method or "").upper().strip()
        corpus = []
        corpus.extend(parsed_requirement.get("actions", []))
        corpus.extend(parsed_requirement.get("expected_results", []))
        corpus.extend(parsed_requirement.get("constraints", []))
        for sentence in corpus:
            lowered_sentence = str(sentence).lower()
            if "basic auth" not in lowered_sentence and "admin/password" not in lowered_sentence:
                continue
            if _sentence_matches_endpoint(str(sentence), target_path, target_method):
                return True
    return False


_INTENT_METHOD_MAP: dict[str, str] = {
    "login": "POST",
    "create": "POST",
    "query": "GET",
    "update": "PUT",
    "delete": "DELETE",
    "action": "POST",
}


def _match_endpoint(text: str, intent: str, endpoints: list[dict]) -> dict | None:
    """Pick the best matching endpoint from a list by intent + path keyword."""
    if not endpoints:
        return None
    expected_method = _INTENT_METHOD_MAP.get(intent, "POST")
    lowered = text.lower()
    path_segments = lambda ep: [s for s in ep.get("path", "").lower().split("/") if s]

    explicit_in_text = [(m.group(1).upper(), _canonicalize_endpoint_path(m.group(2))) for m in _EXPLICIT_PATH_RE.finditer(text)]
    if explicit_in_text:
        for method, path in explicit_in_text:
            for ep in endpoints:
                ep_method = str(ep.get("method", "")).upper()
                ep_path = _canonicalize_endpoint_path(str(ep.get("path", "")))
                if ep_path != path:
                    continue
                if ep_method == method or method == "ANY" or ep_method == "ANY":
                    return ep

    # Pass 1: method match + any path segment appears in step text
    for ep in endpoints:
        if ep.get("method", "").upper() == expected_method:
            if any(seg in lowered for seg in path_segments(ep)):
                return ep

    # Pass 2: method match only
    for ep in endpoints:
        if ep.get("method", "").upper() == expected_method:
            return ep

    # Pass 3: path keyword match regardless of method
    for ep in endpoints:
        if any(seg in lowered for seg in path_segments(ep)):
            return ep

    return endpoints[0]


def _infer_resource_with_method(text: str, parsed_requirement: dict, intent: str = "action") -> tuple[str, str, str | None]:
    """Return (resource_name, path, explicit_method_or_None)."""
    endpoints = [ep for ep in (parsed_requirement.get("api_endpoints") or []) if ep.get("path")]
    if endpoints:
        ep = _match_endpoint(text, intent, endpoints)
        if ep:
            method = str(ep.get("method") or "").strip().upper() or None
            desc = str(ep.get("description") or ep.get("path", ""))
            return desc, str(ep["path"]), method

    m = _EXPLICIT_PATH_RE.search(text)
    if m:
        return "resource", m.group(2), m.group(1).upper()

    m = _BARE_PATH_RE.search(text)
    if m:
        return "resource", m.group(1), None

    corpus = " ".join([text, " ".join(parsed_requirement.get("entities", [])), " ".join(parsed_requirement.get("actions", []))]).lower()
    for resource_name, candidates in RESOURCE_ALIASES:
        for candidate in candidates:
            if candidate.lower() in corpus:
                return resource_name, candidates[0], None
    return "resource", "/resource", None


def _infer_resource(text: str, parsed_requirement: dict) -> tuple[str, str]:
    # 1. Explicit endpoints extracted by LLM from the requirement document
    for ep in parsed_requirement.get("api_endpoints") or []:
        path = str(ep.get("path") or "").strip()
        if path:
            desc = str(ep.get("description") or path)
            return desc, path

    # 2. Explicit "METHOD /path" pattern in the step text
    m = _EXPLICIT_PATH_RE.search(text)
    if m:
        return "resource", m.group(2)

    # 3. Bare path pattern (e.g. /api/login) in the step text
    m = _BARE_PATH_RE.search(text)
    if m:
        return "resource", m.group(1)

    # 4. Keyword-based fallback
    corpus = " ".join([text, " ".join(parsed_requirement.get("entities", [])), " ".join(parsed_requirement.get("actions", []))]).lower()
    for resource_name, candidates in RESOURCE_ALIASES:
        for candidate in candidates:
            if candidate.lower() in corpus:
                return resource_name, candidates[0]
    return "resource", "/resource"


def _resource_needs_identifier(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ("detail", "详情", "id", "single", "one", "指定"))


def _identifier_context_for_path(path: str, uses_context: list[str]) -> str | None:
    canonical_path = _canonicalize_endpoint_path(path)
    placeholders = [match.group(1) for match in _PLACEHOLDER_RE.finditer(canonical_path)]
    for candidate in ("username", "order_id", "pet_id", "booking_id", "todo_id", "challenger_guid", "task_id", "session_id", "resource_id"):
        if candidate in placeholders and candidate in uses_context:
            return candidate
    lowered_path = canonical_path.lower()
    if lowered_path.startswith("/booking/") and "booking_id" in uses_context:
        return "booking_id"
    if lowered_path.startswith("/todos/") and "todo_id" in uses_context:
        return "todo_id"
    if lowered_path.startswith("/tasks/") and "task_id" in uses_context:
        return "task_id"
    if lowered_path.startswith("/store/order/") and "order_id" in uses_context:
        return "order_id"
    if lowered_path.startswith("/pet/") and "pet_id" in uses_context:
        return "pet_id"
    if "username" in uses_context:
        return "username"
    if "order_id" in uses_context:
        return "order_id"
    if "pet_id" in uses_context:
        return "pet_id"
    if "booking_id" in uses_context:
        return "booking_id"
    if "todo_id" in uses_context:
        return "todo_id"
    if "challenger_guid" in uses_context:
        return "challenger_guid"
    if "task_id" in uses_context:
        return "task_id"
    if "resource_id" in uses_context:
        return "resource_id"
    return None


def _apply_identifier_to_path(path: str, identifier_context: str) -> str:
    normalized_path = str(path or "").strip()
    if not normalized_path:
        return normalized_path
    if "{" in normalized_path or "}" in normalized_path:
        return normalized_path
    return normalized_path.rstrip("/") + f"/{{{{{identifier_context}}}}}"


def _context_headers_for_request(path: str, uses_context: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    lowered_path = _canonicalize_endpoint_path(path).lower()
    if "challenger_guid" in uses_context and lowered_path != "/challenger":
        headers["X-CHALLENGER"] = "{{challenger_guid}}"
    if "auth_token" in uses_context and lowered_path.startswith("/secret/") and lowered_path != "/secret/token":
        headers["X-AUTH-TOKEN"] = "{{auth_token}}"
    return headers


def _infer_fixed_headers(parsed_requirement: dict, path: str, method: str, text: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    target_path = _canonicalize_endpoint_path(path)
    target_method = str(method or "").upper().strip()
    corpus = [str(text or "")]
    corpus.extend(str(item or "") for item in (parsed_requirement.get("constraints") or []))
    corpus.extend(str(item or "") for item in (parsed_requirement.get("expected_results") or []))
    corpus.extend(str(item or "") for item in (parsed_requirement.get("actions") or []))
    haystack = "\n".join(corpus).lower()
    if (
        target_path.startswith("/pet")
        and "api_key" in haystack
        and "special-key" in haystack
        and target_method in {"POST", "GET", "DELETE", "PUT"}
    ):
        headers["api_key"] = "special-key"
    return headers


def _infer_request_params(parsed_requirement: dict, path: str, method: str, text: str) -> dict[str, object]:
    params: dict[str, object] = {}
    target_path = _canonicalize_endpoint_path(path)
    target_method = str(method or "").upper().strip()
    endpoint = _find_endpoint_spec(parsed_requirement, target_method, target_path)
    corpus = [str(text or "")]
    corpus.extend(str(item or "") for item in (parsed_requirement.get("constraints") or []))
    corpus.extend(str(item or "") for item in (parsed_requirement.get("expected_results") or []))
    corpus.extend(str(item or "") for item in (parsed_requirement.get("actions") or []))
    for endpoint_item in parsed_requirement.get("api_endpoints") or []:
        if not isinstance(endpoint_item, dict):
            continue
        corpus.extend(
            str(endpoint_item.get(field) or "")
            for field in ("path", "description", "group")
        )
    joined = "\n".join(corpus).lower()
    if target_path == "/user/login":
        params["username"] = "demo_user"
        params["password"] = "demo_pass"
    elif target_path == "/cookies/set":
        if any(token in joined for token in ("query", "cookie 键值", "cookie键值", "name=value", "/cookies/set?name=value")):
            params["name"] = "value"
    elif target_method == "GET" and "?" in target_path and not params:
        query = target_path.split("?", 1)[1]
        for part in query.split("&"):
            key, _, value = part.partition("=")
            canonical = _canonical_placeholder_name(value.strip("{}")) if value else ""
            if key and canonical:
                if canonical in {"resource_id", "booking_id", "todo_id", "task_id", "order_id", "pet_id"}:
                    params[key] = 1
                elif canonical == "username":
                    params[key] = "demo_user"
    if target_path == "/pet/findByStatus" and ("status" in joined or "available" in joined):
        params["status"] = "available"
    if endpoint is not None:
        for field in endpoint.get("request_body_fields") or []:
            name = str(field.get("name", "") if isinstance(field, dict) else field).strip()
            if not name:
                continue
            lowered = name.lower()
            if lowered in {"username", "password", "status"} and name not in params:
                params[name] = _default_value_for_field(name)
    return params


def _requirement_has_preloaded_resource_signal(parsed_requirement: dict, resource_path: str) -> bool:
    normalized_path = _canonicalize_endpoint_path(resource_path).lower()
    resource_tokens = [segment for segment in normalized_path.split("/") if segment and "{" not in segment and "}" not in segment]
    haystack_parts: list[str] = []
    for key in ("expected_results", "constraints", "preconditions", "actions"):
        haystack_parts.extend(str(item or "") for item in (parsed_requirement.get(key) or []))
    for endpoint in parsed_requirement.get("api_endpoints") or []:
        haystack_parts.extend(str((endpoint or {}).get(field, "")) for field in ("path", "description", "group"))
    haystack = " ".join(part for part in haystack_parts if part).lower()
    preload_hints = ("preloaded", "pre-existing", "preexisting", "preset", "预置", "官方预置", "已存在", "建议使用", "默认使用")
    return any(token and token in haystack for token in resource_tokens) and any(hint in haystack for hint in preload_hints)


def _apply_preloaded_identifier_defaults(path: str, parsed_requirement: dict, uses_context: list[str]) -> str:
    normalized = _normalize_path_placeholders(path, uses_context)
    if "{{" not in normalized or _identifier_context_for_path(path, uses_context):
        return normalized
    canonical_path = _canonicalize_endpoint_path(normalized)
    explicit_defaults = {
        "/todos/{todo_id}": "1",
        "/todos/{resource_id}": "1",
        "/todos/user/{user_id}": "5",
        "/todos/user/{resource_id}": "5",
    }
    if canonical_path in explicit_defaults:
        return _PLACEHOLDER_RE.sub(explicit_defaults[canonical_path], normalized)
    if "?" not in normalized and not _requirement_has_preloaded_resource_signal(parsed_requirement, path):
        return normalized

    def repl(match: re.Match[str]) -> str:
        canonical = _canonical_placeholder_name(match.group(1))
        if canonical in {"resource_id", "booking_id", "todo_id", "task_id"}:
            return "1"
        return "{{" + canonical + "}}"

    return _PLACEHOLDER_RE.sub(repl, normalized)


def _apply_parameterized_path_defaults(path: str) -> str:
    normalized = str(path or "")
    if not normalized:
        return normalized
    canonical_path = _canonicalize_endpoint_path(normalized).lower()
    explicit_defaults = {
        "/status/{code}": {"code": "200"},
        "/delay/{n}": {"n": "1"},
        "/redirect/{n}": {"n": "1"},
        "/basic-auth/{user}/{passwd}": {"user": "admin", "passwd": "password123"},
    }
    defaults = explicit_defaults.get(canonical_path)

    def repl(match: re.Match[str]) -> str:
        raw_name = match.group(1)
        lowered = raw_name.lower()
        if defaults and lowered in defaults:
            return defaults[lowered]
        generic_defaults = {
            "code": "200",
            "status": "200",
            "n": "1",
            "count": "1",
            "page": "1",
            "user": "admin",
            "username": "demo_user",
            "passwd": "password123",
            "password": "password123",
        }
        return generic_defaults.get(lowered, match.group(0))

    return _PLACEHOLDER_RE.sub(repl, normalized)


def _build_save_context(text: str, intent: str, request: dict) -> dict[str, str]:
    lowered = text.lower()
    request_url = str(request.get("url", ""))
    request_method = str(request.get("method", "")).upper()

    def _candidate_endpoint() -> dict | None:
        return request.get("_matched_endpoint") if isinstance(request.get("_matched_endpoint"), dict) else None

    def _field_names_from_endpoint(ep: dict | None) -> list[str]:
        if not ep:
            return []
        fields = ep.get("response_fields") or []
        names: list[str] = []
        for item in fields:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
            else:
                name = str(item).strip()
            if name:
                names.append(name)
        return names

    def _json_path_for_field(name: str) -> str:
        normalized = str(name or "").strip()
        if not normalized:
            return ""
        if normalized.startswith("json."):
            return normalized
        if "." in normalized:
            return f"json.{normalized}"
        if request_url.startswith("/api/"):
            return f"json.data.{normalized}"
        return f"json.{normalized}"

    def _best_identifier_source() -> str:
        endpoint = _candidate_endpoint()
        preferred = (
            "username",
            "orderid",
            "order_id",
            "petid",
            "pet_id",
            "bookingid",
            "booking_id",
            "token",
            "task_id",
            "order_id",
            "id",
        )
        endpoint_fields = {str(name).lower(): name for name in _field_names_from_endpoint(endpoint)}
        for key in preferred:
            if key in endpoint_fields:
                return _json_path_for_field(endpoint_fields[key])
        if request_url in {"/api/tasks", "/tasks"}:
            return "json.data.task_id"
        if request_url.endswith("/booking"):
            return "json.bookingid"
        if request_url.endswith("/auth"):
            return "json.token"
        if request_url.endswith("/user"):
            return "request.json.username"
        if request_url.endswith("/store/order"):
            return "request.json.id"
        if request_url.endswith("/pet"):
            return "request.json.id"
        if "order" in lowered or request_url == "/orders":
            return "json.order_id"
        return ""

    if intent == "login":
        saved: dict[str, str] = {}
        if request_url.endswith("/auth/login"):
            saved["access_token"] = "json.accessToken"
            saved["refresh_token"] = "json.refreshToken"
            return saved
        if request_url == "/session" or any(keyword in lowered for keyword in SESSION_HINTS):
            saved["session_id"] = "json.session_id"
        if request_url != "/session":
            saved["token"] = "json.token"
        return saved
    if intent == "create":
        if request_url == "/challenger" and request_method == "POST":
            return {"challenger_guid": "headers.x-challenger"}
        if request_url == "/secret/token" and request_method == "POST":
            return {"auth_token": "headers.x-auth-token"}
        if request_url.endswith("/auth/refresh") and request_method == "POST":
            return {"access_token": "json.accessToken", "refresh_token": "json.refreshToken"}
        if (
            "/parse" in request_url
            or "/execute" in request_url
            or "/execution/stop" in request_url
            or request_url.endswith("/scenarios/generate")
        ):
            return {}
        if request_url in {"/api/tasks", "/tasks"}:
            return {"task_id": "json.data.task_id", "resource_id": "json.data.task_id"}
        if request_url.endswith("/todos") and request_method == "POST":
            return {"todo_id": "json.id", "resource_id": "json.id"}
        identifier = _best_identifier_source()
        if identifier:
            if request_url.endswith("/user") and request_method == "POST":
                return {"username": identifier}
            if request_url.endswith("/store/order") and request_method == "POST":
                return {"order_id": identifier, "resource_id": identifier}
            if request_url.endswith("/pet") and request_method == "POST":
                return {"pet_id": identifier, "resource_id": identifier}
            if request_url.endswith("/booking") and request_method == "POST":
                return {"booking_id": identifier, "resource_id": identifier}
            return {"resource_id": identifier}
        if "order" in lowered or request_url == "/orders":
            return {"resource_id": "json.order_id"}
        return {}
    return {}


def _build_fallback_assertions(scenario: ScenarioModel, step: dict) -> list[dict | str]:
    if step.get("type") == "then":
        return scenario.assertions[:2]
    return []


def _normalize_path_placeholders(path: str, uses_context: list[str]) -> str:
    normalized = str(path or "")
    if not normalized:
        return normalized
    canonical_path = _canonicalize_endpoint_path(normalized).lower()

    def repl(match: re.Match[str]) -> str:
        canonical = _canonical_placeholder_name(match.group(1))
        if canonical == "username" and "username" in uses_context:
            return "{{username}}"
        if canonical == "order_id" and "order_id" in uses_context:
            return "{{order_id}}"
        if canonical == "pet_id" and "pet_id" in uses_context:
            return "{{pet_id}}"
        if canonical == "task_id" and "task_id" in uses_context:
            return "{{task_id}}"
        if canonical == "booking_id" and "booking_id" in uses_context:
            return "{{booking_id}}"
        if canonical == "todo_id" and "todo_id" in uses_context:
            return "{{todo_id}}"
        if canonical == "challenger_guid" and "challenger_guid" in uses_context:
            return "{{challenger_guid}}"
        if canonical == "session_id" and "session_id" in uses_context:
            return "{{session_id}}"
        if canonical == "resource_id":
            if canonical_path.startswith("/booking/") and "booking_id" in uses_context:
                return "{{booking_id}}"
            if canonical_path.startswith("/todos/") and "todo_id" in uses_context:
                return "{{todo_id}}"
            if canonical_path.startswith("/tasks/") and "task_id" in uses_context:
                return "{{task_id}}"
            if canonical_path.startswith("/store/order/") and "order_id" in uses_context:
                return "{{order_id}}"
            if canonical_path.startswith("/pet/") and "pet_id" in uses_context:
                return "{{pet_id}}"
            if "resource_id" in uses_context:
                return "{{resource_id}}"
            if "booking_id" in uses_context:
                return "{{booking_id}}"
            if "todo_id" in uses_context:
                return "{{todo_id}}"
            if "challenger_guid" in uses_context:
                return "{{challenger_guid}}"
            if "task_id" in uses_context:
                return "{{task_id}}"
            if "order_id" in uses_context:
                return "{{order_id}}"
            if "pet_id" in uses_context:
                return "{{pet_id}}"
            if "username" in uses_context:
                return "{{username}}"
        return "{{" + canonical + "}}"

    return _PLACEHOLDER_RE.sub(repl, normalized)
