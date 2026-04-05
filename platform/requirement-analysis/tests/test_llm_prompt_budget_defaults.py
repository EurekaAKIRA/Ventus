from __future__ import annotations

from requirement_analysis.openai_enhancement import (
    _llm_parse_context_limits,
    _llm_parse_head_tail_chars,
    _llm_parse_max_requirement_chars,
    _llm_parse_rule_list_limits,
)


def test_llm_prompt_budget_defaults(monkeypatch) -> None:
    for name in (
        "LLM_PARSE_MAX_REQUIREMENT_CHARS",
        "LLM_PARSE_HEAD_CHARS",
        "LLM_PARSE_TAIL_CHARS",
        "LLM_PARSE_MAX_CONTEXT_CHUNKS",
        "LLM_PARSE_MAX_CHUNK_CHARS",
        "LLM_PARSE_MAX_RULE_LIST_ITEMS",
        "LLM_PARSE_MAX_RULE_ITEM_CHARS",
    ):
        monkeypatch.delenv(name, raising=False)

    assert _llm_parse_max_requirement_chars() == 8000
    assert _llm_parse_head_tail_chars() == (4500, 2500)
    assert _llm_parse_context_limits() == (4, 800)
    assert _llm_parse_rule_list_limits() == (8, 240)
