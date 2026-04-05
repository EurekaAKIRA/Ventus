"""Backward-compatible runtime config facade for requirement-analysis."""

from __future__ import annotations

from dataclasses import dataclass

from platform_shared.runtime_config import get_requirement_analysis_runtime_config


@dataclass(frozen=True, slots=True)
class AnalysisDefaults:
    use_llm: bool = False
    rag_enabled: bool = False
    retrieval_top_k: int = 5
    rerank_enabled: bool = False


@dataclass(frozen=True, slots=True)
class RetrievalScoringDefaults:
    lexical_weight: float = 4.0
    vector_weight: float = 6.0
    rerank_vector_weight: float = 7.0
    rerank_lexical_weight: float = 2.0
    rerank_title_boost: float = 0.2
    rerank_content_boost: float = 0.2


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    analysis_defaults: AnalysisDefaults = AnalysisDefaults()
    retrieval_scoring: RetrievalScoringDefaults = RetrievalScoringDefaults()
    embedding_batch_size: int = 32


def get_runtime_config() -> RuntimeConfig:
    shared = get_requirement_analysis_runtime_config()
    return RuntimeConfig(
        analysis_defaults=AnalysisDefaults(
            use_llm=shared.defaults.use_llm,
            rag_enabled=shared.defaults.rag_enabled,
            retrieval_top_k=shared.defaults.retrieval_top_k,
            rerank_enabled=shared.defaults.rerank_enabled,
        ),
        retrieval_scoring=RetrievalScoringDefaults(
            lexical_weight=shared.retrieval_scoring.lexical_weight,
            vector_weight=shared.retrieval_scoring.vector_weight,
            rerank_vector_weight=shared.retrieval_scoring.rerank_vector_weight,
            rerank_lexical_weight=shared.retrieval_scoring.rerank_lexical_weight,
            rerank_title_boost=shared.retrieval_scoring.rerank_title_boost,
            rerank_content_boost=shared.retrieval_scoring.rerank_content_boost,
        ),
        embedding_batch_size=shared.embedding_batch_size,
    )
