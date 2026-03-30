"""Lightweight document parsing utilities."""

from __future__ import annotations

import re

STOPWORDS = {
    "用户",
    "系统",
    "页面",
    "功能",
    "需要",
    "应该",
    "可以",
    "进行",
    "相关",
    "一个",
    "以及",
    "其中",
    "支持",
    "如果",
    "为了",
    "并且",
}


def clean_document_text(text: str) -> str:
    """Perform cleanup while preserving enough structure for later stages."""
    lines: list[str] = []
    previous_blank = False
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            if not previous_blank:
                lines.append("")
            previous_blank = True
            continue
        previous_blank = False
        line = re.sub(r"^```[\w-]*$", "", line).strip()
        if line:
            lines.append(line)
    cleaned = "\n".join(lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def extract_document_outline(text: str) -> list[dict]:
    """Extract headings, bullets and numbered items from markdown-like text."""
    outline: list[dict] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            outline.append(
                {
                    "type": "heading",
                    "level": len(stripped) - len(stripped.lstrip("#")),
                    "text": stripped.lstrip("#").strip(),
                    "line": line_no,
                }
            )
            continue
        if re.match(r"^[-*]\s+", stripped):
            outline.append({"type": "bullet", "text": re.sub(r"^[-*]\s+", "", stripped), "line": line_no})
            continue
        if re.match(r"^\d+[.)、]\s+", stripped):
            outline.append({"type": "ordered_item", "text": re.sub(r"^\d+[.)、]\s+", "", stripped), "line": line_no})
    return outline


def tokenize_text(text: str) -> list[str]:
    """Split Chinese and mixed text into reusable lightweight retrieval tokens."""
    raw_tokens = re.split(r"[\s，。；、,:：()（）\[\]{}<>《》/\\|`'\"!?！？]+", text)
    tokens: list[str] = []
    for token in raw_tokens:
        normalized = token.strip().lower()
        if len(normalized) < 2:
            continue
        if re.fullmatch(r"[\d.#-]+", normalized):
            continue
        if normalized in STOPWORDS:
            continue
        tokens.append(normalized)
    return tokens


def extract_keywords(text: str, limit: int = 10) -> list[str]:
    """Extract lightweight keywords from cleaned text."""
    seen: list[str] = []
    for token in tokenize_text(text):
        if token not in seen:
            seen.append(token)
        if len(seen) >= limit:
            break
    return seen


def extract_sentences(text: str) -> list[str]:
    """Split cleaned text into sentence-like units."""
    sentences = re.split(r"(?<=[。！？!?；;])\s*|\n{2,}", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def extract_candidate_test_points(text: str) -> list[dict]:
    """Build lightweight sentence-level cues for requirement parsing."""
    cues: list[dict] = []
    for sentence in extract_sentences(text):
        normalized_sentence = re.sub(r"^#+\s*", "", sentence).strip()
        normalized_sentence = re.sub(r"^[-*]\s*", "", normalized_sentence).strip()
        normalized_sentence = re.sub(r"^\d+[.)、]\s*", "", normalized_sentence).strip()
        if not normalized_sentence:
            continue
        cue_type = "statement"
        if any(keyword in normalized_sentence for keyword in ("前提", "已登录", "登录后", "进入", "访问")):
            cue_type = "precondition"
        elif any(keyword in normalized_sentence for keyword in ("点击", "输入", "选择", "提交", "打开", "创建", "删除", "修改")):
            cue_type = "action"
        elif any(keyword in normalized_sentence for keyword in ("应", "应当", "应该", "显示", "看到", "返回", "提示", "可见", "成功", "失败")):
            cue_type = "expectation"
        cues.append({"type": cue_type, "text": normalized_sentence, "keywords": extract_keywords(normalized_sentence, limit=6)})
    return cues


def parse_document(text: str) -> dict:
    """Build a parsed document payload for downstream modules."""
    cleaned_text = clean_document_text(text)
    return {
        "cleaned_text": cleaned_text,
        "outline": extract_document_outline(cleaned_text),
        "keywords": extract_keywords(cleaned_text),
        "candidate_test_points": extract_candidate_test_points(cleaned_text),
    }
