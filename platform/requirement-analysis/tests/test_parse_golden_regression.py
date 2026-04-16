from __future__ import annotations

from requirement_analysis.service import AnalysisParseOptions, parse_requirement_bundle


def test_parse_golden_login_requirement_regression() -> None:
    result = parse_requirement_bundle(
        requirement_text="用户输入正确账号密码后登录成功并进入个人中心，页面需显示用户昵称。",
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=True,
            retrieval_top_k=5,
            rerank_enabled=False,
        ),
    )
    parsed = result["parsed_requirement"]
    assert "登录" in parsed["objective"] or "登录" in " ".join(parsed["actions"])
    assert any("昵称" in item for item in parsed["expected_results"])
    assert result["validation_report"]["passed"] is True


def test_parse_golden_order_requirement_regression() -> None:
    result = parse_requirement_bundle(
        requirement_text="用户提交订单后系统应返回订单号，且订单状态为待支付。",
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=True,
            retrieval_top_k=5,
            rerank_enabled=True,
        ),
    )
    parsed = result["parsed_requirement"]
    combined_expected = " ".join(parsed["expected_results"])
    assert "订单号" in combined_expected or "order" in combined_expected.lower()
    assert parsed["actions"], "actions should not be empty"
    assert "retrieval_scoring" in result["parse_metadata"]


def test_parse_golden_extracts_explicit_http_sentence_as_action() -> None:
    result = parse_requirement_bundle(
        requirement_text="""
        用户登录后调用 POST /api/login 获取 token；
        接着调用 GET /api/user/profile 并展示昵称、头像；
        最后调用 PUT /api/user/profile 更新昵称。
        """,
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )
    parsed = result["parsed_requirement"]
    actions = " ".join(parsed["actions"]).lower()
    assert "get /api/user/profile" in actions
    assert "post /api/login" in actions
    assert "put /api/user/profile" in actions


def test_parse_golden_extracts_endpoint_description_from_markdown_table() -> None:
    result = parse_requirement_bundle(
        requirement_text="""
        | 接口 | 方法 | 路径 |
        | 用户登录 | POST | /api/auth/login |
        | 获取个人中心 | GET | /api/user/profile |
        """,
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )
    endpoints = result["parsed_requirement"]["api_endpoints"]
    endpoint_map = {f"{item['method']} {item['path']}": item.get("description", "") for item in endpoints}
    assert endpoint_map["POST /api/auth/login"] == "用户登录"
    assert endpoint_map["GET /api/user/profile"] == "获取个人中心"


def test_parse_golden_dev_doc_ignores_role_bullets_as_actions() -> None:
    result = parse_requirement_bundle(
        requirement_text="""
        # Platform 主链路联调需求说明

        ## 角色与职责
        - **产品/项目负责人**：确认验收范围、签收最终结论。
        - **后端研发**：保障主链路可运行，处理阻断性缺陷。
        - **前端研发**：验证页面主路径与真实接口数据一致性。

        ## 接口基线
        - `POST /api/tasks`
        - `GET /api/tasks/{task_id}`
        - `POST /api/tasks/{task_id}/parse`
        """,
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )
    parsed = result["parsed_requirement"]
    actions = " ".join(parsed["actions"])
    endpoints = {f"{item['method']} {item['path']}" for item in parsed["api_endpoints"]}

    assert "确认验收范围" not in actions
    assert "保障主链路可运行" not in actions
    assert "验证页面主路径" not in actions
    assert "POST /api/tasks" in actions
    assert endpoints == {
        "POST /api/tasks",
        "GET /api/tasks/{task_id}",
        "POST /api/tasks/{task_id}/parse",
    }


def test_parse_golden_preserves_querystring_filter_endpoints() -> None:
    result = parse_requirement_bundle(
        requirement_text="""
        **Request:** `GET /booking`
        **Request:** `GET /booking?firstname=Jamie`
        **Request:** `GET /booking?lastname=Brown`
        **Request:** `GET /booking?checkin=2026-04-11`
        **Request:** `GET /booking?checkout=2026-04-13`
        """,
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )
    endpoints = {f"{item['method']} {item['path']}" for item in result["parsed_requirement"]["api_endpoints"]}
    assert "GET /booking" in endpoints
    assert "GET /booking?firstname=Jamie" in endpoints
    assert "GET /booking?lastname=Brown" in endpoints
    assert "GET /booking?checkin=2026-04-11" in endpoints
    assert "GET /booking?checkout=2026-04-13" in endpoints


def test_parse_golden_light_spec_prefers_scenarios_over_metadata_actions() -> None:
    result = parse_requirement_bundle(
        requirement_text="""
        # Restful Booker E2E2 Plus

        ## 文档定位
        - 用于自动生成 Restful Booker API 的场景、用例、DSL 与执行报告。

        ## 环境信息
        - Base URL: `https://restful-booker.herokuapp.com`

        ## 鉴权与全局约束
        - 鉴权接口：`POST /auth`
        - `GET /ping` 预期返回 HTTP `201`

        ## 资源依赖说明
        - `GET /booking/{id}` 的资源来源：通过 `POST /booking` 创建 booking
        - `PUT /booking/{id}` 的资源来源：通过 `POST /booking` 创建 booking

        ## 接口清单
        ### 接口：创建 booking
        - 方法：`POST`
        - 路径：`/booking`
        - 功能：创建 booking

        ### 接口：删除 booking
        - 方法：`DELETE`
        - 路径：`/booking/{id}`
        - 功能：删除指定 booking

        ### Scenario: Booking 生命周期管理
        覆盖 booking 的健康检查、鉴权、创建、详情读取、全量更新、部分更新与删除能力。

        **涉及接口:** `GET /ping`、`POST /auth`、`POST /booking`、`GET /booking/{id}`、`PUT /booking/{id}`、`PATCH /booking/{id}`、`DELETE /booking/{id}`
        **关键依赖:** `GET /booking/{id}`、`PUT /booking/{id}`、`PATCH /booking/{id}`、`DELETE /booking/{id}` 依赖已存在 booking
        **资源来源:** 默认通过 `POST /booking` 创建 booking

        ### Scenario: Booking 列表过滤能力
        覆盖 booking 列表在 firstname、lastname 条件下的过滤查询能力。

        **涉及接口:** `GET /booking?firstname=Jamie`、`GET /booking?lastname=Brown`
        **关键依赖:** 本场景不依赖创建资源或鉴权 token，直接验证只读过滤能力
        **资源来源:** 不适用

        ## 预期效果
        - 创建成功后应返回新 booking 标识
        - 删除后再次读取应返回资源不存在
        - 过滤查询应返回合法数组结果
        """,
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )
    parsed = result["parsed_requirement"]
    actions = " ".join(parsed["actions"])
    endpoints = {f"{item['method']} {item['path']}" for item in parsed["api_endpoints"]}
    expected = " ".join(parsed["expected_results"])

    assert "Booking 生命周期管理" in actions
    assert "Booking 列表过滤能力" in actions
    assert "涉及接口:**" not in actions
    assert "资源来源：" not in actions
    assert "鉴权接口：" not in actions
    assert "预期返回 HTTP" not in actions
    assert "GET /booking/{id} 的资源来源" not in actions
    assert "POST /booking" in " ".join(sorted(endpoints))
    assert "DELETE /booking/{id}" in " ".join(sorted(endpoints))
    assert "GET /booking?firstname=Jamie" in endpoints
    assert "删除后再次读取应返回资源不存在" in expected


def test_parse_golden_light_spec_maps_cookie_auth_hint_to_authenticated_endpoints() -> None:
    result = parse_requirement_bundle(
        requirement_text="""
        # Restful Booker

        ## 鉴权与全局约束
        - 注入方式：`Cookie: token={{token}}`

        ## 接口清单
        ### 接口：获取鉴权 token
        - 方法：`POST`
        - 路径：`/auth`
        - 功能：获取 token
        - 鉴权：否

        ### 接口：删除 booking
        - 方法：`DELETE`
        - 路径：`/booking/{id}`
        - 功能：删除指定 booking
        - 鉴权：是
        - 资源前置条件：需要已存在 booking
        - 结果语义：删除成功后再次读取应返回资源不存在

        ### Scenario: Booking 删除能力
        覆盖 booking 删除能力。
        """,
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )
    endpoints = result["parsed_requirement"]["api_endpoints"]
    delete_endpoint = next(item for item in endpoints if item["method"] == "DELETE")
    request_fields = [field["name"] for field in delete_endpoint.get("request_body_fields") or []]
    assert "Cookie" in request_fields
    assert "cookie" in str(delete_endpoint.get("description", "")).lower()


def test_parse_golden_constraints_capture_explicit_status_rules_and_drop_placeholder_query_endpoints() -> None:
    result = parse_requirement_bundle(
        requirement_text="""
        ## 鉴权与全局约束
        - `GET /ping` 预期返回 HTTP `201`
        - `DELETE /booking/{id}` 可能返回 HTTP `201`

        ## 接口清单
        ### 接口：过滤查询 booking 列表
        - 方法：`GET`
        - 路径：`/booking?firstname=...`、`/booking?lastname=...`
        - 功能：按姓名过滤 booking 列表

        ### Scenario: Booking 列表过滤能力
        **涉及接口:** `GET /booking?firstname=Jamie`、`GET /booking?lastname=Brown`
        """,
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )
    parsed = result["parsed_requirement"]
    constraints = " ".join(parsed["constraints"])
    endpoints = {f"{item['method']} {item['path']}" for item in parsed["api_endpoints"]}

    assert "GET /ping" in constraints
    assert "201" in constraints
    assert "GET /booking?firstname=..." not in endpoints
    assert "GET /booking?firstname=Jamie" in endpoints
    assert "GET /booking?lastname=Brown" in endpoints
