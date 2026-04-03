from __future__ import annotations

from requirement_analysis.knowledge_index import build_index
from requirement_analysis.openai_enhancement import OpenAIEnhancementConfig, request_embeddings
from requirement_analysis.retriever import retrieve_relevant_chunks
from platform_shared.runtime_config import (
    PlatformRuntimeConfig,
    RequirementAnalysisDefaults,
    RequirementAnalysisRetrievalScoring,
    RequirementAnalysisRuntimeConfig,
)


class _FakeGateway:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embedding(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(index + 1)] for index, _ in enumerate(texts)]


def test_request_embeddings_batches_by_size() -> None:
    gateway = _FakeGateway()
    config = OpenAIEnhancementConfig(gateway=gateway)  # type: ignore[arg-type]

    vectors = request_embeddings(
        ["a", "b", "c", "d", "e"],
        config,
        batch_size=2,
    )

    assert len(vectors) == 5
    assert len(gateway.calls) == 3
    assert gateway.calls[0] == ["a", "b"]
    assert gateway.calls[1] == ["c", "d"]
    assert gateway.calls[2] == ["e"]


def test_build_index_exposes_embedding_coverage(monkeypatch) -> None:
    monkeypatch.setattr(
        "requirement_analysis.knowledge_index.request_embeddings",
        lambda texts, _: [[0.1, 0.2] for _ in texts],
    )
    chunks = [
        {
            "chunk_id": "chunk_001",
            "content": "Login API with username and password",
            "section_title": "Auth",
            "source_file": "",
            "keywords": ["login", "api"],
        },
        {
            "chunk_id": "chunk_002",
            "content": "Query profile API with token",
            "section_title": "Profile",
            "source_file": "",
            "keywords": ["query", "profile", "token"],
        },
    ]

    index = build_index(
        chunks=chunks,
        enable_vector_rag=True,
        embedding_config=OpenAIEnhancementConfig(gateway=_FakeGateway()),  # type: ignore[arg-type]
    )

    assert index["retrieval_mode"] == "vector+keyword"
    assert index["embedding_stats"]["chunk_count"] == 2
    assert index["embedding_stats"]["embedded_chunk_count"] == 2
    assert index["embedding_stats"]["embedding_coverage"] == 1.0


def test_retrieve_relevant_chunks_supports_rerank(monkeypatch) -> None:
    monkeypatch.setattr(
        "requirement_analysis.retriever.request_embeddings",
        lambda texts, _: [[0.0, 1.0] for _ in texts],
    )
    index = {
        "chunks": [
            {
                "chunk_id": "chunk_001",
                "content": "Create order API and return order id",
                "section_title": "Orders",
                "source_file": "",
                "keywords": ["create", "order"],
            },
            {
                "chunk_id": "chunk_002",
                "content": "Query profile API with bearer token",
                "section_title": "Profile",
                "source_file": "",
                "keywords": ["query", "profile", "token"],
            },
        ],
        "chunk_embeddings": {
            "chunk_001": [1.0, 0.0],
            "chunk_002": [0.0, 1.0],
        },
    }

    hits = retrieve_relevant_chunks(
        index=index,
        query="query profile with token",
        top_k=1,
        use_vector_rag=True,
        embedding_config=OpenAIEnhancementConfig(gateway=_FakeGateway()),  # type: ignore[arg-type]
        rerank=True,
        rerank_window=2,
    )

    assert len(hits) == 1
    assert hits[0]["chunk_id"] == "chunk_002"
    assert hits[0]["score"] > 0


def test_retrieve_relevant_chunks_supports_weight_tuning(monkeypatch) -> None:
    monkeypatch.setattr(
        "requirement_analysis.retriever.request_embeddings",
        lambda texts, _: [[1.0, 0.0] for _ in texts],
    )
    index = {
        "chunks": [
            {
                "chunk_id": "chunk_vector",
                "content": "create order endpoint details",
                "section_title": "Orders",
                "source_file": "",
                "keywords": ["create", "order"],
            },
            {
                "chunk_id": "chunk_lexical",
                "content": "query profile token details",
                "section_title": "Profile",
                "source_file": "",
                "keywords": ["query", "profile", "token"],
            },
        ],
        "chunk_embeddings": {
            "chunk_vector": [1.0, 0.0],
            "chunk_lexical": [0.0, 1.0],
        },
    }

    default_hits = retrieve_relevant_chunks(
        index=index,
        query="query profile token",
        top_k=1,
        use_vector_rag=True,
        embedding_config=OpenAIEnhancementConfig(gateway=_FakeGateway()),  # type: ignore[arg-type]
        rerank=False,
    )
    assert default_hits[0]["chunk_id"] == "chunk_vector"

    monkeypatch.setattr(
        "platform_shared.runtime_config._CACHED_PLATFORM_RUNTIME_CONFIG",
        PlatformRuntimeConfig(
            requirement_analysis=RequirementAnalysisRuntimeConfig(
                defaults=RequirementAnalysisDefaults(),
                retrieval_scoring=RequirementAnalysisRetrievalScoring(
                    lexical_weight=9.0,
                    vector_weight=1.0,
                    rerank_vector_weight=7.0,
                    rerank_lexical_weight=2.0,
                    rerank_title_boost=0.2,
                    rerank_content_boost=0.2,
                ),
                embedding_batch_size=32,
            ),
        ),
    )
    lexical_hits = retrieve_relevant_chunks(
        index=index,
        query="query profile token",
        top_k=1,
        use_vector_rag=True,
        embedding_config=OpenAIEnhancementConfig(gateway=_FakeGateway()),  # type: ignore[arg-type]
        rerank=False,
    )
    assert lexical_hits[0]["chunk_id"] == "chunk_lexical"
