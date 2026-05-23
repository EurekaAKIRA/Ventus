"""Run end-to-end RAG ablation on recent API requirement artifacts.

The experiment compares the deterministic generation pipeline with vector RAG
disabled/enabled. Lexical retrieval and curated rules may still apply; this
script therefore reports the comparison as "vector RAG off/on" instead of a
full "no knowledge" baseline.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_ROOT = Path(__file__).resolve().parents[2]
for _p in (
    _ROOT / "shared" / "src",
    _ROOT / "requirement-analysis" / "src",
    _ROOT / "case-generation" / "src",
):
    sys.path.insert(0, str(_p))

from case_generation import build_scenarios, build_test_case_dsl  # noqa: E402
from platform_shared.models import ScenarioModel, TaskContext  # noqa: E402
import requirement_analysis.service as service_module  # noqa: E402
from requirement_analysis.service import AnalysisParseOptions, parse_requirement_bundle  # noqa: E402


_METHODS_REQUIRING_LIVE_RESOURCE = {"PUT", "PATCH", "DELETE"}
_ID_SEGMENT_RE = re.compile(r"/(?:\d+|[0-9a-fA-F-]{8,})(?=/|$)")
_PLACEHOLDER_RE = re.compile(r"\{\{?\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}?\}")


@dataclass(slots=True)
class GenerationMetrics:
    task_id: str
    task_name: str
    mode: str
    use_llm: bool
    rag_enabled: bool
    knowledge_disabled: bool
    rag_used: bool
    parse_mode: str
    llm_used: bool
    fallback_reason: str
    llm_error_type: str
    api_endpoint_count: int
    scenario_count: int
    step_count: int
    request_step_count: int
    unique_request_endpoint_count: int
    endpoint_coverage_ratio: float
    assertion_count: int
    context_save_count: int
    context_use_count: int
    undefined_context_count: int
    naked_live_resource_step_count: int
    knowledge_applied: bool
    retrieved_count: int
    retrieval_mode: str
    elapsed_ms: float
    error: str = ""


@dataclass(frozen=True, slots=True)
class RequirementSample:
    sample_id: str
    task_name: str
    requirement_text: str
    source_path: str


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _discover_artifacts(artifact_root: Path, recent: int) -> list[Path]:
    candidates: list[Path] = []
    for item in artifact_root.iterdir() if artifact_root.exists() else []:
        if not item.is_dir():
            continue
        if not (item / "raw" / "requirement.txt").exists():
            continue
        candidates.append(item)
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[:recent]


def _discover_document_samples(doc_root: Path, recent: int) -> list[RequirementSample]:
    if not doc_root.exists():
        return []
    files = [path for path in doc_root.rglob("*") if path.is_file() and path.suffix.lower() in {".md", ".txt"}]
    files.sort(key=lambda p: p.name.lower())
    if recent > 0:
        files = files[:recent]
    samples: list[RequirementSample] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        sample_id = path.stem
        samples.append(
            RequirementSample(
                sample_id=sample_id,
                task_name=sample_id.replace("_", " "),
                requirement_text=text,
                source_path=str(path),
            )
        )
    return samples


def _artifact_to_sample(artifact_dir: Path) -> RequirementSample:
    return RequirementSample(
        sample_id=artifact_dir.name,
        task_name=_task_name_for(artifact_dir),
        requirement_text=(artifact_dir / "raw" / "requirement.txt").read_text(encoding="utf-8"),
        source_path=str(artifact_dir / "raw" / "requirement.txt"),
    )


def _task_name_for(artifact_dir: Path) -> str:
    context = _read_json(artifact_dir / "metadata" / "task_context.json")
    name = str(context.get("task_name") or "").strip()
    if name:
        return name
    return artifact_dir.name.rsplit("_2026", 1)[0] or artifact_dir.name


def _normalize_endpoint(method: str, url: str) -> str:
    method = str(method or "").upper().strip()
    raw_url = str(url or "").strip()
    if not raw_url:
        return ""
    parsed = urlparse(raw_url)
    path = parsed.path if parsed.scheme and parsed.netloc else raw_url.split("?", 1)[0]
    path = _PLACEHOLDER_RE.sub("{id}", path)
    path = _ID_SEGMENT_RE.sub("/{id}", path)
    path = re.sub(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", "{id}", path)
    return f"{method} {path}".strip()


def _walk_values(value: Any) -> list[Any]:
    if isinstance(value, dict):
        values: list[Any] = []
        for child in value.values():
            values.extend(_walk_values(child))
        return values
    if isinstance(value, list):
        values = []
        for child in value:
            values.extend(_walk_values(child))
        return values
    return [value]


def _context_refs_from_request(request: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for value in _walk_values(request):
        if isinstance(value, str):
            refs.update(match.group(1) for match in _PLACEHOLDER_RE.finditer(value))
    return refs


def _endpoint_set_from_parsed(parsed: dict[str, Any]) -> set[str]:
    endpoints: set[str] = set()
    for endpoint in parsed.get("api_endpoints") or []:
        if not isinstance(endpoint, dict):
            continue
        key = _normalize_endpoint(str(endpoint.get("method", "")), str(endpoint.get("path", "")))
        if key:
            endpoints.add(key)
    return endpoints


def _has_live_resource_source(scenario: dict[str, Any]) -> bool:
    text = json.dumps(scenario, ensure_ascii=False).lower()
    if any(token in text for token in ("预置", "preset", "fixture", "seed", "mock", "模拟")):
        return True
    steps = scenario.get("steps") or []
    has_create = False
    has_saved_id = False
    for step in steps:
        if not isinstance(step, dict):
            continue
        request = step.get("request") if isinstance(step.get("request"), dict) else {}
        method = str(request.get("method") or "").upper()
        url = str(request.get("url") or "")
        if method == "POST" and not any(word in url.lower() for word in ("/login", "/auth", "/refresh")):
            has_create = True
        save_context = step.get("save_context") if isinstance(step.get("save_context"), dict) else {}
        saves_context = step.get("saves_context") if isinstance(step.get("saves_context"), list) else []
        saved_keys = {str(item).lower() for item in list(save_context.keys()) + saves_context}
        if any(key.endswith("_id") or key == "id" or key.endswith("id") for key in saved_keys):
            has_saved_id = True
    return has_create or has_saved_id


def _measure_dsl(
    *,
    task_id: str,
    task_name: str,
    mode: str,
    use_llm: bool,
    rag_enabled: bool,
    knowledge_disabled: bool,
    bundle: dict[str, Any],
    scenarios: list[ScenarioModel],
    dsl: dict[str, Any],
    elapsed_ms: float,
) -> GenerationMetrics:
    parsed = bundle.get("parsed_requirement") or {}
    meta = bundle.get("parse_metadata") or {}
    parsed_endpoint_set = _endpoint_set_from_parsed(parsed)
    request_endpoint_set: set[str] = set()
    step_count = 0
    request_step_count = 0
    assertion_count = 0
    saved_context: set[str] = set()
    used_context: set[str] = set()
    naked_live_resource_step_count = 0

    for scenario in dsl.get("scenarios") or []:
        if not isinstance(scenario, dict):
            continue
        scenario_has_source = _has_live_resource_source(scenario)
        for step in scenario.get("steps") or []:
            if not isinstance(step, dict):
                continue
            step_count += 1
            assertions = step.get("assertions") or []
            assertion_count += len(assertions) if isinstance(assertions, list) else 0
            save_context = step.get("save_context") if isinstance(step.get("save_context"), dict) else {}
            saves_context = step.get("saves_context") if isinstance(step.get("saves_context"), list) else []
            saved_context.update(str(item) for item in save_context.keys())
            saved_context.update(str(item) for item in saves_context)
            uses_context = step.get("uses_context") if isinstance(step.get("uses_context"), list) else []
            used_context.update(str(item) for item in uses_context)
            request = step.get("request") if isinstance(step.get("request"), dict) else {}
            used_context.update(_context_refs_from_request(request))
            method = str(request.get("method") or "").upper().strip()
            url = str(request.get("url") or "").strip()
            if method and url:
                request_step_count += 1
                key = _normalize_endpoint(method, url)
                if key:
                    request_endpoint_set.add(key)
                if method in _METHODS_REQUIRING_LIVE_RESOURCE and not scenario_has_source:
                    naked_live_resource_step_count += 1

    coverage = 0.0
    if parsed_endpoint_set:
        coverage = len(parsed_endpoint_set & request_endpoint_set) / len(parsed_endpoint_set)
    retrieval_metrics = meta.get("retrieval_metrics") if isinstance(meta.get("retrieval_metrics"), dict) else {}
    knowledge = meta.get("knowledge_base") if isinstance(meta.get("knowledge_base"), dict) else {}
    return GenerationMetrics(
        task_id=task_id,
        task_name=task_name,
        mode=mode,
        use_llm=use_llm,
        rag_enabled=rag_enabled,
        knowledge_disabled=knowledge_disabled,
        rag_used=bool(meta.get("rag_used", False)),
        parse_mode=str(meta.get("parse_mode", "")),
        llm_used=bool(meta.get("llm_used", False)),
        fallback_reason=str(meta.get("fallback_reason", "")),
        llm_error_type=str(meta.get("llm_error_type", "")),
        api_endpoint_count=len(parsed_endpoint_set),
        scenario_count=len(scenarios),
        step_count=step_count,
        request_step_count=request_step_count,
        unique_request_endpoint_count=len(request_endpoint_set),
        endpoint_coverage_ratio=round(coverage, 4),
        assertion_count=assertion_count,
        context_save_count=len(saved_context),
        context_use_count=len(used_context),
        undefined_context_count=len(used_context - saved_context),
        naked_live_resource_step_count=naked_live_resource_step_count,
        knowledge_applied=bool(knowledge.get("applied", False)),
        retrieved_count=int(retrieval_metrics.get("returned_count") or 0),
        retrieval_mode=str(meta.get("retrieval_mode", "")),
        elapsed_ms=round(elapsed_ms, 2),
    )


def _run_one(
    *,
    sample: RequirementSample,
    use_llm: bool,
    rag_enabled: bool,
    mode: str,
    knowledge_disabled: bool,
    retrieval_top_k: int,
    rerank_enabled: bool,
) -> GenerationMetrics:
    task_id = sample.sample_id
    task_name = sample.task_name
    requirement_text = sample.requirement_text
    started = time.perf_counter()
    original_curated_loader = service_module.load_curated_knowledge_chunks
    original_contract_builder = service_module.build_contract_chunks
    try:
        if knowledge_disabled:
            service_module.load_curated_knowledge_chunks = lambda **_: []
            service_module.build_contract_chunks = lambda *_args, **_kwargs: []
        bundle = parse_requirement_bundle(
            requirement_text=requirement_text,
            options=AnalysisParseOptions(
                use_llm=use_llm,
                rag_enabled=rag_enabled,
                retrieval_top_k=retrieval_top_k,
                rerank_enabled=rerank_enabled,
            ),
        )
        parsed = bundle.get("parsed_requirement") or {}
        scenarios_raw = build_scenarios(parsed, use_llm=use_llm)
        scenarios = [ScenarioModel(**item) for item in scenarios_raw]
        dsl = build_test_case_dsl(
            TaskContext(
                task_id=f"{task_id}_{mode}",
                task_name=task_name,
                source_type="rag_e2e_ablation",
                rag_enabled=rag_enabled,
            ),
            scenarios,
            parsed_requirement=parsed,
            enable_assertion_enhancement=use_llm,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        return _measure_dsl(
            task_id=task_id,
            task_name=task_name,
            mode=mode,
            use_llm=use_llm,
            rag_enabled=rag_enabled,
            knowledge_disabled=knowledge_disabled,
            bundle=bundle,
            scenarios=scenarios,
            dsl=dsl,
            elapsed_ms=elapsed_ms,
        )
    except Exception as exc:  # pragma: no cover - diagnostic script
        elapsed_ms = (time.perf_counter() - started) * 1000
        return GenerationMetrics(
            task_id=task_id,
            task_name=task_name,
            mode=mode,
            use_llm=use_llm,
            rag_enabled=rag_enabled,
            knowledge_disabled=knowledge_disabled,
            rag_used=False,
            parse_mode="",
            llm_used=False,
            fallback_reason="script_exception",
            llm_error_type=type(exc).__name__,
            api_endpoint_count=0,
            scenario_count=0,
            step_count=0,
            request_step_count=0,
            unique_request_endpoint_count=0,
            endpoint_coverage_ratio=0.0,
            assertion_count=0,
            context_save_count=0,
            context_use_count=0,
            undefined_context_count=0,
            naked_live_resource_step_count=0,
            knowledge_applied=False,
            retrieved_count=0,
            retrieval_mode="",
            elapsed_ms=round(elapsed_ms, 2),
            error=str(exc),
        )
    finally:
        service_module.load_curated_knowledge_chunks = original_curated_loader
        service_module.build_contract_chunks = original_contract_builder


def _aggregate(rows: list[GenerationMetrics]) -> dict[str, Any]:
    by_mode: dict[str, list[GenerationMetrics]] = {}
    for row in rows:
        by_mode.setdefault(row.mode, []).append(row)
    summary: dict[str, Any] = {}
    for mode, items in by_mode.items():
        valid = [item for item in items if not item.error]
        denominator = len(valid) or 1
        summary[mode] = {
            "sample_count": len(items),
            "valid_count": len(valid),
            "mean_endpoint_coverage_ratio": round(sum(i.endpoint_coverage_ratio for i in valid) / denominator, 4),
            "mean_scenario_count": round(sum(i.scenario_count for i in valid) / denominator, 2),
            "mean_assertion_count": round(sum(i.assertion_count for i in valid) / denominator, 2),
            "mean_context_links": round(sum(i.context_save_count + i.context_use_count for i in valid) / denominator, 2),
            "total_naked_live_resource_steps": sum(i.naked_live_resource_step_count for i in valid),
            "mean_elapsed_ms": round(sum(i.elapsed_ms for i in valid) / denominator, 2),
            "rag_used_count": sum(1 for i in valid if i.rag_used),
            "knowledge_applied_count": sum(1 for i in valid if i.knowledge_applied),
            "error_count": len(items) - len(valid),
        }
    delta_pairs = (
        ("knowledge_off", "knowledge_on_keyword", "delta_keyword_knowledge_minus_off"),
        ("knowledge_on_keyword", "knowledge_on_vector", "delta_vector_minus_keyword"),
        ("vector_rag_off", "vector_rag_on", "delta_on_minus_off"),
    )
    for off_key, on_key, delta_key in delta_pairs:
        if off_key not in summary or on_key not in summary:
            continue
        off = summary[off_key]
        on = summary[on_key]
        summary[delta_key] = {
            "mean_endpoint_coverage_ratio": round(
                on["mean_endpoint_coverage_ratio"] - off["mean_endpoint_coverage_ratio"], 4
            ),
            "mean_scenario_count": round(on["mean_scenario_count"] - off["mean_scenario_count"], 2),
            "mean_assertion_count": round(on["mean_assertion_count"] - off["mean_assertion_count"], 2),
            "mean_context_links": round(on["mean_context_links"] - off["mean_context_links"], 2),
            "total_naked_live_resource_steps": on["total_naked_live_resource_steps"] - off["total_naked_live_resource_steps"],
            "mean_elapsed_ms": round(on["mean_elapsed_ms"] - off["mean_elapsed_ms"], 2),
        }
    return summary


def _write_csv(path: Path, rows: list[GenerationMetrics]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    rows = [GenerationMetrics(**row) for row in payload["rows"]]
    summary = payload["summary"]
    lines = [
        "# RAG 端到端消融实验报告",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 样本数：{payload['sample_count']}",
        f"- LLM 增强：{'开启' if payload['use_llm'] else '关闭'}",
        f"- 对比口径：{payload['comparison_scope']}",
        "",
        "## 汇总",
        "",
        "| 模式 | 有效样本 | 接口覆盖率 | 平均场景数 | 平均断言数 | 平均上下文链路 | 裸跑活资源步骤 | 平均耗时(ms) | RAG 实际命中 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode in payload["modes"]:
        data = summary.get(mode) or {}
        lines.append(
            "| {mode} | {valid_count} | {coverage:.2%} | {scenario:.2f} | {assertions:.2f} | {context:.2f} | {naked} | {elapsed:.2f} | {rag_used} |".format(
                mode=mode,
                valid_count=data.get("valid_count", 0),
                coverage=float(data.get("mean_endpoint_coverage_ratio", 0.0)),
                scenario=float(data.get("mean_scenario_count", 0.0)),
                assertions=float(data.get("mean_assertion_count", 0.0)),
                context=float(data.get("mean_context_links", 0.0)),
                naked=data.get("total_naked_live_resource_steps", 0),
                elapsed=float(data.get("mean_elapsed_ms", 0.0)),
                rag_used=data.get("rag_used_count", 0),
            )
        )
    lines.extend(["", "## 差值", ""])
    for key, title in (
        ("delta_keyword_knowledge_minus_off", "知识增强 - 无知识增强"),
        ("delta_vector_minus_keyword", "向量 RAG - 词法知识"),
        ("delta_on_minus_off", "vector RAG on - off"),
    ):
        delta = summary.get(key)
        if not delta:
            continue
        lines.extend(
            [
                f"### {title}",
                "",
                f"- 接口覆盖率变化：{float(delta.get('mean_endpoint_coverage_ratio', 0.0)):.2%}",
                f"- 平均场景数变化：{float(delta.get('mean_scenario_count', 0.0)):.2f}",
                f"- 平均断言数变化：{float(delta.get('mean_assertion_count', 0.0)):.2f}",
                f"- 平均上下文链路变化：{float(delta.get('mean_context_links', 0.0)):.2f}",
                f"- 裸跑活资源步骤变化：{delta.get('total_naked_live_resource_steps', 0)}",
                f"- 平均耗时变化：{float(delta.get('mean_elapsed_ms', 0.0)):.2f} ms",
                "",
            ]
        )
    lines.extend(
        [
            "## 明细",
            "",
            "| 任务 | 模式 | 解析模式 | RAG used | 知识关闭 | 接口数 | 场景数 | 请求步骤 | 覆盖率 | 断言数 | 上下文保存/使用 | 未定义上下文 | 裸跑活资源 | 耗时(ms) | 异常 |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| {task} | {mode} | {parse_mode} | {rag_used} | {knowledge_disabled} | {api_count} | {scenario_count} | {request_steps} | {coverage:.2%} | {assertions} | {context} | {undefined} | {naked} | {elapsed:.2f} | {error} |".format(
                task=row.task_name,
                mode=row.mode,
                parse_mode=row.parse_mode or "-",
                rag_used="是" if row.rag_used else "否",
                knowledge_disabled="是" if row.knowledge_disabled else "否",
                api_count=row.api_endpoint_count,
                scenario_count=row.scenario_count,
                request_steps=row.request_step_count,
                coverage=row.endpoint_coverage_ratio,
                assertions=row.assertion_count,
                context=row.context_save_count + row.context_use_count,
                undefined=row.undefined_context_count,
                naked=row.naked_live_resource_step_count,
                elapsed=row.elapsed_ms,
                error=row.error.replace("|", "/") if row.error else "",
            )
        )
    lines.extend(
        [
            "",
            "## 论文使用建议",
            "",
            "- 该结果适合证明知识检索链路与用例生成链路已经打通，并能量化 RAG 开关对生成质量指标的影响。",
            "- 如果 off/on 差异较小，通常说明当前文档结构已经足够规范，规则解析和词法知识检索已经覆盖主链路；论文中应写为“规范化输入下 RAG 主要提供稳健性补强”。",
            "- 若需要证明 RAG 对弱规范文档的提升，应补充一组省略资源来源、上下文和接口依赖的弱文档样本再跑同一脚本。",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run vector RAG off/on generation ablation.")
    parser.add_argument("--recent", type=int, default=6, help="Number of recent task artifacts to sample.")
    parser.add_argument("--use-llm", action="store_true", help="Enable LLM enhancement during the experiment.")
    parser.add_argument("--top-k", type=int, default=5, help="Retrieval top_k.")
    parser.add_argument("--rerank", action="store_true", help="Enable rerank if configured.")
    parser.add_argument(
        "--include-knowledge-baseline",
        action="store_true",
        help="Also compare knowledge_off, knowledge_on_keyword and knowledge_on_vector.",
    )
    parser.add_argument("--artifact-root", type=Path, default=_ROOT / "task-center" / "api_artifacts")
    parser.add_argument(
        "--doc-root",
        type=Path,
        default=None,
        help="Optional directory of .md/.txt requirement samples. When set, samples are read from this directory instead of task artifacts.",
    )
    parser.add_argument("--output-dir", type=Path, default=_ROOT / "delivery_reports")
    args = parser.parse_args()

    if args.doc_root is not None:
        samples = _discover_document_samples(args.doc_root, args.recent)
        sample_source = str(args.doc_root)
    else:
        samples = [_artifact_to_sample(path) for path in _discover_artifacts(args.artifact_root, args.recent)]
        sample_source = str(args.artifact_root)
    rows: list[GenerationMetrics] = []
    if args.include_knowledge_baseline:
        mode_plan = (
            ("knowledge_off", False, True),
            ("knowledge_on_keyword", False, False),
            ("knowledge_on_vector", True, False),
        )
        comparison_scope = "knowledge_off / knowledge_on_keyword / knowledge_on_vector"
    else:
        mode_plan = (
            ("vector_rag_off", False, False),
            ("vector_rag_on", True, False),
        )
        comparison_scope = "vector RAG off/on（词法检索与规则/知识库仍按系统默认参与）"
    for sample in samples:
        for mode, rag_enabled, knowledge_disabled in mode_plan:
            rows.append(
                _run_one(
                    sample=sample,
                    use_llm=args.use_llm,
                    rag_enabled=rag_enabled,
                    mode=mode,
                    knowledge_disabled=knowledge_disabled,
                    retrieval_top_k=args.top_k,
                    rerank_enabled=args.rerank,
                )
            )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sample_count": len(samples),
        "sample_source": sample_source,
        "use_llm": args.use_llm,
        "retrieval_top_k": args.top_k,
        "rerank_enabled": args.rerank,
        "comparison_scope": comparison_scope,
        "modes": [item[0] for item in mode_plan],
        "artifact_ids": [sample.sample_id for sample in samples],
        "summary": _aggregate(rows),
        "rows": [asdict(row) for row in rows],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"rag_e2e_ablation_{stamp}.json"
    csv_path = args.output_dir / f"rag_e2e_ablation_{stamp}.csv"
    md_path = args.output_dir / f"rag_e2e_ablation_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(csv_path, rows)
    _write_markdown(md_path, payload)
    print(json.dumps({"markdown": str(md_path), "json": str(json_path), "csv": str(csv_path), "summary": payload["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
