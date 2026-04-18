from __future__ import annotations

from requirement_analysis.service import AnalysisParseOptions, parse_requirement_bundle


def test_parse_service_baseline() -> None:
    result = parse_requirement_bundle(
        requirement_text="用户登录后进入个人中心并查看昵称",
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=True,
            retrieval_top_k=5,
            rerank_enabled=False,
        ),
    )
    assert "parsed_requirement" in result
    assert "retrieved_context" in result
    assert "validation_report" in result
    assert result["parse_metadata"]["parse_mode"] in {"rules", "llm"}
    assert result["parse_metadata"]["llm_attempted"] is False
    assert result["parse_metadata"]["rag_enabled"] is True
    assert result["parse_metadata"]["rag_used"] is True
    assert result["parse_metadata"]["retrieval_top_k"] == 5
    assert result["parse_metadata"]["retrieval_query_char_count"] > 0
    assert "retrieval_query_preview" in result["parse_metadata"]
    assert result["parse_metadata"]["retrieval_scoring"]["lexical_weight"] > 0
    assert result["parse_metadata"]["document_char_count"] > 0
    assert result["parse_metadata"]["chunk_count"] > 0
    assert result["parse_metadata"]["processing_tier"] in {"realtime", "batch", "large_document"}
    assert "embedding_error_detail" in result["parse_metadata"]["retrieval_metrics"]
    ck = result["parse_metadata"]["contract_knowledge"]
    assert ck["enabled"] is True
    assert ck["applied"] is False
    assert ck["merged_snippet_count"] == 0
    kb = result["parse_metadata"]["knowledge_base"]
    assert kb["enabled"] is True
    assert kb["applied"] is False
    assert kb["merged_snippet_count"] == 0
    assert result["parse_metadata"]["retrieval_metrics"]["retrieval_low_score_rejection"] is False


def test_parse_service_llm_fallback_when_missing_config(monkeypatch) -> None:
    monkeypatch.delenv("HUNYUAN_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = parse_requirement_bundle(
        requirement_text="用户提交订单后应返回订单号",
        options=AnalysisParseOptions(
            use_llm=True,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )
    metadata = result["parse_metadata"]
    assert metadata["parse_mode"] == "rules"
    assert metadata["llm_attempted"] is True
    assert metadata["rag_enabled"] is False
    assert metadata["rag_used"] is False
    assert metadata["fallback_reason"] == "llm_config_missing"
    assert metadata["llm_error_type"] == "configuration_error"


def test_parse_service_llm_response_invalid_fallback(monkeypatch) -> None:
    monkeypatch.setenv("HUNYUAN_API_KEY", "test-key")
    monkeypatch.setattr(
        "requirement_analysis.api_requirement_parser.enhance_parsed_requirement_with_metadata",
        lambda **kwargs: (
            kwargs.get("out_response_diagnostics", {}).update({"empty_payload_reason": "nested_payload_wrapper"}) or None,
            "llm_response_invalid",
            "ModelGatewayResponseError",
        ),
    )
    result = parse_requirement_bundle(
        requirement_text="用户提交订单后应返回订单号",
        options=AnalysisParseOptions(
            use_llm=True,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )
    metadata = result["parse_metadata"]
    assert metadata["parse_mode"] == "rules"
    assert metadata["fallback_reason"] == "llm_response_invalid"
    assert metadata["llm_error_type"] == "ModelGatewayResponseError"
    assert metadata["llm_response_diagnostics"]["empty_payload_reason"] == "nested_payload_wrapper"


def test_parse_service_llm_wrapped_payload_can_be_applied(monkeypatch) -> None:
    monkeypatch.setenv("HUNYUAN_API_KEY", "test-key")
    monkeypatch.setattr(
        "requirement_analysis.api_requirement_parser.enhance_parsed_requirement_with_metadata",
        lambda **kwargs: (
            {"objective": "包装结果", "actions": ["创建任务"]},
            "",
            "",
        ),
    )
    result = parse_requirement_bundle(
        requirement_text="用户提交订单后应返回订单号",
        options=AnalysisParseOptions(
            use_llm=True,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )
    metadata = result["parse_metadata"]
    assert metadata["parse_mode"] == "llm"
    assert metadata["llm_used"] is True
    assert result["parsed_requirement"]["objective"] == "包装结果"


def test_parse_service_llm_timeout_fallback(monkeypatch) -> None:
    monkeypatch.setenv("HUNYUAN_API_KEY", "test-key")
    monkeypatch.setattr(
        "requirement_analysis.api_requirement_parser.enhance_parsed_requirement_with_metadata",
        lambda **_: (None, "llm_timeout", "ModelGatewayTimeoutError"),
    )
    result = parse_requirement_bundle(
        requirement_text="用户提交订单后应返回订单号",
        options=AnalysisParseOptions(
            use_llm=True,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )
    metadata = result["parse_metadata"]
    assert metadata["parse_mode"] == "rules"
    assert metadata["fallback_reason"] == "llm_timeout"
    assert metadata["llm_error_type"] == "ModelGatewayTimeoutError"


def test_parse_service_options_priority_request_overrides_defaults() -> None:
    options = AnalysisParseOptions.resolve(
        {
            "use_llm": True,
            "rag_enabled": False,
            "retrieval_top_k": 2,
            "rerank_enabled": True,
            "model_profile": "high_quality",
        }
    )
    assert options.use_llm is True
    assert options.rag_enabled is False
    assert options.retrieval_top_k == 2
    assert options.rerank_enabled is True
    assert options.model_profile == "high_quality"


def test_parse_service_prefers_hunyuan_api_key(monkeypatch) -> None:
    monkeypatch.setenv("HUNYUAN_API_KEY", "hunyuan-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    result = parse_requirement_bundle(
        requirement_text="用户登录后进入个人中心并查看昵称",
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=True,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )
    metadata = result["parse_metadata"]
    assert metadata["llm_provider_profile"] == "tencent_hunyuan_openai_compat"
    assert metadata["model_profile"] == "default"
    assert "rag_fallback_reason" in metadata


def test_parse_service_marks_batch_tier_for_large_text() -> None:
    text = "用户登录后进入个人中心并查看昵称。"
    large_requirement = text * 1200
    result = parse_requirement_bundle(
        requirement_text=large_requirement,
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )
    metadata = result["parse_metadata"]
    assert metadata["cleaned_char_count"] > 20000
    assert metadata["processing_tier"] in {"batch", "large_document"}


def test_parse_service_flags_suspiciously_truncated_input() -> None:
    truncated_requirement = (
        "# Restful Booker\n\n"
        "## Step 1\n\n"
        "**Request:** `POST /booking`\n\n"
        "**Body:**\n\n"
        "```json\n"
        "{\n"
        '  "firstname": "Jim",\n'
        '  "bookingdates": {\n'
        '    "checkin": "2026-0'
    )
    padded_requirement = truncated_requirement + ("x" * (1024 - len(truncated_requirement)))

    result = parse_requirement_bundle(
        requirement_text=padded_requirement,
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )

    metadata = result["parse_metadata"]
    assert metadata["input_truncation_suspected"] is True
    assert metadata["input_integrity_issues"]
    assert result["validation_report"]["passed"] is False
    assert any("疑似被截断" in item for item in result["validation_report"]["errors"])
    assert any("疑似被截断" in item for item in result["parsed_requirement"]["ambiguities"])


def test_parse_service_retrieval_query_prefers_structured_api_signals() -> None:
    result = parse_requirement_bundle(
        requirement_text="""
        # Restful Booker E2E2 Plus

        ## 鉴权与全局约束
        - 鉴权接口：`POST /auth`

        ## 接口清单
        ### 接口：创建 booking
        - 方法：`POST`
        - 路径：`/booking`

        ### Scenario: Booking 生命周期管理
        **涉及接口:** `POST /auth`、`POST /booking`、`DELETE /booking/{id}`
        """,
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )

    preview = result["parse_metadata"]["retrieval_query_preview"]
    assert "Restful Booker E2E2 Plus" in preview
    assert "Scenario: Booking 生命周期管理" in preview
    assert "POST /auth" in preview
    assert "POST /booking" in preview


def test_parse_service_applies_contract_knowledge_only_for_platform_docs() -> None:
    result = parse_requirement_bundle(
        requirement_text="""
        # Task Center 主链路

        ## 接口基线
        - `POST /api/tasks`
        - `GET /api/tasks/{task_id}`
        - `POST /api/tasks/{task_id}/execute`
        """,
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )

    ck = result["parse_metadata"]["contract_knowledge"]
    assert ck["enabled"] is True
    assert ck["applied"] is True
    assert ck["merged_snippet_count"] >= 1
    kb = result["parse_metadata"]["knowledge_base"]
    assert kb["applied"] is True
    assert any(path.endswith("domain/platform/task_center_api.md") for path in kb["source_files"])


def test_parse_service_warns_on_implicit_resource_dependency_and_context() -> None:
    result = parse_requirement_bundle(
        requirement_text="""
        # API 文档

        Scenario: update profile
        使用上一步返回值继续调用接口

        GET /users/{id}
        PUT /users/{id}
        DELETE /users/{id}
        """,
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )

    warnings = result["validation_report"]["warnings"]
    assert any("资源来源/关键依赖" in item for item in warnings)
    assert any("save_context / uses_context" in item for item in warnings)


def test_parse_service_detects_base_url_from_document() -> None:
    result = parse_requirement_bundle(
        requirement_text="""
        # Restful Booker API

        ## 环境信息
        - Base URL: `https://restful-booker.herokuapp.com`

        ## 场景
        **涉及接口:** `POST /auth`、`POST /booking`
        """,
        options=AnalysisParseOptions(
            use_llm=False,
            rag_enabled=False,
            retrieval_top_k=3,
            rerank_enabled=False,
        ),
    )

    assert result["parse_metadata"]["detected_base_url"] == "https://restful-booker.herokuapp.com"
