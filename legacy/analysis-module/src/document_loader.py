"""Document loading utilities for analysis-module."""

from __future__ import annotations

from pathlib import Path


def _normalize_text(text: str) -> str:
    """Normalize encoding artefacts and line endings early in the pipeline."""
    normalized = text.replace("\ufeff", "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.strip()


def load_text_file(path: str) -> str:
    """Load plain text or markdown content from disk."""
    return _normalize_text(Path(path).read_text(encoding="utf-8"))


def load_document(source_path: str | None = None, inline_text: str | None = None) -> str:
    """Load content from disk or inline text with a single entry point."""
    if inline_text and inline_text.strip():
        return _normalize_text(inline_text)
    if source_path:
        return load_text_file(source_path)
    return ""
