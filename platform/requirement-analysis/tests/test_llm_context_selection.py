from __future__ import annotations

from requirement_analysis.openai_enhancement import _build_retrieved_context_preview


def test_llm_context_preview_prioritizes_interface_and_scenario_chunks() -> None:
    preview = _build_retrieved_context_preview(
        [
            {
                "chunk_id": "chunk_goal",
                "section_title": "文档定位",
                "content": "说明自动生成目标与执行报告。",
                "score": 4.0,
                "doc_type": "",
            },
            {
                "chunk_id": "chunk_contract",
                "section_title": "创建任务 POST /api/tasks",
                "content": "POST /api/tasks 创建任务。",
                "score": 3.9,
                "doc_type": "platform_contract",
            },
            {
                "chunk_id": "chunk_interface",
                "section_title": "接口：创建 booking",
                "content": "- 方法：`POST`\n- 路径：`/booking`\n- 功能：创建 booking",
                "score": 2.8,
                "doc_type": "",
            },
            {
                "chunk_id": "chunk_scenario",
                "section_title": "Scenario: Booking 生命周期管理",
                "content": "**涉及接口:** `POST /booking`、`DELETE /booking/{id}`",
                "score": 2.7,
                "doc_type": "",
            },
        ]
    )

    titles = [item["section_title"] for item in preview]
    assert titles[:2] == ["接口：创建 booking", "Scenario: Booking 生命周期管理"]
