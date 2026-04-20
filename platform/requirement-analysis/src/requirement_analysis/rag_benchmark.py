"""Benchmark runner for retrieval-oriented RAG evaluation."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .knowledge_library import load_curated_knowledge_chunks
from .openai_enhancement import OpenAIEnhancementConfig
from .rag_evaluator import RagEvalCase, evaluate_retrieval_cases


@dataclass(frozen=True, slots=True)
class RagBenchmarkCase:
    case_id: str
    title: str
    raw_text: str
    cleaned_text: str
    query: str
    expected_source_files: list[str]
    top_k: int = 5


def default_benchmark_path() -> Path:
    return Path(__file__).resolve().parents[2] / "benchmarks" / "rag_benchmark_cases.json"


def load_benchmark_cases(path: str | Path | None = None) -> list[RagBenchmarkCase]:
    target = Path(path) if path is not None else default_benchmark_path()
    payload = json.loads(target.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        return []
    out: list[RagBenchmarkCase] = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id", "")).strip()
        title = str(item.get("title", "")).strip()
        raw_text = str(item.get("raw_text", ""))
        cleaned_text = str(item.get("cleaned_text", raw_text))
        query = str(item.get("query", "")).strip()
        expected_source_files = [str(value).strip() for value in (item.get("expected_source_files") or []) if str(value).strip()]
        top_k = int(item.get("top_k", 5) or 5)
        if not case_id or not title or not query or not expected_source_files:
            continue
        out.append(
            RagBenchmarkCase(
                case_id=case_id,
                title=title,
                raw_text=raw_text,
                cleaned_text=cleaned_text,
                query=query,
                expected_source_files=expected_source_files,
                top_k=max(1, min(top_k, 20)),
            )
        )
    return out


def run_rag_benchmark(
    *,
    cases: list[RagBenchmarkCase] | None = None,
    model_profile: str = "default",
) -> dict[str, Any]:
    benchmark_cases = cases or load_benchmark_cases()
    if not benchmark_cases:
        return {"summary": {"case_count": 0}, "modes": {}}

    embedding_config = OpenAIEnhancementConfig.from_env(model_profile)
    modes: list[tuple[str, dict[str, Any]]] = [
        ("keyword", {"use_vector_rag": False, "rerank": False, "embedding_config": None, "enabled": True}),
        (
            "vector_keyword",
            {
                "use_vector_rag": True,
                "rerank": False,
                "embedding_config": embedding_config,
                "enabled": embedding_config is not None,
                "skip_reason": "embedding_config_missing" if embedding_config is None else "",
            },
        ),
        (
            "vector_keyword_rerank",
            {
                "use_vector_rag": True,
                "rerank": True,
                "embedding_config": embedding_config,
                "enabled": embedding_config is not None,
                "skip_reason": "embedding_config_missing" if embedding_config is None else "",
            },
        ),
    ]

    mode_results: dict[str, Any] = {}
    for mode_name, config in modes:
        if not config["enabled"]:
            mode_results[mode_name] = {
                "enabled": False,
                "skip_reason": config.get("skip_reason", "disabled"),
                "summary": {"case_count": len(benchmark_cases), "hit_count": 0, "recall_at_k": 0.0, "mrr": 0.0},
                "cases": [],
            }
            continue

        eval_cases = [_to_eval_case(case, use_vector_rag=config["use_vector_rag"], rerank=config["rerank"]) for case in benchmark_cases]
        evaluated = evaluate_retrieval_cases(eval_cases, embedding_config=config["embedding_config"])
        mode_results[mode_name] = {"enabled": True, **evaluated}

    return {
        "summary": {"case_count": len(benchmark_cases)},
        "modes": mode_results,
    }


def export_rag_benchmark_reports(
    result: dict[str, Any],
    *,
    output_dir: str | Path,
    stem: str = "rag_benchmark",
) -> dict[str, str]:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    json_path = target_dir / f"{stem}.json"
    csv_path = target_dir / f"{stem}_summary.csv"
    markdown_path = target_dir / f"{stem}.md"

    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary_csv(csv_path, result)
    markdown_path.write_text(_render_markdown_report(result), encoding="utf-8")

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "markdown": str(markdown_path),
    }


def _to_eval_case(case: RagBenchmarkCase, *, use_vector_rag: bool, rerank: bool) -> RagEvalCase:
    chunks = [chunk.to_dict() for chunk in load_curated_knowledge_chunks(raw_text=case.raw_text, cleaned_text=case.cleaned_text)]
    expected_chunk_ids = [
        str(chunk["chunk_id"])
        for chunk in chunks
        if str(chunk.get("source_file", "")) in set(case.expected_source_files)
    ]
    return RagEvalCase(
        case_id=case.case_id,
        query=case.query,
        chunks=chunks,
        expected_chunk_ids=expected_chunk_ids,
        use_vector_rag=use_vector_rag,
        top_k=case.top_k,
        rerank=rerank,
    )


def _write_summary_csv(path: Path, result: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["mode", "enabled", "case_count", "hit_count", "recall_at_k", "mrr", "skip_reason"],
        )
        writer.writeheader()
        for mode_name, mode_payload in (result.get("modes") or {}).items():
            summary = mode_payload.get("summary") or {}
            writer.writerow(
                {
                    "mode": mode_name,
                    "enabled": bool(mode_payload.get("enabled", False)),
                    "case_count": summary.get("case_count", 0),
                    "hit_count": summary.get("hit_count", 0),
                    "recall_at_k": summary.get("recall_at_k", 0.0),
                    "mrr": summary.get("mrr", 0.0),
                    "skip_reason": mode_payload.get("skip_reason", ""),
                }
            )


def _render_markdown_report(result: dict[str, Any]) -> str:
    lines: list[str] = []
    case_count = int((result.get("summary") or {}).get("case_count", 0) or 0)
    lines.append("# RAG Benchmark Report")
    lines.append("")
    lines.append(f"- Case Count: `{case_count}`")
    lines.append("")
    lines.append("## Mode Summary")
    lines.append("")
    lines.append("| Mode | Enabled | Recall@K | MRR | Hit Count | Skip Reason |")
    lines.append("| --- | --- | ---: | ---: | ---: | --- |")
    for mode_name, mode_payload in (result.get("modes") or {}).items():
        summary = mode_payload.get("summary") or {}
        lines.append(
            f"| `{mode_name}` | `{bool(mode_payload.get('enabled', False))}` | "
            f"{summary.get('recall_at_k', 0.0)} | {summary.get('mrr', 0.0)} | "
            f"{summary.get('hit_count', 0)} / {summary.get('case_count', 0)} | "
            f"{mode_payload.get('skip_reason', '')} |"
        )
    lines.append("")
    lines.append("## Case Details")
    lines.append("")
    for mode_name, mode_payload in (result.get("modes") or {}).items():
        lines.append(f"### {mode_name}")
        lines.append("")
        if not mode_payload.get("enabled", False):
            lines.append(f"- Skipped: `{mode_payload.get('skip_reason', 'disabled')}`")
            lines.append("")
            continue
        lines.append("| Case ID | Hit | Rank | Retrieval Mode | Matched Source Files |")
        lines.append("| --- | --- | ---: | --- | --- |")
        for item in mode_payload.get("cases") or []:
            matched_sources = ", ".join(item.get("matched_source_files") or [])
            lines.append(
                f"| `{item.get('case_id', '')}` | `{item.get('hit', False)}` | "
                f"{item.get('hit_rank', '-') if item.get('hit_rank') is not None else '-'} | "
                f"`{item.get('retrieval_mode', '')}` | {matched_sources} |"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"
