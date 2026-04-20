from __future__ import annotations

from requirement_analysis.rag_evaluator import RagEvalCase, evaluate_retrieval_cases


def test_evaluate_retrieval_cases_computes_recall_and_mrr() -> None:
    cases = [
        RagEvalCase(
            case_id="case_auth",
            query="POST /auth login endpoint",
            chunks=[
                {
                    "chunk_id": "chunk_auth",
                    "content": "POST /auth returns token for login",
                    "section_title": "Authentication",
                    "source_file": "restful_booker.md",
                    "keywords": ["POST", "/auth", "login", "token"],
                },
                {
                    "chunk_id": "chunk_booking",
                    "content": "GET /booking list bookings",
                    "section_title": "Bookings",
                    "source_file": "restful_booker.md",
                    "keywords": ["GET", "/booking", "booking"],
                },
            ],
            expected_chunk_ids=["chunk_auth"],
            top_k=2,
        ),
        RagEvalCase(
            case_id="case_delete",
            query="DELETE /booking/{id} delete booking",
            chunks=[
                {
                    "chunk_id": "chunk_create",
                    "content": "POST /booking create booking resource",
                    "section_title": "Create",
                    "source_file": "restful_booker.md",
                    "keywords": ["POST", "/booking", "create"],
                },
                {
                    "chunk_id": "chunk_delete",
                    "content": "DELETE /booking/{id} deletes a booking by id",
                    "section_title": "Delete",
                    "source_file": "restful_booker.md",
                    "keywords": ["DELETE", "/booking/{id}", "delete", "id"],
                },
            ],
            expected_chunk_ids=["chunk_delete"],
            top_k=2,
        ),
    ]

    result = evaluate_retrieval_cases(cases)

    assert result["summary"]["case_count"] == 2
    assert result["summary"]["hit_count"] == 2
    assert result["summary"]["recall_at_k"] == 1.0
    assert result["summary"]["mrr"] == 1.0
    assert result["source_file_hit_count"]["restful_booker.md"] == 2

