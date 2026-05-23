"""Run generation + real API execution ablation for RAG evidence.

This script is intentionally stricter than generation-only reports: a sample
with no HTTP request steps is marked as not_executable instead of being counted
as a successful test run.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


_ROOT = Path(__file__).resolve().parents[2]
for _p in (
    _ROOT / "shared" / "src",
    _ROOT / "requirement-analysis" / "src",
    _ROOT / "case-generation" / "src",
    _ROOT / "execution-engine" / "api-runner" / "src",
):
    sys.path.insert(0, str(_p))

from api_runner import execute_test_case_dsl  # noqa: E402
from case_generation import build_scenarios, build_test_case_dsl  # noqa: E402
from platform_shared.models import ScenarioModel, TaskContext  # noqa: E402
import requirement_analysis.service as service_module  # noqa: E402
from requirement_analysis.service import AnalysisParseOptions, parse_requirement_bundle  # noqa: E402


_BASE_URL_RE = re.compile(r"https?://[^\s)`>\"']+")


class _LocalApiMock:
    """Small deterministic API target for execution ablation samples."""

    def __init__(self, kind: str):
        self.kind = kind
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self) -> str:
        kind = self.kind

        class Handler(BaseHTTPRequestHandler):
            booking_seq = 100
            product_seq = 200
            todo_seq = 300
            bookings: dict[int, dict[str, Any]] = {}
            products: dict[int, dict[str, Any]] = {
                1: {"id": 1, "name": "demo product", "price": 19.9, "status": "active"}
            }
            todos: dict[int, dict[str, Any]] = {
                1: {"id": 1, "todo": "write API test", "completed": False, "userId": 5}
            }

            def log_message(self, _format: str, *args: Any) -> None:  # noqa: A003
                return

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0:
                    return {}
                try:
                    return json.loads(self.rfile.read(length).decode("utf-8"))
                except json.JSONDecodeError:
                    return {}

            def _send(self, payload: Any, status: int = 200) -> None:
                raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                path = parsed.path.rstrip("/") or "/"
                if kind == "dummyjson":
                    if path == "/auth/me":
                        self._send({"id": 1, "username": "emilys", "firstName": "Emily", "lastName": "Johnson"})
                    elif path == "/todos":
                        items = list(self.todos.values())
                        self._send({"todos": items, "total": len(items), "skip": 0, "limit": 30})
                    elif path.startswith("/todos/user/"):
                        items = [item for item in self.todos.values() if item.get("userId") == 5]
                        self._send({"todos": items, "total": len(items), "skip": 0, "limit": 30})
                    elif path.startswith("/todos/"):
                        self._send(self.todos.get(_last_int(path), self.todos[1]))
                    else:
                        self._send({"ok": True})
                    return
                if kind == "booker":
                    if path == "/booking":
                        if not self.bookings:
                            self.bookings[1] = _booking_payload()
                        self._send([{"bookingid": key} for key in self.bookings])
                    elif path.startswith("/booking/"):
                        self._send(self.bookings.get(_last_int(path), _booking_payload()))
                    elif path == "/ping":
                        self._send({"ok": True})
                    else:
                        self._send({"ok": True})
                    return
                if kind == "store":
                    if path == "/products":
                        items = list(self.products.values())
                        self._send({"products": items, "items": items, "total": len(items)})
                    elif path.startswith("/products/"):
                        self._send(self.products.get(_last_int(path), self.products[1]))
                    else:
                        self._send({"ok": True})
                    return
                self._send({"ok": True})

            def do_POST(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                path = parsed.path.rstrip("/") or "/"
                body = self._read_json()
                if kind == "dummyjson":
                    if path == "/auth/login":
                        self._send({"accessToken": "access-token-demo", "refreshToken": "refresh-token-demo", "id": 1})
                    elif path == "/auth/refresh":
                        self._send({"accessToken": "access-token-refreshed", "refreshToken": "refresh-token-refreshed"})
                    elif path in {"/todos", "/todos/add"}:
                        self.todo_seq += 1
                        payload = {"id": self.todo_seq, "todo": body.get("todo", "write API test"), "completed": body.get("completed", False), "userId": body.get("userId", 5)}
                        self.todos[self.todo_seq] = payload
                        self._send(payload)
                    else:
                        self._send({"ok": True})
                    return
                if kind == "booker":
                    if path == "/auth":
                        self._send({"token": "booker-token-demo"})
                    elif path == "/booking":
                        self.booking_seq += 1
                        payload = _booking_payload(body)
                        self.bookings[self.booking_seq] = payload
                        self._send({"bookingid": self.booking_seq, "booking": payload})
                    else:
                        self._send({"ok": True})
                    return
                if kind == "store":
                    if path == "/products":
                        self.product_seq += 1
                        payload = {"id": self.product_seq, "name": body.get("name", "demo product"), "price": body.get("price", 19.9), "status": body.get("status", "active")}
                        self.products[self.product_seq] = payload
                        self._send(payload, status=201)
                    else:
                        self._send({"ok": True})
                    return
                self._send({"ok": True})

            def do_PUT(self) -> None:  # noqa: N802
                self._mutation()

            def do_PATCH(self) -> None:  # noqa: N802
                self._mutation(partial=True)

            def do_DELETE(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                path = parsed.path.rstrip("/") or "/"
                if kind == "booker" and path.startswith("/booking/"):
                    self.bookings.pop(_last_int(path), None)
                    self._send({"deleted": True}, status=201)
                elif kind == "dummyjson" and path.startswith("/todos/"):
                    item = dict(self.todos.get(_last_int(path), self.todos[1]))
                    item.update({"isDeleted": True, "deletedOn": "2026-05-01T00:00:00.000Z"})
                    self._send(item)
                elif kind == "store" and path.startswith("/products/"):
                    item = dict(self.products.get(_last_int(path), self.products[1]))
                    item.update({"deleted": True, "isDeleted": True})
                    self._send(item)
                else:
                    self._send({"deleted": True})

            def _mutation(self, partial: bool = False) -> None:
                parsed = urlparse(self.path)
                path = parsed.path.rstrip("/") or "/"
                body = self._read_json()
                if kind == "booker" and path.startswith("/booking/"):
                    current = _booking_payload()
                    current.update(body)
                    self.bookings[_last_int(path)] = current
                    self._send(current)
                elif kind == "dummyjson" and path.startswith("/todos/"):
                    current = dict(self.todos.get(_last_int(path), self.todos[1]))
                    current.update(body or {"completed": True})
                    self.todos[_last_int(path)] = current
                    self._send(current)
                elif kind == "store" and path.startswith("/products/"):
                    current = dict(self.products.get(_last_int(path), self.products[1]))
                    current.update(body or {"status": "active"})
                    self.products[_last_int(path)] = current
                    self._send(current)
                else:
                    self._send({"ok": True, "partial": partial})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        if self.server is not None:
            self.server.shutdown()
        if self.thread is not None:
            self.thread.join(timeout=2)


def _last_int(path: str) -> int:
    for part in reversed(path.split("/")):
        if part.isdigit():
            return int(part)
    return 1


def _booking_payload(seed: dict[str, Any] | None = None) -> dict[str, Any]:
    seed = seed or {}
    return {
        "firstname": seed.get("firstname", "Jim"),
        "lastname": seed.get("lastname", "Brown"),
        "totalprice": seed.get("totalprice", 111),
        "depositpaid": seed.get("depositpaid", True),
        "bookingdates": seed.get("bookingdates", {"checkin": "2026-04-10", "checkout": "2026-04-12"}),
        "additionalneeds": seed.get("additionalneeds", "Breakfast"),
    }


def _mock_kind_for_base_url(base_url: str) -> str:
    lowered = base_url.lower()
    if "dummyjson.com" in lowered:
        return "dummyjson"
    if "restful-booker.herokuapp.com" in lowered:
        return "booker"
    if "api.example.local" in lowered:
        return "store"
    return ""


@dataclass(frozen=True, slots=True)
class RequirementSample:
    sample_id: str
    task_name: str
    requirement_text: str
    source_path: str


@dataclass(slots=True)
class ExecutionAblationRow:
    sample_id: str
    task_name: str
    mode: str
    use_llm: bool
    rag_enabled: bool
    knowledge_disabled: bool
    parse_mode: str
    llm_used: bool
    rag_used: bool
    knowledge_applied: bool
    base_url: str
    api_endpoint_count: int
    scenario_count: int
    request_step_count: int
    assertion_count: int
    execution_status: str
    executable: bool
    scenario_pass_rate: float
    step_pass_rate: float
    assertion_pass_rate: float
    api_coverage_ratio: float
    avg_elapsed_ms: float
    generation_elapsed_ms: float
    execution_elapsed_ms: float
    failure_categories: str
    error: str = ""


def _discover_document_samples(doc_root: Path, limit: int) -> list[RequirementSample]:
    files = [path for path in doc_root.rglob("*") if path.is_file() and path.suffix.lower() in {".md", ".txt"}]
    files.sort(key=lambda p: p.name.lower())
    if limit > 0:
        files = files[:limit]
    return [
        RequirementSample(
            sample_id=path.stem,
            task_name=path.stem.replace("_", " "),
            requirement_text=path.read_text(encoding="utf-8"),
            source_path=str(path),
        )
        for path in files
    ]


def _extract_base_url(requirement_text: str, parse_metadata: dict[str, Any]) -> str:
    detected = str(parse_metadata.get("detected_base_url") or "").strip()
    if detected:
        return detected.rstrip("/")
    for candidate in _BASE_URL_RE.findall(requirement_text or ""):
        if "example.local" not in candidate and "{BASE_URL}" not in candidate:
            return candidate.rstrip("/")
    return ""


def _count_request_steps(dsl: dict[str, Any]) -> int:
    total = 0
    for scenario in dsl.get("scenarios") or []:
        for step in scenario.get("steps") or []:
            request = step.get("request") if isinstance(step, dict) else {}
            if isinstance(request, dict) and request.get("method") and request.get("url"):
                total += 1
    return total


def _count_assertions(dsl: dict[str, Any]) -> int:
    total = 0
    for scenario in dsl.get("scenarios") or []:
        for step in scenario.get("steps") or []:
            assertions = step.get("assertions") if isinstance(step, dict) else []
            total += len(assertions) if isinstance(assertions, list) else 0
    return total


def _inject_execution_metadata(dsl: dict[str, Any], base_url: str) -> None:
    metadata = dict(dsl.get("metadata") or {})
    execution = dict(metadata.get("execution") or {})
    execution["base_url"] = base_url
    execution.setdefault("default_headers", {"Accept": "application/json", "Content-Type": "application/json"})
    execution.setdefault("default_step_timeout", 12)
    execution.setdefault("default_step_retries", 1)
    metadata["execution"] = execution
    dsl["metadata"] = metadata


def _execution_summary(execution_result: dict[str, Any]) -> dict[str, Any]:
    scenarios = execution_result.get("scenario_results") or []
    passed_scenarios = sum(1 for item in scenarios if item.get("status") == "passed")
    total_steps = 0
    passed_steps = 0
    total_assertions = 0
    passed_assertions = 0
    failure_categories: dict[str, int] = {}
    for scenario in scenarios:
        for step in scenario.get("steps") or []:
            total_steps += 1
            if step.get("status") == "passed":
                passed_steps += 1
            summary = step.get("assertion_summary") or {}
            total_assertions += int(summary.get("total") or 0)
            passed_assertions += int(summary.get("passed") or 0)
            if step.get("status") != "passed":
                category = str(step.get("error_category") or "unknown")
                failure_categories[category] = failure_categories.get(category, 0) + 1
    metrics = execution_result.get("metrics") or {}
    api_coverage_ratio = float(metrics.get("api_coverage_ratio") or 0.0)
    if api_coverage_ratio > 1.0:
        api_coverage_ratio = api_coverage_ratio / 100.0
    return {
        "status": str(execution_result.get("status") or ""),
        "scenario_pass_rate": round(passed_scenarios / len(scenarios), 4) if scenarios else 0.0,
        "step_pass_rate": round(passed_steps / total_steps, 4) if total_steps else 0.0,
        "assertion_pass_rate": round(passed_assertions / total_assertions, 4) if total_assertions else 0.0,
        "api_coverage_ratio": round(api_coverage_ratio, 4),
        "avg_elapsed_ms": round(float(metrics.get("avg_elapsed_ms") or 0.0), 2),
        "failure_categories": "; ".join(f"{key}:{value}" for key, value in sorted(failure_categories.items())),
    }


def _run_one(
    *,
    sample: RequirementSample,
    mode: str,
    use_llm: bool,
    rag_enabled: bool,
    knowledge_disabled: bool,
    retrieval_top_k: int,
) -> ExecutionAblationRow:
    original_curated_loader = service_module.load_curated_knowledge_chunks
    original_contract_builder = service_module.build_contract_chunks
    generation_started = time.perf_counter()
    try:
        if knowledge_disabled:
            service_module.load_curated_knowledge_chunks = lambda **_: []
            service_module.build_contract_chunks = lambda *_args, **_kwargs: []
        bundle = parse_requirement_bundle(
            requirement_text=sample.requirement_text,
            options=AnalysisParseOptions(
                use_llm=use_llm,
                rag_enabled=rag_enabled,
                retrieval_top_k=retrieval_top_k,
                rerank_enabled=False,
            ),
        )
        meta = bundle.get("parse_metadata") or {}
        parsed = bundle.get("parsed_requirement") or {}
        scenarios = [ScenarioModel(**item) for item in build_scenarios(parsed, use_llm=use_llm)]
        dsl = build_test_case_dsl(
            TaskContext(
                task_id=f"{sample.sample_id}_{mode}",
                task_name=sample.task_name,
                source_type="rag_execution_ablation",
                rag_enabled=rag_enabled,
            ),
            scenarios,
            parsed_requirement=parsed,
            enable_assertion_enhancement=use_llm,
        )
        generation_elapsed_ms = round((time.perf_counter() - generation_started) * 1000, 2)
        base_url = _extract_base_url(sample.requirement_text, meta)
        request_step_count = _count_request_steps(dsl)
        assertion_count = _count_assertions(dsl)
        executable = bool(base_url and request_step_count > 0)
        execution_summary = {
            "status": "not_executable",
            "scenario_pass_rate": 0.0,
            "step_pass_rate": 0.0,
            "assertion_pass_rate": 0.0,
            "api_coverage_ratio": 0.0,
            "avg_elapsed_ms": 0.0,
            "failure_categories": "not_executable:1",
        }
        execution_elapsed_ms = 0.0
        if executable:
            mock_kind = _mock_kind_for_base_url(base_url)
            execution_started = time.perf_counter()
            if mock_kind:
                with _LocalApiMock(mock_kind) as local_base_url:
                    _inject_execution_metadata(dsl, local_base_url)
                    execution_result = execute_test_case_dsl(dsl)
            else:
                _inject_execution_metadata(dsl, base_url)
                execution_result = execute_test_case_dsl(dsl)
            execution_elapsed_ms = round((time.perf_counter() - execution_started) * 1000, 2)
            execution_summary = _execution_summary(execution_result)
        knowledge = meta.get("knowledge_base") if isinstance(meta.get("knowledge_base"), dict) else {}
        return ExecutionAblationRow(
            sample_id=sample.sample_id,
            task_name=sample.task_name,
            mode=mode,
            use_llm=use_llm,
            rag_enabled=rag_enabled,
            knowledge_disabled=knowledge_disabled,
            parse_mode=str(meta.get("parse_mode") or ""),
            llm_used=bool(meta.get("llm_used", False)),
            rag_used=bool(meta.get("rag_used", False)),
            knowledge_applied=bool(knowledge.get("applied", False)),
            base_url=base_url,
            api_endpoint_count=len(parsed.get("api_endpoints") or []),
            scenario_count=len(scenarios),
            request_step_count=request_step_count,
            assertion_count=assertion_count,
            execution_status=execution_summary["status"],
            executable=executable,
            scenario_pass_rate=execution_summary["scenario_pass_rate"],
            step_pass_rate=execution_summary["step_pass_rate"],
            assertion_pass_rate=execution_summary["assertion_pass_rate"],
            api_coverage_ratio=execution_summary["api_coverage_ratio"],
            avg_elapsed_ms=execution_summary["avg_elapsed_ms"],
            generation_elapsed_ms=generation_elapsed_ms,
            execution_elapsed_ms=execution_elapsed_ms,
            failure_categories=execution_summary["failure_categories"],
        )
    except Exception as exc:  # pragma: no cover - diagnostic script
        generation_elapsed_ms = round((time.perf_counter() - generation_started) * 1000, 2)
        return ExecutionAblationRow(
            sample_id=sample.sample_id,
            task_name=sample.task_name,
            mode=mode,
            use_llm=use_llm,
            rag_enabled=rag_enabled,
            knowledge_disabled=knowledge_disabled,
            parse_mode="",
            llm_used=False,
            rag_used=False,
            knowledge_applied=False,
            base_url="",
            api_endpoint_count=0,
            scenario_count=0,
            request_step_count=0,
            assertion_count=0,
            execution_status="error",
            executable=False,
            scenario_pass_rate=0.0,
            step_pass_rate=0.0,
            assertion_pass_rate=0.0,
            api_coverage_ratio=0.0,
            avg_elapsed_ms=0.0,
            generation_elapsed_ms=generation_elapsed_ms,
            execution_elapsed_ms=0.0,
            failure_categories=type(exc).__name__,
            error=str(exc),
        )
    finally:
        service_module.load_curated_knowledge_chunks = original_curated_loader
        service_module.build_contract_chunks = original_contract_builder


def _aggregate(rows: list[ExecutionAblationRow]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    by_mode: dict[str, list[ExecutionAblationRow]] = {}
    for row in rows:
        by_mode.setdefault(row.mode, []).append(row)
    for mode, items in by_mode.items():
        valid = [item for item in items if not item.error]
        executable = [item for item in valid if item.executable]
        denominator = len(executable) or 1
        out[mode] = {
            "sample_count": len(items),
            "valid_count": len(valid),
            "executable_count": len(executable),
            "passed_execution_count": sum(1 for item in executable if item.execution_status == "passed"),
            "mean_api_endpoint_count": round(sum(item.api_endpoint_count for item in valid) / (len(valid) or 1), 2),
            "mean_request_step_count": round(sum(item.request_step_count for item in valid) / (len(valid) or 1), 2),
            "mean_assertion_count": round(sum(item.assertion_count for item in valid) / (len(valid) or 1), 2),
            "mean_scenario_pass_rate": round(sum(item.scenario_pass_rate for item in executable) / denominator, 4),
            "mean_step_pass_rate": round(sum(item.step_pass_rate for item in executable) / denominator, 4),
            "mean_assertion_pass_rate": round(sum(item.assertion_pass_rate for item in executable) / denominator, 4),
            "mean_api_coverage_ratio": round(sum(item.api_coverage_ratio for item in executable) / denominator, 4),
            "mean_generation_elapsed_ms": round(sum(item.generation_elapsed_ms for item in valid) / (len(valid) or 1), 2),
            "mean_execution_elapsed_ms": round(sum(item.execution_elapsed_ms for item in executable) / denominator, 2),
            "rag_used_count": sum(1 for item in valid if item.rag_used),
            "knowledge_applied_count": sum(1 for item in valid if item.knowledge_applied),
            "error_count": len(items) - len(valid),
        }
    for left, right, key in (
        ("knowledge_off", "knowledge_on_keyword", "delta_keyword_knowledge_minus_off"),
        ("knowledge_on_keyword", "knowledge_on_vector", "delta_vector_minus_keyword"),
    ):
        if left not in out or right not in out:
            continue
        out[key] = {
            metric: round(out[right][metric] - out[left][metric], 4)
            for metric in (
                "executable_count",
                "passed_execution_count",
                "mean_api_endpoint_count",
                "mean_request_step_count",
                "mean_assertion_count",
                "mean_scenario_pass_rate",
                "mean_step_pass_rate",
                "mean_assertion_pass_rate",
                "mean_api_coverage_ratio",
                "mean_generation_elapsed_ms",
                "mean_execution_elapsed_ms",
            )
        }
    return out


def _write_csv(path: Path, rows: list[ExecutionAblationRow]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    rows = [ExecutionAblationRow(**item) for item in payload["rows"]]
    summary = payload["summary"]
    lines = [
        "# RAG 执行成功率消融实验报告",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 样本来源：{payload['sample_source']}",
        f"- 样本数：{payload['sample_count']}",
        f"- LLM 增强：{'开启' if payload['use_llm'] else '关闭'}",
        "",
        "## 汇总",
        "",
        "| 模式 | 有效样本 | 可执行样本 | 执行通过 | 平均接口数 | 平均请求步骤 | 平均断言数 | 场景通过率 | 步骤通过率 | 断言通过率 | API覆盖率 | 生成耗时(ms) | 执行耗时(ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode in payload["modes"]:
        data = summary.get(mode) or {}
        lines.append(
            "| {mode} | {valid} | {exec_count} | {passed} | {endpoint:.2f} | {requests:.2f} | {assertions:.2f} | {scenario:.2%} | {step:.2%} | {assertion:.2%} | {coverage:.2%} | {gen:.2f} | {exe:.2f} |".format(
                mode=mode,
                valid=data.get("valid_count", 0),
                exec_count=data.get("executable_count", 0),
                passed=data.get("passed_execution_count", 0),
                endpoint=float(data.get("mean_api_endpoint_count", 0)),
                requests=float(data.get("mean_request_step_count", 0)),
                assertions=float(data.get("mean_assertion_count", 0)),
                scenario=float(data.get("mean_scenario_pass_rate", 0)),
                step=float(data.get("mean_step_pass_rate", 0)),
                assertion=float(data.get("mean_assertion_pass_rate", 0)),
                coverage=float(data.get("mean_api_coverage_ratio", 0)),
                gen=float(data.get("mean_generation_elapsed_ms", 0)),
                exe=float(data.get("mean_execution_elapsed_ms", 0)),
            )
        )
    lines.extend(
        [
            "",
            "## 明细",
            "",
            "| 样本 | 模式 | 解析 | RAG used | 接口数 | 请求步骤 | 断言数 | 执行状态 | 可执行 | 场景通过率 | 步骤通过率 | 断言通过率 | 失败分类 |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| {task} | {mode} | {parse_mode} | {rag_used} | {endpoint} | {requests} | {assertions} | {status} | {executable} | {scenario:.2%} | {step:.2%} | {assertion:.2%} | {failure} |".format(
                task=row.task_name,
                mode=row.mode,
                parse_mode=row.parse_mode or "-",
                rag_used="是" if row.rag_used else "否",
                endpoint=row.api_endpoint_count,
                requests=row.request_step_count,
                assertions=row.assertion_count,
                status=row.execution_status,
                executable="是" if row.executable else "否",
                scenario=row.scenario_pass_rate,
                step=row.step_pass_rate,
                assertion=row.assertion_pass_rate,
                failure=(row.failure_categories or "").replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## 论文使用建议",
            "",
            "- 可执行样本数可以证明生成结果是否真正形成了可运行接口测试，而不是只生成说明性场景。",
            "- 执行通过率、断言通过率和 API 覆盖率适合放在实验结果表中，与生成质量指标形成闭环。",
            "- 公共 API 存在网络波动，论文中建议同时报告失败分类，区分网络失败、上下文失败和断言失败。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAG generation + execution ablation.")
    parser.add_argument("--doc-root", type=Path, default=_ROOT / "task-center" / "benchmark_inputs" / "rag_sparse_docs")
    parser.add_argument("--recent", type=int, default=2)
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=_ROOT / "delivery_reports")
    args = parser.parse_args()

    modes = (
        ("knowledge_off", False, True),
        ("knowledge_on_keyword", False, False),
        ("knowledge_on_vector", True, False),
    )
    samples = _discover_document_samples(args.doc_root, args.recent)
    rows: list[ExecutionAblationRow] = []
    for sample in samples:
        for mode, rag_enabled, knowledge_disabled in modes:
            rows.append(
                _run_one(
                    sample=sample,
                    mode=mode,
                    use_llm=args.use_llm,
                    rag_enabled=rag_enabled,
                    knowledge_disabled=knowledge_disabled,
                    retrieval_top_k=args.top_k,
                )
            )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sample_source": str(args.doc_root),
        "sample_count": len(samples),
        "use_llm": args.use_llm,
        "modes": [item[0] for item in modes],
        "summary": _aggregate(rows),
        "rows": [asdict(row) for row in rows],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"rag_execution_ablation_{stamp}.json"
    csv_path = args.output_dir / f"rag_execution_ablation_{stamp}.csv"
    md_path = args.output_dir / f"rag_execution_ablation_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(csv_path, rows)
    _write_markdown(md_path, payload)
    print(json.dumps({"markdown": str(md_path), "json": str(json_path), "csv": str(csv_path), "summary": payload["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
