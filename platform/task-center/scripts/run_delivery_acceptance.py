from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_command(command: list[str]) -> list[str]:
    if not command:
        return command

    executable = command[0]
    resolved = shutil.which(executable)
    if resolved:
        return [resolved, *command[1:]]

    if os.name == "nt" and Path(executable).suffix == "":
        for suffix in (".cmd", ".exe", ".bat"):
            resolved = shutil.which(f"{executable}{suffix}")
            if resolved:
                return [resolved, *command[1:]]
    return command


def _run_command(name: str, command: list[str], *, cwd: Path, timeout_s: int) -> dict[str, Any]:
    started = time.perf_counter()
    resolved_command = _resolve_command(command)
    try:
        completed = subprocess.run(
            resolved_command,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
            check=False,
        )
        output = completed.stdout or ""
        return {
            "name": name,
            "command": command,
            "resolved_command": resolved_command,
            "cwd": str(cwd),
            "status": "passed" if completed.returncode == 0 else "failed",
            "return_code": completed.returncode,
            "duration_s": round(time.perf_counter() - started, 2),
            "output_tail": output[-6000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "resolved_command": resolved_command,
            "cwd": str(cwd),
            "status": "failed",
            "return_code": None,
            "duration_s": round(time.perf_counter() - started, 2),
            "output_tail": f"Timed out after {timeout_s}s\n{exc.stdout or ''}",
        }
    except FileNotFoundError as exc:
        return {
            "name": name,
            "command": command,
            "resolved_command": resolved_command,
            "cwd": str(cwd),
            "status": "failed",
            "return_code": None,
            "duration_s": round(time.perf_counter() - started, 2),
            "output_tail": f"Command not found: {command[0]}\n{exc}",
        }


def _default_checks(root: Path, *, skip_frontend: bool) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = [
        {
            "name": "rag_benchmark_unit",
            "command": [sys.executable, "-m", "pytest", "platform/requirement-analysis/tests/test_rag_benchmark.py"],
            "cwd": root,
            "timeout_s": 120,
        },
        {
            "name": "parse_and_case_generation_regression",
            "command": [
                sys.executable,
                "-m",
                "pytest",
                "platform/case-generation/tests/api_dsl_generation_test.py",
                "platform/requirement-analysis/tests/test_parse_golden_regression.py",
            ],
            "cwd": root,
            "timeout_s": 240,
        },
        {
            "name": "execution_assertion_regression",
            "command": [sys.executable, "-m", "pytest", "platform/execution-engine/api-runner/tests/test_assertion_enhancement.py"],
            "cwd": root,
            "timeout_s": 180,
        },
        {
            "name": "task_center_api_regression",
            "command": [
                sys.executable,
                "-m",
                "pytest",
                "platform/task-center/tests/async_execution_api_test.py",
                "platform/task-center/tests/preflight_explanations_api_test.py",
            ],
            "cwd": root,
            "timeout_s": 240,
        },
        {
            "name": "rag_benchmark_report",
            "command": [sys.executable, "platform/requirement-analysis/scripts/run_rag_benchmark.py"],
            "cwd": root,
            "timeout_s": 180,
        },
    ]
    if not skip_frontend:
        checks.append(
            {
                "name": "frontend_build",
                "command": ["npm", "run", "build"],
                "cwd": root / "platform" / "platform-ui",
                "timeout_s": 240,
            }
        )
    return checks


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Delivery Acceptance Report",
        "",
        f"- Generated At: `{report['generated_at']}`",
        f"- Overall Status: `{summary['overall_status']}`",
        f"- Passed Checks: `{summary['passed']}`",
        f"- Failed Checks: `{summary['failed']}`",
        f"- Total Duration: `{summary['duration_s']}s`",
        "",
        "## Check Summary",
        "",
        "| Check | Status | Duration(s) |",
        "| --- | --- | ---: |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | `{item['status']}` | {item['duration_s']} |")
    lines.extend(["", "## Failure Output"])
    failures = [item for item in report["checks"] if item["status"] != "passed"]
    if not failures:
        lines.append("")
        lines.append("No failed checks.")
    for item in failures:
        lines.extend(
            [
                "",
                f"### {item['name']}",
                "",
                "```text",
                str(item.get("output_tail") or "").strip(),
                "```",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run delivery acceptance checks and export thesis-friendly evidence.")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip npm build for faster backend-only validation.")
    parser.add_argument("--output-dir", default="platform/delivery_reports", help="Directory for JSON and Markdown reports.")
    args = parser.parse_args()

    root = _repo_root()
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now().strftime("%Y%m%d_%H%M%S")
    checks = []
    started = time.perf_counter()
    for spec in _default_checks(root, skip_frontend=args.skip_frontend):
        checks.append(_run_command(spec["name"], spec["command"], cwd=spec["cwd"], timeout_s=spec["timeout_s"]))

    passed = len([item for item in checks if item["status"] == "passed"])
    failed = len(checks) - passed
    report = {
        "generated_at": generated_at,
        "summary": {
            "overall_status": "passed" if failed == 0 else "failed",
            "passed": passed,
            "failed": failed,
            "duration_s": round(time.perf_counter() - started, 2),
        },
        "checks": checks,
    }

    json_path = output_dir / f"delivery_acceptance_{generated_at}.json"
    md_path = output_dir / f"delivery_acceptance_{generated_at}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")

    print(json.dumps({"summary": report["summary"], "json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False, indent=2))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
