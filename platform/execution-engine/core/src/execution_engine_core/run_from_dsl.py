"""Run execution-engine directly from a TestCaseDSL file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from execution_engine_core.dsl_runtime import run_dsl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run execution-engine from TestCaseDSL")
    parser.add_argument("--dsl-file", required=True, help="Path to test_case_dsl.json")
    parser.add_argument("--mode", help="Override execution mode")
    parser.add_argument("--print-json", action="store_true", help="Print full execution result JSON")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    payload = json.loads(Path(args.dsl_file).read_text(encoding="utf-8"))
    result = run_dsl(payload, execution_mode=args.mode)

    if args.print_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"task_id = {result['task_id']}")
        print(f"executor = {result['executor']}")
        print(f"status = {result['status']}")
        print(f"scenario_count = {len(result['scenario_results'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
