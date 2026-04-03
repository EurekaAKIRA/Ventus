"""Execution preflight checks (base_url reachability, minimal config hints)."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse


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
            try:
                probe = urllib.request.Request(
                    url=base_url.rstrip("/") + "/health",
                    method="GET",
                    headers={"User-Agent": "platform-preflight/1.0"},
                )
                with urllib.request.urlopen(probe, timeout=5.0) as resp:
                    _ = resp.read(256)
                code = 200
            except urllib.error.HTTPError as exc:
                code = exc.code
                if code in {404, 405}:
                    status = "warning"
                    message = f"/health returned HTTP {code}, base host responded"
                else:
                    status = "failed"
                    message = f"/health HTTP {code}"
                    blocking_issues.append(f"目标 /health 返回 HTTP {code}，请确认服务已启动")
            except urllib.error.URLError as exc:
                status = "failed"
                reason = str(exc.reason or exc)
                message = f"connection failed: {reason}"
                blocking_issues.append(f"无法连接目标地址：{reason}")
            except Exception as exc:  # pragma: no cover - defensive
                status = "failed"
                message = str(exc)
                blocking_issues.append(f"探测异常：{exc}")

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
