"""CLI entry point for analysis-module."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_analysis_pipeline


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for standalone execution."""
    parser = argparse.ArgumentParser(description="运行 analysis-module 需求分析流水线")
    parser.add_argument("--task-name", required=True, help="任务名称")
    parser.add_argument("--input-file", help="需求文档路径，支持 txt/md")
    parser.add_argument("--requirement-text", help="内联需求文本")
    parser.add_argument(
        "--artifacts-dir",
        default=str(Path(__file__).resolve().parents[1] / "artifacts"),
        help="产物输出目录",
    )
    parser.add_argument("--use-llm", action="store_true", help="启用 LLM 增强模式占位开关")
    parser.add_argument("--print-json", action="store_true", help="在控制台输出完整 JSON 结果")
    return parser


def main() -> int:
    """Run the pipeline from CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.input_file and not args.requirement_text:
        parser.error("必须提供 --input-file 或 --requirement-text 之一")

    result = run_analysis_pipeline(
        task_name=args.task_name,
        requirement_text=args.requirement_text or "",
        source_type="file" if args.input_file else "text",
        source_path=args.input_file,
        artifacts_base_dir=args.artifacts_dir,
        use_llm=args.use_llm,
    )

    if args.print_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"task_name = {result['task_context']['task_name']}")
        print(f"scenario_count = {len(result['scenarios'])}")
        print(f"validation_passed = {result['validation_report']['passed']}")
        print(f"feature_name = {result['validation_report']['feature_name']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
