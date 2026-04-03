"""Unified model gateway for llm/embedding/vision access."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ModelEndpointConfig:
    provider: str
    model: str
    api_base: str
    api_key: str
    timeout: float = 20.0
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
        for attempt in range(endpoint.retries + 1):
            try:
                return self._request_json_once(endpoint, path, payload)
            except ModelGatewayTimeoutError as exc:
                last_error = exc
                break  # timeout won't improve with same payload; fail fast
            except ModelGatewayError as exc:
                last_error = exc
                msg = str(exc).lower()
                is_client_error = any(f"http {code}" in msg for code in ("400", "401", "403", "404", "422"))
                if is_client_error or attempt >= endpoint.retries:
                    break  # 4xx client errors: retrying won't help
            if attempt < endpoint.retries:
                time.sleep(min(0.2 * (attempt + 1), 0.8))
        if isinstance(last_error, ModelGatewayError):
            raise last_error
        raise ModelGatewayError("model request failed")

    def _request_json_once(
        self,
        endpoint: ModelEndpointConfig,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not endpoint.api_key.strip():
            raise ModelGatewayError("api_key is empty")
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
        try:
            with urllib.request.urlopen(req, timeout=endpoint.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network dependent
            detail = exc.read().decode("utf-8", errors="replace")
            raise ModelGatewayError(f"http {exc.code}: {detail[:300]}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network dependent
            reason = str(getattr(exc, "reason", exc))
            if "timed out" in reason.lower():
                raise ModelGatewayTimeoutError(reason) from exc
            raise ModelGatewayError(reason) from exc
        except TimeoutError as exc:  # socket read timeout during resp.read()
            raise ModelGatewayTimeoutError(str(exc)) from exc
