"""Standalone launcher for DSL runtime execution."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[3]
    legacy = root / "legacy"
    additions = [
        root / "platform" / "shared" / "src",
        root / "platform" / "execution-engine" / "api-runner" / "src",
        root / "platform" / "execution-engine" / "core" / "src",
        legacy / "lavague-core",
        legacy / "lavague-integrations" / "drivers" / "lavague-drivers-selenium",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


def main() -> int:
    _extend_path()
    spec = importlib.util.find_spec("execution_engine_core.run_from_dsl")
    if spec is None:
        raise RuntimeError("Cannot locate execution_engine_core.run_from_dsl")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
