"""Model gateway httpx backend selection (mocked, no network)."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from platform_shared.model_gateway import (
    ModelEndpointConfig,
    ModelGateway,
    ModelGatewayConfig,
    ModelGatewayError,
)


@pytest.fixture
def endpoint() -> ModelEndpointConfig:
    return ModelEndpointConfig(
        provider="openai",
        model="test-model",
        api_base="https://example.com/v1",
        api_key="k",
        timeout=10.0,
        retries=0,
    )


def test_httpx_backend_posts_json(monkeypatch: pytest.MonkeyPatch, endpoint: ModelEndpointConfig) -> None:
    monkeypatch.setenv("PLATFORM_MODEL_GATEWAY_HTTP", "httpx")
    fake_httpx = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    fake_httpx.Client.return_value = mock_client
    fake_httpx.TimeoutException = type("TimeoutException", (Exception,), {})
    fake_httpx.RequestError = type("RequestError", (Exception,), {})

    gw = ModelGateway(ModelGatewayConfig(llm=endpoint))
    with patch("platform_shared.model_gateway._get_httpx", return_value=fake_httpx):
        with patch("platform_shared.model_gateway._want_httpx_backend", return_value=True):
            out = gw._request_json_once(endpoint, "/x", {"a": 1})  # noqa: SLF001

    assert out == {"ok": True}
    mock_client.post.assert_called_once()
    call_kw = mock_client.post.call_args.kwargs
    assert call_kw["json"] == {"a": 1}
    assert call_kw["timeout"] == 10.0


def test_forced_httpx_without_package_raises(monkeypatch: pytest.MonkeyPatch, endpoint: ModelEndpointConfig) -> None:
    monkeypatch.setenv("PLATFORM_MODEL_GATEWAY_HTTP", "httpx")
    gw = ModelGateway(ModelGatewayConfig(llm=endpoint))
    with patch("platform_shared.model_gateway._get_httpx", return_value=None):
        with pytest.raises(ModelGatewayError, match="pip install httpx"):
            gw._request_json_once(endpoint, "/x", {})  # noqa: SLF001


def test_auto_non_windows_skips_httpx(monkeypatch: pytest.MonkeyPatch, endpoint: ModelEndpointConfig) -> None:
    monkeypatch.delenv("PLATFORM_MODEL_GATEWAY_HTTP", raising=False)
    gw = ModelGateway(ModelGatewayConfig(llm=endpoint))
    with patch.object(sys, "platform", "linux"):
        from platform_shared import model_gateway as mg

        assert mg._want_httpx_backend() is False  # noqa: SLF001
