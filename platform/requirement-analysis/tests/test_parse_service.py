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
    assert result["parse_metadata"]["retrieval_scoring"]["lexical_weight"] > 0
    assert result["parse_metadata"]["document_char_count"] > 0
    assert result["parse_metadata"]["chunk_count"] > 0
    assert result["parse_metadata"]["processing_tier"] in {"realtime", "batch", "large_document"}
    assert "embedding_error_detail" in result["parse_metadata"]["retrieval_metrics"]
    ck = result["parse_metadata"]["contract_knowledge"]
    assert ck["enabled"] is True
    assert ck["merged_snippet_count"] >= 1
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
        lambda **_: (None, "llm_response_invalid", "ModelGatewayResponseError"),
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
