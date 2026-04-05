"""Minimal orchestrated pipeline for platform task center."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .input_handler import normalize_input
from .artifact_manager import build_task_artifact_dir, ensure_task_subdirs, write_json_artifact, write_text_artifact
from case_generation import build_scenarios, build_test_case_dsl, generate_feature, validate_feature_text
from platform_shared.models import (
    AnalysisReport,
    DocumentChunk,
    ParsedRequirement,
    PipelineResult,
    RetrievedChunk,
    ScenarioModel,
    ScenarioStep,
    TaskContext,
    TestCaseDSL,
    ValidationReport,
)
from result_analysis import build_analysis_report
from requirement_analysis import AnalysisParseOptions, parse_requirement_bundle


def _build_scenario_model(payload: dict) -> ScenarioModel:
    """Convert a dict payload into a typed scenario model."""
    steps = [ScenarioStep(**step) for step in payload.get("steps", [])]
    return ScenarioModel(
        scenario_id=payload.get("scenario_id", "scenario_001"),
        name=payload.get("name") or "未命名场景",
        goal=payload.get("goal", ""),
        steps=steps,
        assertions=payload.get("assertions", []),
        source_chunks=payload.get("source_chunks", []),
        priority=payload.get("priority", "P1"),
        preconditions=payload.get("preconditions", []),
    )


def run_analysis_pipeline(
    task_name: str,
    requirement_text: str = "",
    source_type: str = "text",
    source_path: str | None = None,
    artifacts_base_dir: str | None = None,
    task_id: str | None = None,
    created_at: str | None = None,
    task_status: str = "received",
    artifact_dir_name: str | None = None,
    use_llm: bool | None = None,
    rag_enabled: bool | None = None,
    retrieval_top_k: int | None = None,
    rerank_enabled: bool | None = None,
    model_profile: str | None = None,
) -> dict:
    """Run the current minimal end-to-end platform pipeline."""
    parse_options = AnalysisParseOptions.resolve(
        {
            "use_llm": use_llm,
            "rag_enabled": rag_enabled,
            "retrieval_top_k": retrieval_top_k,
            "rerank_enabled": rerank_enabled,
            "model_profile": model_profile,
        }
    )
    payload = normalize_input(
        task_name=task_name,
        requirement_text=requirement_text,
        source_type=source_type,
        source_path=source_path,
        task_id=task_id,
        created_at=created_at,
        status=task_status,
    )
    task_context = TaskContext(**payload["task_context"])
    task_context = replace(task_context, rag_enabled=parse_options.rag_enabled)

    parse_bundle = parse_requirement_bundle(
        requirement_text=payload["raw_requirement"],
        source_path=source_path,
        options=parse_options,
    )
    raw_requirement = parse_bundle["raw_requirement"]
    cleaned_text = parse_bundle["cleaned_text"]
    outline = parse_bundle["outline"]
    chunks = [DocumentChunk(**item) for item in parse_bundle["chunks"]]
    retrieved_context = [RetrievedChunk(**item) for item in parse_bundle["retrieved_context"]]

    parsed_requirement = ParsedRequirement(**parse_bundle["parsed_requirement"])
    parse_validation_report = ValidationReport(**parse_bundle["validation_report"])
    scenarios = [
        _build_scenario_model(scenario)
        for scenario in build_scenarios(parsed_requirement.to_dict(), use_llm=parse_options.use_llm)
    ]
    test_case_dsl = TestCaseDSL(
        **build_test_case_dsl(
            task_context,
            scenarios,
            parsed_requirement=parsed_requirement.to_dict(),
        )
    )
    feature_text = generate_feature(task_context.task_name, [scenario.to_dict() for scenario in scenarios])
    feature_validation_report = ValidationReport(**validate_feature_text(feature_text))
    validation_report = ValidationReport(
        feature_name=feature_validation_report.feature_name,
        passed=parse_validation_report.passed and feature_validation_report.passed,
        errors=parse_validation_report.errors + feature_validation_report.errors,
        warnings=parse_validation_report.warnings + feature_validation_report.warnings,
        metrics={
            **feature_validation_report.metrics,
            "parse_metrics": parse_validation_report.metrics,
            "parse_mode": parse_bundle.get("parse_metadata", {}).get("parse_mode", "rules"),
        },
    )
    analysis_report = AnalysisReport(
        **build_analysis_report(
            task_context=task_context,
            validation_report=validation_report,
            scenario_count=len(scenarios),
            test_case_dsl=test_case_dsl.to_dict(),
        )
    )

    result = PipelineResult(
        task_context=task_context,
        raw_requirement=raw_requirement,
        cleaned_text=cleaned_text,
        outline=outline,
        chunks=chunks,
        retrieved_context=retrieved_context,
        parsed_requirement=parsed_requirement,
        scenarios=scenarios,
        test_case_dsl=test_case_dsl,
        feature_text=feature_text,
        validation_report=validation_report,
        analysis_report=analysis_report,
    )
    result.analysis_report.summary["enhancement"] = parse_bundle.get("parse_metadata", {})

    result_payload = result.to_dict()
    result_payload["parse_metadata"] = parse_bundle.get("parse_metadata", {})

    if artifacts_base_dir:
        result_payload["artifact_dir"] = persist_pipeline_artifacts(
            result_payload,
            artifacts_base_dir,
            task_dir_name=artifact_dir_name or task_context.task_id,
        )

    return result_payload


def persist_pipeline_artifacts(result: dict, artifacts_base_dir: str, task_dir_name: str | None = None) -> str:
    """Persist the standard artifacts for one analysis task."""
    task_context = result["task_context"]
    task_dir = build_task_artifact_dir(
        artifacts_base_dir,
        task_dir_name or task_context["task_name"],
        None if task_dir_name else datetime.utcnow().strftime("%Y%m%d%H%M%S"),
    )
    subdirs = ensure_task_subdirs(task_dir)

    write_text_artifact(
        str(Path(subdirs["raw"]) / "requirement.txt"),
        result["raw_requirement"],
    )
    write_json_artifact(
        str(Path(subdirs["metadata"]) / "task_context.json"),
        task_context,
    )
    write_json_artifact(
        str(Path(subdirs["parsed"]) / "cleaned_document.json"),
        {
            "cleaned_text": result["cleaned_text"],
            "outline": result["outline"],
            "chunks": result["chunks"],
        },
    )
    write_json_artifact(
        str(Path(subdirs["parsed"]) / "parsed_requirement.json"),
        result["parsed_requirement"],
    )
    write_json_artifact(
        str(Path(subdirs["parsed"]) / "parse_metadata.json"),
        result.get("parse_metadata", {}),
    )
    write_json_artifact(
        str(Path(subdirs["retrieval"]) / "retrieved_chunks.json"),
        {
            "query": result["raw_requirement"],
            "hits": result["retrieved_context"],
            "retrieval_notes": [],
        },
    )
    write_json_artifact(
        str(Path(subdirs["scenarios"]) / "scenario_bundle.json"),
        {
            "task_context": task_context,
            "raw_requirement": result["raw_requirement"],
            "parsed_requirement": result["parsed_requirement"],
            "retrieved_context": result["retrieved_context"],
            "scenarios": result["scenarios"],
            "test_case_dsl": result["test_case_dsl"],
            "validation_report": result["validation_report"],
            "analysis_report": result["analysis_report"],
            "parse_metadata": result.get("parse_metadata", {}),
        },
    )
    write_json_artifact(
        str(Path(subdirs["validation"]) / "validation_report.json"),
        result["validation_report"],
    )
    write_json_artifact(
        str(Path(subdirs["scenarios"]) / "test_case_dsl.json"),
        result["test_case_dsl"],
    )
    write_json_artifact(
        str(Path(subdirs["validation"]) / "analysis_report.json"),
        result["analysis_report"],
    )
    write_json_artifact(
        str(Path(subdirs["execution"]) / "execution_result.json"),
        {},
    )
    write_text_artifact(
        str(Path(task_dir) / "generated.feature"),
        result["feature_text"],
    )
    return task_dir
