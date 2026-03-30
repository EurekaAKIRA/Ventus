"""Requirement parsing helpers with API-oriented cues."""

from __future__ import annotations

import re

from platform_shared.models import ParsedRequirement

from .document_parser import extract_candidate_test_points, extract_keywords

ACTION_VERBS = (
    "click",
    "input",
    "select",
    "submit",
    "open",
    "enter",
    "create",
    "delete",
    "update",
    "search",
    "save",
    "view",
    "login",
    "query",
    "request",
    "call",
    "invoke",
    "post",
    "get",
    "put",
    "点击",
    "输入",
    "提交",
    "打开",
    "创建",
    "删除",
    "更新",
    "查询",
    "查看",
    "登录",
)
EXPECTATION_CUES = (
    "should",
    "returns",
    "return",
    "response",
    "status",
    "contains",
    "success",
    "failed",
    "显示",
    "返回",
    "提示",
    "成功",
    "失败",
)
CONSTRAINT_CUES = ("must", "cannot", "only", "require", "必须", "只能", "不可", "不能", "限制")
PRECONDITION_CUES = ("precondition", "before", "authenticated", "existing", "前提", "已登录", "登录后", "准备好", "存在")
ACTOR_HINTS = ("admin", "reviewer", "guest", "user", "operator", "service", "管理员", "审核员", "访客", "用户", "运营")


def _normalize_statement(text: str) -> str:
    normalized = text.strip()
    normalized = re.sub(r"^#+\s*", "", normalized)
    normalized = re.sub(r"^[-*]\s*", "", normalized)
    normalized = re.sub(r"^\d+[.)、\s]*", "", normalized)
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
    return "Requirement objective pending"


def _merge_context(requirement_text: str, retrieved_context: list[dict]) -> str:
    parts = [requirement_text.strip()]
    for item in retrieved_context[:3]:
        content = item.get("content", "").strip()
        if content and content not in parts:
            parts.append(content)
    return "\n".join(part for part in parts if part)


def _extract_actors(text: str) -> list[str]:
    lowered = text.lower()
    actors = [actor for actor in ACTOR_HINTS if actor in lowered or actor in text]
    return actors or ["user"]


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
    constraints = [sentence for sentence in re.split(r"[\n。；;]+", merged_text) if any(cue in sentence.lower() for cue in CONSTRAINT_CUES)]

    if not actions:
        for sentence in re.split(r"[\n。；;]+", base_text):
            sentence = sentence.strip()
            if sentence and any(verb in sentence.lower() or verb in sentence for verb in ACTION_VERBS):
                actions.append(sentence)

    if not expectations:
        for sentence in re.split(r"[\n。；;]+", merged_text):
            sentence = sentence.strip()
            if sentence and any(cue in sentence.lower() or cue in sentence for cue in EXPECTATION_CUES):
                expectations.append(sentence)

    if not preconditions:
        for sentence in re.split(r"[\n。；;]+", merged_text):
            sentence = sentence.strip()
            if sentence and any(cue in sentence.lower() or cue in sentence for cue in PRECONDITION_CUES):
                preconditions.append(sentence)

    if not actions:
        actions.append("Execute the core business action")
    if not expectations:
        expectations.append("System returns an observable result aligned with the requirement")

    ambiguities: list[str] = []
    if len(base_text) < 12:
        ambiguities.append("Requirement is short; add business goal, API path, and assertion details")
    if not retrieved_context:
        ambiguities.append("No retrieved context was available; output is inferred from the raw requirement only")
    if use_llm:
        ambiguities.append("LLM enhancement is not wired yet; current parsing stays rule-based")

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
