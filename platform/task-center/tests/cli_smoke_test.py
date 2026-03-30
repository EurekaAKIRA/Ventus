"""CLI smoke test for platform task center."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        str(root / "run_task_center.py"),
        "--task-name",
        "cli_smoke_test",
        "--input-file",
        str(root.parent / "requirement-analysis" / "examples" / "sample_requirement.md"),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    assert "validation_passed = True" in result.stdout
    assert "scenario_count =" in result.stdout
    print("cli smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
