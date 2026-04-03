"""Minimal in-memory knowledge index."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .openai_enhancement import OpenAIEnhancementConfig, request_embeddings


def build_index(
    chunks: list[object],
    enable_vector_rag: bool = False,
    embedding_config: OpenAIEnhancementConfig | None = None,
) -> dict:
    """Build a lightweight in-memory index for task-scoped retrieval."""
    normalized = [chunk.to_dict() if hasattr(chunk, "to_dict") else chunk for chunk in chunks]
    inverted_index: dict[str, list[str]] = defaultdict(list)
    for chunk in normalized:
        chunk_id = chunk.get("chunk_id", "")
        for keyword in chunk.get("keywords", []):
            if chunk_id and chunk_id not in inverted_index[keyword]:
                inverted_index[keyword].append(chunk_id)
    chunk_embeddings: dict[str, list[float]] = {}
    embedding_error = ""
    embedding_error_detail = ""
    if enable_vector_rag and embedding_config is not None:
        texts = [item.get("content", "") for item in normalized]
        try:
            vectors = request_embeddings(texts, embedding_config)
            for item, vector in zip(normalized, vectors):
                chunk_id = item.get("chunk_id", "")
                if chunk_id and vector:
                    chunk_embeddings[chunk_id] = [float(x) for x in vector]
        except Exception as exc:
            embedding_error = exc.__class__.__name__
            embedding_error_detail = str(exc)[:300]
            chunk_embeddings = {}
    embedding_stats = {
        "chunk_count": len(normalized),
        "embedded_chunk_count": len(chunk_embeddings),
        "embedding_coverage": round((len(chunk_embeddings) / len(normalized)), 3) if normalized else 0.0,
        "embedding_error": embedding_error,
        "embedding_error_detail": embedding_error_detail,
    }
    return {
        "chunks": normalized,
        "chunk_count": len(normalized),
        "inverted_index": dict(inverted_index),
        "chunk_embeddings": chunk_embeddings,
        "retrieval_mode": "vector+keyword" if chunk_embeddings else "keyword",
        "embedding_stats": embedding_stats,
    }
