"""Minimal orchestrated pipeline for platform task center."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .input_handler import normalize_input
from .artifact_manager import build_task_artifact_dir, ensure_task_subdirs, write_json_artifact, write_text_artifact
from case_generation import build_scenarios, build_test_case_dsl, generate_feature, validate_feature_text
from platform_shared.models import (
    AnalysisReport,
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
from requirement_analysis import build_index, chunk_text, load_document, parse_document, parse_requirement, retrieve_relevant_chunks


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
    use_llm: bool = False,
) -> dict:
    """Run the current minimal end-to-end platform pipeline."""
    payload = normalize_input(
        task_name=task_name,
        requirement_text=requirement_text,
        source_type=source_type,
        source_path=source_path,
    )
    task_context = TaskContext(**payload["task_context"])

    raw_requirement = payload["raw_requirement"]
    loaded_text = load_document(source_path=source_path, inline_text=raw_requirement)
    parsed_document = parse_document(loaded_text)

    chunks = chunk_text(
        parsed_document["cleaned_text"],
        source_file=source_path or "",
    )
    index = build_index(chunks)
    query = raw_requirement or parsed_document["cleaned_text"]
    retrieved_context = [RetrievedChunk(**item) for item in retrieve_relevant_chunks(index, query)]

    parsed_requirement = ParsedRequirement(
        **parse_requirement(
            raw_requirement or parsed_document["cleaned_text"],
            [item.to_dict() for item in retrieved_context],
            use_llm=use_llm,
        )
    )
    scenarios = [
        _build_scenario_model(scenario)
        for scenario in build_scenarios(parsed_requirement.to_dict(), use_llm=use_llm)
    ]
    test_case_dsl = TestCaseDSL(
        **build_test_case_dsl(
            task_context,
            scenarios,
            parsed_requirement=parsed_requirement.to_dict(),
        )
    )
    feature_text = generate_feature(task_context.task_name, [scenario.to_dict() for scenario in scenarios])
    validation_report = ValidationReport(**validate_feature_text(feature_text))
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
        raw_requirement=raw_requirement or loaded_text,
        cleaned_text=parsed_document["cleaned_text"],
        outline=parsed_document["outline"],
        chunks=chunks,
        retrieved_context=retrieved_context,
        parsed_requirement=parsed_requirement,
        scenarios=scenarios,
        test_case_dsl=test_case_dsl,
        feature_text=feature_text,
        validation_report=validation_report,
        analysis_report=analysis_report,
    )

    if artifacts_base_dir:
        persist_pipeline_artifacts(result, artifacts_base_dir)

    return result.to_dict()


def persist_pipeline_artifacts(result: PipelineResult, artifacts_base_dir: str) -> str:
    """Persist the standard artifacts for one analysis task."""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    task_dir = build_task_artifact_dir(artifacts_base_dir, result.task_context.task_name, timestamp)
    subdirs = ensure_task_subdirs(task_dir)

    write_text_artifact(
        str(Path(subdirs["raw"]) / "requirement.txt"),
        result.raw_requirement,
    )
    write_json_artifact(
        str(Path(subdirs["metadata"]) / "task_context.json"),
        result.task_context.to_dict(),
    )
    write_json_artifact(
        str(Path(subdirs["parsed"]) / "cleaned_document.json"),
        {
            "cleaned_text": result.cleaned_text,
            "outline": result.outline,
            "chunks": [item.to_dict() for item in result.chunks],
        },
    )
    write_json_artifact(
        str(Path(subdirs["parsed"]) / "parsed_requirement.json"),
        result.parsed_requirement.to_dict(),
    )
    write_json_artifact(
        str(Path(subdirs["retrieval"]) / "retrieved_chunks.json"),
        {
            "query": result.raw_requirement,
            "hits": [item.to_dict() for item in result.retrieved_context],
            "retrieval_notes": [],
        },
    )
    write_json_artifact(
        str(Path(subdirs["scenarios"]) / "scenario_bundle.json"),
        {
            "task_context": result.task_context.to_dict(),
            "raw_requirement": result.raw_requirement,
            "parsed_requirement": result.parsed_requirement.to_dict(),
            "retrieved_context": [item.to_dict() for item in result.retrieved_context],
            "scenarios": [item.to_dict() for item in result.scenarios],
            "test_case_dsl": result.test_case_dsl.to_dict(),
            "validation_report": result.validation_report.to_dict(),
            "analysis_report": result.analysis_report.to_dict(),
        },
    )
    write_json_artifact(
        str(Path(subdirs["validation"]) / "validation_report.json"),
        result.validation_report.to_dict(),
    )
    write_json_artifact(
        str(Path(subdirs["scenarios"]) / "test_case_dsl.json"),
        result.test_case_dsl.to_dict(),
    )
    write_json_artifact(
        str(Path(subdirs["validation"]) / "analysis_report.json"),
        result.analysis_report.to_dict(),
    )
    write_json_artifact(
        str(Path(subdirs["execution"]) / "execution_result.json"),
        {},
    )
    write_text_artifact(
        str(Path(task_dir) / "generated.feature"),
        result.feature_text,
    )
    return task_dir
