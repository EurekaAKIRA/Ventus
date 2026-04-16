"""HTTP-capable API runner for TestCaseDSL."""

from __future__ import annotations

import base64
import json
import re
import socket
import time
from collections.abc import Callable
from http.cookiejar import CookieJar
from json import JSONDecodeError
from typing import Any
from urllib import error, parse, request
from urllib.request import OpenerDirector

import requests

from platform_shared import ContextBus
from platform_shared.models import ExecutionResult


PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")
JSON_PATH_INDEX_PATTERN = re.compile(r"\[(\d+)\]")
SENSITIVE_HEADER_KEYS = {"authorization", "cookie", "set-cookie", "proxy-authorization"}
TOKEN_PATH_PATTERN = re.compile(
    r"""
    ([^.\[\]]+)
    |\[(-?\d+)\]
    |\[['"]([^'"]+)['"]\]
    """,
    re.VERBOSE,
)


def execute_test_case_dsl(
    test_case_dsl: dict,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict:
    """Execute TestCaseDSL in real HTTP mode when request specs are present."""
    scenario_results: list[dict] = []
    logs: list[dict] = []
    total_steps = 0
    passed_steps = 0
    elapsed_samples: list[float] = []
    context = ContextBus()
    runtime_state = _build_runtime_state(test_case_dsl)
    assertion_inventory = _collect_assertion_inventory(test_case_dsl)
    for key, value in (runtime_state.get("context_seed") or {}).items():
        context.set(str(key), value)

    for scenario in test_case_dsl.get("scenarios", []):
        scenario_id = scenario.get("scenario_id")
        scenario_name = scenario.get("name")
        step_results: list[dict] = []
        scenario_failed = False

        for step in scenario.get("steps", []):
            total_steps += 1
            start_log = _build_step_event_log(step, "step_start", scenario_id=scenario_id, scenario_name=scenario_name)
            logs.append(start_log)
            _emit_progress(progress_callback, start_log)
            try:
                if step.get("request"):
                    step_result = _execute_request_step(step, context, runtime_state, logs)
                else:
                    step_result = _execute_non_request_step(step, context)
            except Exception as exc:  # pragma: no cover - defensive top-level guard
                step_result = {
                    "step_id": step.get("step_id"),
                    "step_type": step.get("step_type"),
                    "text": step.get("text"),
                    "status": "failed",
                    "message": str(exc),
                    "error_category": _classify_exception(exc),
                }

            if step_result["status"] == "passed":
                passed_steps += 1
            else:
                scenario_failed = True
            response = step_result.get("response") or {}
            if isinstance(response.get("elapsed_ms"), (int, float)):
                elapsed_samples.append(float(response["elapsed_ms"]))

            step_results.append(step_result)
            step_log = _build_step_log(step_result, scenario_id=scenario_id, scenario_name=scenario_name)
            logs.append(step_log)
            _emit_progress(progress_callback, step_log)

        scenario_item = {
            "scenario_id": scenario_id,
            "name": scenario_name,
            "status": "failed" if scenario_failed else "passed",
            "steps": step_results,
            "failed_steps": len([step for step in step_results if step.get("status") != "passed"]),
        }
        scenario_results.append(scenario_item)
        _emit_progress(
            progress_callback,
            {
                "level": "error" if scenario_item["status"] == "failed" else "info",
                "event": "scenario_result",
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "status": scenario_item["status"],
                "failed_steps": scenario_item["failed_steps"],
                "message": f"{scenario_name or scenario_id or 'scenario'} {scenario_item['status']}",
            },
        )

    overall_status = "passed" if passed_steps == total_steps else "failed"
    result = ExecutionResult(
        task_id=test_case_dsl.get("task_id", "unknown_task"),
        executor="api-runner",
        status=overall_status,
        scenario_results=scenario_results,
        metrics={
            "scenario_count": len(scenario_results),
            "step_count": total_steps,
            "passed_step_count": passed_steps,
            "failed_step_count": total_steps - passed_steps,
            "context_key_count": len(context.snapshot()),
            "cookie_count": _count_runtime_cookies(runtime_state),
            "avg_elapsed_ms": round(sum(elapsed_samples) / len(elapsed_samples), 2) if elapsed_samples else 0,
            "max_elapsed_ms": round(max(elapsed_samples), 2) if elapsed_samples else 0,
            "assertion_category_counts": assertion_inventory["category_counts"],
            "assertion_generated_by_counts": assertion_inventory["generated_by_counts"],
            "fallback_assertion_count": assertion_inventory["fallback_count"],
        },
        logs=logs,
    )
    return result.to_dict()


def _emit_progress(
    callback: Callable[[dict[str, Any]], None] | None,
    payload: dict[str, Any],
) -> None:
    if callback is None:
        return
    try:
        callback(dict(payload))
    except Exception:
        # Progress callback must not interrupt core execution.
        return


def _execute_non_request_step(step: dict, context: ContextBus) -> dict:
    missing_context = context.require(step.get("uses_context") or [])
    if missing_context:
        return {
            "step_id": step.get("step_id"),
            "step_type": step.get("step_type"),
            "text": step.get("text"),
            "status": "failed",
            "message": f"Missing context: {', '.join(missing_context)}",
            "error_category": "context_error",
        }
    assertions = step.get("assertions") or []
    assertion_failures = _evaluate_assertions(assertions, {}, context)
    status = "failed" if assertion_failures else "passed"
    message = "Assertions passed" if not assertion_failures else "; ".join(item["message"] for item in assertion_failures)
    return {
        "step_id": step.get("step_id"),
        "step_type": step.get("step_type"),
        "text": step.get("text"),
        "status": status,
        "message": message,
        "error_category": "assertion_error" if assertion_failures else "",
        "assertion_summary": _build_assertion_summary(assertions, assertion_failures),
        "assertion_failures": assertion_failures,
    }


def _execute_request_step(
    step: dict,
    context: ContextBus,
    runtime_state: dict[str, Any],
    logs: list[dict],
) -> dict:
    missing_context = context.require(step.get("uses_context") or [])
    if missing_context:
        return {
            "step_id": step.get("step_id"),
            "step_type": step.get("step_type"),
            "text": step.get("text"),
            "status": "failed",
            "message": f"Missing context: {', '.join(missing_context)}",
            "error_category": "context_error",
        }
    request_spec = _render_templates(step.get("request", {}), context)
    request_spec = _normalize_request_spec(request_spec, runtime_state, context)
    if "timeout" not in request_spec:
        request_spec["timeout"] = float(runtime_state.get("default_step_timeout", 30))
    if "retries" not in request_spec:
        request_spec["retries"] = int(runtime_state.get("default_step_retries", 2))
    logs.append(_build_request_log(step, request_spec))
    response_payload = _perform_http_request(request_spec, runtime_state["opener"])
    logs.append(_build_response_log(step, response_payload))
    context.set("last_response", response_payload)
    context.set("last_status_code", response_payload.get("status_code"))
    context.set("last_request", _summarize_request(request_spec))

    save_context = step.get("save_context") or {}
    saved_context: dict[str, Any] = {}
    if isinstance(save_context, dict):
        for key, source in save_context.items():
            value = _read_source(source, response_payload, context)
            if value is None and isinstance(source, str) and source.startswith("json."):
                value = _read_json_path_with_envelope(
                    response_payload.get("json"), source[5:], None
                )
            context.set(key, value)
            saved_context[key] = value
    if saved_context:
        logs.append(_build_context_log(step, saved_context))

    assertions = step.get("assertions") or []
    assertion_failures = _evaluate_assertions(assertions, response_payload, context)
    assertion_summary = _build_assertion_summary(assertions, assertion_failures)
    logs.append(_build_assertion_log(step, assertion_summary))
    status = "failed" if assertion_failures else "passed"
    error_category = response_payload.get("error_category", "")
    if assertion_failures:
        error_category = error_category or "assertion_error"
    message = (
        f"{request_spec.get('method', 'GET')} {request_spec.get('url')} -> {response_payload['status_code']}"
        if not assertion_failures
        else "; ".join(item["message"] for item in assertion_failures)
    )
    return {
        "step_id": step.get("step_id"),
        "step_type": step.get("step_type"),
        "text": step.get("text"),
        "status": status,
        "message": message,
        "error_category": error_category,
        "request": {
            "method": request_spec.get("method", "GET"),
            "url": request_spec.get("url", ""),
            "headers": _sanitize_headers(request_spec.get("headers") or {}),
            "params": request_spec.get("params") or {},
            "auth_type": (request_spec.get("auth") or {}).get("type", ""),
        },
        "request_summary": _summarize_request(request_spec),
        "response": {
            "status_code": response_payload["status_code"],
            "headers": response_payload["headers"],
            "json": response_payload["json"],
            "body_preview": response_payload["body_text"][:200],
            "elapsed_ms": response_payload["elapsed_ms"],
            "error": response_payload["error"],
            "error_category": response_payload["error_category"],
        },
        "response_summary": _summarize_response(response_payload),
        "context_snapshot": context.snapshot(),
        "saved_context": saved_context,
        "assertion_summary": assertion_summary,
        "assertion_failures": assertion_failures,
    }


def _perform_http_request(request_spec: dict, opener: OpenerDirector | requests.Session) -> dict:
    method = request_spec.get("method", "GET").upper()
    url = request_spec.get("url", "")
    if not url:
        raise ValueError("request.url is required for api-runner steps")
    headers = dict(request_spec.get("headers") or {})
    params = request_spec.get("params") or {}
    body = request_spec.get("json")
    data = request_spec.get("data")
    timeout = float(request_spec.get("timeout", 30))
    retries = int(request_spec.get("retries", 0))

    if params:
        query = parse.urlencode(params, doseq=True)
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{query}"

    encoded_data = None
    if body is not None:
        encoded_data = json.dumps(body).encode("utf-8")
        # Apifox-like behavior: auto add JSON headers unless user already specified.
        if not _has_header_case_insensitive(headers, "Content-Type"):
            headers["Content-Type"] = "application/json"
        if not _has_header_case_insensitive(headers, "Accept"):
            headers["Accept"] = "application/json"
    elif isinstance(data, (dict, list, tuple)):
        encoded_data = parse.urlencode(data, doseq=True).encode("utf-8")
        if not _has_header_case_insensitive(headers, "Content-Type"):
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if not _has_header_case_insensitive(headers, "Accept"):
            headers["Accept"] = "application/json"
    elif isinstance(data, str):
        encoded_data = data.encode("utf-8")
    elif isinstance(data, bytes):
        encoded_data = data
    if not _has_header_case_insensitive(headers, "Accept"):
        headers["Accept"] = "application/json"

    raw = b""
    status_code = 0
    response_headers: dict[str, Any] = {}
    response_error = ""
    error_category = ""
    started = time.time()
    for attempt in range(retries + 1):
        try:
            if isinstance(opener, requests.Session):
                resp = opener.request(
                    method=method,
                    url=url,
                    params=params or None,
                    data=encoded_data,
                    headers=headers,
                    timeout=_resolve_timeout(timeout),
                )
                raw = resp.content or b""
                status_code = int(resp.status_code)
                response_headers = dict(resp.headers.items())
                response_error = ""
                error_category = ""
                if status_code >= 400:
                    response_error = f"HTTP Error {status_code}: {resp.reason or 'Request Failed'}"
                    error_category = _classify_http_error(status_code)
                break

            req = request.Request(url=url, data=encoded_data, headers=headers, method=method)
            with opener.open(req, timeout=timeout) as resp:
                raw = resp.read()
                status_code = resp.getcode()
                response_headers = dict(resp.headers.items())
                response_error = ""
                error_category = ""
                break
        except error.HTTPError as exc:
            raw = exc.read()
            status_code = exc.code
            response_headers = dict(exc.headers.items())
            response_error = str(exc)
            error_category = _classify_http_error(exc.code)
            break
        except requests.Timeout as exc:
            response_error = str(exc)
            status_code = 0
            error_category = "timeout_error"
            if attempt >= retries:
                break
            time.sleep(0.15 * (attempt + 1))
        except requests.RequestException as exc:
            response_error = str(exc)
            status_code = 0
            error_category = "network_error"
            if attempt >= retries:
                break
            time.sleep(0.15 * (attempt + 1))
        except error.URLError as exc:
            response_error = str(exc.reason or exc)
            status_code = 0
            error_category = _classify_url_error(exc)
            if attempt >= retries:
                break
            time.sleep(0.15 * (attempt + 1))
    elapsed_ms = round((time.time() - started) * 1000, 2)

    body_text = raw.decode("utf-8", errors="replace")
    parse_error = ""
    if body_text:
        try:
            body_json = json.loads(body_text)
        except JSONDecodeError as exc:
            body_json = None
            parse_error = str(exc)
            if not error_category and _looks_like_json(response_headers):
                error_category = "response_parse_error"
    else:
        body_json = None

    return {
        "status_code": status_code,
        "headers": response_headers,
        "body_text": body_text,
        "json": body_json,
        "elapsed_ms": elapsed_ms,
        "error": response_error,
        "error_category": error_category,
        "parse_error": parse_error,
    }


def _render_templates(payload: Any, context: ContextBus) -> Any:
    if isinstance(payload, str):
        return PLACEHOLDER_PATTERN.sub(lambda m: str(context.get(m.group(1), "")), payload)
    if isinstance(payload, list):
        return [_render_templates(item, context) for item in payload]
    if isinstance(payload, dict):
        return {key: _render_templates(value, context) for key, value in payload.items()}
    return payload


def _resolve_timeout(timeout: float) -> tuple[float, float]:
    timeout = max(float(timeout), 0.1)
    connect_timeout = min(timeout, 5.0)
    read_timeout = max(timeout, connect_timeout)
    return (connect_timeout, read_timeout)


def _count_runtime_cookies(runtime_state: dict[str, Any]) -> int:
    opener = runtime_state.get("opener")
    if isinstance(opener, requests.Session):
        return len(opener.cookies)
    cookie_jar = runtime_state.get("cookie_jar")
    try:
        return len(cookie_jar)
    except TypeError:
        return 0


def _evaluate_assertions(assertions: list[Any], response_payload: dict, context: ContextBus) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for assertion in assertions:
        if isinstance(assertion, str):
            continue
        normalized = _normalize_assertion(assertion)
        source = normalized.get("source", "")
        op = normalized.get("op", "eq")
        actual = _read_source(source, response_payload, context)
        expected = _render_templates(normalized.get("expected"), context)
        if not _compare(actual, op, expected):
            short_actual = _short_repr(actual)
            errors.append(
                {
                    "assertion_id": normalized["assertion_id"],
                    "source": source,
                    "op": op,
                    "expected": expected,
                    "actual": actual,
                    "category": normalized["category"],
                    "severity": normalized["severity"],
                    "confidence": normalized["confidence"],
                    "generated_by": normalized["generated_by"],
                    "fallback_used": normalized["fallback_used"],
                    "message": f"Assertion failed [{normalized['assertion_id']}]: {source} {op} {expected!r}, actual={short_actual}",
                }
            )
    return errors


def _compare(actual: Any, op: str, expected: Any) -> bool:
    left, right = _coerce_pair(actual, expected)
    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    if op == "in":
        return _membership_compare(left, right, invert=False)
    if op == "not_in":
        return _membership_compare(left, right, invert=True)
    if op == "ge":
        return _safe_order_compare(left, right, lambda a, b: a >= b)
    if op == "le":
        return _safe_order_compare(left, right, lambda a, b: a <= b)
    if op == "contains":
        return right in left if left is not None else False
    if op == "not_contains":
        return right not in left if left is not None else False
    if op == "exists":
        return actual is not None
    if op == "not_exists":
        return actual is None
    if op == "gt":
        return _safe_order_compare(left, right, lambda a, b: a > b)
    if op == "lt":
        return _safe_order_compare(left, right, lambda a, b: a < b)
    if op == "startswith":
        return str(actual).startswith(str(expected)) if actual is not None else False
    if op == "endswith":
        return str(actual).endswith(str(expected)) if actual is not None else False
    if op == "matches":
        return re.search(str(expected), str(actual)) is not None if actual is not None else False
    if op == "len_eq":
        return _safe_len(actual) == expected
    if op == "len_gt":
        return _safe_len(actual) > expected
    if op == "len_lt":
        return _safe_len(actual) < expected
    if op == "len_ge":
        return _safe_len(actual) >= expected
    if op == "len_le":
        return _safe_len(actual) <= expected
    if op == "is_true":
        return _coerce_bool(actual) is True
    if op == "is_false":
        return _coerce_bool(actual) is False
    return False


def _read_source(source: str, response_payload: dict, context: ContextBus, default: Any = None) -> Any:
    if not source:
        return default
    if source == "status_code":
        return response_payload.get("status_code", default)
    if source == "elapsed_ms":
        return response_payload.get("elapsed_ms", default)
    if source == "error":
        value = response_payload.get("error", default)
        if isinstance(value, str) and not value.strip():
            return None
        return value
    if source == "error_category":
        return response_payload.get("error_category", default)
    if source == "body_text":
        return response_payload.get("body_text", default)
    if source == "json":
        return response_payload.get("json", default)
    if source.startswith("json."):
        return _read_json_path_with_envelope(response_payload.get("json"), source[5:], default)
    if source.startswith("json["):
        return _read_json_path_with_envelope(response_payload.get("json"), source[4:], default)
    if source.startswith("headers."):
        return _read_header(response_payload.get("headers", {}), source[8:], default)
    if source.startswith("headers["):
        return _read_header(response_payload.get("headers", {}), source[7:].strip("[]'\""), default)
    if source.startswith("context."):
        return context.get(source[8:], default)
    return default


def _read_json_path(payload: Any, path: str, default: Any = None) -> Any:
    tokens = _tokenize_path(path)
    if not tokens:
        return payload if path.strip(".") == "" else default
    return _read_token_path(payload, tokens, default)


def _read_json_path_with_envelope(payload: Any, path: str, default: Any = None) -> Any:
    """Resolve json path; if missing, retry under `data` for `{success, data:{...}}` API envelopes."""
    if payload is None:
        return default
    direct = _read_json_path(payload, path, None)
    if direct is not None:
        return direct
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        nested = _read_json_path(payload["data"], path, None)
        if nested is not None:
            return nested
    return default


def _read_header(headers: dict[str, Any], name: str, default: Any = None) -> Any:
    if name in headers:
        return headers[name]
    lowered = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lowered:
            return value
    return default


def _has_header_case_insensitive(headers: dict[str, Any], name: str) -> bool:
    target = str(name).lower()
    for key in headers.keys():
        if str(key).lower() == target:
            return True
    return False


def _read_dotted_path(payload: Any, path: str, default: Any = None) -> Any:
    current = payload
    if path == "":
        return current
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part, default)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if 0 <= index < len(current) else default
        else:
            return default
    return current


def _tokenize_path(path: str) -> list[str | int]:
    normalized = JSON_PATH_INDEX_PATTERN.sub(r"[\1]", path).strip(".")
    tokens: list[str | int] = []
    for match in TOKEN_PATH_PATTERN.finditer(normalized):
        key = match.group(1)
        index = match.group(2)
        quoted_key = match.group(3)
        if key is not None:
            tokens.append(key)
        elif index is not None:
            tokens.append(int(index))
        elif quoted_key is not None:
            tokens.append(quoted_key)
    return tokens


def _read_token_path(payload: Any, tokens: list[str | int], default: Any = None) -> Any:
    current = payload
    for token in tokens:
        if isinstance(token, int):
            if not isinstance(current, list):
                return default
            index = token if token >= 0 else len(current) + token
            if not 0 <= index < len(current):
                return default
            current = current[index]
            continue
        if isinstance(current, dict):
            current = current.get(token, default)
            continue
        return default
    return current


def _safe_len(value: Any) -> int:
    if value is None:
        return 0
    try:
        return len(value)
    except TypeError:
        return 0


def _coerce_pair(left: Any, right: Any) -> tuple[Any, Any]:
    left_bool = _coerce_bool(left)
    right_bool = _coerce_bool(right)
    if left_bool is not None and right_bool is not None:
        return left_bool, right_bool
    for caster in (int, float):
        try:
            if left is not None and right is not None:
                return caster(left), caster(right)
        except (TypeError, ValueError):
            continue
    return left, right


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return None


def _membership_compare(left: Any, right: Any, *, invert: bool) -> bool:
    if not isinstance(right, (list, tuple, set)):
        return False
    outcome = left in right
    return not outcome if invert else outcome


def _safe_order_compare(left: Any, right: Any, comparator) -> bool:
    try:
        return comparator(left, right)
    except TypeError:
        return False


def _build_runtime_state(test_case_dsl: dict) -> dict[str, Any]:
    metadata = test_case_dsl.get("metadata") or {}
    execution = metadata.get("execution") or {}
    cookie_jar = CookieJar()
    opener = request.build_opener(request.HTTPCookieProcessor(cookie_jar))
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=0, pool_block=False)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return {
        "base_url": execution.get("base_url", ""),
        "default_headers": execution.get("default_headers") or {},
        "default_auth": execution.get("auth") or {},
        "default_cookies": execution.get("cookies") or {},
        "context_seed": execution.get("context") or {},
        "cookie_jar": cookie_jar,
        "opener": session,
        "legacy_opener": opener,
        "default_step_timeout": float(execution.get("step_timeout_seconds", 15)),
        "default_step_retries": int(execution.get("step_retries", 0)),
    }


def _normalize_request_spec(
    request_spec: dict,
    runtime_state: dict[str, Any],
    context: ContextBus,
) -> dict[str, Any]:
    spec = dict(request_spec)
    url = spec.get("url", "")
    base_url = runtime_state.get("base_url", "")
    if base_url and url:
        if url.startswith("/"):
            spec["url"] = base_url.rstrip("/") + url
        elif not _is_absolute_http_url(url):
            spec["url"] = base_url.rstrip("/") + "/" + str(url).lstrip("/")

    merged_headers = dict(runtime_state.get("default_headers") or {})
    merged_headers.update(spec.get("headers") or {})
    spec["headers"] = merged_headers

    auth = spec.get("auth") or runtime_state.get("default_auth") or {}
    if auth:
        spec["auth"] = auth
        _apply_auth(spec, auth, context)

    cookies = dict(runtime_state.get("default_cookies") or {})
    cookies.update(spec.get("cookies") or {})
    if cookies:
        spec["headers"]["Cookie"] = "; ".join(f"{key}={value}" for key, value in cookies.items())
    spec["method"] = str(spec.get("method", "GET")).upper()
    return spec


def _is_absolute_http_url(url: str) -> bool:
    lowered = str(url).lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def _apply_auth(spec: dict[str, Any], auth: dict[str, Any], context: ContextBus) -> None:
    auth_type = str(auth.get("type", "")).lower()
    if auth_type == "bearer":
        token = auth.get("token")
        if token is None and auth.get("token_context"):
            token = context.get(str(auth["token_context"]))
        if token:
            spec["headers"]["Authorization"] = f"Bearer {token}"
        return
    if auth_type == "basic":
        username = auth.get("username")
        password = auth.get("password")
        if username is None and auth.get("username_context"):
            username = context.get(str(auth["username_context"]))
        if password is None and auth.get("password_context"):
            password = context.get(str(auth["password_context"]))
        if username is not None and password is not None:
            encoded = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
            spec["headers"]["Authorization"] = f"Basic {encoded}"


def _summarize_request(request_spec: dict[str, Any]) -> dict[str, Any]:
    body = request_spec.get("json")
    form = request_spec.get("data")
    headers = request_spec.get("headers") or {}
    return {
        "method": request_spec.get("method", "GET"),
        "url": request_spec.get("url", ""),
        "headers": _sanitize_headers(headers),
        "params": request_spec.get("params") or {},
        "has_json_body": body is not None,
        "has_form_body": form is not None,
        "auth_type": (request_spec.get("auth") or {}).get("type", ""),
        "body_keys": sorted(body.keys())[:10] if isinstance(body, dict) else [],
        "form_keys": sorted(form.keys())[:10] if isinstance(form, dict) else [],
        "cookie_header_present": "Cookie" in headers or "cookie" in headers,
    }


def _summarize_response(response_payload: dict[str, Any]) -> dict[str, Any]:
    body_json = response_payload.get("json")
    json_keys = sorted(body_json.keys())[:10] if isinstance(body_json, dict) else []
    return {
        "status_code": response_payload.get("status_code", 0),
        "elapsed_ms": response_payload.get("elapsed_ms", 0),
        "content_type": _read_header(response_payload.get("headers", {}), "Content-Type", ""),
        "json_keys": json_keys,
        "body_preview": response_payload.get("body_text", "")[:120],
        "error_category": response_payload.get("error_category", ""),
        "parse_error": response_payload.get("parse_error", ""),
        "body_size": len(response_payload.get("body_text", "")),
    }


def _sanitize_headers(headers: dict[str, Any]) -> dict[str, Any]:
    return {
        key: ("***" if str(key).lower() in SENSITIVE_HEADER_KEYS else value)
        for key, value in headers.items()
    }


def _build_step_log(
    step_result: dict[str, Any],
    *,
    scenario_id: str | None = None,
    scenario_name: str | None = None,
) -> dict[str, Any]:
    payload = {
        "level": "info" if step_result["status"] == "passed" else "error",
        "event": "step_result",
        "step_id": step_result.get("step_id"),
        "message": step_result.get("message", ""),
        "status": step_result.get("status", ""),
        "scenario_id": scenario_id,
        "scenario_name": scenario_name,
    }
    if step_result.get("error_category"):
        payload["error_category"] = step_result["error_category"]
    if step_result.get("request_summary"):
        payload["request_summary"] = step_result["request_summary"]
    if step_result.get("response_summary"):
        payload["response_summary"] = step_result["response_summary"]
    if step_result.get("assertion_summary"):
        payload["assertion_summary"] = step_result["assertion_summary"]
    return payload


def _build_step_event_log(
    step: dict[str, Any],
    event: str,
    *,
    scenario_id: str | None = None,
    scenario_name: str | None = None,
) -> dict[str, Any]:
    return {
        "level": "info",
        "event": event,
        "step_id": step.get("step_id"),
        "step_type": step.get("step_type"),
        "message": step.get("text", ""),
        "scenario_id": scenario_id,
        "scenario_name": scenario_name,
    }


def _build_request_log(step: dict[str, Any], request_spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "level": "info",
        "event": "request_prepared",
        "step_id": step.get("step_id"),
        "message": f"Dispatching {request_spec.get('method', 'GET')} {request_spec.get('url', '')}",
        "request_summary": _summarize_request(request_spec),
    }


def _build_response_log(step: dict[str, Any], response_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "level": "info" if not response_payload.get("error_category") else "error",
        "event": "response_received",
        "step_id": step.get("step_id"),
        "message": f"Received {response_payload.get('status_code', 0)}",
        "response_summary": _summarize_response(response_payload),
    }


def _build_context_log(step: dict[str, Any], saved_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "level": "info",
        "event": "context_saved",
        "step_id": step.get("step_id"),
        "message": f"Saved context keys: {', '.join(sorted(saved_context.keys()))}",
        "saved_context": saved_context,
    }


def _build_assertion_log(step: dict[str, Any], assertion_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "level": "info" if assertion_summary["failed"] == 0 else "error",
        "event": "assertions_evaluated",
        "step_id": step.get("step_id"),
        "message": f"Assertions passed={assertion_summary['passed']} failed={assertion_summary['failed']}",
        "assertion_summary": assertion_summary,
    }


def _build_assertion_summary(assertions: list[Any], assertion_errors: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = [_normalize_assertion(item) for item in assertions if not isinstance(item, str)]
    total = len(normalized)
    failed = len(assertion_errors)
    category_counts: dict[str, int] = {}
    generated_by_counts: dict[str, int] = {}
    fallback_count = 0
    for item in normalized:
        category = item["category"]
        generated_by = item["generated_by"]
        category_counts[category] = category_counts.get(category, 0) + 1
        generated_by_counts[generated_by] = generated_by_counts.get(generated_by, 0) + 1
        if item["fallback_used"]:
            fallback_count += 1
    return {
        "total": total,
        "passed": max(total - failed, 0),
        "failed": failed,
        "failures": [item["message"] for item in assertion_errors],
        "failure_details": assertion_errors,
        "category_counts": category_counts,
        "generated_by_counts": generated_by_counts,
        "fallback_count": fallback_count,
        "weak_assertion": bool(normalized) and all(item["source"] == "status_code" for item in normalized),
    }


def _normalize_assertion(assertion: dict[str, Any]) -> dict[str, Any]:
    source = str(assertion.get("source", "")).strip()
    op = str(assertion.get("op", "eq")).strip()
    try:
        confidence = float(assertion.get("confidence", 0.5) or 0.5)
    except (TypeError, ValueError):
        confidence = 0.5
    return {
        "assertion_id": str(assertion.get("assertion_id", f"{source or 'assertion'}_{op}")),
        "source": source,
        "op": op,
        "expected": assertion.get("expected"),
        "category": str(assertion.get("category", "business")),
        "severity": str(assertion.get("severity", "major")),
        "confidence": confidence,
        "generated_by": str(assertion.get("generated_by", "rules")),
        "fallback_used": bool(assertion.get("fallback_used", False)),
    }


def _short_repr(value: Any, max_chars: int = 120) -> str:
    text = repr(value)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _collect_assertion_inventory(test_case_dsl: dict[str, Any]) -> dict[str, Any]:
    category_counts: dict[str, int] = {}
    generated_by_counts: dict[str, int] = {}
    fallback_count = 0
    for scenario in test_case_dsl.get("scenarios", []):
        for step in scenario.get("steps", []):
            for assertion in step.get("assertions") or []:
                if isinstance(assertion, str):
                    continue
                normalized = _normalize_assertion(assertion)
                category = normalized["category"]
                generated_by = normalized["generated_by"]
                category_counts[category] = category_counts.get(category, 0) + 1
                generated_by_counts[generated_by] = generated_by_counts.get(generated_by, 0) + 1
                if normalized["fallback_used"]:
                    fallback_count += 1
    return {
        "category_counts": category_counts,
        "generated_by_counts": generated_by_counts,
        "fallback_count": fallback_count,
    }


def _classify_http_error(status_code: int) -> str:
    if status_code in {401, 403}:
        return "auth_error"
    if 400 <= status_code < 500:
        return "http_client_error"
    if 500 <= status_code < 600:
        return "http_server_error"
    return "http_error"


def _classify_url_error(exc: error.URLError) -> str:
    reason = exc.reason
    if isinstance(reason, TimeoutError) or isinstance(reason, socket.timeout):
        return "timeout_error"
    return "network_error"


def _classify_exception(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return "request_validation_error"
    if isinstance(exc, error.URLError):
        return _classify_url_error(exc)
    return "unexpected_error"


def _looks_like_json(headers: dict[str, Any]) -> bool:
    content_type = str(_read_header(headers, "Content-Type", "")).lower()
    return "json" in content_type
