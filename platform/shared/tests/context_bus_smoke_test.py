"""Smoke test for ContextBus."""

from __future__ import annotations

import sys
from pathlib import Path


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[3]
    shared_src = root / "platform" / "shared" / "src"
    if str(shared_src) not in sys.path:
        sys.path.insert(0, str(shared_src))


def main() -> int:
    _extend_path()
    from platform_shared import ContextBus

    bus = ContextBus()
    bus.set("token", "abc")
    bus.set("user.id", 123)
    bus.set("user.profile.name", "demo")

    assert bus.get("token") == "abc"
    assert bus.get("user.id") == 123
    assert bus.get("user.profile.name") == "demo"
    assert bus.require(["token", "user.id"]) == []
    assert bus.require(["missing"]) == ["missing"]

    print("context bus smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
