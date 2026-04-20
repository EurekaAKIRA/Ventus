"""Helpers for encrypting and masking environment secrets."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from platform_shared.models import EnvironmentConfig

MASKED_SECRET_PLACEHOLDER = "***MASKED***"
SECURE_PAYLOAD_MARKER = "__task_center_secure__"
SECURE_PAYLOAD_VERSION = 1

SENSITIVE_HEADER_KEYS = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "api-key",
    "apikey",
    "x-auth-token",
    "x-access-token",
    "access-token",
}

VISIBLE_AUTH_VALUE_KEYS = {
    "type",
    "scheme",
    "header",
    "prefix",
    "token_context",
}


def _normalize_secret_material() -> bytes:
    raw = (
        str(os.getenv("TASK_CENTER_CONFIG_SECRET", "")).strip()
        or str(os.getenv("TASK_CENTER_JWT_SECRET", "")).strip()
        or "task-center-dev-config-secret-change-me"
    )
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    return Fernet(_normalize_secret_material())


def encrypt_json_payload(payload: dict[str, Any] | list[Any] | None) -> dict[str, Any] | list[Any] | None:
    if payload is None:
        return None
    if payload == {} or payload == []:
        return payload
    plaintext = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    token = _fernet().encrypt(plaintext).decode("utf-8")
    return {
        SECURE_PAYLOAD_MARKER: True,
        "version": SECURE_PAYLOAD_VERSION,
        "ciphertext": token,
    }


def decrypt_json_payload(payload: dict[str, Any] | list[Any] | None) -> dict[str, Any] | list[Any] | None:
    if payload is None:
        return None
    if isinstance(payload, dict) and payload.get(SECURE_PAYLOAD_MARKER) is True:
        ciphertext = str(payload.get("ciphertext", "")).strip()
        if not ciphertext:
            return {}
        try:
            plaintext = _fernet().decrypt(ciphertext.encode("utf-8"))
        except InvalidToken as exc:
            raise RuntimeError(
                "Failed to decrypt environment secrets. Check TASK_CENTER_CONFIG_SECRET / TASK_CENTER_JWT_SECRET."
            ) from exc
        decoded = json.loads(plaintext.decode("utf-8"))
        if isinstance(decoded, (dict, list)):
            return decoded
        return {}
    return payload


def is_sensitive_header_key(key: str) -> bool:
    normalized = str(key or "").strip().lower()
    return normalized in SENSITIVE_HEADER_KEYS or normalized.endswith("token") or normalized.endswith("secret")


def _mask_structure(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _mask_structure(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_mask_structure(item) for item in value]
    if value in {None, ""}:
        return value
    return MASKED_SECRET_PLACEHOLDER


def mask_auth_payload(value: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, item in (value or {}).items():
        if key in VISIBLE_AUTH_VALUE_KEYS:
            output[key] = item
        else:
            output[key] = _mask_structure(item)
    return output


def mask_default_headers(headers: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    output: dict[str, Any] = {}
    masked_keys: list[str] = []
    for key, value in (headers or {}).items():
        if is_sensitive_header_key(key) and value not in {None, ""}:
            output[key] = MASKED_SECRET_PLACEHOLDER
            masked_keys.append(str(key))
        else:
            output[key] = value
    return output, masked_keys


def restore_masked_structure(candidate: Any, existing: Any) -> Any:
    if candidate == MASKED_SECRET_PLACEHOLDER:
        return existing
    if isinstance(candidate, dict) and isinstance(existing, dict):
        restored: dict[str, Any] = {}
        for key, value in candidate.items():
            restored[key] = restore_masked_structure(value, existing.get(key))
        return restored
    if isinstance(candidate, list) and isinstance(existing, list):
        restored_list: list[Any] = []
        for index, value in enumerate(candidate):
            previous = existing[index] if index < len(existing) else None
            restored_list.append(restore_masked_structure(value, previous))
        return restored_list
    return candidate


def restore_masked_default_headers(candidate: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    restored: dict[str, Any] = {}
    for key, value in (candidate or {}).items():
        if value == MASKED_SECRET_PLACEHOLDER and is_sensitive_header_key(key):
            restored[key] = existing.get(key)
        else:
            restored[key] = value
    return restored


def merge_masked_environment_config(candidate: EnvironmentConfig, existing: EnvironmentConfig | None) -> EnvironmentConfig:
    if existing is None:
        return candidate
    merged_headers = restore_masked_default_headers(
        dict(candidate.default_headers or {}),
        dict(existing.default_headers or {}),
    )
    merged_auth = restore_masked_structure(dict(candidate.auth or {}), dict(existing.auth or {}))
    merged_cookies = restore_masked_structure(dict(candidate.cookies or {}), dict(existing.cookies or {}))
    return EnvironmentConfig(
        name=candidate.name,
        base_url=candidate.base_url,
        default_headers=merged_headers,
        auth=merged_auth if isinstance(merged_auth, dict) else {},
        cookies=merged_cookies if isinstance(merged_cookies, dict) else {},
        description=candidate.description,
    )


def mask_environment_config(config: EnvironmentConfig) -> dict[str, Any]:
    masked_headers, masked_header_keys = mask_default_headers(dict(config.default_headers or {}))
    auth_payload = dict(config.auth or {})
    cookies_payload = dict(config.cookies or {})
    return {
        "name": config.name,
        "base_url": config.base_url,
        "default_headers": masked_headers,
        "auth": mask_auth_payload(auth_payload) if auth_payload else {},
        "cookies": _mask_structure(cookies_payload) if cookies_payload else {},
        "description": config.description,
        "default_headers_masked": bool(masked_header_keys),
        "masked_header_keys": masked_header_keys,
        "auth_masked": bool(auth_payload),
        "cookies_masked": bool(cookies_payload),
    }
