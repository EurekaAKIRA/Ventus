"""Unified launcher for the new platform architecture."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run entrypoints from the new platform architecture")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pipeline = subparsers.add_parser("pipeline", help="Run the task-center pipeline")
    pipeline.add_argument("--task-name", required=True)
    pipeline.add_argument("--input-file")
    pipeline.add_argument("--requirement-text")
    pipeline.add_argument("--artifacts-dir")
    pipeline.add_argument("--use-llm", action="store_true")
    pipeline.add_argument("--print-json", action="store_true")

    subparsers.add_parser("smoke-test", help="Run task-center smoke tests")
    subparsers.add_parser("api-smoke-test", help="Run api-runner smoke test")
    subparsers.add_parser("api-edge-test", help="Run api-runner edge case tests")
    subparsers.add_parser("cloud-load-smoke-test", help="Run cloud-load-runner smoke test")
    subparsers.add_parser("server-smoke-test", help="Run task-center API server smoke test")
    subparsers.add_parser("serve-api", help="Run the FastAPI task-center service")
    subparsers.add_parser("execution-help", help="Show execution-engine core CLI help")
    execute = subparsers.add_parser("execute-dsl", help="Run execution-engine from a TestCaseDSL file")
    execute.add_argument("--dsl-file", required=True)
    execute.add_argument("--mode")
    execute.add_argument("--print-json", action="store_true")
    return parser


def run_subprocess(args: list[str]) -> int:
    result = subprocess.run(args, cwd=ROOT)
    return result.returncode


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "pipeline":
        command = [sys.executable, str(ROOT / "platform" / "task-center" / "run_task_center.py")]
        command += ["--task-name", args.task_name]
        if args.input_file:
            command += ["--input-file", args.input_file]
        if args.requirement_text:
            command += ["--requirement-text", args.requirement_text]
        if args.artifacts_dir:
            command += ["--artifacts-dir", args.artifacts_dir]
        if args.use_llm:
            command.append("--use-llm")
        if args.print_json:
            command.append("--print-json")
        return run_subprocess(command)

    if args.command == "smoke-test":
        command = [
            sys.executable,
            str(ROOT / "platform" / "task-center" / "tests" / "smoke_test.py"),
        ]
        return run_subprocess(command)

    if args.command == "api-smoke-test":
        command = [
            sys.executable,
            str(ROOT / "platform" / "execution-engine" / "api-runner" / "tests" / "api_runner_smoke_test.py"),
        ]
        return run_subprocess(command)

    if args.command == "api-edge-test":
        command = [
            sys.executable,
            str(ROOT / "platform" / "execution-engine" / "api-runner" / "tests" / "api_runner_edge_cases_test.py"),
        ]
        return run_subprocess(command)

    if args.command == "cloud-load-smoke-test":
        command = [
            sys.executable,
            str(
                ROOT
                / "platform"
                / "execution-engine"
                / "cloud-load-runner"
                / "tests"
                / "cloud_load_runner_smoke_test.py"
            ),
        ]
        return run_subprocess(command)

    if args.command == "server-smoke-test":
        command = [
            sys.executable,
            str(ROOT / "platform" / "task-center" / "tests" / "api_server_smoke_test.py"),
        ]
        return run_subprocess(command)

    if args.command == "serve-api":
        command = [
            sys.executable,
            str(ROOT / "platform" / "task-center" / "run_api_server.py"),
        ]
        return run_subprocess(command)

    if args.command == "execution-help":
        command = [
            sys.executable,
            str(ROOT / "platform" / "execution-engine" / "core" / "run_execution_tests.py"),
            "--help",
        ]
        return run_subprocess(command)

    if args.command == "execute-dsl":
        command = [
            sys.executable,
            str(ROOT / "platform" / "execution-engine" / "core" / "run_dsl_runtime.py"),
            "--dsl-file",
            args.dsl_file,
        ]
        if args.mode:
            command += ["--mode", args.mode]
        if args.print_json:
            command.append("--print-json")
        return run_subprocess(command)

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
