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
