"""Unified model gateway for llm/embedding/vision access."""

from __future__ import annotations

import importlib
import json
import logging
import os
import re
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


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def _assistant_message_json_blobs(message: dict[str, Any] | None) -> list[str]:
    """Build candidate strings to parse (content, reasoning_content, and sensible merges).

    Some OpenAI-compatible gateways leave ``content`` empty and put the assistant text in
    ``reasoning_content``, or split thinking vs final answer across both fields.
    """
    if not message:
        return []
    main = _normalize_assistant_message_content(message.get("content")).strip()
    reason = _normalize_assistant_message_content(message.get("reasoning_content")).strip()
    ordered: list[str] = []
    seen: set[str] = set()

    def add(blob: str) -> None:
        piece = blob.strip()
        if piece and piece not in seen:
            seen.add(piece)
            ordered.append(piece)

    add(main)
    add(reason)
    if main and reason:
        add(main + "\n" + reason)
        add(reason + "\n" + main)
    return ordered


def _normalize_assistant_message_content(content: Any) -> str:
    """Turn chat message ``content`` into a single string (OpenAI-compatible + list segments)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if str(item.get("type", "")).lower() == "text":
                    parts.append(str(item.get("text", "")))
                elif "text" in item:
                    parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


def _extract_first_json_object_dict(text: str) -> dict[str, Any] | None:
    """Parse the first JSON object in *text* using incremental decode (ignores trailing junk)."""
    decoder = json.JSONDecoder()
    n = len(text)
    i = 0
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        try:
            obj, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            i += 1
            continue
        if isinstance(obj, dict):
            return obj
        i = end if end > i else i + 1
    return None


def parse_llm_json_object_content(content: str) -> dict[str, Any]:
    """Parse a JSON object from raw LLM message text.

    Tolerates markdown ```json fences and short prose before/after the object.
    Some OpenAI-compatible providers still wrap or prefix the payload despite
    ``response_format: json_object``.
    """
    text = (content or "").strip().lstrip("\ufeff")
    if not text:
        raise ModelGatewayResponseError("empty content from llm")
    last_error: json.JSONDecodeError | None = None
    for candidate in _llm_json_object_string_candidates(text):
        parsed_dict: dict[str, Any] | None = None
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                parsed_dict = parsed
        except json.JSONDecodeError as exc:
            last_error = exc
        if parsed_dict is None:
            parsed_dict = _extract_first_json_object_dict(candidate)
        if parsed_dict is not None:
            return parsed_dict
    if last_error is not None:
        raise ModelGatewayResponseError("llm returned non-json content") from last_error
    raise ModelGatewayResponseError("llm returned non-json content")


def _llm_json_object_string_candidates(text: str) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    def add(fragment: str) -> None:
        piece = fragment.strip()
        if piece and piece not in seen:
            seen.add(piece)
            ordered.append(piece)

    add(text)
    for match in _JSON_FENCE_RE.finditer(text):
        add(match.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        add(text[start : end + 1])
    return ordered


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
        message = choices[0].get("message") or {}
        blobs = _assistant_message_json_blobs(message if isinstance(message, dict) else {})
        if not blobs:
            raise ModelGatewayResponseError("empty content from llm")
        last_exc: BaseException | None = None
        for blob in blobs:
            try:
                return parse_llm_json_object_content(blob)
            except ModelGatewayResponseError as exc:
                last_exc = exc
        preview = max(blobs, key=len)
        _LOG.warning(
            "model_gateway chat_json parse failed model=%s attempts=%s preview=%r",
            endpoint.model,
            len(blobs),
            preview[:800],
        )
        if last_exc is not None:
            raise last_exc
        raise ModelGatewayResponseError("llm returned non-json content")

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
