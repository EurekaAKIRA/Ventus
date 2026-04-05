"""Unified model gateway for llm/embedding/vision access."""

from __future__ import annotations

import importlib
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

_LOG = logging.getLogger(__name__)

# PLATFORM_MODEL_GATEWAY_HTTP: auto (default) | urllib | httpx
# auto: use httpx on Windows when installed; else urllib (avoids WinError 10035 with urllib/ssl).
_HTTP_BACKEND_ENV = "PLATFORM_MODEL_GATEWAY_HTTP"
_HTTPPX: Any | None = None  # lazy: None=uncached, False=import failed, else httpx module


def _http_backend_mode() -> str:
    raw = (os.environ.get(_HTTP_BACKEND_ENV) or "auto").strip().lower()
    if raw in ("auto", "urllib", "httpx"):
        return raw
    return "auto"


def _get_httpx():
    """Return httpx module or None if unavailable."""
    global _HTTPPX
    if _HTTPPX is None:
        try:
            _HTTPPX = importlib.import_module("httpx")
        except ImportError:
            _HTTPPX = False
    return _HTTPPX if _HTTPPX is not False else None


def _want_httpx_backend() -> bool:
    mode = _http_backend_mode()
    if mode == "urllib":
        return False
    if mode == "httpx":
        return True
    return sys.platform == "win32"

# Windows: WSAEWOULDBLOCK (10035) can surface during urllib/ssl recv despite a blocking
# socket when a timeout is set (see CPython issues around non-blocking edge cases).
_WOULDBLOCK_RETRIES = 40


def _socket_wouldblock(exc: BaseException) -> bool:
    if isinstance(exc, BlockingIOError):
        return True
    if isinstance(exc, OSError):
        if getattr(exc, "winerror", None) == 10035:
            return True
        if exc.errno == 10035:
            return True
    return False


def _urllib_wouldblock(exc: urllib.error.URLError) -> bool:
    reason = exc.reason
    if reason is None:
        return False
    if isinstance(reason, urllib.error.URLError):
        return _urllib_wouldblock(reason)
    return _socket_wouldblock(reason)


def _read_http_response_body(resp: Any, *, per_read_attempts: int = 64) -> bytes:
    """Read full body; retry transient Windows WSAEWOULDBLOCK during recv."""
    chunks: list[bytes] = []
    while True:
        chunk: bytes | None = None
        last_exc: BaseException | None = None
        for attempt in range(per_read_attempts):
            try:
                chunk = resp.read(65536)
                last_exc = None
                break
            except (BlockingIOError, OSError) as e:
                last_exc = e
                if not _socket_wouldblock(e):
                    raise
                time.sleep(min(0.001 * (attempt + 1), 0.05))
        if last_exc is not None:
            raise last_exc
        assert chunk is not None
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


@dataclass(slots=True)
class ModelEndpointConfig:
    provider: str
    model: str
    api_base: str
    api_key: str
    timeout: float = 60.0
    retries: int = 1


@dataclass(slots=True)
class ModelGatewayConfig:
    llm: ModelEndpointConfig | None = None
    embedding: ModelEndpointConfig | None = None
    vision: ModelEndpointConfig | None = None


class ModelGatewayError(RuntimeError):
    """Base gateway exception."""


class ModelGatewayTimeoutError(ModelGatewayError):
    """Timeout during model call."""


class ModelGatewayResponseError(ModelGatewayError):
    """Unexpected response payload."""


class ModelGateway:
    """Unified gateway that encapsulates provider-specific HTTP calls."""

    def __init__(self, config: ModelGatewayConfig):
        self.config = config

    def embedding(self, texts: list[str]) -> list[list[float]]:
        endpoint = self.config.embedding
        if endpoint is None:
            raise ModelGatewayError("embedding endpoint config is missing")
        if endpoint.provider != "openai":
            raise ModelGatewayError(f"unsupported embedding provider: {endpoint.provider}")
        payload = {"model": endpoint.model, "input": texts}
        response = self._request_json(endpoint, "/embeddings", payload)
        data = response.get("data") or []
        vectors: list[list[float]] = []
        for item in data:
            embedding = item.get("embedding")
            if isinstance(embedding, list):
                vectors.append([float(value) for value in embedding])
        return vectors

    def chat_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        endpoint = self.config.llm
        if endpoint is None:
            raise ModelGatewayError("llm endpoint config is missing")
        if endpoint.provider != "openai":
            raise ModelGatewayError(f"unsupported llm provider: {endpoint.provider}")
        payload = {
            "model": endpoint.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "temperature": temperature,
        }
        response = self._request_json(endpoint, "/chat/completions", payload)
        choices = response.get("choices") or []
        if not choices:
            raise ModelGatewayResponseError("empty choices from llm")
        content = ((choices[0].get("message") or {}).get("content") or "").strip()
        if not content:
            raise ModelGatewayResponseError("empty content from llm")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ModelGatewayResponseError("llm returned non-json content") from exc
        if not isinstance(parsed, dict):
            raise ModelGatewayResponseError("llm response is not a JSON object")
        return parsed

    def _request_json(
        self,
        endpoint: ModelEndpointConfig,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        max_attempts = endpoint.retries + 1
        for attempt in range(max_attempts):
            try:
                result = self._request_json_once(endpoint, path, payload)
                if attempt > 0:
                    _LOG.info(
                        "model_gateway request succeeded after retry path=%s attempt=%s/%s model=%s",
                        path,
                        attempt + 1,
                        max_attempts,
                        endpoint.model,
                    )
                return result
            except ModelGatewayTimeoutError as exc:
                last_error = exc
                if attempt >= endpoint.retries:
                    _LOG.warning(
                        "model_gateway request exhausted timeouts path=%s attempts=%s model=%s error=%s",
                        path,
                        max_attempts,
                        endpoint.model,
                        exc,
                    )
                    break
                backoff = min(0.2 * (attempt + 1), 0.8)
                _LOG.warning(
                    "model_gateway request timeout path=%s attempt=%s/%s model=%s backoff_s=%.2f error=%s",
                    path,
                    attempt + 1,
                    max_attempts,
                    endpoint.model,
                    backoff,
                    exc,
                )
            except ModelGatewayError as exc:
                last_error = exc
                msg = str(exc).lower()
                is_client_error = any(f"http {code}" in msg for code in ("400", "401", "403", "404", "422"))
                if is_client_error or attempt >= endpoint.retries:
                    if attempt >= endpoint.retries and not is_client_error:
                        _LOG.warning(
                            "model_gateway request failed path=%s attempts=%s model=%s error=%s",
                            path,
                            attempt + 1,
                            endpoint.model,
                            exc,
                        )
                    break  # 4xx client errors: retrying won't help
                backoff = min(0.2 * (attempt + 1), 0.8)
                _LOG.warning(
                    "model_gateway request error will_retry path=%s attempt=%s/%s model=%s backoff_s=%.2f error=%s",
                    path,
                    attempt + 1,
                    max_attempts,
                    endpoint.model,
                    backoff,
                    exc,
                )
            if attempt < endpoint.retries:
                time.sleep(min(0.2 * (attempt + 1), 0.8))
        if isinstance(last_error, ModelGatewayError):
            raise last_error
        raise ModelGatewayError("model request failed")

    def _request_json_once_httpx(
        self,
        endpoint: ModelEndpointConfig,
        path: str,
        payload: dict[str, Any],
        httpx_mod: Any,
    ) -> dict[str, Any]:
        url = endpoint.api_base.rstrip("/") + path
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {endpoint.api_key}",
        }
        try:
            with httpx_mod.Client(http2=False) as client:
                response = client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=endpoint.timeout,
                )
        except httpx_mod.TimeoutException as exc:
            raise ModelGatewayTimeoutError(str(exc)) from exc
        except httpx_mod.RequestError as exc:
            raise ModelGatewayError(str(exc)) from exc

        if response.status_code >= 400:
            detail = (response.text or "")[:300]
            raise ModelGatewayError(f"http {response.status_code}: {detail}")

        try:
            parsed = response.json()
        except json.JSONDecodeError as exc:
            raise ModelGatewayError("invalid json in response body") from exc
        if not isinstance(parsed, dict):
            raise ModelGatewayError("response json is not an object")
        return parsed

    def _request_json_once(
        self,
        endpoint: ModelEndpointConfig,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not endpoint.api_key.strip():
            raise ModelGatewayError("api_key is empty")

        use_httpx = _want_httpx_backend()
        if use_httpx:
            httpx_mod = _get_httpx()
            if httpx_mod is not None:
                return self._request_json_once_httpx(endpoint, path, payload, httpx_mod)
            if _http_backend_mode() == "httpx":
                raise ModelGatewayError(
                    "PLATFORM_MODEL_GATEWAY_HTTP=httpx requires the httpx package; install with: pip install httpx"
                )
            _LOG.debug(
                "model_gateway httpx backend wanted but httpx not installed; falling back to urllib"
            )

        url = endpoint.api_base.rstrip("/") + path
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {endpoint.api_key}",
            },
            data=body,
        )
        for wb in range(_WOULDBLOCK_RETRIES):
            try:
                with urllib.request.urlopen(req, timeout=endpoint.timeout) as resp:
                    raw = _read_http_response_body(resp)
                return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:  # pragma: no cover - network dependent
                detail = exc.read().decode("utf-8", errors="replace")
                raise ModelGatewayError(f"http {exc.code}: {detail[:300]}") from exc
            except urllib.error.URLError as exc:  # pragma: no cover - network dependent
                if _urllib_wouldblock(exc) and wb < _WOULDBLOCK_RETRIES - 1:
                    time.sleep(min(0.05 * (wb + 1), 0.5))
                    continue
                reason = str(getattr(exc, "reason", exc))
                if "timed out" in reason.lower():
                    raise ModelGatewayTimeoutError(reason) from exc
                raise ModelGatewayError(reason) from exc
            except TimeoutError as exc:  # socket read timeout during resp.read()
                raise ModelGatewayTimeoutError(str(exc)) from exc
            except (BlockingIOError, OSError) as exc:  # pragma: no cover - network dependent
                if _socket_wouldblock(exc) and wb < _WOULDBLOCK_RETRIES - 1:
                    time.sleep(min(0.05 * (wb + 1), 0.5))
                    continue
                raise ModelGatewayError(str(exc)) from exc
