"""Regression tests for api-runner performance-oriented defaults."""

from __future__ import annotations

import sys
from pathlib import Path


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[4]
    for rel in (
        "platform/shared/src",
        "platform/execution-engine/api-runner/src",
    ):
        p = str(root / rel)
        if p not in sys.path:
            sys.path.insert(0, p)


def test_runtime_state_uses_faster_defaults():
    _extend_path()
    from api_runner.executor import _build_runtime_state

    runtime_state = _build_runtime_state({"metadata": {"execution": {}}})

    assert runtime_state["default_step_timeout"] == 15
    assert runtime_state["default_step_retries"] == 0


def test_resolve_timeout_caps_connect_phase():
    _extend_path()
    from api_runner.executor import _resolve_timeout

    assert _resolve_timeout(15) == (5.0, 15.0)
    assert _resolve_timeout(3) == (3.0, 3.0)
