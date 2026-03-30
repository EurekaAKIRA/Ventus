"""Lightweight retrieval for analysis-module."""

from __future__ import annotations

from .document_parser import extract_keywords, tokenize_text
from platform_shared.models import RetrievedChunk


def _score_chunk(chunk: dict, query_terms: set[str], query_keywords: list[str]) -> float:
    chunk_terms = set(tokenize_text(chunk.get("content", "")))
    chunk_keywords = set(chunk.get("keywords", []))
    overlap_score = len(query_terms & chunk_terms) * 2.0
    keyword_score = len(set(query_keywords) & chunk_keywords) * 1.5
    title_bonus = 0.5 if any(word in chunk.get("section_title", "") for word in query_keywords[:3]) else 0.0
    return overlap_score + keyword_score + title_bonus


def retrieve_relevant_chunks(index: dict, query: str, top_k: int = 5) -> list[dict]:
    """Return chunks with the highest simple keyword overlap."""
    query_terms = set(tokenize_text(query))
    query_keywords = extract_keywords(query, limit=8)
    scored = []
    for chunk in index.get("chunks", []):
        score = _score_chunk(chunk, query_terms, query_keywords)
        if score <= 0:
            continue
        payload = RetrievedChunk(
            chunk_id=chunk.get("chunk_id", ""),
            content=chunk.get("content", ""),
            score=round(score, 3),
            section_title=chunk.get("section_title", ""),
            source_file=chunk.get("source_file", ""),
        )
        scored.append(payload.to_dict())
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]
