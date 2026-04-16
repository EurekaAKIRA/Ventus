"""Tests for tolerant JSON extraction from LLM chat message content."""

from __future__ import annotations

import pytest

from platform_shared.model_gateway import (
    ModelGatewayResponseError,
    _assistant_message_json_blobs,
    _normalize_assistant_message_content,
    parse_llm_json_object_content,
)


def test_parse_plain_json_object() -> None:
    assert parse_llm_json_object_content('  {"a": 1}  ') == {"a": 1}


def test_parse_json_inside_markdown_fence() -> None:
    raw = 'Sure.\n```json\n{"ok": true, "n": 2}\n```\n'
    assert parse_llm_json_object_content(raw) == {"ok": True, "n": 2}


def test_parse_json_fence_without_lang_tag() -> None:
    raw = "```\n{\"x\": \"y\"}\n```"
    assert parse_llm_json_object_content(raw) == {"x": "y"}


def test_parse_prose_then_brace_object() -> None:
    raw = 'Here is the result: {"entities": ["a"]} thanks.'
    assert parse_llm_json_object_content(raw) == {"entities": ["a"]}


def test_parse_rejects_array_top_level() -> None:
    with pytest.raises(ModelGatewayResponseError, match="non-json content"):
        parse_llm_json_object_content("[1, 2]")


def test_parse_rejects_empty() -> None:
    with pytest.raises(ModelGatewayResponseError, match="empty content"):
        parse_llm_json_object_content("   ")


def test_parse_rejects_garbage() -> None:
    with pytest.raises(ModelGatewayResponseError, match="non-json content"):
        parse_llm_json_object_content("not json at all")


def test_parse_json_with_trailing_prose_raw_decode() -> None:
    raw = '说明如下：{"objective": "smoke", "actors": ["qa"]} 以上。'
    assert parse_llm_json_object_content(raw) == {"objective": "smoke", "actors": ["qa"]}


def test_parse_strips_bom() -> None:
    assert parse_llm_json_object_content('\ufeff{"a": 1}') == {"a": 1}


def test_parse_picks_first_valid_object_after_garbage_object() -> None:
    raw = 'x {"broken": } y {"ok": true}'
    assert parse_llm_json_object_content(raw) == {"ok": True}


def test_assistant_message_json_blobs_reasoning_only() -> None:
    msg = {"content": "", "reasoning_content": '{"objective": "smoke", "actors": ["qa"]}'}
    blobs = _assistant_message_json_blobs(msg)
    assert blobs
    assert parse_llm_json_object_content(blobs[0]) == {"objective": "smoke", "actors": ["qa"]}


def test_normalize_assistant_message_content_list_segments() -> None:
    chunks = [
        {"type": "text", "text": '{"entities": ['},
        {"type": "text", "text": '"api"]}'},
    ]
    # Joined string is invalid JSON; ensures we concatenate list parts like real APIs do.
    assert _normalize_assistant_message_content(chunks) == '{"entities": ["api"]}'
    assert parse_llm_json_object_content(_normalize_assistant_message_content(chunks)) == {"entities": ["api"]}
