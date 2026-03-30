"""Standalone launcher for platform task center without installing packages."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[2]
    additions = [
        root / "platform" / "shared" / "src",
        root / "platform" / "requirement-analysis" / "src",
        root / "platform" / "case-generation" / "src",
        root / "platform" / "result-analysis" / "src",
        root / "platform" / "task-center" / "src",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


def main() -> int:
    _extend_path()
    spec = importlib.util.find_spec("task_center.cli")
    if spec is None:
        raise RuntimeError("Cannot locate task_center.cli")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
