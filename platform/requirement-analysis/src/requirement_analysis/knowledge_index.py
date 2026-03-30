"""Minimal in-memory knowledge index."""

from __future__ import annotations

from collections import defaultdict


def build_index(chunks: list[object]) -> dict:
    """Build a lightweight in-memory index for task-scoped retrieval."""
    normalized = [chunk.to_dict() if hasattr(chunk, "to_dict") else chunk for chunk in chunks]
    inverted_index: dict[str, list[str]] = defaultdict(list)
    for chunk in normalized:
        chunk_id = chunk.get("chunk_id", "")
        for keyword in chunk.get("keywords", []):
            if chunk_id and chunk_id not in inverted_index[keyword]:
                inverted_index[keyword].append(chunk_id)
    return {
        "chunks": normalized,
        "chunk_count": len(normalized),
        "inverted_index": dict(inverted_index),
    }
