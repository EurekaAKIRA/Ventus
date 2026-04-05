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


_TABLE_SEPARATOR_RE = re.compile(r"^\|?\s*[-:]+[-|\s:]+\|?\s*$")
_TABLE_ROW_RE = re.compile(r"^\|.*\|")


class MarkdownTable:
    """Parsed markdown table with typed access to rows and columns."""

    __slots__ = ("headers", "rows", "section_title", "line_start")

    def __init__(
        self,
        headers: list[str],
        rows: list[list[str]],
        section_title: str = "",
        line_start: int = 0,
    ):
        self.headers = headers
        self.rows = rows
        self.section_title = section_title
        self.line_start = line_start

    @property
    def column_count(self) -> int:
        return len(self.headers)

    def column(self, name: str) -> list[str]:
        """Return all values for a column identified by header name (case-insensitive)."""
        lowered = name.lower()
        for idx, header in enumerate(self.headers):
            if header.lower() == lowered:
                return [row[idx] if idx < len(row) else "" for row in self.rows]
        return []

    def to_dict(self) -> dict:
        return {
            "headers": self.headers,
            "rows": self.rows,
            "section_title": self.section_title,
            "line_start": self.line_start,
        }


def _split_table_cells(line: str) -> list[str]:
    return [cell.strip().strip("`").strip() for cell in line.strip().strip("|").split("|")]


def extract_markdown_tables(text: str) -> list[MarkdownTable]:
    """Identify markdown tables in *text* and return structured ``MarkdownTable`` objects."""
    lines = text.splitlines()
    tables: list[MarkdownTable] = []
    current_heading = ""
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("#"):
            current_heading = stripped.lstrip("#").strip()
            i += 1
            continue

        if (
            i + 2 < len(lines)
            and _TABLE_ROW_RE.match(stripped)
            and _TABLE_SEPARATOR_RE.match(lines[i + 1].strip())
        ):
            header_cells = _split_table_cells(stripped)
            data_rows: list[list[str]] = []
            j = i + 2
            while j < len(lines) and _TABLE_ROW_RE.match(lines[j].strip()):
                row_cells = _split_table_cells(lines[j])
                while len(row_cells) < len(header_cells):
                    row_cells.append("")
                data_rows.append(row_cells[: len(header_cells)])
                j += 1
            tables.append(
                MarkdownTable(
                    headers=header_cells,
                    rows=data_rows,
                    section_title=current_heading,
                    line_start=i + 1,
                )
            )
            i = j
            continue
        i += 1
    return tables


def parse_document(text: str) -> dict:
    """Build a parsed document payload for downstream modules."""
    cleaned_text = clean_document_text(text)
    tables = extract_markdown_tables(cleaned_text)
    return {
        "cleaned_text": cleaned_text,
        "outline": extract_document_outline(cleaned_text),
        "keywords": extract_keywords(cleaned_text),
        "candidate_test_points": extract_candidate_test_points(cleaned_text),
        "tables": [table.to_dict() for table in tables],
    }
