from __future__ import annotations

from requirement_analysis.retriever import retrieve_relevant_chunks


def _minimal_index() -> dict:
    return {
        "chunks": [
            {
                "chunk_id": "user_a",
                "content": "无关业务描述 登录 昵称",
                "keywords": ["登录", "昵称"],
                "section_title": "用户故事",
                "doc_type": "",
            },
            {
                "chunk_id": "contract_post_tasks",
                "content": "POST /api/tasks 创建任务 task_name requirement",
                "keywords": ["POST", "/api/tasks", "task_name"],
                "section_title": "创建任务",
                "doc_type": "platform_contract",
            },
        ],
        "chunk_embeddings": {},
    }


def test_official_boost_prefers_contract_chunk_when_lexical_tie() -> None:
    index = _minimal_index()
    # Query overlaps both similarly; boost should lift contract above user.
    hits = retrieve_relevant_chunks(
        index,
        "创建任务 POST task_name 接口",
        top_k=2,
        use_vector_rag=False,
        official_doc_boost=5.0,
        min_final_score=0.0,
    )
    assert hits and hits[0]["chunk_id"] == "contract_post_tasks"


def test_min_final_score_drops_weak_hits_and_sets_diagnostic() -> None:
    index = _minimal_index()
    diag: dict = {}
    hits = retrieve_relevant_chunks(
        index,
        "创建任务 POST task_name 接口",
        top_k=5,
        use_vector_rag=False,
        official_doc_boost=0.0,
        min_final_score=100.0,
        out_diagnostics=diag,
    )
    assert hits == []
    assert diag.get("retrieval_low_score_rejection") is True
    assert diag.get("retrieval_candidates_before_threshold", 0) > 0
