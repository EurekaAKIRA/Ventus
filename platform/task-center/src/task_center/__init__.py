"""Task center package."""

from __future__ import annotations

from typing import Any

__all__ = ["persist_pipeline_artifacts", "run_analysis_pipeline"]


def persist_pipeline_artifacts(*args: Any, **kwargs: Any) -> Any:
    from .pipeline import persist_pipeline_artifacts as _persist_pipeline_artifacts

    return _persist_pipeline_artifacts(*args, **kwargs)


def run_analysis_pipeline(*args: Any, **kwargs: Any) -> Any:
    from .pipeline import run_analysis_pipeline as _run_analysis_pipeline

    return _run_analysis_pipeline(*args, **kwargs)
