from __future__ import annotations

from pathlib import Path

from requirement_analysis.rag_benchmark import (
    default_benchmark_path,
    export_rag_benchmark_reports,
    load_benchmark_cases,
    run_rag_benchmark,
)


def test_load_benchmark_cases_reads_default_dataset() -> None:
    cases = load_benchmark_cases(default_benchmark_path())
    assert cases
    case_ids = {case.case_id for case in cases}
    assert "platform_task_create" in case_ids
    assert "restful_booker_auth" in case_ids


def test_run_rag_benchmark_returns_keyword_metrics_without_embeddings(monkeypatch) -> None:
    monkeypatch.delenv("HUNYUAN_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = run_rag_benchmark()
    assert result["summary"]["case_count"] >= 1
    assert result["modes"]["keyword"]["enabled"] is True
    assert "summary" in result["modes"]["keyword"]
    assert result["modes"]["vector_keyword"]["enabled"] is False
    assert result["modes"]["vector_keyword"]["skip_reason"] == "embedding_config_missing"


def test_export_rag_benchmark_reports_writes_json_csv_and_markdown(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("HUNYUAN_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = run_rag_benchmark()

    exported = export_rag_benchmark_reports(result, output_dir=tmp_path, stem="demo_rag")

    assert Path(exported["json"]).exists()
    assert Path(exported["csv"]).exists()
    assert Path(exported["markdown"]).exists()
    assert "RAG Benchmark Report" in Path(exported["markdown"]).read_text(encoding="utf-8")
