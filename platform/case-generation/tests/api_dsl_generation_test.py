"""API-oriented DSL generation tests for case-generation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


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


def _build_task_context():
    from platform_shared.models import TaskContext

    return TaskContext(
        task_id="task_api_dsl",
        task_name="API DSL Demo",
        source_type="text",
    )


def test_login_then_profile_query_generates_auth_context() -> None:
    from case_generation import build_scenarios, build_test_case_dsl
    from platform_shared.models import ScenarioModel
    from requirement_analysis import parse_requirement

    requirement_text = """
    # Authenticated profile API
    Precondition: test account already exists.
    1. Login via auth API with username and password.
    2. Query profile API with bearer token from previous response.
    Expected: profile API returns current user data.
    """
    parsed_requirement = parse_requirement(requirement_text)
    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    dsl = build_test_case_dsl(_build_task_context(), scenarios, parsed_requirement=parsed_requirement)

    assert dsl["dsl_version"] == "0.2.0"
    assert len(dsl["scenarios"]) == 1
    steps = dsl["scenarios"][0]["steps"]
    assert steps[1]["request"]["method"] == "POST"
    assert steps[1]["request"]["url"] == "/login"
    assert steps[1]["save_context"] == {"token": "json.token"}
    assert steps[1]["assertions"][0]["generated_by"] == "rules"
    assert "assertion_quality" in steps[1]
    assert steps[2]["uses_context"] == ["token"]
    assert steps[2]["request"]["auth"] == {"type": "bearer", "token_context": "token"}
    assert any(assertion["source"] == "status_code" for assertion in steps[2]["assertions"] if isinstance(assertion, dict))


def test_create_then_detail_query_generates_resource_dependency() -> None:
    from case_generation import build_scenarios, build_test_case_dsl
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "Create order and query order detail",
        "actors": ["user"],
        "entities": ["order", "detail"],
        "preconditions": ["User is authenticated"],
        "actions": [
            "Create order API with sku and quantity",
            "Get order detail API with order id from previous response",
        ],
        "expected_results": ["Order detail API returns the created order"],
        "constraints": [],
        "ambiguities": [],
        "source_chunks": [],
    }
    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    dsl = build_test_case_dsl(_build_task_context(), scenarios, parsed_requirement=parsed_requirement)

    assert len(dsl["scenarios"]) == 1
    steps = dsl["scenarios"][0]["steps"]
    assert steps[1]["request"]["method"] == "POST"
    assert steps[1]["request"]["url"] == "/orders"
    assert steps[1]["save_context"] == {"resource_id": "json.order_id"}
    assert steps[2]["uses_context"] == ["resource_id"]
    assert steps[2]["request"]["url"] == "/orders/{{resource_id}}"
    assert any(assertion["source"] == "json" for assertion in steps[2]["assertions"] if isinstance(assertion, dict))


def test_form_session_login_generates_cookie_and_context_dependency() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_001",
        name="form login then query profile",
        goal="Authenticate and fetch profile",
        steps=[
            ScenarioStep(type="given", text="Test account exists"),
            ScenarioStep(type="when", text="Login API with form and session"),
            ScenarioStep(type="and", text="Query profile API with bearer token and session from previous response"),
            ScenarioStep(type="then", text="Profile API returns current user data"),
        ],
        assertions=["Profile API returns current user data"],
        source_chunks=[],
        preconditions=["Test account exists"],
    )
    parsed_requirement = {
        "objective": "Authenticate and fetch profile",
        "actors": ["user"],
        "entities": ["profile", "session"],
        "preconditions": ["Test account exists"],
        "actions": [
            "Login API with form and session",
            "Query profile API with bearer token and session from previous response",
        ],
        "expected_results": ["Profile API returns current user data"],
        "constraints": [],
        "ambiguities": [],
        "source_chunks": [],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    steps = dsl["scenarios"][0]["steps"]

    assert steps[1]["request"]["data"] == {"username": "demo_user", "password": "demo_pass"}
    assert steps[1]["save_context"] == {"session_id": "json.session_id", "token": "json.token"}
    assert steps[2]["uses_context"] == ["session_id", "token"]
    assert steps[2]["request"]["auth"] == {"type": "bearer", "token_context": "token"}
    assert steps[2]["request"]["cookies"] == {"session_id": "{{session_id}}"}


def test_basic_auth_query_generates_query_request_instead_of_login() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_002",
        name="basic auth query",
        goal="Query profile with basic auth",
        steps=[
            ScenarioStep(type="given", text="Service is available"),
            ScenarioStep(type="when", text="Get profile API with basic auth credentials"),
            ScenarioStep(type="then", text="Profile API returns current user data"),
        ],
        assertions=["Profile API returns current user data"],
        source_chunks=[],
        preconditions=["Service is available"],
    )
    parsed_requirement = {
        "objective": "Query profile with basic auth",
        "actors": ["user"],
        "entities": ["profile"],
        "preconditions": ["Service is available"],
        "actions": ["Get profile API with basic auth credentials"],
        "expected_results": ["Profile API returns current user data"],
        "constraints": [],
        "ambiguities": [],
        "source_chunks": [],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    step = dsl["scenarios"][0]["steps"][1]

    assert step["request"]["method"] == "GET"
    assert step["request"]["url"] == "/profile"
    assert step["request"]["auth"] == {"type": "basic", "username": "demo", "password": "secret"}
    assert step["save_context"] == {}


def test_chinese_actions_keep_priority_and_dependency_grouping() -> None:
    from case_generation import build_scenarios, build_test_case_dsl
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "登录后查询订单详情",
        "actors": ["用户"],
        "entities": ["订单", "详情"],
        "preconditions": ["测试账号已存在"],
        "actions": [
            "登录接口获取 token",
            "使用上一步返回值查询订单详情接口",
        ],
        "expected_results": ["订单详情接口返回订单信息"],
        "constraints": [],
        "ambiguities": [],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    assert len(scenarios) == 1
    assert scenarios[0].priority == "P0"

    dsl = build_test_case_dsl(_build_task_context(), scenarios, parsed_requirement=parsed_requirement)
    steps = dsl["scenarios"][0]["steps"]

    assert steps[1]["save_context"] == {"token": "json.token"}
    assert steps[2]["uses_context"] == ["token"]
    assert steps[2]["request"]["method"] == "GET"
    assert steps[2]["request"]["url"] == "/orders"
    assert steps[2]["request"]["params"] == {"page": 1, "size": 20}


def test_api_endpoints_generate_independent_scenarios() -> None:
    from case_generation import build_scenarios
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "用户个人中心接口流程",
        "actors": ["用户"],
        "entities": ["profile"],
        "preconditions": ["测试账号存在且可登录"],
        "actions": [
            "调用 POST /api/login 获取 token",
            "调用 PUT /api/user/profile 更新昵称和头像",
        ],
        "expected_results": [
            "登录成功返回 200",
            "获取个人信息返回 200 并展示昵称头像",
            "更新个人信息返回 200 并刷新页面",
        ],
        "constraints": [],
        "ambiguities": [],
        "source_chunks": [],
        "api_endpoints": [
            {"method": "POST", "path": "/api/login", "description": "用户登录"},
            {"method": "GET", "path": "/api/user/profile", "description": "获取个人信息"},
            {"method": "PUT", "path": "/api/user/profile", "description": "更新个人信息"},
        ],
    }
    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]

    assert len(scenarios) == 3
    assert str(scenarios[0].steps[1]["text"]).lower().find("post /api/login") >= 0
    assert str(scenarios[1].steps[1]["text"]).lower().find("get /api/user/profile") >= 0
    assert str(scenarios[2].steps[1]["text"]).lower().find("put /api/user/profile") >= 0


def test_expectation_and_step_with_status_code_does_not_generate_request() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_003",
        name="update profile expectation",
        goal="Update profile and verify response code",
        steps=[
            ScenarioStep(type="given", text="用户已登录"),
            ScenarioStep(type="when", text="调用 PUT /api/user/profile 更新昵称"),
            ScenarioStep(type="and", text="返回 200 并刷新页面"),
            ScenarioStep(type="then", text="页面显示最新昵称"),
        ],
        assertions=["返回 200", "页面显示最新昵称"],
        source_chunks=[],
        preconditions=["用户已登录"],
    )
    parsed_requirement = {
        "objective": "Update profile",
        "actors": ["user"],
        "entities": ["profile"],
        "preconditions": ["用户已登录"],
        "actions": ["调用 PUT /api/user/profile 更新昵称"],
        "expected_results": ["返回 200 并刷新页面", "页面显示最新昵称"],
        "constraints": [],
        "ambiguities": [],
        "source_chunks": [],
        "api_endpoints": [{"method": "PUT", "path": "/api/user/profile", "description": "更新个人信息"}],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    steps = dsl["scenarios"][0]["steps"]
    assert steps[2]["request"] == {}
    assert steps[2]["assertions"] == []


def test_login_body_fields_are_extracted_from_requirement_text() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_004",
        name="login body fields",
        goal="Login with required fields",
        steps=[
            ScenarioStep(type="given", text="账号已创建"),
            ScenarioStep(type="when", text="调用 POST /api/auth/login"),
            ScenarioStep(type="then", text="登录成功"),
        ],
        assertions=["登录成功"],
        source_chunks=[],
        preconditions=["账号已创建"],
    )
    parsed_requirement = {
        "objective": "用户登录",
        "actors": ["user"],
        "entities": ["username", "password"],
        "preconditions": ["账号已创建"],
        "actions": ["调用 POST /api/auth/login，请求体包含 username 和 password 字段"],
        "expected_results": ["返回 200"],
        "constraints": [],
        "ambiguities": [],
        "source_chunks": [],
        "api_endpoints": [{"method": "POST", "path": "/api/auth/login", "description": "用户登录"}],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    login_step = dsl["scenarios"][0]["steps"][1]
    assert login_step["request"]["json"] == {"username": "demo_user", "password": "demo_pass"}


def test_httpbin_cookies_set_infers_default_query_params() -> None:
    from case_generation import build_scenarios, build_test_case_dsl
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "httpbin cookies",
        "actors": ["user"],
        "entities": ["cookie"],
        "preconditions": [],
        "actions": [
            "Scenario: Cookie 链路",
            "调用 GET /cookies/set",
            "调用 GET /cookies",
        ],
        "expected_results": [
            "/cookies/set 后再调用 /cookies 应能读到设置的 cookie",
        ],
        "constraints": [
            "请求语义：通过 query 传入 cookie 键值",
        ],
        "ambiguities": [],
        "source_chunks": [],
        "api_endpoints": [
            {"method": "GET", "path": "/cookies/set", "description": "设置 cookie"},
            {"method": "GET", "path": "/cookies", "description": "读取当前请求携带的 cookie"},
            {"method": "GET", "path": "/cookies/set?name=value", "description": "示例 query 写法"},
        ],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement, use_llm=False)]
    dsl = build_test_case_dsl(_build_task_context(), scenarios, parsed_requirement=parsed_requirement)
    cookie_steps = [
        step
        for scenario in dsl["scenarios"]
        for step in scenario["steps"]
        if step.get("request", {}).get("url") == "/cookies/set"
    ]

    assert cookie_steps
    assert all(step["request"].get("params") == {"name": "value"} for step in cookie_steps)


def test_create_task_request_uses_task_id_instead_of_generic_id() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_005",
        name="create task then parse task",
        goal="Create task and trigger parse endpoint",
        steps=[
            ScenarioStep(type="given", text="task center is available"),
            ScenarioStep(type="when", text="调用 POST /api/tasks 请求体包含 task_name、source_type、requirement_text、environment 字段"),
            ScenarioStep(type="and", text="调用 POST /api/tasks/{task_id}/parse 请求体包含 use_llm、rag_enabled、retrieval_top_k、rerank_enabled 字段"),
            ScenarioStep(type="then", text="返回 200 并包含 parse_metadata"),
        ],
        assertions=["返回 200"],
        source_chunks=[],
        preconditions=["task center is available"],
    )
    parsed_requirement = {
        "objective": "task-center e2e create and parse",
        "actors": ["qa"],
        "entities": ["task"],
        "preconditions": ["task center is available"],
        "actions": [
            "调用 POST /api/tasks 请求体包含 task_name、source_type、requirement_text、environment 字段",
            "调用 POST /api/tasks/{task_id}/parse 请求体包含 use_llm、rag_enabled、retrieval_top_k、rerank_enabled 字段",
        ],
        "expected_results": ["返回 200 并包含 parse_metadata"],
        "constraints": [],
        "ambiguities": [],
        "source_chunks": [],
        "api_endpoints": [
            {"method": "POST", "path": "/api/tasks", "description": "创建任务"},
            {"method": "POST", "path": "/api/tasks/{task_id}/parse", "description": "解析任务"},
        ],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    create_step = dsl["scenarios"][0]["steps"][1]
    parse_step = dsl["scenarios"][0]["steps"][2]

    assert create_step["save_context"] == {"task_id": "json.data.task_id", "resource_id": "json.data.task_id"}
    assert any(item.get("source") == "json.data.task_id" for item in create_step["assertions"] if isinstance(item, dict))
    assert set(create_step["request"]["json"].keys()) == {"task_name", "source_type", "requirement_text", "environment"}
    assert set(parse_step["request"]["json"].keys()) == {"use_llm", "rag_enabled", "retrieval_top_k", "rerank_enabled"}


def test_unknown_action_without_explicit_endpoint_does_not_generate_generic_resource_request() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_006",
        name="generic business action",
        goal="Execute business action without a concrete API contract",
        steps=[
            ScenarioStep(type="given", text="系统可用"),
            ScenarioStep(type="when", text="执行核心业务动作"),
            ScenarioStep(type="then", text="系统返回符合需求的可观察结果"),
        ],
        assertions=["系统返回符合需求的可观察结果"],
        source_chunks=[],
        preconditions=["系统可用"],
    )
    parsed_requirement = {
        "objective": "执行核心业务动作",
        "actors": ["user"],
        "entities": [],
        "preconditions": ["系统可用"],
        "actions": ["执行核心业务动作"],
        "expected_results": ["系统返回符合需求的可观察结果"],
        "constraints": [],
        "ambiguities": [],
        "source_chunks": [],
        "api_endpoints": [],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    action_step = dsl["scenarios"][0]["steps"][1]

    assert action_step["request"] == {}
    assert action_step["assertions"] == []
    assert action_step["assertion_quality"]["warning"] == "weak_assertion_set"


def test_assertion_planner_filters_invalid_llm_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    from case_generation import assertion_planner as planner_module
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    def fake_generate(*, mode: str, **_: object) -> tuple[list[dict[str, object]], str, str]:
        if mode == "enhance":
            return [
                {"source": "json.nickname", "op": "unsupported", "expected": "demo", "confidence": 0.95},
                {"source": "json.nickname", "op": "exists", "confidence": 0.2},
            ], "", ""
        return [], "llm_response_invalid", "InvalidAssertionPayload"

    monkeypatch.setattr(planner_module, "generate_assertion_candidates", fake_generate)
    scenario = ScenarioModel(
        scenario_id="scenario_010",
        name="create task",
        goal="create task",
        steps=[
            ScenarioStep(type="given", text="task center is available"),
            ScenarioStep(type="when", text="`POST /api/tasks`"),
        ],
        assertions=[],
        source_chunks=[],
        preconditions=["task center is available"],
    )
    parsed_requirement = {
        "objective": "create task",
        "actions": ["`POST /api/tasks`"],
        "expected_results": ["response contains `task_name` field"],
        "entities": ["task", "task_name"],
        "api_endpoints": [{"method": "POST", "path": "/api/tasks", "description": "create task"}],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    request_step = dsl["scenarios"][0]["steps"][1]
    assertions = [item for item in request_step["assertions"] if isinstance(item, dict)]

    assert any(item["generated_by"] == "rules" for item in assertions)
    assert request_step["assertion_quality"]["invalid_assertion_count"] >= 2
    assert not any(item["generated_by"] == "llm" and item["source"] == "json.data.task_name" for item in assertions)


def test_assertion_planner_accepts_llm_repair_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    from case_generation import assertion_planner as planner_module
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    def fake_generate(*, mode: str, **_: object) -> tuple[list[dict[str, object]], str, str]:
        if mode == "enhance":
            return [], "llm_response_invalid", "EmptyAssertionPayload"
        return [
            {
                "source": "json.data.task_context.task_name",
                "op": "exists",
                "confidence": 0.92,
                "severity": "major",
                "category": "field_presence",
                "generated_by": "llm_repair",
                "reasoning": "task create response should expose task context",
            }
        ], "", ""

    monkeypatch.setattr(planner_module, "generate_assertion_candidates", fake_generate)
    monkeypatch.setattr(planner_module, "_is_weak_assertion_set", lambda assertions: True)
    scenario = ScenarioModel(
        scenario_id="scenario_011",
        name="create task",
        goal="create task",
        steps=[
            ScenarioStep(type="given", text="task center is available"),
            ScenarioStep(type="when", text="`POST /api/tasks`"),
        ],
        assertions=[],
        source_chunks=[],
        preconditions=["task center is available"],
    )
    parsed_requirement = {
        "objective": "create task",
        "actions": ["`POST /api/tasks`"],
        "expected_results": ["response contains task context field"],
        "entities": ["task", "task_name"],
        "api_endpoints": [{"method": "POST", "path": "/api/tasks", "description": "create task"}],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    request_step = dsl["scenarios"][0]["steps"][1]
    assertions = [item for item in request_step["assertions"] if isinstance(item, dict)]

    assert any(item["generated_by"] == "llm_repair" for item in assertions)
    assert any(item["source"] == "json.data.task_context.task_name" for item in assertions)
    assert request_step["assertion_quality"]["llm_attempted"] is True


def test_task_center_collection_queries_do_not_inherit_task_detail_fields() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_012",
        name="query task scenarios",
        goal="Fetch generated scenarios for a task",
        steps=[
            ScenarioStep(type="given", text="Task already exists"),
            ScenarioStep(type="when", text="调用 GET /api/tasks/{task_id}/scenarios"),
            ScenarioStep(type="then", text="任务详情响应位于 data 下，包含 task_name 和 task_context"),
        ],
        assertions=["任务详情响应位于 data 下，包含 task_name 和 task_context"],
        source_chunks=[],
        preconditions=["Task already exists"],
    )
    parsed_requirement = {
        "objective": "task-center scenarios query",
        "actors": ["qa"],
        "entities": ["task", "scenario"],
        "preconditions": ["Task already exists"],
        "actions": ["调用 GET /api/tasks/{task_id}/scenarios"],
        "expected_results": ["任务详情响应位于 data 下，包含 task_name 和 task_context"],
        "constraints": [],
        "ambiguities": [],
        "source_chunks": [],
        "api_endpoints": [
            {"method": "GET", "path": "/api/tasks/{task_id}/scenarios", "description": "查询任务场景"},
        ],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    query_step = dsl["scenarios"][0]["steps"][1]
    assertion_sources = [item.get("source") for item in query_step["assertions"] if isinstance(item, dict)]

    assert query_step["request"]["url"] == "/api/tasks/{{task_id}}/scenarios"
    assert "json.task_context" not in assertion_sources
    assert "json.task_name" not in assertion_sources


def test_task_center_llm_candidates_are_filtered_by_endpoint_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    from case_generation import assertion_planner as planner_module
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    def fake_generate(*, mode: str, **_: object) -> tuple[list[dict[str, object]], str, str]:
        if mode == "enhance":
            return [
                {
                    "source": "json.data.task_name",
                    "op": "eq",
                    "expected": "demo_task_name",
                    "confidence": 0.91,
                    "severity": "major",
                    "category": "field_value",
                    "reasoning": "wrong nesting",
                },
                {
                    "source": "response.data",
                    "op": "exists",
                    "expected": True,
                    "confidence": 0.95,
                    "severity": "major",
                    "category": "schema",
                    "reasoning": "unsupported response source",
                },
                {
                    "source": "json.data.task_context.task_name",
                    "op": "exists",
                    "confidence": 0.88,
                    "severity": "major",
                    "category": "field_presence",
                    "reasoning": "valid nested field",
                },
            ], "", ""
        return [], "llm_response_invalid", "EmptyAssertionPayload"

    monkeypatch.setattr(planner_module, "generate_assertion_candidates", fake_generate)
    scenario = ScenarioModel(
        scenario_id="scenario_013",
        name="create task",
        goal="create task",
        steps=[
            ScenarioStep(type="given", text="task center is available"),
            ScenarioStep(type="when", text="璋冪敤 POST /api/tasks"),
        ],
        assertions=[],
        source_chunks=[],
        preconditions=["task center is available"],
    )
    parsed_requirement = {
        "objective": "create task",
        "actions": ["璋冪敤 POST /api/tasks"],
        "expected_results": ["response contains task context"],
        "entities": ["task", "task_name"],
        "api_endpoints": [{"method": "POST", "path": "/api/tasks", "description": "create task"}],
    }

    dsl = build_test_case_dsl(
        _build_task_context(),
        [scenario],
        parsed_requirement=parsed_requirement,
        enable_assertion_enhancement=True,
    )
    request_step = dsl["scenarios"][0]["steps"][1]
    assertions = [item for item in request_step["assertions"] if isinstance(item, dict)]
    sources = [item["source"] for item in assertions]

    assert "json.data.task_name" not in sources
    assert "response.data" not in sources
    assert "json.data.task_context.task_name" in sources
    assert request_step["assertion_quality"]["invalid_assertion_count"] >= 2


def test_explanatory_task_center_step_does_not_attempt_llm_enhancement(monkeypatch: pytest.MonkeyPatch) -> None:
    from case_generation import assertion_planner as planner_module
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    calls: list[str] = []

    def fake_generate(**kwargs: object) -> tuple[list[dict[str, object]], str, str]:
        calls.append(str(kwargs.get("mode")))
        return [], "llm_response_invalid", "EmptyAssertionPayload"

    monkeypatch.setattr(planner_module, "generate_assertion_candidates", fake_generate)
    scenario = ScenarioModel(
        scenario_id="scenario_014",
        name="task detail explanation",
        goal="explain task detail contract",
        steps=[
            ScenarioStep(type="given", text="task exists"),
            ScenarioStep(
                type="when",
                text="因此，联调和断言设计中不应把任务详情查询接口当作列表接口，也不应假设存在 `data.tasks`",
            ),
        ],
        assertions=[],
        source_chunks=[],
        preconditions=["task exists"],
    )
    parsed_requirement = {
        "objective": "task detail explanation",
        "actions": ["GET /api/tasks/{task_id}"],
        "expected_results": ["response envelope is stable"],
        "entities": ["task", "task_id"],
        "api_endpoints": [{"method": "GET", "path": "/api/tasks/{task_id}", "description": "task detail"}],
    }

    dsl = build_test_case_dsl(
        _build_task_context(),
        [scenario],
        parsed_requirement=parsed_requirement,
        enable_assertion_enhancement=True,
    )
    request_step = dsl["scenarios"][0]["steps"][1]

    assert calls == []
    assert request_step["assertion_quality"]["llm_attempted"] is False


def test_low_value_query_endpoint_skips_llm_enhancement(monkeypatch: pytest.MonkeyPatch) -> None:
    from case_generation import assertion_planner as planner_module
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    calls: list[str] = []

    def fake_generate(**kwargs: object) -> tuple[list[dict[str, object]], str, str]:
        calls.append(str(kwargs.get("mode")))
        return [], "llm_response_invalid", "EmptyAssertionPayload"

    monkeypatch.setattr(planner_module, "generate_assertion_candidates", fake_generate)
    scenario = ScenarioModel(
        scenario_id="scenario_015",
        name="task detail",
        goal="fetch task detail",
        steps=[
            ScenarioStep(type="given", text="task exists"),
            ScenarioStep(type="when", text="`GET /api/tasks/{task_id}`"),
        ],
        assertions=[],
        source_chunks=[],
        preconditions=["task exists"],
    )
    parsed_requirement = {
        "objective": "task detail",
        "actions": ["`GET /api/tasks/{task_id}`"],
        "expected_results": ["response contains task context"],
        "entities": ["task", "task_id"],
        "api_endpoints": [{"method": "GET", "path": "/api/tasks/{task_id}", "description": "task detail"}],
    }

    dsl = build_test_case_dsl(
        _build_task_context(),
        [scenario],
        parsed_requirement=parsed_requirement,
        enable_assertion_enhancement=True,
    )
    request_step = dsl["scenarios"][0]["steps"][1]

    assert calls == []
    assert request_step["assertion_quality"]["llm_attempted"] is False


def test_task_center_endpoint_scenarios_do_not_reuse_global_explanatory_expectations() -> None:
    from case_generation import build_scenarios

    parsed_requirement = {
        "objective": "Platform 主链路联调需求说明（当前实现对齐版）",
        "actors": ["qa"],
        "entities": ["task"],
        "preconditions": ["执行完成且进入终态"],
        "actions": [
            "`POST /api/tasks`",
            "`GET /api/tasks/{task_id}`",
            "`POST /api/tasks/{task_id}/parse`",
        ],
        "expected_results": [
            "当前 task-center API 统一使用如下响应结构：",
            "因此，联调和断言设计中不应把任务详情查询接口当作列表接口，也不应假设存在 `data.tasks`",
            "`POST /api/tasks/{task_id}/parse` -> 200",
        ],
        "constraints": [],
        "ambiguities": [],
        "source_chunks": [],
        "api_endpoints": [
            {"method": "POST", "path": "/api/tasks", "description": "创建任务"},
            {"method": "GET", "path": "/api/tasks/{task_id}", "description": "任务详情"},
            {"method": "POST", "path": "/api/tasks/{task_id}/parse", "description": "解析任务"},
        ],
    }

    scenarios = build_scenarios(parsed_requirement)
    scenario_goals = [scenario["goal"] for scenario in scenarios]
    scenario_step_texts = [[step["text"] for step in scenario["steps"]] for scenario in scenarios]

    assert scenario_goals == ["创建任务", "解析任务"]
    assert not any("当前 task-center API 统一使用如下响应结构" in " ".join(texts) for texts in scenario_step_texts)
    assert not any("不应假设存在 `data.tasks`" in " ".join(texts) for texts in scenario_step_texts)
    assert scenarios[0]["steps"][2]["text"] not in parsed_requirement["expected_results"][:2]
    assert scenarios[1]["steps"][2]["text"] not in parsed_requirement["expected_results"][:2]
    assert scenarios[1]["steps"][2]["text"] == "`POST /api/tasks/{task_id}/parse` -> 200"


def test_infer_intent_post_auth_is_login_not_create() -> None:
    from case_generation.dsl_generator import _infer_intent

    assert _infer_intent("获取鉴权 token，向 POST /auth 发送包含用户名和密码的请求") == "login"
    assert _infer_intent("call POST /auth to obtain token") == "login"
    assert _infer_intent("POST /api/users to register") == "create"


def test_restful_booker_host_whitelists_assertion_llm_url() -> None:
    from case_generation import assertion_planner as ap

    assert ap._is_high_value_assertion_url("https://restful-booker.herokuapp.com/auth")
    assert ap._is_high_value_assertion_url("https://restful-booker.herokuapp.com/booking/1")
    assert ap._is_high_value_assertion_url("https://restful-booker.herokuapp.com:443/booking")
    assert not ap._is_high_value_assertion_url("https://evil.example/restful-booker.herokuapp.com/booking")
    assert ap._is_high_value_assertion_url("/api/tasks")


def test_restful_booker_endpoints_generate_token_and_bookingid_context() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_016",
        name="restful booker create flow",
        goal="auth then create booking",
        steps=[
            ScenarioStep(type="given", text="restful booker is reachable"),
            ScenarioStep(type="when", text="Step 1 获取鉴权 token: POST /auth"),
            ScenarioStep(type="and", text="Step 2 创建 booking: POST /booking"),
            ScenarioStep(type="then", text="booking 创建成功"),
        ],
        assertions=["booking 创建成功"],
        source_chunks=[],
        preconditions=["restful booker is reachable"],
    )
    parsed_requirement = {
        "objective": "restful booker flow",
        "actions": ["POST /auth", "POST /booking"],
        "expected_results": ["token exists", "bookingid exists"],
        "api_endpoints": [
            {
                "method": "POST",
                "path": "/auth",
                "description": "auth",
                "response_fields": [{"name": "token"}],
            },
            {
                "method": "POST",
                "path": "/booking",
                "description": "create booking",
                "response_fields": [{"name": "bookingid"}],
            },
        ],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    auth_step = dsl["scenarios"][0]["steps"][1]
    create_step = dsl["scenarios"][0]["steps"][2]

    assert auth_step["request"]["url"] == "/auth"
    assert auth_step["request"]["json"] == {"username": "admin", "password": "password123"}
    assert auth_step["save_context"] == {"token": "json.token"}
    assert create_step["request"]["url"] == "/booking"
    assert create_step["request"]["json"] == {
        "firstname": "Jim",
        "lastname": "Brown",
        "totalprice": 111,
        "depositpaid": True,
        "bookingdates": {
            "checkin": "2026-04-10",
            "checkout": "2026-04-12",
        },
        "additionalneeds": "Breakfast",
    }
    assert create_step["save_context"] == {"booking_id": "json.bookingid", "resource_id": "json.bookingid"}
    assert any(item.get("source") == "json.bookingid" for item in create_step["assertions"] if isinstance(item, dict))


def test_restful_booker_known_payload_overrides_synthetic_field_extraction() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_018",
        name="restful booker explicit field hints",
        goal="respect known request examples for auth and booking",
        steps=[
            ScenarioStep(type="given", text="restful booker is reachable"),
            ScenarioStep(type="when", text="POST /auth"),
            ScenarioStep(type="and", text="POST /booking"),
            ScenarioStep(type="then", text="request payloads remain valid"),
        ],
        assertions=["request payloads remain valid"],
        source_chunks=[],
        preconditions=["restful booker is reachable"],
    )
    parsed_requirement = {
        "objective": "restful booker contract",
        "actions": [
            "POST /auth request body contains username and password fields",
            "POST /booking request body contains firstname, lastname, totalprice, depositpaid, bookingdates, additionalneeds fields",
        ],
        "expected_results": ["token exists", "bookingid exists"],
        "api_endpoints": [
            {"method": "POST", "path": "/auth", "description": "auth"},
            {"method": "POST", "path": "/booking", "description": "create booking"},
        ],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    auth_step = dsl["scenarios"][0]["steps"][1]
    create_step = dsl["scenarios"][0]["steps"][2]

    assert auth_step["request"]["json"] == {"username": "admin", "password": "password123"}
    assert create_step["request"]["json"] == {
        "firstname": "Jim",
        "lastname": "Brown",
        "totalprice": 111,
        "depositpaid": True,
        "bookingdates": {
            "checkin": "2026-04-10",
            "checkout": "2026-04-12",
        },
        "additionalneeds": "Breakfast",
    }


def test_restful_booker_delete_status_defaults_to_201() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_017",
        name="delete booking",
        goal="delete booking by id",
        steps=[
            ScenarioStep(type="given", text="booking_id exists"),
            ScenarioStep(type="when", text="DELETE /booking/{id}"),
            ScenarioStep(type="then", text="删除成功"),
        ],
        assertions=["删除成功"],
        source_chunks=[],
        preconditions=["booking_id exists"],
    )
    parsed_requirement = {
        "objective": "delete booking",
        "actions": ["DELETE /booking/{id}"],
        "expected_results": ["HTTP 201"],
        "api_endpoints": [{"method": "DELETE", "path": "/booking/{id}", "description": "delete booking"}],
    }
    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    delete_step = dsl["scenarios"][0]["steps"][1]
    status_assertions = [item for item in delete_step["assertions"] if isinstance(item, dict) and item.get("source") == "status_code"]

    assert status_assertions
    assert status_assertions[0]["expected"] == 201


def test_legacy_api_scenario_builder_uses_clean_default_assertion_text() -> None:
    from case_generation.api_scenario_builder import _build_dependency_flow_scenarios

    parsed_requirement = {
        "objective": "booking flow",
        "preconditions": ["service is reachable"],
        "actions": ["POST /booking", "GET /booking/{id}"],
        "expected_results": [],
        "source_chunks": [],
        "api_endpoints": [
            {"method": "POST", "path": "/booking", "description": "create booking"},
            {"method": "GET", "path": "/booking/{id}", "description": "get booking", "depends_on": ["/booking"]},
        ],
    }

    scenarios = _build_dependency_flow_scenarios(parsed_requirement, parsed_requirement["actions"], [], 1)

    assert scenarios
    assert scenarios[0]["steps"][-1]["text"] == "系统返回符合需求的可观察结果"
    assert scenarios[0]["assertions"] == ["系统返回符合需求的可观察结果"]


def test_restful_booker_dependency_flow_filters_meta_actions_and_keeps_cookie_auth() -> None:
    from case_generation import build_scenarios, build_test_case_dsl
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "验证从鉴权到删除 booking 的最小闭环",
        "actions": [
            "`DELETE /booking/{{booking_id}}` 必须显式携带 `Cookie: token={{token}}`（认证信息不会被自动补）",
            "Request:** `POST /auth`",
            "Request:** `POST /booking`",
            "Request:** `GET /booking/{{booking_id}}`",
            "Request:** `DELETE /booking/{{booking_id}}`",
            "统一目标：验证从鉴权、创建 booking、读取 booking 到删除 booking 的最小闭环",
            "Scenario: 创建并清理 booking",
            "Step 2 — 创建 booking",
            "Step 4 — 删除 booking",
        ],
        "expected_results": [
            "| 鉴权 | 成功拿到 `token` 并保存 |",
            "| 创建 | 成功返回 `bookingid`，保存 `booking_id` |",
            "| 删除 | 携带 `Cookie: token={{token}}` 后删除成功 |",
        ],
        "api_endpoints": [
            {
                "method": "DELETE",
                "path": "/booking/{{booking_id}}",
                "description": "必须显式携带 Cookie: token={{token}}（认证信息不会被自动补）",
                "depends_on": ["/booking"],
                "request_body_fields": [{"name": "Cookie", "field_type": "string", "required": True}],
            },
            {"method": "POST", "path": "/auth", "description": "**Request:**", "depends_on": []},
            {"method": "POST", "path": "/booking", "description": "**Request:**", "depends_on": []},
            {"method": "GET", "path": "/booking/{{booking_id}}", "description": "**Request:**", "depends_on": ["/booking"]},
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    names = [item.name for item in scenarios]

    assert all(not name.startswith("Scenario:") for name in names)
    assert all("统一目标：" not in name for name in names)
    assert any(
        "/auth" in str(step.text if hasattr(step, "text") else step["text"])
        and "/booking" in " ".join(str(s.text if hasattr(s, "text") else s["text"]) for s in item.steps)
        for item in scenarios
        for step in item.steps
    )

    dsl = build_test_case_dsl(_build_task_context(), scenarios, parsed_requirement=parsed_requirement)
    delete_steps = [
        step
        for scenario in dsl["scenarios"]
        for step in scenario["steps"]
        if (step.get("request") or {}).get("method") == "DELETE"
    ]

    assert delete_steps
    assert any(step["request"]["url"] == "/booking/{{booking_id}}" for step in delete_steps)
    assert any({"booking_id", "token"}.issubset(set(step["uses_context"])) for step in delete_steps)
    assert any(step["request"].get("cookies") == {"token": "{{token}}"} for step in delete_steps)
    assert all((step["request"].get("auth") or {}).get("type") != "bearer" for step in delete_steps)


def test_restful_booker_chinese_scenario_meta_action_does_not_create_unauthed_cleanup_flow() -> None:
    from case_generation import build_scenarios, build_test_case_dsl
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "验证 booking 删除链路",
        "actions": [
            "场景：创建并清理 booking",
            "POST /auth",
            "POST /booking",
            "`DELETE /booking/{{booking_id}}` 必须显式携带 `Cookie: token={{token}}`",
        ],
        "expected_results": [
            "获取 token 成功",
            "创建 booking 成功并返回 bookingid",
            "删除 booking 成功",
        ],
        "api_endpoints": [
            {"method": "POST", "path": "/auth", "description": "auth", "depends_on": []},
            {"method": "POST", "path": "/booking", "description": "create booking", "depends_on": []},
            {"method": "DELETE", "path": "/booking/{{booking_id}}", "description": "delete booking", "depends_on": ["/booking", "/auth"]},
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    assert all("场景：创建并清理 booking" not in item.name for item in scenarios)

    dsl = build_test_case_dsl(_build_task_context(), scenarios, parsed_requirement=parsed_requirement)
    delete_scenarios = [
        scenario
        for scenario in dsl["scenarios"]
        if any((step.get("request") or {}).get("method") == "DELETE" for step in scenario["steps"])
    ]

    assert delete_scenarios
    assert all(
        any((step.get("request") or {}).get("url") == "/auth" for step in scenario["steps"])
        for scenario in delete_scenarios
    )


def test_flow_summary_action_is_filtered_from_api_scenarios() -> None:
    from case_generation import build_scenarios
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "Restful Booker E2E2",
        "actions": [
            "获取鉴权 token，向 POST /auth 发送包含用户名和密码的请求",
            "创建 booking，向 POST /booking 发送包含预订信息的请求",
            "读取 booking 详情，向 GET /booking/{{booking_id}} 发送请求",
            "删除 booking，向 DELETE /booking/{{booking_id}} 发送携带 token 的请求",
            "验证从鉴权、创建 booking、读取 booking 到删除 booking 的最小闭环",
        ],
        "expected_results": ["token exists", "bookingid exists", "query succeeds", "delete succeeds"],
        "api_endpoints": [
            {"method": "POST", "path": "/auth", "description": "auth", "depends_on": []},
            {"method": "POST", "path": "/booking", "description": "create booking", "depends_on": []},
            {"method": "GET", "path": "/booking/{{booking_id}}", "description": "get booking", "depends_on": ["/booking"]},
            {"method": "DELETE", "path": "/booking/{{booking_id}}", "description": "delete booking", "depends_on": ["/booking"]},
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]

    assert all("最小闭环" not in item.name for item in scenarios)
    assert all(
        all("最小闭环" not in str(step.text if hasattr(step, "text") else step.get("text", "")) for step in item.steps)
        for item in scenarios
    )


def test_dsl_treats_flow_summary_step_as_non_request() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_020",
        name="flow summary should not execute",
        goal="restful booker flow",
        steps=[
            ScenarioStep(type="given", text="`token` 存在且非空"),
            ScenarioStep(type="when", text="删除 booking，向 DELETE /booking/{{booking_id}} 发送携带 token 的请求"),
            ScenarioStep(type="and", text="验证从鉴权、创建 booking、读取 booking 到删除 booking 的最小闭环"),
            ScenarioStep(type="then", text="删除成功"),
        ],
        assertions=["删除成功"],
        source_chunks=[],
        preconditions=["`token` 存在且非空"],
    )
    parsed_requirement = {
        "objective": "Restful Booker E2E2",
        "actions": [
            "获取鉴权 token，向 POST /auth 发送包含用户名和密码的请求",
            "创建 booking，向 POST /booking 发送包含预订信息的请求",
            "读取 booking 详情，向 GET /booking/{{booking_id}} 发送请求",
            "删除 booking，向 DELETE /booking/{{booking_id}} 发送携带 token 的请求",
        ],
        "expected_results": ["token exists", "bookingid exists", "query succeeds", "delete succeeds"],
        "api_endpoints": [
            {"method": "POST", "path": "/auth", "description": "auth", "depends_on": []},
            {"method": "POST", "path": "/booking", "description": "create booking", "depends_on": []},
            {"method": "GET", "path": "/booking/{{booking_id}}", "description": "get booking", "depends_on": ["/booking"]},
            {
                "method": "DELETE",
                "path": "/booking/{{booking_id}}",
                "description": "delete booking with Cookie token",
                "depends_on": ["/booking"],
                "request_body_fields": [{"name": "Cookie", "field_type": "string", "required": True}],
            },
        ],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    summary_step = dsl["scenarios"][0]["steps"][2]

    assert summary_step["request"] == {}
    assert summary_step["save_context"] == {}
    assert summary_step["assertion_quality"]["warning"] == "non_request_step"


def test_restful_booker_placeholder_aliases_normalize_to_booking_id_context() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_021",
        name="placeholder aliases",
        goal="normalize booking placeholders",
        steps=[
            ScenarioStep(type="given", text="booking context exists"),
            ScenarioStep(type="when", text="向 /booking/{bookingid} 发送 GET 请求读取 booking 详情"),
            ScenarioStep(type="and", text="向 /booking/{bookingid} 发送 DELETE 请求删除 booking"),
            ScenarioStep(type="then", text="请求使用统一上下文变量"),
        ],
        assertions=["请求使用统一上下文变量"],
        source_chunks=[],
        preconditions=["booking context exists"],
    )
    parsed_requirement = {
        "objective": "placeholder normalization",
        "actions": ["GET /booking/{bookingid}", "DELETE /booking/{bookingid}"],
        "expected_results": ["booking query succeeds", "booking delete succeeds"],
        "api_endpoints": [
            {"method": "GET", "path": "/booking/{bookingid}", "description": "get booking", "depends_on": ["/booking"]},
            {"method": "DELETE", "path": "/booking/{bookingid}", "description": "delete booking", "depends_on": ["/booking"]},
        ],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    get_step = dsl["scenarios"][0]["steps"][1]
    delete_step = dsl["scenarios"][0]["steps"][2]

    assert get_step["request"]["url"] == "/booking/{{booking_id}}"
    assert delete_step["request"]["url"] == "/booking/{{booking_id}}"


def test_restful_booker_cookie_contract_beats_bearer_fallback() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_022",
        name="cookie auth precedence",
        goal="prefer explicit cookie contract",
        steps=[
            ScenarioStep(type="given", text="token and booking_id exist"),
            ScenarioStep(type="when", text="向 /booking/{bookingid} 发送 DELETE 请求删除 booking"),
            ScenarioStep(type="then", text="删除成功"),
        ],
        assertions=["删除成功"],
        source_chunks=[],
        preconditions=["token and booking_id exist"],
    )
    parsed_requirement = {
        "objective": "cookie auth precedence",
        "actions": [
            "DELETE /booking/{bookingid}",
            "DELETE /booking/{bookingid} 必须显式携带 Cookie: token={{token}}",
        ],
        "expected_results": ["删除时携带 Cookie token"],
        "api_endpoints": [
            {
                "method": "DELETE",
                "path": "/booking/{bookingid}",
                "description": "delete booking",
                "depends_on": ["/booking"],
            }
        ],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    delete_step = dsl["scenarios"][0]["steps"][1]

    assert delete_step["request"]["url"] == "/booking/{{booking_id}}"
    assert delete_step["request"].get("cookies") == {"token": "{{token}}"}
    assert "auth" not in delete_step["request"]


def test_explicit_put_and_patch_with_token_text_are_not_misclassified_as_login() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_023",
        name="booking updates",
        goal="update booking",
        steps=[
            ScenarioStep(type="given", text="token and booking_id exist"),
            ScenarioStep(type="when", text="全量更新 booking，发送 PUT /booking/{{booking_id}} 请求并携带更新信息和鉴权 token"),
            ScenarioStep(type="and", text="部分更新 booking，发送 PATCH /booking/{{booking_id}} 请求并携带部分更新信息和鉴权 token"),
            ScenarioStep(type="then", text="更新成功"),
        ],
        assertions=["更新成功"],
        source_chunks=[],
        preconditions=["token and booking_id exist"],
    )
    parsed_requirement = {
        "objective": "update booking",
        "actions": [
            "PUT /booking/{{booking_id}}",
            "PATCH /booking/{{booking_id}}",
        ],
        "expected_results": ["更新成功"],
        "api_endpoints": [
            {"method": "PUT", "path": "/booking/{{booking_id}}", "description": "replace booking", "depends_on": ["/booking"]},
            {"method": "PATCH", "path": "/booking/{{booking_id}}", "description": "patch booking", "depends_on": ["/booking"]},
        ],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    put_step = dsl["scenarios"][0]["steps"][1]
    patch_step = dsl["scenarios"][0]["steps"][2]

    assert put_step["request"]["method"] == "PUT"
    assert put_step["request"]["json"]["firstname"] == "James"
    assert put_step["save_context"] == {}
    assert patch_step["request"]["method"] == "PATCH"
    assert patch_step["request"]["json"] == {"firstname": "Jamie", "additionalneeds": "Dinner"}
    assert patch_step["save_context"] == {}


def test_simple_ping_endpoint_only_generates_status_assertion() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_024",
        name="ping",
        goal="service health",
        steps=[
            ScenarioStep(type="given", text="service is reachable"),
            ScenarioStep(type="when", text="进行健康检查，发送 GET /ping 请求"),
            ScenarioStep(type="then", text="服务可用"),
        ],
        assertions=["服务可用"],
        source_chunks=[],
        preconditions=["service is reachable"],
    )
    parsed_requirement = {
        "objective": "health check",
        "actions": ["GET /ping"],
        "expected_results": ["HTTP 200"],
        "api_endpoints": [{"method": "GET", "path": "/ping", "description": "ping", "depends_on": []}],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    ping_step = dsl["scenarios"][0]["steps"][1]
    assertion_sources = [item.get("source") for item in ping_step["assertions"] if isinstance(item, dict)]

    assert assertion_sources == ["status_code"]


def test_booking_list_query_only_asserts_collection_shape_and_identifier() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_025",
        name="booking list",
        goal="query booking list",
        steps=[
            ScenarioStep(type="given", text="service is reachable"),
            ScenarioStep(type="when", text="查询 booking 列表，发送 GET /booking 请求"),
            ScenarioStep(type="then", text="查询 booking 列表的 GET /booking 请求返回 HTTP 200 且返回数组，数组首项存在 bookingid"),
        ],
        assertions=["列表返回 bookingid"],
        source_chunks=[],
        preconditions=["service is reachable"],
    )
    parsed_requirement = {
        "objective": "query booking list",
        "actions": ["GET /booking"],
        "expected_results": [
            "查询 booking 列表的 GET /booking 请求返回 HTTP 200 且返回数组，数组首项存在 bookingid",
            "读取 booking 详情的 GET /booking/{{booking_id}} 请求返回 HTTP 200 且关键字段与创建信息一致",
            "创建 booking 的 POST /booking 请求返回 HTTP 200 或 201 且 bookingid 存在，且 firstname 为 Jim，lastname 为 Brown",
        ],
        "api_endpoints": [
            {
                "method": "GET",
                "path": "/booking",
                "description": "list booking",
                "depends_on": [],
                "response_fields": [{"name": "bookingid", "field_type": "string", "required": True}],
            }
        ],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    query_step = dsl["scenarios"][0]["steps"][1]
    assertion_sources = [item.get("source") for item in query_step["assertions"] if isinstance(item, dict)]

    assert "json" in assertion_sources
    assert "json[0].bookingid" in assertion_sources
    assert "json.firstname" not in assertion_sources
    assert "json.lastname" not in assertion_sources
    assert "json.depositpaid" not in assertion_sources


def test_full_flow_focuses_on_primary_resource_chain_not_auxiliary_endpoints() -> None:
    from case_generation import build_scenarios
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "Restful Booker E2E2 Plus",
        "actions": [
            "进行健康检查，发送 GET /ping 请求",
            "获取鉴权 token，发送 POST /auth 请求并携带用户名和密码",
            "查询 booking 列表，发送 GET /booking 请求",
            "创建 booking，发送 POST /booking 请求并携带相关预订信息",
            "读取 booking 详情，发送 GET /booking/{{booking_id}} 请求",
            "全量更新 booking，发送 PUT /booking/{{booking_id}} 请求并携带更新信息和鉴权 token",
            "部分更新 booking，发送 PATCH /booking/{{booking_id}} 请求并携带部分更新信息和鉴权 token",
            "删除 booking，发送 DELETE /booking/{{booking_id}} 请求并携带鉴权 token",
        ],
        "expected_results": ["success"],
        "api_endpoints": [
            {"method": "GET", "path": "/ping", "description": "ping", "depends_on": []},
            {"method": "POST", "path": "/auth", "description": "auth", "depends_on": []},
            {"method": "GET", "path": "/booking", "description": "list booking", "depends_on": []},
            {"method": "POST", "path": "/booking", "description": "create booking", "depends_on": []},
            {"method": "GET", "path": "/booking/{{booking_id}}", "description": "get booking", "depends_on": ["/booking"]},
            {"method": "PUT", "path": "/booking/{{booking_id}}", "description": "replace booking", "depends_on": ["/booking", "/auth"]},
            {"method": "PATCH", "path": "/booking/{{booking_id}}", "description": "patch booking", "depends_on": ["/booking", "/auth"]},
            {"method": "DELETE", "path": "/booking/{{booking_id}}", "description": "delete booking", "depends_on": ["/booking", "/auth"]},
            {"method": "PUT", "path": "/booking/{id}", "description": "replace booking alias", "depends_on": ["/booking", "/auth"]},
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    full_flow = max(scenarios, key=lambda item: len(item.steps))
    step_texts = [step.text if hasattr(step, "text") else step["text"] for step in full_flow.steps]

    assert not any("/ping" in step for step in step_texts)
    assert not any(step == "查询 booking 列表，发送 GET /booking 请求" for step in step_texts)
    assert sum(1 for step in step_texts if "PUT /booking" in step) <= 1
    assert sum(1 for step in step_texts if "PATCH /booking" in step) <= 1


def test_low_confidence_request_and_summary_endpoints_do_not_expand_scenarios() -> None:
    from case_generation import build_scenarios
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "Restful Booker E2E2 Plus",
        "actions": [
            "进行健康检查，发送 GET /ping 请求",
            "获取鉴权 token，发送 POST /auth 请求并携带用户名和密码",
            "查询 booking 列表，发送 GET /booking 请求",
            "创建 booking，发送 POST /booking 请求并携带预订信息",
            "读取 booking 详情，发送 GET /booking/{{booking_id}} 请求",
            "删除 booking，发送 DELETE /booking/{{booking_id}} 请求并携带鉴权 token",
            "Request:** `GET /booking/{{booking_id}}`",
            "Scenario: 健康检查 + 创建 + 查询 + 更新 + 删除",
        ],
        "expected_results": ["success"],
        "api_endpoints": [
            {"method": "GET", "path": "/ping", "description": "健康检查接口", "depends_on": []},
            {"method": "POST", "path": "/auth", "description": "获取鉴权 token 接口", "depends_on": []},
            {"method": "GET", "path": "/booking", "description": "查询 booking 列表接口", "depends_on": []},
            {"method": "POST", "path": "/booking", "description": "创建 booking 接口", "depends_on": []},
            {"method": "GET", "path": "/booking/{booking_id}", "description": "读取 booking 详情接口", "depends_on": ["/booking"]},
            {"method": "DELETE", "path": "/booking/{booking_id}", "description": "删除 booking 接口", "depends_on": ["/booking", "/auth"]},
            {"method": "GET", "path": "/booking/{{booking_id}}", "description": "**Request:**", "group": "Step 4 — 读取 booking 详情", "depends_on": ["/booking"]},
            {"method": "PUT", "path": "/booking/{id}", "description": "| 全量更新 | 后所有字段按新值覆盖 |", "group": "断言摘要", "depends_on": ["/booking"]},
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    names = [scenario.name for scenario in scenarios]

    assert len(scenarios) == 8
    assert not any("Request:**" in name for name in names)
    assert not any("断言摘要" in (scenario.goal if hasattr(scenario, "goal") else "") for scenario in scenarios)


def test_resource_mutation_scenarios_without_in_scenario_resource_seed_are_filtered() -> None:
    from case_generation import build_scenarios
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "Restful Booker E2E2 Plus",
        "actions": [
            "获取鉴权 token，发送 POST /auth 请求并携带用户名和密码",
            "创建 booking，发送 POST /booking 请求并携带预订信息",
            "全量更新 booking，发送 PUT /booking/{{booking_id}} 请求并携带更新信息和鉴权 token",
            "部分更新 booking，发送 PATCH /booking/{{booking_id}} 请求并携带部分更新信息和鉴权 token",
            "删除 booking，发送 DELETE /booking/{{booking_id}} 请求并携带鉴权 token",
        ],
        "expected_results": [
            "创建 booking 的 POST /booking 请求返回 HTTP 200 或 201 且 bookingid 存在，保存 booking_id",
            "全量更新 booking 的 PUT /booking/{{booking_id}} 请求返回 HTTP 200",
            "部分更新 booking 的 PATCH /booking/{{booking_id}} 请求返回 HTTP 200",
            "删除 booking 的 DELETE /booking/{{booking_id}} 请求返回 HTTP 201",
        ],
        "preconditions": ["`token` 存在且非空"],
        "api_endpoints": [
            {"method": "POST", "path": "/auth", "description": "auth", "depends_on": []},
            {"method": "POST", "path": "/booking", "description": "create booking", "depends_on": []},
            {"method": "PUT", "path": "/booking/{{booking_id}}", "description": "replace booking", "depends_on": ["/booking", "/auth"]},
            {"method": "PATCH", "path": "/booking/{{booking_id}}", "description": "patch booking", "depends_on": ["/booking", "/auth"]},
            {"method": "DELETE", "path": "/booking/{{booking_id}}", "description": "delete booking", "depends_on": ["/booking", "/auth"]},
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    step_sets = [
        [step.text if hasattr(step, "text") else step["text"] for step in scenario.steps]
        for scenario in scenarios
    ]

    assert not any(
        any("PUT /booking/{{booking_id}}" in step for step in steps)
        and any("PATCH /booking/{{booking_id}}" in step for step in steps)
        and not any("POST /booking" in step for step in steps)
        for steps in step_sets
    )
    assert any(
        any("POST /booking" in step for step in steps)
        and any("PUT /booking/{{booking_id}}" in step for step in steps)
        for steps in step_sets
    )
    assert any(
        any("POST /booking" in step for step in steps)
        and any("PATCH /booking/{{booking_id}}" in step for step in steps)
        for steps in step_sets
    )


def test_restful_booker_put_uses_known_full_body_for_single_brace_path() -> None:
    from case_generation.dsl_generator import _build_request_template

    parsed_requirement = {
        "api_endpoints": [
            {"method": "PUT", "path": "/booking/{booking_id}", "description": "全量更新 booking 接口"},
        ],
        "actions": ["全量更新 booking，发送 PUT /booking/{{booking_id}} 请求并携带更新信息和鉴权 token"],
        "expected_results": [],
        "constraints": [],
    }

    request = _build_request_template(
        "全量更新 booking，发送 PUT /booking/{{booking_id}} 请求并携带更新信息和鉴权 token",
        "update",
        parsed_requirement,
        [],
    )

    assert request["method"] == "PUT"
    assert request["url"] == "/booking/{{booking_id}}"
    assert request["json"] == {
        "firstname": "James",
        "lastname": "Brown",
        "totalprice": 222,
        "depositpaid": False,
        "bookingdates": {
            "checkin": "2026-04-11",
            "checkout": "2026-04-13",
        },
        "additionalneeds": "Lunch",
    }


def test_querystring_endpoints_are_preserved_as_distinct_scenarios() -> None:
    from case_generation import build_scenarios
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "Booking filter coverage",
        "actions": [
            "查询 booking 列表，发送 GET /booking 请求",
            "按 firstname 过滤查询 booking 列表，发送 GET /booking?firstname=Jamie 请求",
            "按 lastname 过滤查询 booking 列表，发送 GET /booking?lastname=Brown 请求",
        ],
        "expected_results": [
            "GET /booking 返回 HTTP 200 且返回数组",
            "GET /booking?firstname=Jamie 返回 HTTP 200 且返回数组",
            "GET /booking?lastname=Brown 返回 HTTP 200 且返回数组",
        ],
        "api_endpoints": [
            {"method": "GET", "path": "/booking", "description": "查询 booking 列表接口", "depends_on": []},
            {"method": "GET", "path": "/booking?firstname=Jamie", "description": "按 firstname 过滤查询 booking 列表接口", "depends_on": []},
            {"method": "GET", "path": "/booking?lastname=Brown", "description": "按 lastname 过滤查询 booking 列表接口", "depends_on": []},
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    names = [scenario.name for scenario in scenarios]

    assert any("/booking 请求" in name for name in names)
    assert any("/booking?firstname=Jamie" in name for name in names)
    assert any("/booking?lastname=Brown" in name for name in names)
    assert len(scenarios) == 3


def test_placeholder_querystring_endpoints_are_filtered_but_concrete_filters_are_kept() -> None:
    from case_generation import build_scenarios
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "Booking filter coverage",
        "actions": [
            "按 firstname 过滤查询 booking 列表，发送 GET /booking?firstname=Jamie 请求",
            "按 lastname 过滤查询 booking 列表，发送 GET /booking?lastname=Brown 请求",
        ],
        "expected_results": [
            "过滤查询应返回合法数组结果",
        ],
        "api_endpoints": [
            {"method": "GET", "path": "/booking?firstname=...", "description": "占位过滤", "depends_on": []},
            {"method": "GET", "path": "/booking?lastname=...", "description": "占位过滤", "depends_on": []},
            {"method": "GET", "path": "/booking?firstname=Jamie", "description": "按 firstname 过滤查询 booking 列表接口", "depends_on": []},
            {"method": "GET", "path": "/booking?lastname=Brown", "description": "按 lastname 过滤查询 booking 列表接口", "depends_on": []},
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    names = [scenario.name for scenario in scenarios]

    assert len(scenarios) == 2
    assert any("/booking?firstname=Jamie" in name for name in names)
    assert any("/booking?lastname=Brown" in name for name in names)
    assert not any("..." in name for name in names)


def test_dependency_backed_endpoint_variant_is_preferred_over_dependencyless_duplicate() -> None:
    from case_generation import build_scenarios
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "Booking update chain",
        "actions": [
            "获取鉴权 token",
            "创建 booking",
            "读取 booking 详情",
            "全量更新 booking",
            "部分更新 booking",
            "删除 booking",
            "Request:** `GET /booking?firstname=Jamie`",
        ],
        "expected_results": ["success"],
        "api_endpoints": [
            {"method": "POST", "path": "/auth", "description": "获取鉴权 token 接口", "depends_on": []},
            {"method": "POST", "path": "/booking", "description": "创建 booking 接口", "depends_on": []},
            {"method": "GET", "path": "/booking/{booking_id}", "description": "读取 booking 详情接口", "depends_on": []},
            {"method": "GET", "path": "/booking/{{booking_id}}", "description": "读取 booking 详情接口", "depends_on": ["/booking"]},
            {"method": "PUT", "path": "/booking/{booking_id}", "description": "全量更新 booking 接口", "depends_on": []},
            {"method": "PUT", "path": "/booking/{{booking_id}}", "description": "全量更新 booking 接口", "depends_on": ["/booking", "/auth"]},
            {"method": "PATCH", "path": "/booking/{booking_id}", "description": "部分更新 booking 接口", "depends_on": []},
            {"method": "PATCH", "path": "/booking/{{booking_id}}", "description": "部分更新 booking 接口", "depends_on": ["/booking", "/auth"]},
            {"method": "DELETE", "path": "/booking/{booking_id}", "description": "删除 booking 接口", "depends_on": []},
            {"method": "DELETE", "path": "/booking/{{booking_id}}", "description": "删除 booking 接口", "depends_on": ["/booking", "/auth"]},
            {"method": "GET", "path": "/booking?firstname=Jamie", "description": "**Request:**", "group": "Step 1 — 查询 firstname 过滤", "depends_on": []},
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    step_sets = [
        [step.text if hasattr(step, "text") else step["text"] for step in scenario.steps]
        for scenario in scenarios
    ]

    assert any(
        any("POST /booking" in step for step in steps)
        and any("GET /booking/{{booking_id}}" in step for step in steps)
        for steps in step_sets
    )
    assert any(
        any("POST /auth" in step for step in steps)
        and any("POST /booking" in step for step in steps)
        and any("PUT /booking/{{booking_id}}" in step for step in steps)
        for steps in step_sets
    )
    assert any(
        any("POST /auth" in step for step in steps)
        and any("POST /booking" in step for step in steps)
        and any("PATCH /booking/{{booking_id}}" in step for step in steps)
        for steps in step_sets
    )
    assert any(
        any("POST /auth" in step for step in steps)
        and any("POST /booking" in step for step in steps)
        and any("DELETE /booking/{{booking_id}}" in step for step in steps)
        for steps in step_sets
    )
    assert any(any("/booking?firstname=Jamie" in step for step in steps) for steps in step_sets)


def test_method_qualified_dependency_paths_still_pull_create_chain() -> None:
    from case_generation import build_scenarios
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "Booking update chain",
        "actions": [
            "POST /auth",
            "POST /booking",
            "PUT /booking/{id}",
        ],
        "expected_results": ["PUT /booking/{id} 返回 HTTP 200"],
        "api_endpoints": [
            {"method": "POST", "path": "/auth", "description": "auth", "depends_on": []},
            {"method": "POST", "path": "/booking", "description": "create booking", "depends_on": []},
            {"method": "PUT", "path": "/booking/{id}", "description": "replace booking", "depends_on": ["POST /booking", "POST /auth"]},
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    step_sets = [
        [step.text if hasattr(step, "text") else step["text"] for step in scenario.steps]
        for scenario in scenarios
    ]

    assert any(
        any("POST /auth" in step for step in steps)
        and any("POST /booking" in step for step in steps)
        and any("PUT /booking/{id}" in step for step in steps)
        for steps in step_sets
    )


def test_filter_query_assertions_do_not_require_non_empty_results() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_026",
        name="booking firstname filter",
        goal="query booking filter",
        steps=[
            ScenarioStep(type="given", text="service is reachable"),
            ScenarioStep(type="when", text="按 firstname 过滤查询 booking 列表，发送 GET /booking?firstname=Jamie 请求"),
            ScenarioStep(type="then", text="返回合法数组结果"),
        ],
        assertions=["返回合法数组结果"],
        source_chunks=[],
        preconditions=["service is reachable"],
    )
    parsed_requirement = {
        "objective": "query booking filter",
        "actions": ["GET /booking?firstname=Jamie"],
        "expected_results": ["GET /booking?firstname=Jamie 返回 HTTP 200 且返回合法数组结果"],
        "constraints": ["列表过滤接口返回结果以“合法数组”为主，不要求固定业务记录数"],
        "api_endpoints": [
            {"method": "GET", "path": "/booking?firstname=Jamie", "description": "按 firstname 过滤查询 booking 列表接口", "depends_on": []},
        ],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    query_step = dsl["scenarios"][0]["steps"][1]
    assertion_sources = [item.get("source") for item in query_step["assertions"] if isinstance(item, dict)]

    assert "status_code" in assertion_sources
    assert "json" in assertion_sources
    assert "json[0].bookingid" not in assertion_sources
    assert not any(item.get("op") == "len_gt" for item in query_step["assertions"] if isinstance(item, dict))


def test_restful_booker_ping_constraint_and_booking_id_alias_shape_assertions() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    ping_scenario = ScenarioModel(
        scenario_id="scenario_027",
        name="ping",
        goal="service health",
        steps=[
            ScenarioStep(type="given", text="service is reachable"),
            ScenarioStep(type="when", text="调用 GET /ping"),
            ScenarioStep(type="then", text="服务可用"),
        ],
        assertions=["服务可用"],
        source_chunks=[],
        preconditions=["service is reachable"],
    )
    update_scenario = ScenarioModel(
        scenario_id="scenario_028",
        name="booking update",
        goal="update booking",
        steps=[
            ScenarioStep(type="given", text="service is reachable"),
            ScenarioStep(type="when", text="调用 PUT /booking/{id}"),
            ScenarioStep(type="then", text="更新成功"),
        ],
        assertions=["更新成功"],
        source_chunks=[],
        preconditions=["service is reachable"],
    )
    parsed_requirement = {
        "objective": "restful booker",
        "actions": ["GET /ping", "PUT /booking/{id}"],
        "expected_results": ["success"],
        "constraints": ["GET /ping 预期返回 HTTP 201"],
        "api_endpoints": [
            {"method": "GET", "path": "/ping", "description": "ping", "depends_on": []},
            {"method": "PUT", "path": "/booking/{id}", "description": "replace booking", "depends_on": ["POST /booking"]},
        ],
    }

    dsl = build_test_case_dsl(_build_task_context(), [ping_scenario, update_scenario], parsed_requirement=parsed_requirement)
    ping_assertions = [item for item in dsl["scenarios"][0]["steps"][1]["assertions"] if isinstance(item, dict)]
    put_request = dsl["scenarios"][1]["steps"][1]["request"]

    assert ping_assertions[0]["expected"] == 201
    assert put_request["json"] == {
        "firstname": "James",
        "lastname": "Brown",
        "totalprice": 222,
        "depositpaid": False,
        "bookingdates": {
            "checkin": "2026-04-11",
            "checkout": "2026-04-13",
        },
        "additionalneeds": "Lunch",
    }


def test_api_challenges_challenger_header_context_is_saved_and_reused() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_029",
        name="challenger init",
        goal="challenger init",
        steps=[
            ScenarioStep(type="given", text="service is reachable"),
            ScenarioStep(type="when", text="调用 POST /challenger"),
            ScenarioStep(type="and", text="调用 GET /challenges"),
            ScenarioStep(type="then", text="挑战列表可读取"),
        ],
        assertions=["挑战列表可读取"],
        source_chunks=[],
        preconditions=["service is reachable"],
    )
    parsed_requirement = {
        "objective": "API Challenges",
        "actions": ["POST /challenger", "GET /challenges"],
        "expected_results": [
            "创建 challenger 成功后应返回 201，并可提取 X-CHALLENGER",
            "挑战列表应在携带 X-CHALLENGER 时返回当前 session 对应进度",
        ],
        "constraints": ["POST /challenger 成功返回 201"],
        "api_endpoints": [
            {"method": "POST", "path": "/challenger", "description": "创建 challenger 会话", "depends_on": []},
            {"method": "GET", "path": "/challenges", "description": "获取挑战列表", "depends_on": []},
        ],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    create_step = dsl["scenarios"][0]["steps"][1]
    query_step = dsl["scenarios"][0]["steps"][2]

    assert create_step["request"] == {"method": "POST", "url": "/challenger"}
    assert create_step["save_context"] == {"challenger_guid": "headers.x-challenger"}
    assert any(item.get("source") == "headers.x-challenger" for item in create_step["assertions"] if isinstance(item, dict))
    assert query_step["request"]["headers"]["X-CHALLENGER"] == "{{challenger_guid}}"
    assert "json" not in [item.get("source") for item in create_step["assertions"] if isinstance(item, dict)]


def test_api_challenges_secret_token_uses_basic_auth_and_header_token() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    scenario = ScenarioModel(
        scenario_id="scenario_030",
        name="secret token",
        goal="secret token",
        steps=[
            ScenarioStep(type="given", text="service is reachable"),
            ScenarioStep(type="when", text="调用 POST /challenger"),
            ScenarioStep(type="and", text="调用 POST /secret/token"),
            ScenarioStep(type="and", text="调用 GET /secret/note"),
            ScenarioStep(type="then", text="受保护资源可读取"),
        ],
        assertions=["受保护资源可读取"],
        source_chunks=[],
        preconditions=["service is reachable"],
    )
    parsed_requirement = {
        "objective": "API Challenges",
        "actions": ["POST /challenger", "POST /secret/token", "GET /secret/note"],
        "expected_results": [
            "POST /secret/token 在 admin/password 下返回 201",
            "secret/note 合法 token 返回 200",
        ],
        "constraints": [
            "POST /secret/token 在 admin/password 下返回 201",
            "GET /secret/note 合法 token 返回 200",
        ],
        "api_endpoints": [
            {"method": "POST", "path": "/challenger", "description": "创建 challenger 会话", "depends_on": []},
            {"method": "POST", "path": "/secret/token", "description": "获取 secret token", "depends_on": []},
            {"method": "GET", "path": "/secret/note", "description": "读取 secret note", "depends_on": []},
        ],
    }

    dsl = build_test_case_dsl(_build_task_context(), [scenario], parsed_requirement=parsed_requirement)
    token_step = dsl["scenarios"][0]["steps"][2]
    note_step = dsl["scenarios"][0]["steps"][3]

    assert token_step["request"]["method"] == "POST"
    assert token_step["request"]["url"] == "/secret/token"
    assert token_step["request"]["auth"] == {"type": "basic", "username": "admin", "password": "password123"}
    assert token_step["request"]["headers"]["X-CHALLENGER"] == "{{challenger_guid}}"
    assert token_step["save_context"] == {"auth_token": "headers.x-auth-token"}
    assert any(item.get("source") == "headers.x-auth-token" for item in token_step["assertions"] if isinstance(item, dict))
    assert note_step["request"]["headers"]["X-CHALLENGER"] == "{{challenger_guid}}"
    assert note_step["request"]["headers"]["X-AUTH-TOKEN"] == "{{auth_token}}"


def test_api_challenges_header_and_token_dependencies_generate_chains() -> None:
    from case_generation import build_scenarios
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "API Challenges",
        "actions": [
            "POST /challenger",
            "GET /challenges",
            "POST /todos",
            "POST /secret/token",
            "GET /secret/note",
        ],
        "expected_results": [
            "创建 challenger 后可查询 challenges",
            "创建 todo 成功",
            "获取 secret token 后可读取 secret note",
        ],
        "api_endpoints": [
            {"method": "POST", "path": "/challenger", "description": "创建 challenger 会话", "depends_on": []},
            {
                "method": "GET",
                "path": "/challenges",
                "description": "获取挑战列表",
                "depends_on": [],
                "request_body_fields": [{"name": "X-CHALLENGER", "field_type": "string", "required": True}],
            },
            {
                "method": "POST",
                "path": "/todos",
                "description": "创建 todo",
                "depends_on": [],
                "request_body_fields": [{"name": "X-CHALLENGER", "field_type": "string", "required": True}],
            },
            {
                "method": "POST",
                "path": "/secret/token",
                "description": "获取 secret token",
                "depends_on": [],
                "request_body_fields": [{"name": "X-CHALLENGER", "field_type": "string", "required": True}],
            },
            {
                "method": "GET",
                "path": "/secret/note",
                "description": "读取 secret note",
                "depends_on": [],
                "request_body_fields": [
                    {"name": "X-CHALLENGER", "field_type": "string", "required": True},
                    {"name": "X-AUTH-TOKEN", "field_type": "string", "required": True},
                ],
            },
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    step_sets = [
        [step.text if hasattr(step, "text") else step["text"] for step in scenario.steps]
        for scenario in scenarios
    ]

    assert all(not (len(steps) == 2 and any("GET /challenges" in step for step in steps)) for steps in step_sets)
    assert all(not (len(steps) == 2 and any("POST /todos" in step for step in steps)) for steps in step_sets)
    assert all(not (len(steps) == 2 and any("POST /secret/token" in step for step in steps)) for steps in step_sets)
    assert any(
        any("POST /challenger" in step for step in steps) and any("GET /challenges" in step for step in steps)
        for steps in step_sets
    )
    assert any(
        any("POST /challenger" in step for step in steps) and any("POST /todos" in step for step in steps)
        for steps in step_sets
    )
    assert any(
        any("POST /challenger" in step for step in steps)
        and any("POST /secret/token" in step for step in steps)
        and any("GET /secret/note" in step for step in steps)
        for steps in step_sets
    )


def test_api_challenges_detail_and_protected_endpoints_do_not_run_bare_without_metadata() -> None:
    from case_generation import build_scenarios
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "API Challenges",
        "actions": [
            "POST /challenger",
            "POST /todos",
            "GET /todos/{id}",
            "POST /secret/token",
            "GET /secret/note",
            "GET /challenger/{guid}",
        ],
        "expected_results": [
            "todo 详情可读取",
            "secret note 可读取",
            "challenger 导出可读取",
        ],
        "api_endpoints": [
            {"method": "POST", "path": "/challenger", "description": "会话初始化接口", "depends_on": []},
            {"method": "GET", "path": "/challenger", "description": "相关接口", "group": "API Challenges"},
            {"method": "POST", "path": "/todos", "description": "Todo 资源相关接口", "depends_on": []},
            {"method": "GET", "path": "/todos/{id}", "description": "Todo 资源相关接口", "group": "API Challenges"},
            {"method": "POST", "path": "/secret/token", "description": "受保护资源令牌接口", "depends_on": []},
            {"method": "GET", "path": "/secret/note", "description": "相关接口", "group": "API Challenges"},
            {"method": "GET", "path": "/challenger/{guid}", "description": "相关接口", "group": "API Challenges"},
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    step_sets = [
        [step.text if hasattr(step, "text") else step["text"] for step in scenario.steps]
        for scenario in scenarios
    ]

    assert all(not (len(steps) == 2 and any("GET /challenger" == step for step in steps)) for steps in step_sets)
    assert all(not (len(steps) == 2 and any("GET /todos/{id}" in step for step in steps)) for steps in step_sets)
    assert all(not (len(steps) == 2 and any("GET /secret/note" in step for step in steps)) for steps in step_sets)
    assert any(
        any("POST /todos" in step for step in steps) and any("GET /todos/{id}" in step for step in steps)
        for steps in step_sets
    )
    assert any(
        any("POST /challenger" in step for step in steps) and any("GET /challenger/{guid}" in step for step in steps)
        for steps in step_sets
    )
    assert any(
        any("POST /challenger" in step for step in steps)
        and any("POST /secret/token" in step for step in steps)
        and any("GET /secret/note" in step for step in steps)
        for steps in step_sets
    )


def test_api_challenges_heartbeat_status_and_guid_placeholder_do_not_pollute_assertions() -> None:
    from case_generation import build_test_case_dsl
    from platform_shared.models import ScenarioModel, ScenarioStep

    heartbeat = ScenarioModel(
        scenario_id="scenario_031",
        name="heartbeat",
        goal="heartbeat",
        steps=[
            ScenarioStep(type="given", text="service is reachable"),
            ScenarioStep(type="when", text="调用 GET /heartbeat"),
            ScenarioStep(type="then", text="心跳返回成功"),
        ],
        assertions=["心跳返回成功"],
        source_chunks=[],
        preconditions=["service is reachable"],
    )
    challenger_export = ScenarioModel(
        scenario_id="scenario_032",
        name="challenger export",
        goal="challenger export",
        steps=[
            ScenarioStep(type="given", text="service is reachable"),
            ScenarioStep(type="when", text="调用 POST /challenger"),
            ScenarioStep(type="and", text="调用 GET /challenger/{guid}"),
            ScenarioStep(type="then", text="导出 challenger 成功"),
        ],
        assertions=["导出 challenger 成功"],
        source_chunks=[],
        preconditions=["service is reachable"],
    )
    parsed_requirement = {
        "objective": "API Challenges",
        "actions": ["POST /challenger", "GET /challenger/{guid}", "GET /heartbeat"],
        "expected_results": ["GET /heartbeat 返回 204", "GET /challenger/{guid} 返回 200"],
        "constraints": ["GET /heartbeat 返回 204", "GET /challenger/{guid} 返回 200"],
        "api_endpoints": [
            {"method": "POST", "path": "/challenger", "description": "会话初始化接口", "depends_on": []},
            {"method": "GET", "path": "/challenger/{guid}", "description": "相关接口", "group": "API Challenges"},
            {"method": "GET", "path": "/heartbeat", "description": "相关接口", "group": "API Challenges"},
        ],
    }

    dsl = build_test_case_dsl(_build_task_context(), [heartbeat, challenger_export], parsed_requirement=parsed_requirement)
    heartbeat_step = dsl["scenarios"][0]["steps"][1]
    export_step = dsl["scenarios"][1]["steps"][2]

    assert any(item.get("source") == "status_code" and item.get("expected") == 204 for item in heartbeat_step["assertions"] if isinstance(item, dict))
    assert not any(item.get("source") == "json.guid" for item in export_step["assertions"] if isinstance(item, dict))


def test_dependency_endpoints_generate_targeted_chain_scenarios_and_full_flow() -> None:
    from case_generation import build_scenarios
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "restful booker minimal e2e",
        "actions": [
            "POST /auth",
            "POST /booking",
            "GET /booking/{{booking_id}}",
            "DELETE /booking/{{booking_id}}",
            "Scenario: create and clean booking",
            "Request:** `POST /auth`",
        ],
        "expected_results": [
            "token exists",
            "bookingid exists",
            "booking detail matches request",
            "delete succeeds with cookie token",
        ],
        "api_endpoints": [
            {"method": "POST", "path": "/auth", "description": "auth", "depends_on": []},
            {"method": "POST", "path": "/booking", "description": "create booking", "depends_on": []},
            {"method": "GET", "path": "/booking/{{booking_id}}", "description": "get booking", "depends_on": ["/booking"]},
            {
                "method": "DELETE",
                "path": "/booking/{{booking_id}}",
                "description": "delete booking with Cookie token",
                "depends_on": ["/booking"],
                "request_body_fields": [{"name": "Cookie", "field_type": "string", "required": True}],
            },
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    names = [scenario.name for scenario in scenarios]
    step_sets = [
        [step.text if hasattr(step, "text") else step["text"] for step in scenario.steps]
        for scenario in scenarios
    ]

    assert len(scenarios) == 5
    assert any("POST /auth" in name for name in names)
    assert any("POST /booking" in name for name in names)
    assert any(any("POST /booking" in step for step in steps) and any("GET /booking/{{booking_id}}" in step for step in steps) for steps in step_sets)
    assert any(any("POST /auth" in step for step in steps) and any("POST /booking" in step for step in steps) and any("DELETE /booking/{{booking_id}}" in step for step in steps) for steps in step_sets)
    assert any(any("POST /auth" in step for step in steps) and any("POST /booking" in step for step in steps) and any("GET /booking/{{booking_id}}" in step for step in steps) and any("DELETE /booking/{{booking_id}}" in step for step in steps) for steps in step_sets)


def test_narrative_scenarios_do_not_duplicate_structural_endpoint_coverage() -> None:
    from case_generation import build_scenarios
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "restful booker minimal e2e",
        "actions": [
            "获取鉴权 token，向 POST /auth 发送包含用户名和密码的请求",
            "创建 booking，向 POST /booking 发送包含预订信息的请求",
            "读取 booking 详情，向 GET /booking/{{booking_id}} 发送请求",
            "删除 booking，向 DELETE /booking/{{booking_id}} 发送携带 Cookie 的请求",
            "用户完成 booking 主链路",
            "确认从创建到删除的完整流程",
        ],
        "expected_results": [
            "token exists",
            "bookingid exists",
            "booking detail matches request",
            "delete succeeds with cookie token",
        ],
        "api_endpoints": [
            {"method": "POST", "path": "/auth", "description": "auth", "depends_on": []},
            {"method": "POST", "path": "/booking", "description": "create booking", "depends_on": []},
            {"method": "GET", "path": "/booking/{{booking_id}}", "description": "get booking", "depends_on": ["/booking"]},
            {
                "method": "DELETE",
                "path": "/booking/{{booking_id}}",
                "description": "delete booking with Cookie token",
                "depends_on": ["/booking"],
                "request_body_fields": [{"name": "Cookie", "field_type": "string", "required": True}],
            },
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    names = [scenario.name for scenario in scenarios]
    step_sets = [
        [step.text if hasattr(step, "text") else step["text"] for step in scenario.steps]
        for scenario in scenarios
    ]

    assert len(scenarios) == 5
    assert any("POST /auth" in name for name in names)
    assert any("POST /booking" in name for name in names)
    assert any(any("POST /booking" in step for step in steps) and any("GET /booking/{{booking_id}}" in step for step in steps) for steps in step_sets)
    assert any(any("POST /auth" in step for step in steps) and any("POST /booking" in step for step in steps) and any("DELETE /booking/{{booking_id}}" in step for step in steps) for steps in step_sets)
    assert any(any("POST /auth" in step for step in steps) and any("POST /booking" in step for step in steps) and any("GET /booking/{{booking_id}}" in step for step in steps) and any("DELETE /booking/{{booking_id}}" in step for step in steps) for steps in step_sets)


def test_jsonplaceholder_fake_rest_scenarios_keep_unique_ids_and_targeted_expectations() -> None:
    from case_generation import build_scenarios
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "JSONPlaceholder",
        "actions": [
            "GET /posts",
            "GET /posts/{id}",
            "POST /posts",
            "PUT /posts/{id}",
            "PATCH /posts/{id}",
            "DELETE /posts/{id}",
            "GET /posts/{id}/comments",
            "GET /comments?postId={id}",
        ],
        "expected_results": [
            "`GET /posts/{id}` 应返回预置 post 详情",
            "`POST /posts` 应返回新对象与新 id，但不应作为真实持久化断言依据",
            "`PUT /posts/{id}` 与 `PATCH /posts/{id}` 应返回更新结果，但不应期望服务器真实改变",
            "`DELETE /posts/{id}` 应返回删除成功语义，但不应期望真实删除",
            "`/posts/{id}/comments` 与 `/comments?postId={id}` 应返回等价关联结果",
        ],
        "constraints": [
            "POST /posts 返回创建结果，但不会真正写入服务器",
            "PUT /posts/{id}、PATCH /posts/{id}、DELETE /posts/{id} 也都是 fake success",
            "GET /posts/{id} 应返回预置 post 详情，建议使用 post_id=1",
        ],
        "api_endpoints": [
            {"method": "GET", "path": "/posts", "description": "查询 posts 集合", "depends_on": []},
            {"method": "GET", "path": "/posts/{id}", "description": "读取指定 post", "depends_on": ["/posts"]},
            {"method": "POST", "path": "/posts", "description": "模拟创建 post", "depends_on": []},
            {"method": "PUT", "path": "/posts/{id}", "description": "模拟全量更新 post", "depends_on": ["/posts"]},
            {"method": "PATCH", "path": "/posts/{id}", "description": "模拟部分更新 post", "depends_on": ["/posts"]},
            {"method": "DELETE", "path": "/posts/{id}", "description": "模拟删除 post", "depends_on": ["/posts"]},
            {"method": "GET", "path": "/posts/{id}/comments", "description": "读取 comments", "depends_on": ["/posts/{id}"]},
            {"method": "GET", "path": "/comments?postId={id}", "description": "过滤 comments", "depends_on": []},
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    scenario_ids = [scenario.scenario_id for scenario in scenarios]
    scenario_map = {scenario.name: scenario for scenario in scenarios}

    assert len(scenario_ids) == len(set(scenario_ids))
    assert "GET /posts" in scenario_map
    assert "GET /posts/{id}" in scenario_map
    assert "POST /posts" in scenario_map
    assert "PUT /posts/{id}" in scenario_map
    assert "PATCH /posts/{id}" in scenario_map
    assert "DELETE /posts/{id}" in scenario_map
    assert "GET /comments?postId={id}" in scenario_map
    assert scenario_map["GET /posts"].assertions == ["系统返回符合需求的可观察结果"]
    assert scenario_map["GET /posts/{id}"].assertions == ["`GET /posts/{id}` 应返回预置 post 详情"]
    assert scenario_map["POST /posts"].assertions == ["`POST /posts` 应返回新对象与新 id，但不应作为真实持久化断言依据"]


def test_jsonplaceholder_dsl_uses_known_post_body_and_preloaded_identifier() -> None:
    from case_generation import build_scenarios, build_test_case_dsl
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "JSONPlaceholder",
        "actions": [
            "POST /posts",
            "PUT /posts/{id}",
            "PATCH /posts/{id}",
            "GET /comments?postId={id}",
        ],
        "expected_results": [
            "POST /posts 返回新对象",
            "PUT /posts/{id} 返回更新结果",
            "PATCH /posts/{id} 返回部分更新结果",
            "GET /comments?postId={id} 返回过滤结果",
        ],
        "constraints": [
            "POST /posts 不会真正写入服务器",
            "PUT /posts/{id} 与 PATCH /posts/{id} 使用官方预置资源，建议使用 post_id=1",
        ],
        "api_endpoints": [
            {"method": "POST", "path": "/posts", "description": "模拟创建 post", "depends_on": []},
            {"method": "PUT", "path": "/posts/{id}", "description": "模拟全量更新 post", "depends_on": []},
            {"method": "PATCH", "path": "/posts/{id}", "description": "模拟部分更新 post", "depends_on": []},
            {"method": "GET", "path": "/comments?postId={id}", "description": "按 postId 过滤 comments", "depends_on": []},
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    dsl = build_test_case_dsl(_build_task_context(), scenarios, parsed_requirement=parsed_requirement)
    steps = {
        step["text"]: step
        for scenario in dsl["scenarios"]
        for step in scenario["steps"]
        if step["request"]
    }

    assert steps["POST /posts"]["request"]["json"] == {
        "title": "write API test",
        "body": "created by automated test",
        "userId": 1,
    }
    assert steps["PUT /posts/{id}"]["request"]["url"] == "/posts/1"
    assert steps["PUT /posts/{id}"]["request"]["json"] == {
        "id": 1,
        "title": "write API test updated",
        "body": "updated by automated test",
        "userId": 1,
    }
    assert steps["PATCH /posts/{id}"]["request"]["url"] == "/posts/1"
    assert steps["PATCH /posts/{id}"]["request"]["json"] == {
        "title": "write API test updated",
    }
    assert steps["GET /comments?postId={id}"]["request"]["url"] == "/comments?postId=1"


def test_petstore_dsl_uses_openapi_style_fields_headers_and_context() -> None:
    from case_generation import build_scenarios, build_test_case_dsl
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "Swagger Petstore",
        "actions": [
            "POST /user",
            "GET /user/login",
            "GET /user/{username}",
            "POST /store/order",
            "GET /store/order/{orderId}",
            "POST /pet",
            "GET /pet/findByStatus",
            "GET /pet/{petId}",
            "DELETE /pet/{petId}",
        ],
        "expected_results": [
            "GET /user/login 应返回登录成功消息",
            "POST /user 后应能通过 GET /user/{username} 读取到用户",
            "POST /store/order 后应返回 order 数据，并可被读取",
            "GET /pet/findByStatus 应按状态返回 pet 列表",
            "带 api_key: special-key 的 pet 组请求应可作为 header 注入验证样例",
        ],
        "constraints": [
            "GET /user/login query 传 username、password",
            "User 常用字段包括 id、username、firstName、lastName、email、password",
            "Order 常用字段包括 id、petId、quantity、shipDate、status、complete",
            "Pet 至少需要 name、photoUrls",
            "固定 API Key：api_key: special-key",
        ],
        "api_endpoints": [
            {"method": "POST", "path": "/user", "description": "创建单个用户", "depends_on": []},
            {"method": "GET", "path": "/user/login", "description": "用户登录", "depends_on": ["/user"]},
            {"method": "GET", "path": "/user/{username}", "description": "读取指定用户", "depends_on": ["POST /user"]},
            {"method": "POST", "path": "/store/order", "description": "创建宠物订单", "depends_on": []},
            {"method": "GET", "path": "/store/order/{orderId}", "description": "读取指定订单", "depends_on": ["POST /store/order"]},
            {"method": "POST", "path": "/pet", "description": "新增 pet", "depends_on": []},
            {"method": "GET", "path": "/pet/findByStatus", "description": "按状态筛选 pet", "depends_on": ["/pet"]},
            {"method": "GET", "path": "/pet/{petId}", "description": "读取指定 pet", "depends_on": ["POST /pet"]},
            {"method": "DELETE", "path": "/pet/{petId}", "description": "删除指定 pet", "depends_on": ["POST /pet"]},
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    dsl = build_test_case_dsl(_build_task_context(), scenarios, parsed_requirement=parsed_requirement)
    steps = {
        step["text"]: step
        for scenario in dsl["scenarios"]
        for step in scenario["steps"]
        if step["request"]
    }

    assert steps["POST /user"]["request"]["json"]["username"] == "demo_user"
    assert steps["POST /user"]["request"]["json"]["email"] == "demo@example.com"
    assert steps["POST /user"]["save_context"] == {"username": "request.json.username"}
    assert steps["GET /user/login"]["request"]["params"] == {"username": "demo_user", "password": "demo_pass"}
    assert steps["POST /store/order"]["save_context"] == {"order_id": "request.json.id", "resource_id": "request.json.id"}
    assert steps["GET /store/order/{orderId}"]["request"]["url"] == "/store/order/{{order_id}}"
    assert steps["POST /pet"]["save_context"] == {"pet_id": "request.json.id", "resource_id": "request.json.id"}
    assert steps["GET /pet/{petId}"]["request"]["url"] == "/pet/{{pet_id}}"
    assert steps["DELETE /pet/{petId}"]["request"]["url"] == "/pet/{{pet_id}}"
    assert steps["POST /pet"]["request"]["headers"]["api_key"] == "special-key"
    assert steps["GET /pet/findByStatus"]["request"]["headers"]["api_key"] == "special-key"
    assert steps["GET /pet/findByStatus"]["request"]["params"]["status"] == "available"


def test_dummyjson_dsl_uses_known_auth_and_todo_defaults() -> None:
    from case_generation import build_scenarios, build_test_case_dsl
    from platform_shared.models import ScenarioModel

    parsed_requirement = {
        "objective": "DummyJSON",
        "actions": [
            "POST /auth/login",
            "GET /auth/me",
            "POST /auth/refresh",
            "POST /todos/add",
            "GET /todos/{id}",
            "GET /todos/user/{id}",
            "PUT /todos/{id}",
            "PATCH /todos/{id}",
        ],
        "expected_results": [
            "POST /auth/login 成功后应返回非空 accessToken 与 refreshToken",
            "GET /auth/me 携带合法 Bearer token 时应返回当前用户信息",
            "POST /auth/refresh 应返回新的 token 对",
            "POST /todos/add 应返回新 todo",
        ],
        "constraints": [
            "Authorization: Bearer {{access_token}}",
            "POST /todos/add 请求语义提交 todo、completed、userId",
        ],
        "api_endpoints": [
            {"method": "POST", "path": "/auth/login", "description": "登录", "depends_on": []},
            {"method": "GET", "path": "/auth/me", "description": "当前用户", "depends_on": ["accessToken"]},
            {"method": "POST", "path": "/auth/refresh", "description": "刷新 token", "depends_on": ["refreshToken"]},
            {"method": "POST", "path": "/todos/add", "description": "模拟创建 todo", "depends_on": []},
            {"method": "GET", "path": "/todos/{id}", "description": "读取 todo", "depends_on": []},
            {"method": "GET", "path": "/todos/user/{id}", "description": "按用户查询 todos", "depends_on": []},
            {"method": "PUT", "path": "/todos/{id}", "description": "更新 todo", "depends_on": []},
            {"method": "PATCH", "path": "/todos/{id}", "description": "部分更新 todo", "depends_on": []},
        ],
        "source_chunks": [],
    }

    scenarios = [ScenarioModel(**payload) for payload in build_scenarios(parsed_requirement)]
    dsl = build_test_case_dsl(_build_task_context(), scenarios, parsed_requirement=parsed_requirement)
    steps = {
        step["text"]: step
        for scenario in dsl["scenarios"]
        for step in scenario["steps"]
        if step["request"]
    }

    assert steps["POST /auth/login"]["request"]["json"] == {"username": "emilys", "password": "emilyspass", "expiresInMins": 30}
    assert steps["POST /auth/login"]["save_context"] == {"access_token": "json.accessToken", "refresh_token": "json.refreshToken"}
    assert steps["GET /auth/me"]["request"]["auth"] == {"type": "bearer", "token_context": "access_token"}
    assert steps["POST /auth/refresh"]["request"]["json"]["refreshToken"] == "{{refresh_token}}"
    assert steps["POST /todos/add"]["request"]["json"] == {"todo": "write API test", "completed": False, "userId": 5}
    assert steps["GET /todos/{id}"]["request"]["url"] == "/todos/1"
    assert steps["GET /todos/user/{id}"]["request"]["url"] == "/todos/user/5"
    assert steps["PUT /todos/{id}"]["request"]["json"] == {"todo": "write API test updated", "completed": True, "userId": 5}
    assert steps["PATCH /todos/{id}"]["request"]["json"] == {"completed": True}


def main() -> int:
    _extend_path()
    test_login_then_profile_query_generates_auth_context()
    test_create_then_detail_query_generates_resource_dependency()
    test_form_session_login_generates_cookie_and_context_dependency()
    test_basic_auth_query_generates_query_request_instead_of_login()
    test_chinese_actions_keep_priority_and_dependency_grouping()
    test_api_endpoints_generate_independent_scenarios()
    test_expectation_and_step_with_status_code_does_not_generate_request()
    test_login_body_fields_are_extracted_from_requirement_text()
    test_create_task_request_uses_task_id_instead_of_generic_id()
    test_assertion_planner_filters_invalid_llm_candidates(pytest.MonkeyPatch())
    test_assertion_planner_accepts_llm_repair_candidates(pytest.MonkeyPatch())
    test_task_center_collection_queries_do_not_inherit_task_detail_fields()
    test_restful_booker_host_whitelists_assertion_llm_url()
    test_restful_booker_endpoints_generate_token_and_bookingid_context()
    test_restful_booker_known_payload_overrides_synthetic_field_extraction()
    test_restful_booker_delete_status_defaults_to_201()
    test_restful_booker_dependency_flow_filters_meta_actions_and_keeps_cookie_auth()
    test_restful_booker_chinese_scenario_meta_action_does_not_create_unauthed_cleanup_flow()
    test_dependency_endpoints_generate_targeted_chain_scenarios_and_full_flow()
    test_infer_intent_post_auth_is_login_not_create()
    print("api dsl generation test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
