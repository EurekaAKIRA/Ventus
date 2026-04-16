"""Service-level API for requirement-analysis module."""

from __future__ import annotations

import time
from dataclasses import dataclass
from math import ceil
from typing import Any

from platform_shared import get_requirement_analysis_runtime_config
from platform_shared.models import ParsedRequirement, RetrievedChunk, ValidationReport

from .chunker import chunk_text
from .contract_knowledge import build_contract_chunks
from .document_loader import load_document
from .document_parser import parse_document
from .knowledge_index import build_index
from .openai_enhancement import OpenAIEnhancementConfig
from .api_requirement_parser import parse_requirement as parse_requirement_rules
from .retriever import get_retrieval_scoring_config, retrieve_relevant_chunks

_REALTIME_DOC_CHAR_LIMIT = 20_000
_BATCH_DOC_CHAR_LIMIT = 100_000


@dataclass(slots=True)
class AnalysisParseOptions:
    """Parse options from API / runtime defaults.

    ``rag_enabled`` controls **vector** retrieval only (chunk embeddings, vector
    similarity in ranking). Lexical retrieval always runs; the same retrieved
    snippets are passed to **both** rule parsing and LLM enhancement—turning RAG
    off does not strip chunks from the LLM prompt (only removes the vector path).
    """

    use_llm: bool
    rag_enabled: bool
    retrieval_top_k: int
    rerank_enabled: bool
    model_profile: str = "default"

    @classmethod
    def resolve(cls, overrides: dict[str, Any] | None = None) -> "AnalysisParseOptions":
        overrides = overrides or {}
        runtime_config = get_requirement_analysis_runtime_config()
        defaults = runtime_config.defaults
        return cls(
            use_llm=_resolve_bool(overrides.get("use_llm"), defaults.use_llm),
            rag_enabled=_resolve_bool(overrides.get("rag_enabled"), defaults.rag_enabled),
            retrieval_top_k=_resolve_int(overrides.get("retrieval_top_k"), defaults.retrieval_top_k, min_value=1, max_value=20),
            rerank_enabled=_resolve_bool(overrides.get("rerank_enabled"), defaults.rerank_enabled),
            model_profile=_resolve_profile(overrides.get("model_profile"), runtime_config.default_model_profile),
        )


def parse_requirement_bundle(
    *,
    requirement_text: str = "",
    source_path: str | None = None,
    options: AnalysisParseOptions | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    parse_options = options or AnalysisParseOptions.resolve()
    runtime_ra = get_requirement_analysis_runtime_config()
    contract_cfg = runtime_ra.contract_knowledge
    enhancement_config = (
        OpenAIEnhancementConfig.from_env(parse_options.model_profile)
        if (parse_options.use_llm or parse_options.rag_enabled)
        else None
    )

    raw_text = load_document(source_path=source_path, inline_text=requirement_text)
    input_integrity_issues = _detect_input_integrity_issues(raw_text)
    document = parse_document(raw_text)
    t_after_document = time.perf_counter()
    chunks = chunk_text(document.get("cleaned_text", ""), source_file=source_path or "")
    contract_extra = build_contract_chunks(contract_cfg)
    chunks = list(chunks) + contract_extra
    sizing_metadata = _build_document_sizing_metadata(
        raw_text=raw_text,
        cleaned_text=document.get("cleaned_text", ""),
        chunk_count=len(chunks),
    )
    t_after_chunk = time.perf_counter()
    index = build_index(
        chunks,
        enable_vector_rag=parse_options.rag_enabled,
        embedding_config=enhancement_config,
    )
    t_after_index = time.perf_counter()
    query = requirement_text.strip() or document.get("cleaned_text", "")
    retrieval_scoring = get_retrieval_scoring_config()
    retrieval_diagnostics: dict[str, Any] = {}
    boost = contract_cfg.official_score_boost if contract_cfg.enabled else 0.0
    min_score = contract_cfg.min_retrieval_score if contract_cfg.enabled else 0.0
    retrieval_items = retrieve_relevant_chunks(
        index,
        query,
        top_k=parse_options.retrieval_top_k,
        use_vector_rag=parse_options.rag_enabled,
        embedding_config=enhancement_config,
        rerank=parse_options.rerank_enabled,
        scoring_config=retrieval_scoring,
        official_doc_boost=boost,
        min_final_score=min_score,
        out_diagnostics=retrieval_diagnostics,
    )
    retrieval_items = _dedupe_chunks(retrieval_items)
    retrieved_context = [RetrievedChunk(**item) for item in retrieval_items]
    t_after_retrieval = time.perf_counter()

    fallback_reason = ""
    llm_error_type = ""
    llm_attempted = parse_options.use_llm
    parse_mode = "rules"
    parsed_payload = parse_requirement_rules(
        requirement_text=requirement_text or document.get("cleaned_text", ""),
        retrieved_context=[item.to_dict() for item in retrieved_context],
        use_llm=False,
        out_diagnostics={},
    )
    if input_integrity_issues:
        ambiguities = list(parsed_payload.get("ambiguities") or [])
        ambiguities.extend(f"原始需求疑似被截断：{issue}" for issue in input_integrity_issues)
        parsed_payload["ambiguities"] = _dedupe_strings(ambiguities)
    t_after_rules = time.perf_counter()
    pre_llm_enhancement_ms = round((t_after_rules - started) * 1000, 2)
    document_load_parse_ms = round((t_after_document - started) * 1000, 2)
    chunk_contract_ms = round((t_after_chunk - t_after_document) * 1000, 2)
    index_build_ms = round((t_after_index - t_after_chunk) * 1000, 2)
    retrieval_ms = round((t_after_retrieval - t_after_index) * 1000, 2)
    rules_parse_ms = round((t_after_rules - t_after_retrieval) * 1000, 2)
    llm_enhancement_ms = 0.0
    llm_diagnostics: dict[str, Any] = {}
    if parse_options.use_llm:
        llm_requirement = requirement_text or document.get("cleaned_text", "")
        if enhancement_config is None:
            fallback_reason = "llm_config_missing"
            llm_error_type = "configuration_error"
        else:
            llm_diagnostics = {}
            t_llm = time.perf_counter()
            try:
                try:
                    enhanced_payload = parse_requirement_rules(
                        requirement_text=llm_requirement,
                        retrieved_context=[item.to_dict() for item in retrieved_context],
                        use_llm=True,
                        llm_config=enhancement_config,
                        out_diagnostics=llm_diagnostics,
                    )
                    if llm_diagnostics.get("llm_applied"):
                        parsed_payload = enhanced_payload
                        parse_mode = "llm"
                    else:
                        fallback_reason = str(llm_diagnostics.get("fallback_reason", "") or "llm_fallback_to_rules")
                        llm_error_type = str(llm_diagnostics.get("llm_error_type", "") or "llm_unavailable")
                except Exception as exc:
                    fallback_reason = "llm_runtime_error"
                    llm_error_type = exc.__class__.__name__
            finally:
                llm_enhancement_ms = round((time.perf_counter() - t_llm) * 1000, 2)

    parsed_requirement = ParsedRequirement(**parsed_payload)
    validation_report = _build_validation_report(
        parsed_requirement,
        input_integrity_issues=input_integrity_issues,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    phase_timings_ms: dict[str, float] = {
        "pre_llm_enhancement": pre_llm_enhancement_ms,
        "llm_enhancement": llm_enhancement_ms,
        "document_load_parse_ms": document_load_parse_ms,
        "chunk_contract_ms": chunk_contract_ms,
        "index_build_ms": index_build_ms,
        "retrieval_ms": retrieval_ms,
        "rules_parse_ms": rules_parse_ms,
    }
    enh_phases = llm_diagnostics.get("enhancement_phase_timings_ms")
    if isinstance(enh_phases, dict):
        for _k, _v in enh_phases.items():
            try:
                phase_timings_ms[str(_k)] = float(_v)
            except (TypeError, ValueError):
                continue
    performance = _build_performance(
        elapsed_ms,
        parse_options.use_llm,
        parse_options.rag_enabled,
        phase_timings_ms=phase_timings_ms,
    )

    parse_metadata = {
        "parse_mode": parse_mode,
        "llm_attempted": llm_attempted,
        "llm_used": parse_mode == "llm",
        "rag_enabled": parse_options.rag_enabled,
        "rag_used": parse_options.rag_enabled,
        "rag_fallback_reason": _build_rag_fallback_reason(
            rag_enabled=parse_options.rag_enabled,
            enhancement_config=enhancement_config,
            index=index,
        ),
        "fallback_reason": fallback_reason or "",
        "llm_error_type": llm_error_type or "",
        "llm_provider_profile": "tencent_hunyuan_openai_compat",
        "model_profile": parse_options.model_profile,
        "retrieval_mode": index.get("retrieval_mode", "keyword"),
        "retrieval_top_k": parse_options.retrieval_top_k,
        "rerank_enabled": parse_options.rerank_enabled,
        "retrieval_metrics": _build_retrieval_metrics(
            retrieval_items,
            parse_options.retrieval_top_k,
            index=index,
            rerank_enabled=parse_options.rerank_enabled,
            diagnostics=retrieval_diagnostics,
        ),
        "contract_knowledge": {
            "enabled": contract_cfg.enabled,
            "merged_snippet_count": len(contract_extra),
            "official_score_boost": boost,
            "min_retrieval_score": min_score,
        },
        "retrieval_scoring": retrieval_scoring.to_dict(),
        "performance": performance,
        "input_integrity_issues": input_integrity_issues,
        "input_truncation_suspected": bool(input_integrity_issues),
        **sizing_metadata,
    }
    return {
        "raw_requirement": raw_text,
        "cleaned_text": document.get("cleaned_text", ""),
        "outline": document.get("outline", []),
        "chunks": [chunk.to_dict() if hasattr(chunk, "to_dict") else chunk for chunk in chunks],
        "retrieved_context": [item.to_dict() for item in retrieved_context],
        "parsed_requirement": parsed_requirement.to_dict(),
        "validation_report": validation_report.to_dict(),
        "parse_metadata": parse_metadata,
    }


def _build_validation_report(
    parsed_requirement: ParsedRequirement,
    *,
    input_integrity_issues: list[str] | None = None,
) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    integrity_issues = input_integrity_issues or []
    if not parsed_requirement.objective.strip():
        errors.append("缺少 objective")
    if not parsed_requirement.actions:
        errors.append("缺少 actions")
    if not parsed_requirement.expected_results:
        warnings.append("expected_results 为空，已按规则补全")
    if len(parsed_requirement.ambiguities) > 3:
        warnings.append("需求存在较多歧义，建议补充业务约束")
    if integrity_issues:
        errors.append(f"原始需求疑似被截断或未完整上传：{'；'.join(integrity_issues)}")
    return ValidationReport(
        feature_name=parsed_requirement.objective[:50] or "requirement_parse",
        passed=not errors,
        errors=errors,
        warnings=warnings,
        metrics={
            "actor_count": len(parsed_requirement.actors),
            "entity_count": len(parsed_requirement.entities),
            "action_count": len(parsed_requirement.actions),
            "expected_count": len(parsed_requirement.expected_results),
            "ambiguity_count": len(parsed_requirement.ambiguities),
            "input_integrity_issue_count": len(integrity_issues),
        },
    )


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        normalized = str(item or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _detect_input_integrity_issues(raw_text: str) -> list[str]:
    text = str(raw_text or "")
    stripped = text.rstrip()
    if not stripped:
        return []

    issues: list[str] = []
    size_aligned = len(text) >= 512 and len(text) % 1024 == 0
    unclosed_code_fence = stripped.count("```") % 2 == 1
    unbalanced_jsonish = stripped.count("{") > stripped.count("}") or stripped.count("[") > stripped.count("]")
    trailing_incomplete = bool(stripped) and stripped[-1] in {'"', "'", "{", "[", ":", ",", "-", "_"}

    if size_aligned and unclosed_code_fence:
        issues.append(f"文本长度为 {len(text)}，且 Markdown 代码块未闭合")
    if size_aligned and unbalanced_jsonish:
        issues.append(f"文本长度为 {len(text)}，且结构化片段括号未闭合")
    if size_aligned and trailing_incomplete:
        issues.append(f"文本长度为 {len(text)}，且末尾停在未完成片段")
    return _dedupe_strings(issues)


def _dedupe_chunks(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = item.get("chunk_id", "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(item)
    return deduped


def _build_retrieval_metrics(
    items: list[dict[str, Any]],
    top_k: int,
    *,
    index: dict[str, Any] | None = None,
    rerank_enabled: bool = False,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    returned = len(items)
    unique_ids = len({item.get("chunk_id", "") for item in items if item.get("chunk_id")})
    duplicate_count = max(returned - unique_ids, 0)
    scores = [float(item.get("score", 0)) for item in items]
    embedding_stats = (index or {}).get("embedding_stats", {})
    diag = diagnostics or {}
    return {
        "returned_count": returned,
        "requested_top_k": top_k,
        "coverage_ratio": round((returned / top_k), 3) if top_k else 0.0,
        "duplicate_ratio": round((duplicate_count / returned), 3) if returned else 0.0,
        "score_avg": round(sum(scores) / len(scores), 3) if scores else 0.0,
        "rerank_applied": rerank_enabled,
        "embedded_chunk_count": embedding_stats.get("embedded_chunk_count", 0),
        "embedding_coverage": embedding_stats.get("embedding_coverage", 0.0),
        "embedding_error": embedding_stats.get("embedding_error", ""),
        "embedding_error_detail": embedding_stats.get("embedding_error_detail", ""),
        "retrieval_min_final_score": float(diag.get("retrieval_min_final_score", 0.0) or 0.0),
        "retrieval_candidates_before_threshold": int(diag.get("retrieval_candidates_before_threshold", 0) or 0),
        "retrieval_low_score_rejection": bool(diag.get("retrieval_low_score_rejection", False)),
    }


def _build_performance(
    elapsed_ms: float,
    use_llm: bool,
    rag_enabled: bool,
    *,
    phase_timings_ms: dict[str, float] | None = None,
) -> dict[str, Any]:
    target_ms = 20000.0 if (use_llm and rag_enabled) else 8000.0
    reason = ""
    if elapsed_ms > target_ms:
        reason = "network_or_model_latency" if use_llm else "large_input_or_retrieval_cost"
    out: dict[str, Any] = {
        "elapsed_ms": elapsed_ms,
        "target_ms": target_ms,
        "within_target": elapsed_ms <= target_ms,
        "slow_reason": reason,
    }
    if phase_timings_ms:
        out["phase_timings_ms"] = phase_timings_ms
    return out


def _build_rag_fallback_reason(
    *,
    rag_enabled: bool,
    enhancement_config: Any,
    index: dict[str, Any],
) -> str:
    if not rag_enabled:
        return ""
    if enhancement_config is None:
        return "embedding_config_missing"
    embedding_error = str((index.get("embedding_stats") or {}).get("embedding_error", "")).strip()
    if embedding_error:
        return f"embedding_{embedding_error}"
    retrieval_mode = str(index.get("retrieval_mode", "keyword"))
    if retrieval_mode != "vector+keyword":
        return "vector_not_available"
    return ""


def _resolve_bool(override: Any, default: bool) -> bool:
    if isinstance(override, bool):
        return override
    if isinstance(override, str) and override.strip():
        return override.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _resolve_int(override: Any, default: int, *, min_value: int, max_value: int) -> int:
    value: int | None = None
    if isinstance(override, int):
        value = override
    elif isinstance(override, str) and override.strip().isdigit():
        value = int(override.strip())
    if value is None:
        value = default
    return max(min_value, min(max_value, value))


def _resolve_profile(override: Any, default: str) -> str:
    if isinstance(override, str):
        value = override.strip()
        if value:
            return value
    return default or "default"


def _build_document_sizing_metadata(
    *,
    raw_text: str,
    cleaned_text: str,
    chunk_count: int,
) -> dict[str, Any]:
    runtime_config = get_requirement_analysis_runtime_config()
    batch_size = max(1, int(runtime_config.embedding_batch_size))
    document_char_count = len(raw_text or "")
    cleaned_char_count = len(cleaned_text or "")
    estimated_embedding_calls = ceil(chunk_count / batch_size) if chunk_count else 0
    if cleaned_char_count <= _REALTIME_DOC_CHAR_LIMIT:
        processing_tier = "realtime"
        large_document_warning = ""
    elif cleaned_char_count <= _BATCH_DOC_CHAR_LIMIT:
        processing_tier = "batch"
        large_document_warning = "Document is large; parse latency may exceed interactive target"
    else:
        processing_tier = "large_document"
        large_document_warning = "Document is very large; consider splitting by sections for stable latency"
    return {
        "document_char_count": document_char_count,
        "cleaned_char_count": cleaned_char_count,
        "chunk_count": chunk_count,
        "embedding_batch_size": batch_size,
        "estimated_embedding_calls": estimated_embedding_calls,
        "processing_tier": processing_tier,
        "large_document_warning": large_document_warning,
    }
