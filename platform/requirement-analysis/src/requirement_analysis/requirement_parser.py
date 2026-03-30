"""Requirement parsing helpers."""

from __future__ import annotations

import re

from .document_parser import extract_candidate_test_points, extract_keywords
from platform_shared.models import ParsedRequirement

ACTION_VERBS = ("点击", "输入", "选择", "提交", "打开", "进入", "创建", "删除", "修改", "搜索", "保存", "查看")
EXPECTATION_CUES = ("应", "应当", "应该", "显示", "看到", "可见", "返回", "提示", "成功", "失败", "跳转", "刷新")
CONSTRAINT_CUES = ("必须", "只能", "不可", "不能", "不应", "至少", "最多", "限制")
PRECONDITION_CUES = ("已登录", "登录后", "进入", "访问", "存在", "准备好", "前提")


def _normalize_statement(text: str) -> str:
    normalized = text.strip()
    normalized = re.sub(r"^#+\s*", "", normalized)
    normalized = re.sub(r"^[-*]\s*", "", normalized)
    normalized = re.sub(r"^\d+[.)、]\s*", "", normalized)
    return normalized.strip(" 。；;")


def _derive_objective(requirement_text: str, candidate_points: list[dict]) -> str:
    heading_match = re.search(r"^\s*#\s+(.+)$", requirement_text, re.MULTILINE)
    if heading_match:
        return heading_match.group(1).strip()
    for item in candidate_points:
        if item["type"] in {"action", "expectation"}:
            return _normalize_statement(item["text"])
    for line in requirement_text.splitlines():
        normalized = _normalize_statement(line)
        if normalized:
            return normalized
    return "待补充需求目标"


def _merge_context(requirement_text: str, retrieved_context: list[dict]) -> str:
    parts = [requirement_text.strip()]
    for item in retrieved_context[:3]:
        content = item.get("content", "").strip()
        if content and content not in parts:
            parts.append(content)
    return "\n".join(part for part in parts if part)


def _extract_actors(text: str) -> list[str]:
    actors: list[str] = []
    for actor in ("管理员", "审核员", "访客", "普通用户", "用户", "运营人员", "客服"):
        if actor in text and actor not in actors:
            actors.append(actor)
    return actors or ["用户"]


def _dedupe(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        normalized = _normalize_statement(item)
        if normalized and normalized not in seen:
            seen.append(normalized)
    return seen


def parse_requirement(
    requirement_text: str,
    retrieved_context: list[dict] | None = None,
    use_llm: bool = False,
) -> dict:
    """Parse requirement text into a structured, test-oriented representation."""
    base_text = requirement_text.strip()
    retrieved_context = retrieved_context or []
    merged_text = _merge_context(base_text, retrieved_context)
    candidate_points = extract_candidate_test_points(merged_text)
    objective = _derive_objective(base_text or merged_text, candidate_points)

    actions = [item["text"] for item in candidate_points if item["type"] == "action"]
    expectations = [item["text"] for item in candidate_points if item["type"] == "expectation"]
    preconditions = [item["text"] for item in candidate_points if item["type"] == "precondition"]
    constraints = [sentence for sentence in re.split(r"[\n。；;]+", merged_text) if any(cue in sentence for cue in CONSTRAINT_CUES)]

    if not actions:
        for sentence in re.split(r"[\n。；;]+", base_text):
            sentence = sentence.strip()
            if sentence and any(verb in sentence for verb in ACTION_VERBS):
                actions.append(sentence)

    if not expectations:
        for sentence in re.split(r"[\n。；;]+", merged_text):
            sentence = sentence.strip()
            if sentence and any(cue in sentence for cue in EXPECTATION_CUES):
                expectations.append(sentence)

    if not preconditions:
        for sentence in re.split(r"[\n。；;]+", merged_text):
            sentence = sentence.strip()
            if sentence and any(cue in sentence for cue in PRECONDITION_CUES):
                preconditions.append(sentence)

    if not actions:
        actions.append("按需求描述执行核心业务动作")
    if not expectations:
        expectations.append("系统呈现与需求描述一致的可观察结果")

    ambiguities: list[str] = []
    if len(base_text) < 12:
        ambiguities.append("原始需求较短，建议补充业务目标、页面对象和断言细节")
    if not retrieved_context:
        ambiguities.append("未命中补充上下文，当前结果主要基于原始需求")
    if len(expectations) == 1 and expectations[0].startswith("系统呈现与需求描述一致"):
        ambiguities.append("断言表达仍偏抽象，建议补充可见元素、提示文案或状态变化")
    if use_llm:
        ambiguities.append("LLM 增强模式尚未接入，本次回退到规则解析结果")

    parsed = ParsedRequirement(
        objective=objective,
        actors=_extract_actors(merged_text),
        entities=extract_keywords(merged_text, limit=10),
        preconditions=_dedupe(preconditions),
        actions=_dedupe(actions),
        expected_results=_dedupe(expectations),
        constraints=_dedupe(constraints),
        ambiguities=_dedupe(ambiguities),
        source_chunks=[item.get("chunk_id", "") for item in retrieved_context if item.get("chunk_id")],
    )
    return parsed.to_dict()
