"""Print parse -> scenarios -> DSL for docs/platform_e2e_requirement.md.

Examples:
  python debug_e2e_requirement_dsl.py
  python debug_e2e_requirement_dsl.py --llm --rag
Requires HUNYUAN_API_KEY or OPENAI_API_KEY (and reachable base URL) when using --llm or --rag.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (
    _ROOT / "shared" / "src",
    _ROOT / "requirement-analysis" / "src",
    _ROOT / "case-generation" / "src",
):
    sys.path.insert(0, str(_p))

from case_generation import build_scenarios, build_test_case_dsl  # noqa: E402
from platform_shared.models import ScenarioModel, TaskContext  # noqa: E402
from requirement_analysis.service import AnalysisParseOptions, parse_requirement_bundle  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E doc -> parse -> scenarios -> DSL")
    parser.add_argument("--llm", action="store_true", help="Enable LLM parse enhancement")
    parser.add_argument("--rag", action="store_true", help="Enable vector RAG (embeddings + retrieval)")
    parser.add_argument("--top-k", type=int, default=5, help="Retrieval top_k (default 5)")
    parser.add_argument("--rerank", action="store_true", help="Enable rerank (if configured)")
    parser.add_argument("--summary-only", action="store_true", help="Print metadata + scenario names only, not full DSL")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write full UTF-8 output (summary + dsl) to this file instead of only stdout",
    )
    args = parser.parse_args()

    repo = _ROOT.parent
    text = (repo / "docs" / "platform_e2e_requirement.md").read_text(encoding="utf-8")
    bundle = parse_requirement_bundle(
        requirement_text=text,
        options=AnalysisParseOptions(
            use_llm=args.llm,
            rag_enabled=args.rag,
            retrieval_top_k=args.top_k,
            rerank_enabled=args.rerank,
        ),
    )
    meta = bundle.get("parse_metadata") or {}
    parsed = bundle["parsed_requirement"]
    scenarios_raw = build_scenarios(parsed, use_llm=args.llm)
    scenarios = [ScenarioModel(**item) for item in scenarios_raw]
    dsl = build_test_case_dsl(
        TaskContext(task_id="e2e_manual", task_name="platform_e2e", source_type="text"),
        scenarios,
        parsed_requirement=parsed,
        enable_assertion_enhancement=args.llm,
    )

    summary = {
        "options": {"use_llm": args.llm, "rag_enabled": args.rag, "top_k": args.top_k},
        "parse_metadata": {
            "parse_mode": meta.get("parse_mode"),
            "llm_attempted": meta.get("llm_attempted"),
            "llm_used": meta.get("llm_used"),
            "rag_used": meta.get("rag_used"),
            "fallback_reason": meta.get("fallback_reason"),
            "llm_error_type": meta.get("llm_error_type"),
        },
        "api_endpoints_count": len(parsed.get("api_endpoints") or []),
        "actions_count": len(parsed.get("actions") or []),
        "scenario_count": len(scenarios),
        "scenario_names": [s.name for s in scenarios],
    }
    lines = [
        json.dumps(summary, ensure_ascii=False, indent=2),
    ]
    if not args.summary_only:
        lines.append("--- dsl ---")
        lines.append(json.dumps({"dsl_version": dsl.get("dsl_version"), "scenarios": dsl.get("scenarios")}, ensure_ascii=False, indent=2))
    text = "\n".join(lines) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
