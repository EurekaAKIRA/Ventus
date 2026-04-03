"""Curated platform API snippets and optional OpenAPI-derived chunks for RAG."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from platform_shared.models import DocumentChunk
from platform_shared.runtime_config import ContractKnowledgeConfig

from .document_parser import extract_keywords


def _shared_config_dir() -> Path:
    import platform_shared.runtime_config as rc

    return Path(rc.__file__).resolve().parents[2] / "config"


def load_platform_contract_chunks() -> list[DocumentChunk]:
    path = _shared_config_dir() / "platform_api_knowledge.json"
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    snippets = raw.get("snippets")
    if not isinstance(snippets, list):
        return []
    out: list[DocumentChunk] = []
    for item in snippets:
        if not isinstance(item, dict):
            continue
        chunk_id = str(item.get("chunk_id", "")).strip()
        content = str(item.get("content", "")).strip()
        if not chunk_id or not content:
            continue
        section = str(item.get("section_title", "")).strip()
        kws = item.get("keywords")
        keywords = [str(k).strip() for k in kws] if isinstance(kws, list) else extract_keywords(content, limit=12)
        keywords = [k for k in keywords if k]
        out.append(
            DocumentChunk(
                chunk_id=chunk_id,
                content=content,
                section_title=section,
                source_file="platform_api_knowledge.json",
                source_block="curated_snippet",
                tokens_estimate=max(1, len(content) // 2),
                keywords=keywords,
                doc_type="platform_contract",
            )
        )
    return out


def _path_keywords(path_str: str) -> list[str]:
    parts = [p for p in path_str.strip("/").split("/") if p and not p.startswith("{")]
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        key = re.sub(r"[{}]", "", p)
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out[:8]


def openapi_spec_to_chunks(spec: dict[str, Any], *, max_operations: int) -> list[DocumentChunk]:
    out: list[DocumentChunk] = []
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return out
    n = 0
    for path_str, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue
            summary = str(op.get("summary") or op.get("operationId") or "").strip()
            desc = str(op.get("description") or "").strip()
            body = f"{method.upper()} {path_str}\n{summary}\n{desc}".strip()[:2400]
            kws = _path_keywords(path_str) + [method.upper()]
            if summary:
                kws.extend(extract_keywords(summary, limit=4))
            seen: set[str] = set()
            keywords: list[str] = []
            for k in kws:
                k = k.strip()
                if k and k.lower() not in seen:
                    seen.add(k.lower())
                    keywords.append(k)
            chunk_id = f"openapi_{method}_{re.sub(r'[^a-zA-Z0-9]+', '_', path_str).strip('_')[:48]}"
            out.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    content=body,
                    section_title=f"OpenAPI {method.upper()} {path_str}",
                    source_file="openapi_spec",
                    source_block="openapi_operation",
                    tokens_estimate=max(1, len(body) // 2),
                    keywords=keywords[:12],
                    doc_type="openapi_spec",
                )
            )
            n += 1
            if n >= max_operations:
                return out
    return out


def fetch_openapi_chunks(config: ContractKnowledgeConfig) -> list[DocumentChunk]:
    url = (os.environ.get("OPENAPI_SPEC_URL") or "").strip() or config.openapi_spec_url
    if not url:
        return []
    timeout = float(config.openapi_fetch_timeout_seconds)
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json, */*"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        spec = json.loads(raw.decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return []
    if not isinstance(spec, dict):
        return []
    return openapi_spec_to_chunks(spec, max_operations=config.openapi_max_operations)


def build_contract_chunks(config: ContractKnowledgeConfig) -> list[DocumentChunk]:
    if not config.enabled:
        return []
    chunks = list(load_platform_contract_chunks())
    chunks.extend(fetch_openapi_chunks(config))
    return chunks
