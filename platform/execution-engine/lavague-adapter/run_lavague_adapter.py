"""Standalone launcher for LaVague execution adapter."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[3]
    legacy = root / "legacy"
    additions = [
        root / "platform" / "execution-engine" / "core" / "src",
        root / "platform" / "execution-engine" / "core",
        root / "platform" / "execution-engine" / "lavague-adapter" / "src",
        legacy / "lavague-core",
        legacy / "lavague-integrations" / "drivers" / "lavague-drivers-selenium",
        legacy / "lavague-integrations" / "drivers" / "lavague-drivers-playwright",
        legacy / "lavague-integrations" / "contexts" / "lavague-contexts-openai",
        legacy / "lavague-integrations" / "contexts" / "lavague-contexts-anthropic",
        legacy / "lavague-integrations" / "contexts" / "lavague-contexts-fireworks",
        legacy / "lavague-integrations" / "contexts" / "lavague-contexts-gemini",
        legacy / "lavague-integrations" / "contexts" / "lavague-contexts-cache",
        legacy / "lavague-integrations" / "retrievers" / "lavague-retrievers-cohere",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


def main() -> int:
    _extend_path()
    spec = importlib.util.find_spec("lavague_adapter.cli")
    if spec is None:
        raise RuntimeError("Cannot locate lavague_adapter.cli")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.cli.main(standalone_mode=False)


if __name__ == "__main__":
    raise SystemExit(main())
