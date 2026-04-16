"""Execution preflight checks (base_url reachability, minimal config hints)."""

from __future__ import annotations

import socket
import time
from typing import Any
from urllib.parse import urlparse

import requests


def _resolve_timeout(timeout_s: float) -> tuple[float, float]:
    timeout_s = max(float(timeout_s), 0.1)
    connect_timeout = min(timeout_s, 3.0)
    read_timeout = max(timeout_s, connect_timeout)
    return (connect_timeout, read_timeout)


def _probe_candidates(base_url: str) -> list[tuple[str, str]]:
    trimmed = base_url.rstrip("/")
    return [
        (trimmed + "/health", "/health"),
        (trimmed + "/ping", "/ping"),
        (trimmed or base_url, "/"),
    ]


def _classify_request_exception(exc: Exception) -> str:
    if isinstance(exc, requests.Timeout):
        return "timeout"
    if isinstance(exc, requests.exceptions.SSLError):
        return "ssl_error"
    if isinstance(exc, requests.ConnectionError):
        return "network_error"
    if isinstance(exc, socket.timeout):
        return "timeout"
    return "unknown_error"


def run_preflight_check(
    *,
    task_id: str,
    base_url: str,
    default_headers: dict[str, Any],
    auth: dict[str, Any],
    latency_threshold_ms: float = 1500.0,
    checks: list[str] | None = None,
) -> dict[str, Any]:
    """Return structured preflight result for API execution (no side effects on task state)."""
    selected = checks or [
        "base_url_reachable",
        "auth_config_valid",
    ]
    check_results: list[dict[str, Any]] = []
    blocking_issues: list[str] = []
    suggestions: list[str] = []

    parsed = urlparse((base_url or "").strip())
    scheme_ok = parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    if "base_url_reachable" in selected:
        if not base_url.strip():
            check_results.append(
                {
                    "name": "base_url_reachable",
                    "status": "failed",
                    "elapsed_ms": 0.0,
                    "message": "base_url is empty",
                }
            )
            blocking_issues.append("缺少执行 base_url（请配置环境 base_url 或任务 target_system）")
        elif not scheme_ok:
            check_results.append(
                {
                    "name": "base_url_reachable",
                    "status": "failed",
                    "elapsed_ms": 0.0,
                    "message": "base_url is not a valid http(s) URL",
                }
            )
            blocking_issues.append("base_url 不是合法的 http(s) 地址")
        else:
            started = time.perf_counter()
            status = "passed"
            message = "base_url reachable"
            code = 0
            timeout_s = 5.0
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=4, max_retries=0, pool_block=False)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            try:
                last_error = ""
                fallback_warning = ""
                for probe_url, probe_name in _probe_candidates(base_url):
                    try:
                        resp = session.get(
                            probe_url,
                            headers={"User-Agent": "platform-preflight/1.0", "Accept": "*/*"},
                            timeout=_resolve_timeout(timeout_s),
                            allow_redirects=True,
                        )
                        _ = resp.content[:256]
                        code = int(resp.status_code)
                        if code < 400:
                            status = "passed"
                            message = f"{probe_name} reachable"
                            if fallback_warning and probe_name != "/health":
                                message = f"{probe_name} reachable after fallback"
                            break
                        if code in {404, 405}:
                            fallback_warning = f"{probe_name} returned HTTP {code}"
                            last_error = fallback_warning
                            continue
                        last_error = f"{probe_name} HTTP {code}"
                    except requests.RequestException as exc:
                        error_kind = _classify_request_exception(exc)
                        last_error = str(exc)
                        if probe_name == "/health":
                            continue
                        if error_kind == "timeout":
                            status = "failed"
                            message = f"connection timed out: {last_error}"
                            blocking_issues.append(f"无法连接目标地址：{last_error}")
                            break
                        status = "failed"
                        message = f"connection failed: {last_error}"
                        blocking_issues.append(f"无法连接目标地址：{last_error}")
                        break
                else:
                    if fallback_warning:
                        status = "warning"
                        message = f"{fallback_warning}, base host responded on fallback probe"
                    else:
                        status = "failed"
                        message = last_error or "connection failed"
                        blocking_issues.append(f"无法连接目标地址：{message}")
            except Exception as exc:  # pragma: no cover - defensive
                status = "failed"
                message = str(exc)
                blocking_issues.append(f"探测异常：{exc}")
            finally:
                session.close()

            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            check_results.append(
                {
                    "name": "base_url_reachable",
                    "status": status,
                    "elapsed_ms": elapsed_ms,
                    "message": message,
                }
            )
            if status == "passed" and elapsed_ms > latency_threshold_ms:
                suggestions.append(
                    f"目标 /health 响应偏慢（{elapsed_ms}ms > {latency_threshold_ms}ms），执行阶段可能耗时较长"
                )

    if "auth_config_valid" in selected:
        auth_type = str((auth or {}).get("type", "")).lower()
        has_bearer = bool(auth_type == "bearer" and (auth.get("token") or auth.get("token_context")))
        has_basic = bool(
            auth_type == "basic"
            and auth.get("username") is not None
            and auth.get("password") is not None
        )
        has_auth_header = any(
            str(k).lower() == "authorization" for k in (default_headers or {}).keys()
        )
        if auth_type and not (has_bearer or has_basic):
            check_results.append(
                {
                    "name": "auth_config_valid",
                    "status": "warning",
                    "elapsed_ms": 0.0,
                    "message": f"auth.type={auth_type} but credentials incomplete",
                }
            )
            suggestions.append("环境 auth 配置不完整，受保护接口可能返回 401/403")
        elif not auth_type and not has_auth_header:
            check_results.append(
                {
                    "name": "auth_config_valid",
                    "status": "warning",
                    "elapsed_ms": 0.0,
                    "message": "no auth configured",
                }
            )
            suggestions.append("未配置鉴权：若目标接口需要 Token，请在环境或 default_headers 中配置")
        else:
            check_results.append(
                {
                    "name": "auth_config_valid",
                    "status": "passed",
                    "elapsed_ms": 0.0,
                    "message": "auth configuration present",
                }
            )

    blocking = bool(blocking_issues)
    if blocking:
        overall = "failed"
    elif any(c.get("status") == "warning" for c in check_results):
        overall = "warning"
    else:
        overall = "passed"

    return {
        "task_id": task_id,
        "overall_status": overall,
        "blocking": blocking,
        "checks": check_results,
        "blocking_issues": blocking_issues,
        "suggestions": suggestions,
        "base_url": base_url,
    }
