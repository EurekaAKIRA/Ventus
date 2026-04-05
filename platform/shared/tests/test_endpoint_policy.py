"""Tests for centralized HTTP surface policy."""

from __future__ import annotations

from platform_shared.endpoint_policy import (
    expects_json_envelope,
    filter_executable_api_endpoints,
    is_documentation_ui_path,
    normalize_api_path,
)


def test_normalize_api_path_strips_host_and_query() -> None:
    assert normalize_api_path("http://127.0.0.1:8001/docs") == "/docs"
    assert normalize_api_path("/api/tasks?page=1") == "/api/tasks"


def test_docs_is_not_json_envelope() -> None:
    assert is_documentation_ui_path("/docs") is True
    assert expects_json_envelope("/docs") is False
    assert expects_json_envelope("http://localhost:8001/docs") is False


def test_api_paths_still_expect_json() -> None:
    assert expects_json_envelope("/api/tasks") is True
    assert expects_json_envelope("/health") is True
    assert is_documentation_ui_path("/openapi.json") is False


def test_filter_executable_api_endpoints_drops_get_docs() -> None:
    eps = [
        {"method": "GET", "path": "/health"},
        {"method": "GET", "path": "/docs"},
        {"method": "POST", "path": "/api/tasks"},
    ]
    out = filter_executable_api_endpoints(eps)
    assert len(out) == 2
    assert {e["path"] for e in out} == {"/health", "/api/tasks"}
