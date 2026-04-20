"""Offline retrieval evaluation helpers for RAG quality tracking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .knowledge_index import build_index
from .openai_enhancement import OpenAIEnhancementConfig
from .retriever import RetrievalScoringConfig, get_retrieval_scoring_config, retrieve_relevant_chunks


@dataclass(frozen=True, slots=True)
class RagEvalCase:
    case_id: str
    query: str
    chunks: list[dict[str, Any]]
    expected_chunk_ids: list[str]
    use_vector_rag: bool = False
    top_k: int = 5
    rerank: bool = False


def evaluate_retrieval_cases(
    cases: list[RagEvalCase],
    *,
    embedding_config: OpenAIEnhancementConfig | None = None,
    scoring_config: RetrievalScoringConfig | None = None,
) -> dict[str, Any]:
    scoring = scoring_config or get_retrieval_scoring_config()
    case_results: list[dict[str, Any]] = []
    recall_hits = 0
    reciprocal_rank_sum = 0.0
    source_file_hits: dict[str, int] = {}

    for case in cases:
        index = build_index(
            case.chunks,
            enable_vector_rag=case.use_vector_rag,
            embedding_config=embedding_config if case.use_vector_rag else None,
        )
        retrieved = retrieve_relevant_chunks(
            index,
            case.query,
            top_k=case.top_k,
            use_vector_rag=case.use_vector_rag,
            embedding_config=embedding_config if case.use_vector_rag else None,
            rerank=case.rerank,
            scoring_config=scoring,
        )
        expected = {item for item in case.expected_chunk_ids if item}
        hit_rank = _find_first_hit_rank(retrieved, expected)
        hit = hit_rank is not None
        if hit:
            recall_hits += 1
            reciprocal_rank_sum += 1.0 / hit_rank
        matched_source_files = sorted(
            {
                str(item.get("source_file", ""))
                for item in retrieved
                if str(item.get("chunk_id", "")) in expected and str(item.get("source_file", ""))
            }
        )
        for source_file in matched_source_files:
            source_file_hits[source_file] = source_file_hits.get(source_file, 0) + 1
        case_results.append(
            {
                "case_id": case.case_id,
                "hit": hit,
                "hit_rank": hit_rank,
                "reciprocal_rank": round((1.0 / hit_rank), 4) if hit_rank else 0.0,
                "expected_chunk_ids": sorted(expected),
                "retrieved_chunk_ids": [str(item.get("chunk_id", "")) for item in retrieved],
                "matched_source_files": matched_source_files,
                "retrieval_mode": index.get("retrieval_mode", "keyword"),
            }
        )

    total = len(cases)
    return {
        "summary": {
            "case_count": total,
            "hit_count": recall_hits,
            "recall_at_k": round((recall_hits / total), 4) if total else 0.0,
            "mrr": round((reciprocal_rank_sum / total), 4) if total else 0.0,
        },
        "source_file_hit_count": source_file_hits,
        "cases": case_results,
    }


def _find_first_hit_rank(retrieved: list[dict[str, Any]], expected_chunk_ids: set[str]) -> int | None:
    if not expected_chunk_ids:
        return None
    for index, item in enumerate(retrieved, start=1):
        if str(item.get("chunk_id", "")) in expected_chunk_ids:
            return index
    return None
