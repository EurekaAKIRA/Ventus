"""Standalone launcher for the FastAPI task-center service."""

from __future__ import annotations

import sys
from pathlib import Path

import uvicorn


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[2]
    legacy = root / "legacy"
    additions = [
        root / "platform" / "shared" / "src",
        root / "platform" / "requirement-analysis" / "src",
        root / "platform" / "case-generation" / "src",
        root / "platform" / "result-analysis" / "src",
        root / "platform" / "execution-engine" / "api-runner" / "src",
        root / "platform" / "execution-engine" / "core" / "src",
        root / "platform" / "task-center" / "src",
        legacy / "lavague-core",
        legacy / "lavague-integrations" / "drivers" / "lavague-drivers-selenium",
        legacy / "lavague-integrations" / "drivers" / "lavague-drivers-playwright",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


def main() -> int:
    _extend_path()
    uvicorn.run("task_center.api:app", host="127.0.0.1", port=8001, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
