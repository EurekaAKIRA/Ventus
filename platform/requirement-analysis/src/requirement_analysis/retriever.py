"""Lightweight retrieval for analysis-module."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from platform_shared import get_requirement_analysis_runtime_config
from platform_shared.models import RetrievedChunk

from .document_parser import extract_keywords, tokenize_text
from .openai_enhancement import OpenAIEnhancementConfig, cosine_similarity, request_embeddings

_API_PATH_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+/", re.IGNORECASE)
_API_SECTION_HINTS = ("接口", "scenario", "鉴权", "依赖", "资源", "请求", "路由")
_API_CONTENT_HINTS = ("路径：", "**涉及接口:**", "资源来源：", "资源前置条件：")


@dataclass(frozen=True, slots=True)
class RetrievalScoringConfig:
    lexical_weight: float = 4.0
    vector_weight: float = 6.0
    rerank_vector_weight: float = 7.0
    rerank_lexical_weight: float = 2.0
    rerank_title_boost: float = 0.2
    rerank_content_boost: float = 0.2

    def to_dict(self) -> dict[str, float]:
        return {
            "lexical_weight": self.lexical_weight,
            "vector_weight": self.vector_weight,
            "rerank_vector_weight": self.rerank_vector_weight,
            "rerank_lexical_weight": self.rerank_lexical_weight,
            "rerank_title_boost": self.rerank_title_boost,
            "rerank_content_boost": self.rerank_content_boost,
        }


def get_retrieval_scoring_config() -> RetrievalScoringConfig:
    defaults = get_requirement_analysis_runtime_config().retrieval_scoring
    return RetrievalScoringConfig(
        lexical_weight=defaults.lexical_weight,
        vector_weight=defaults.vector_weight,
        rerank_vector_weight=defaults.rerank_vector_weight,
        rerank_lexical_weight=defaults.rerank_lexical_weight,
        rerank_title_boost=defaults.rerank_title_boost,
        rerank_content_boost=defaults.rerank_content_boost,
    )


def _official_doc_boost_amount(chunk: dict, official_doc_boost: float) -> float:
    if official_doc_boost <= 0:
        return 0.0
    dt = str(chunk.get("doc_type", "") or "")
    if dt in ("platform_contract", "openapi_spec"):
        return official_doc_boost
    return 0.0


def _score_chunk(chunk: dict, query_terms: set[str], query_keywords: list[str]) -> float:
    chunk_terms = set(tokenize_text(chunk.get("content", "")))
    chunk_keywords = set(chunk.get("keywords", []))
    overlap_score = len(query_terms & chunk_terms) * 2.0
    keyword_score = len(set(query_keywords) & chunk_keywords) * 1.5
    title_bonus = 0.5 if any(word in chunk.get("section_title", "") for word in query_keywords[:3]) else 0.0
    return overlap_score + keyword_score + title_bonus


def _query_is_api_focused(query: str) -> bool:
    lowered = str(query or "").lower()
    if _API_PATH_RE.search(query):
        return True
    return any(token in lowered for token in ("接口", "api", "scenario", "鉴权", "依赖", "resource", "endpoint"))


def _api_chunk_boost(chunk: dict, *, api_focused: bool) -> float:
    if not api_focused:
        return 0.0
    title = str(chunk.get("section_title", "") or "")
    content = str(chunk.get("content", "") or "")
    doc_type = str(chunk.get("doc_type", "") or "")
    lowered_title = title.lower()
    boost = 0.0
    if not doc_type:
        boost += 0.15
    if any(hint in title or hint in lowered_title for hint in _API_SECTION_HINTS):
        boost += 0.25
    if _API_PATH_RE.search(content) or any(hint in content for hint in _API_CONTENT_HINTS):
        boost += 0.25
    if title in {"文档定位", "预期效果"}:
        boost -= 0.1
    return boost


def retrieve_relevant_chunks(
    index: dict,
    query: str,
    top_k: int = 5,
    use_vector_rag: bool = False,  # same flag as AnalysisParseOptions.rag_enabled
    embedding_config: OpenAIEnhancementConfig | None = None,
    rerank: bool = False,
    rerank_window: int = 12,
    scoring_config: RetrievalScoringConfig | None = None,
    *,
    official_doc_boost: float = 0.0,
    min_final_score: float = 0.0,
    out_diagnostics: dict[str, Any] | None = None,
) -> list[dict]:
    """Return chunks ranked by keyword score plus optional vector similarity."""
    scoring = scoring_config or get_retrieval_scoring_config()
    query_terms = set(tokenize_text(query))
    query_keywords = extract_keywords(query, limit=8)
    api_focused = _query_is_api_focused(query)
    query_embedding: list[float] = []
    if use_vector_rag and embedding_config is not None:
        try:
            vectors = request_embeddings([query], embedding_config)
            if vectors:
                query_embedding = vectors[0]
        except Exception:
            query_embedding = []
    chunk_embeddings = index.get("chunk_embeddings") or {}
    lexical_scores: dict[str, float] = {}
    vector_scores: dict[str, float] = {}
    chunk_payload: dict[str, dict] = {}
    for chunk in index.get("chunks", []):
        chunk_id = chunk.get("chunk_id", "")
        if not chunk_id:
            continue
        chunk_payload[chunk_id] = chunk
        lexical_scores[chunk_id] = _score_chunk(chunk, query_terms, query_keywords)
        if query_embedding:
            vector = chunk_embeddings.get(chunk_id, [])
            if vector:
                vector_scores[chunk_id] = max(cosine_similarity(query_embedding, vector), 0.0)

    scored = _merge_scores(
        lexical_scores=lexical_scores,
        vector_scores=vector_scores,
        chunk_payload=chunk_payload,
        scoring=scoring,
        official_doc_boost=official_doc_boost,
        api_focused=api_focused,
    )
    window = max(top_k, rerank_window) if rerank else top_k
    ranked = scored[:window]
    if rerank and vector_scores:
        ranked = _rerank_candidates(
            ranked=ranked,
            vector_scores=vector_scores,
            lexical_scores=lexical_scores,
            query_keywords=query_keywords,
            scoring=scoring,
            official_doc_boost=official_doc_boost,
            api_focused=api_focused,
        )
    before_threshold = len(ranked)
    if min_final_score > 0:
        ranked = [item for item in ranked if float(item.get("score", 0.0)) >= min_final_score]
    if out_diagnostics is not None:
        out_diagnostics["retrieval_min_final_score"] = min_final_score
        out_diagnostics["retrieval_candidates_before_threshold"] = before_threshold
        out_diagnostics["retrieval_low_score_rejection"] = bool(
            min_final_score > 0 and before_threshold > 0 and len(ranked) == 0
        )
    return ranked[:top_k]


def _merge_scores(
    *,
    lexical_scores: dict[str, float],
    vector_scores: dict[str, float],
    chunk_payload: dict[str, dict],
    scoring: RetrievalScoringConfig,
    official_doc_boost: float = 0.0,
    api_focused: bool = False,
) -> list[dict]:
    max_lexical = max(lexical_scores.values(), default=0.0) or 1.0
    scored: list[dict] = []
    for chunk_id, chunk in chunk_payload.items():
        lexical_score = lexical_scores.get(chunk_id, 0.0)
        vector_score = vector_scores.get(chunk_id, 0.0)
        if lexical_score <= 0 and vector_score <= 0:
            continue
        normalized_lexical = lexical_score / max_lexical
        score = (normalized_lexical * scoring.lexical_weight) + (vector_score * scoring.vector_weight)
        score += _official_doc_boost_amount(chunk, official_doc_boost)
        score += _api_chunk_boost(chunk, api_focused=api_focused)
        payload = RetrievedChunk(
            chunk_id=chunk_id,
            content=chunk.get("content", ""),
            score=round(score, 3),
            section_title=chunk.get("section_title", ""),
            source_file=chunk.get("source_file", ""),
            doc_type=str(chunk.get("doc_type", "") or ""),
        )
        scored.append(payload.to_dict())
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored


def _rerank_candidates(
    *,
    ranked: list[dict],
    vector_scores: dict[str, float],
    lexical_scores: dict[str, float],
    query_keywords: list[str],
    scoring: RetrievalScoringConfig,
    official_doc_boost: float = 0.0,
    api_focused: bool = False,
) -> list[dict]:
    if not ranked:
        return ranked
    max_lexical = max(lexical_scores.values(), default=0.0) or 1.0
    reranked: list[dict] = []
    for item in ranked:
        chunk_id = item.get("chunk_id", "")
        content = item.get("content", "")
        title = item.get("section_title", "")
        vector_score = vector_scores.get(chunk_id, 0.0)
        lexical_score = lexical_scores.get(chunk_id, 0.0) / max_lexical
        title_boost = scoring.rerank_title_boost if any(keyword.lower() in title.lower() for keyword in query_keywords[:3]) else 0.0
        content_boost = scoring.rerank_content_boost if any(keyword.lower() in content.lower() for keyword in query_keywords[:2]) else 0.0
        final_score = (vector_score * scoring.rerank_vector_weight) + (lexical_score * scoring.rerank_lexical_weight) + title_boost + content_boost
        chunk_stub = {"doc_type": item.get("doc_type", "")}
        final_score += _official_doc_boost_amount(chunk_stub, official_doc_boost)
        final_score += _api_chunk_boost(item, api_focused=api_focused)
        reranked.append({**item, "score": round(final_score, 3)})
    reranked.sort(key=lambda item: item["score"], reverse=True)
    return reranked

