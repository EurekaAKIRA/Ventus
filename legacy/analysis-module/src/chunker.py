"""Document chunking utilities."""

from __future__ import annotations

import re

from .document_parser import extract_keywords, extract_sentences
from .models import DocumentChunk


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split cleaned text into titled sections for chunking."""
    sections: list[tuple[str, str]] = []
    current_title = "未命名章节"
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            sections.append((current_title, "\n".join(buffer).strip()))
            buffer.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if buffer and buffer[-1] != "":
                buffer.append("")
            continue
        if stripped.startswith("#"):
            flush()
            current_title = stripped.lstrip("#").strip() or "未命名章节"
            continue
        buffer.append(stripped)

    flush()
    return sections or [("未命名章节", text.strip())]


def _split_large_paragraph(paragraph: str, chunk_size: int) -> list[str]:
    """Split large blocks at sentence boundaries before retrieval indexing."""
    if len(paragraph) <= chunk_size:
        return [paragraph]
    pieces: list[str] = []
    buffer = ""
    for sentence in extract_sentences(paragraph):
        candidate = f"{buffer} {sentence}".strip() if buffer else sentence
        if len(candidate) > chunk_size and buffer:
            pieces.append(buffer)
            buffer = sentence
        else:
            buffer = candidate
    if buffer:
        pieces.append(buffer)
    return pieces


def chunk_text(text: str, chunk_size: int = 420, source_file: str = "") -> list[DocumentChunk]:
    """Split text into traceable chunks for lightweight retrieval."""
    chunks: list[DocumentChunk] = []

    for section_index, (section_title, section_text) in enumerate(_split_sections(text), start=1):
        paragraphs = [segment.strip() for segment in re.split(r"\n{2,}", section_text) if segment.strip()]
        paragraph_index = 0
        for paragraph in paragraphs:
            paragraph_index += 1
            for fragment_index, fragment in enumerate(_split_large_paragraph(paragraph, chunk_size), start=1):
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"chunk_{len(chunks) + 1:03d}",
                        content=fragment.strip(),
                        section_title=section_title,
                        source_file=source_file,
                        source_block=f"section_{section_index}_paragraph_{paragraph_index}_part_{fragment_index}",
                        tokens_estimate=max(1, len(fragment) // 2),
                        keywords=extract_keywords(fragment, limit=8),
                    )
                )

    return chunks
