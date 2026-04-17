"""LLM JSON cleanup: list-shaped fields must not iterate over a single string."""

from __future__ import annotations

from typing import Any

from requirement_analysis.openai_enhancement import OpenAIEnhancementConfig, enhance_parsed_requirement_with_metadata


class _StubLLMEndpoint:
    model = "stub"
    api_base = "http://stub"
    timeout = 1.0
    retries = 0


class _StubGatewayConfig:
    llm = _StubLLMEndpoint()


class _StringListPayloadGateway:
    config = _StubGatewayConfig()

    def chat_json(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "objective": "目标",
            "preconditions": "同一 task_id 应能关联创建参数与执行结果",
            "actors": ["用户"],
            "actions": ["创建任务", "触发解析"],
            "expected_results": "返回 task_id",
            "api_endpoints": [{"method": "GET", "path": "/health", "description": "探活"}],
            "constraints": "",
            "ambiguities": [],
        }


class _WrappedPayloadGateway:
    config = _StubGatewayConfig()

    def chat_json(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "result": {
                "objective": "目标",
                "actions": ["创建任务"],
            }
        }


def test_enhancement_coerces_string_to_single_element_lists() -> None:
    payload, reason, err = enhance_parsed_requirement_with_metadata(
        requirement_text="示例",
        retrieved_context=[],
        rule_based_result={"objective": "x"},
        config=OpenAIEnhancementConfig(gateway=_StringListPayloadGateway()),  # type: ignore[arg-type]
    )
    assert reason == ""
    assert err == ""
    assert payload is not None
    assert payload["preconditions"] == ["同一 task_id 应能关联创建参数与执行结果"]
    assert payload["expected_results"] == ["返回 task_id"]
    assert payload["constraints"] == []


def test_enhancement_reports_wrapped_payload_diagnostics() -> None:
    diagnostics: dict[str, Any] = {}
    payload, reason, err = enhance_parsed_requirement_with_metadata(
        requirement_text="示例",
        retrieved_context=[],
        rule_based_result={"objective": "x"},
        config=OpenAIEnhancementConfig(gateway=_WrappedPayloadGateway()),  # type: ignore[arg-type]
        out_response_diagnostics=diagnostics,
    )
    assert reason == ""
    assert err == ""
    assert payload is not None
    assert payload["objective"] == "目标"
    assert payload["actions"] == ["创建任务"]
    assert diagnostics == {}
