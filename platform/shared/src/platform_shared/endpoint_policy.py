"""Single source of truth for HTTP surfaces that are not JSON API tests.

Use this from requirement parsing (what enters ``api_endpoints``) and from
case-generation (assertions). Long-term, prefer OpenAPI as the authoritative
contract; this module is the pragmatic default until then.
"""

from __future__ import annotations

__all__ = [
    "normalize_api_path",
    "is_documentation_ui_path",
    "expects_json_envelope",
    "filter_executable_api_endpoints",
]


def normalize_api_path(path: str) -> str:
    """Strip query/fragment, optional absolute URL host, trailing slashes."""
    raw = (path or "").strip()
    if not raw:
        return ""
    if "://" in raw:
        after = raw.split("://", 1)[1]
        slash = after.find("/")
        raw = after[slash:] if slash >= 0 else "/"
    raw = raw.split("?", 1)[0].split("#", 1)[0]
    if raw != "/" and raw.endswith("/"):
        raw = raw.rstrip("/")
    return raw or "/"


def is_documentation_ui_path(path: str) -> bool:
    """True for typical Swagger/Redoc HTML entrypoints (not JSON OpenAPI)."""
    norm = normalize_api_path(path).lower()
    if norm in {"/docs", "/redoc", "/swagger", "/swagger-ui"}:
        return True
    last = norm.rsplit("/", 1)[-1]
    if last in {"docs", "redoc", "swagger", "swagger-ui"} and not norm.startswith("/api/"):
        return True
    return False


def expects_json_envelope(path: str) -> bool:
    """Heuristic for task-center style JSON responses."""
    return not is_documentation_ui_path(path)


def filter_executable_api_endpoints(endpoints: list[dict]) -> list[dict]:
    """Remove doc UI GETs from endpoint lists used for scenario/DSL generation."""
    out: list[dict] = []
    for ep in endpoints:
        method = str(ep.get("method", "")).upper().strip()
        path = str(ep.get("path", ""))
        if method == "GET" and is_documentation_ui_path(path):
            continue
        lowered = path.lower()
        if "..." in lowered:
            continue
        if "、" in path and "`" in path:
            continue
        out.append(ep)
    return out
