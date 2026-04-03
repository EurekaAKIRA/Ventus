from __future__ import annotations

from platform_shared import ModelGatewayError, ModelGatewayTimeoutError
from requirement_analysis.openai_enhancement import (
    OpenAIEnhancementConfig,
    enhance_parsed_requirement_with_metadata,
)


class _RaisingGateway:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def chat_json(self, **_: object):
        raise self._exc


def test_enhancement_classifies_timeout_error() -> None:
    payload, reason, error_type = enhance_parsed_requirement_with_metadata(
        requirement_text="用户登录后进入个人中心",
        retrieved_context=[],
        rule_based_result={"objective": "登录"},
        config=OpenAIEnhancementConfig(gateway=_RaisingGateway(ModelGatewayTimeoutError("timed out"))),  # type: ignore[arg-type]
    )
    assert payload is None
    assert reason == "llm_timeout"
    assert error_type == "ModelGatewayTimeoutError"


def test_enhancement_classifies_auth_error() -> None:
    payload, reason, error_type = enhance_parsed_requirement_with_metadata(
        requirement_text="用户登录后进入个人中心",
        retrieved_context=[],
        rule_based_result={"objective": "登录"},
        config=OpenAIEnhancementConfig(gateway=_RaisingGateway(ModelGatewayError("http 401: unauthorized"))),  # type: ignore[arg-type]
    )
    assert payload is None
    assert reason == "llm_auth_error"
    assert error_type == "ModelGatewayError"
