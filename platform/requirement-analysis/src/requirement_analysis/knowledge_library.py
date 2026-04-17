"""Curated requirement-analysis knowledge library with conditional activation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from platform_shared.models import DocumentChunk

from .document_parser import extract_keywords

_HTTP_ENDPOINT_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[\w/\-{}:.?=&%]+)", re.IGNORECASE)
_PLACEHOLDER_PATH_RE = re.compile(r"/[^`\s]*/\{[a-zA-Z0-9_]+\}")
_AUTH_HINT_RE = re.compile(r"authorization|cookie|token|x-auth-token|x-challenger|basic auth|鉴权|令牌", re.IGNORECASE)
_SAVE_CONTEXT_RE = re.compile(r"save_context|uses_context|json\.[a-zA-Z0-9_.]+", re.IGNORECASE)
_PLATFORM_RE = re.compile(r"/api/tasks(?:/[^{\s`]+|\b)|task-center|任务中心", re.IGNORECASE)
_RESTFUL_BOOKER_RE = re.compile(r"restful\s+booker|restful-booker|/booking(?:\b|/)|/auth\b|/ping\b", re.IGNORECASE)
_API_CHALLENGES_RE = re.compile(r"api\s+challenges|apichallenges|/challenger\b|/secret/token\b|/todos\b", re.IGNORECASE)
_CRUD_CHAIN_RE = re.compile(r"\b(create|detail|update|patch|delete)\b|创建|详情|更新|删除", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class KnowledgeEntry:
    knowledge_id: str
    path: str
    title: str
    knowledge_type: str
    domain: str
    source_scope: str
    priority: str
    activation_conditions: list[str]
    tags: list[str]


def _knowledge_root() -> Path:
    return Path(__file__).resolve().parents[2] / "knowledge"


def _registry_path() -> Path:
    return _knowledge_root() / "manifests" / "knowledge_registry.json"


def load_curated_knowledge_chunks(*, raw_text: str, cleaned_text: str) -> list[DocumentChunk]:
    registry = _load_registry()
    if not registry:
        return []

    context = f"{raw_text or ''}\n{cleaned_text or ''}"
    chunks: list[DocumentChunk] = []
    for entry in registry:
        if not _entry_matches(entry, context):
            continue
        doc_path = _knowledge_root() / entry.path
        if not doc_path.exists():
            continue
        text = doc_path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        sections = _split_sections(text)
        for index, (section_title, content) in enumerate(sections, start=1):
            title = section_title or entry.title
            chunk_id = f"knowledge_{entry.knowledge_id}_{index:02d}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    content=content,
                    section_title=title,
                    source_file=str(doc_path.relative_to(_knowledge_root())).replace("\\", "/"),
                    source_block=f"{entry.knowledge_type}:{entry.knowledge_id}:{index}",
                    tokens_estimate=max(1, len(content) // 2),
                    keywords=_build_keywords(entry, title, content),
                    doc_type=entry.knowledge_type,
                )
            )
    return chunks


def _load_registry() -> list[KnowledgeEntry]:
    path = _registry_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = payload.get("entries")
    if not isinstance(items, list):
        return []
    out: list[KnowledgeEntry] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        knowledge_id = str(item.get("knowledge_id", "")).strip()
        doc_path = str(item.get("path", "")).strip()
        title = str(item.get("title", "")).strip()
        if not knowledge_id or not doc_path or not title:
            continue
        out.append(
            KnowledgeEntry(
                knowledge_id=knowledge_id,
                path=doc_path,
                title=title,
                knowledge_type=str(item.get("knowledge_type", "knowledge")).strip() or "knowledge",
                domain=str(item.get("domain", "generic")).strip() or "generic",
                source_scope=str(item.get("source_scope", "global")).strip() or "global",
                priority=str(item.get("priority", "medium")).strip() or "medium",
                activation_conditions=[str(value).strip() for value in (item.get("activation_conditions") or []) if str(value).strip()],
                tags=[str(value).strip() for value in (item.get("tags") or []) if str(value).strip()],
            )
        )
    return out


def _entry_matches(entry: KnowledgeEntry, context: str) -> bool:
    if not entry.activation_conditions:
        return True
    for condition in entry.activation_conditions:
        if condition == "always":
            return True
        if condition == "api_document" and _HTTP_ENDPOINT_RE.search(context):
            return True
        if condition == "auth_present" and _AUTH_HINT_RE.search(context):
            return True
        if condition == "context_present" and _SAVE_CONTEXT_RE.search(context):
            return True
        if condition == "placeholder_path_present" and _PLACEHOLDER_PATH_RE.search(context):
            return True
        if condition == "resource_lifecycle_present" and _CRUD_CHAIN_RE.search(context):
            return True
        if condition == "platform_doc" and _PLATFORM_RE.search(context):
            return True
        if condition == "restful_booker_doc" and _RESTFUL_BOOKER_RE.search(context):
            return True
        if condition == "api_challenges_doc" and _API_CHALLENGES_RE.search(context):
            return True
    return False


def _split_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_title = ""
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            sections.append((current_title, "\n".join(buffer).strip()))
            buffer.clear()

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            flush()
            current_title = stripped[3:].strip()
            continue
        if stripped.startswith("# "):
            if not current_title:
                current_title = stripped[2:].strip()
            continue
        if stripped:
            buffer.append(stripped)
    flush()
    return sections or [("", text.strip())]


def _build_keywords(entry: KnowledgeEntry, title: str, content: str) -> list[str]:
    ordered: list[str] = []
    for token in [entry.knowledge_type, entry.domain, entry.priority, *entry.tags, title, *extract_keywords(content, limit=10)]:
        normalized = str(token).strip()
        if normalized and normalized not in ordered:
            ordered.append(normalized)
    return ordered[:16]
