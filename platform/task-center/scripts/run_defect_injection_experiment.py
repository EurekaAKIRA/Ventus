"""Run a local defect-injection API experiment for thesis evidence.

The script starts a healthy mock API and a buggy mock API, executes the same
multi-step DSL against both, and exports detection metrics plus defect payloads
that mirror the platform defect-management fields.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parents[2]
for _p in (
    _ROOT / "shared" / "src",
    _ROOT / "execution-engine" / "api-runner" / "src",
):
    sys.path.insert(0, str(_p))

from api_runner import execute_test_case_dsl  # noqa: E402


@dataclass(slots=True)
class RunSummary:
    mode: str
    status: str
    scenario_count: int
    passed_scenarios: int
    failed_scenarios: int
    step_count: int
    passed_steps: int
    failed_steps: int
    assertion_total: int
    assertion_passed: int
    assertion_failed: int
    assertion_pass_rate: float
    api_coverage_ratio: float
    avg_elapsed_ms: float
    failure_categories: dict[str, int]
    detected_defect_count: int
    false_positive_count: int
    execution_elapsed_ms: float


@dataclass(slots=True)
class DefectExport:
    title: str
    severity: str
    source: str
    reproduction_steps: str
    expected_result: str
    actual_result: str
    scenario_name: str
    step_id: str
    error_category: str


INJECTED_DEFECTS = [
    {
        "id": "missing_token",
        "title": "登录响应缺少 token 字段",
        "expected": "POST /login 应返回 json.token",
    },
    {
        "id": "auth_rejected",
        "title": "受保护资料接口错误拒绝合法 token",
        "expected": "GET /profile 携带合法 Bearer token 应返回 200",
    },
    {
        "id": "order_id_type",
        "title": "创建订单响应 id 类型错误",
        "expected": "POST /orders 应返回字符串类型 id",
    },
    {
        "id": "order_status_wrong",
        "title": "订单详情业务状态错误",
        "expected": "GET /orders/{id} 应返回 confirmed 状态",
    },
    {
        "id": "delete_status_error",
        "title": "删除订单返回服务端错误",
        "expected": "DELETE /orders/{id} 应返回 204",
    },
]


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def _read_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    raw = handler.rfile.read(length) if length else b"{}"
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def _make_handler(mode: str) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        server_version = "DefectInjectionMock/1.0"

        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/login":
                if mode == "buggy":
                    _json_response(self, 200, {"user": "demo-admin"})
                    return
                _json_response(self, 200, {"token": "valid-token", "user": "demo-admin"})
                return

            if self.path == "/orders":
                if not _is_authorized(self):
                    _json_response(self, 401, {"error": "unauthorized"})
                    return
                body = _read_body(self)
                order_id: str | int = 1001 if mode == "buggy" else "order-1001"
                _json_response(
                    self,
                    201,
                    {
                        "id": order_id,
                        "item": body.get("item", "unknown"),
                        "status": "created",
                    },
                )
                return

            self.send_error(404)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/profile":
                if mode == "buggy":
                    _json_response(self, 401, {"error": "token rejected"})
                    return
                if not _is_authorized(self):
                    _json_response(self, 401, {"error": "unauthorized"})
                    return
                _json_response(self, 200, {"id": "user-1", "role": "admin"})
                return

            if self.path.startswith("/orders/"):
                if not _is_authorized(self):
                    _json_response(self, 401, {"error": "unauthorized"})
                    return
                status = "pending" if mode == "buggy" else "confirmed"
                _json_response(self, 200, {"id": self.path.rsplit("/", 1)[-1], "status": status})
                return

            self.send_error(404)

        def do_DELETE(self) -> None:  # noqa: N802
            if self.path.startswith("/orders/"):
                if not _is_authorized(self):
                    _json_response(self, 401, {"error": "unauthorized"})
                    return
                if mode == "buggy":
                    _json_response(self, 500, {"error": "delete failed"})
                    return
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            self.send_error(404)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

    return _Handler


def _is_authorized(handler: BaseHTTPRequestHandler) -> bool:
    return handler.headers.get("Authorization") == "Bearer valid-token"


def _start_server(mode: str) -> tuple[HTTPServer, threading.Thread, str]:
    server = HTTPServer(("127.0.0.1", 0), _make_handler(mode))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, thread, f"http://{host}:{port}"


def _build_defect_dsl(base_url: str) -> dict[str, Any]:
    return {
        "dsl_version": "0.2.0",
        "task_id": "defect_injection_experiment",
        "task_name": "defect_injection_experiment",
        "feature_name": "defect_injection_experiment",
        "execution_mode": "api",
        "metadata": {
            "execution": {
                "base_url": base_url,
                "default_headers": {"Accept": "application/json", "Content-Type": "application/json"},
                "step_timeout_seconds": 5,
                "step_retries": 0,
            }
        },
        "scenarios": [
            {
                "scenario_id": "missing_token",
                "name": "登录响应必须返回 token",
                "steps": [
                    {
                        "step_id": "missing_token_01",
                        "step_type": "when",
                        "text": "login and validate token contract",
                        "request": {"method": "POST", "url": "/login", "json": {"username": "demo", "password": "secret"}},
                        "assertions": [
                            {"source": "status_code", "op": "eq", "expected": 200, "category": "status", "severity": "critical"},
                            {"source": "json.token", "op": "exists", "category": "field_presence", "severity": "critical"},
                            {"source": "json.token", "op": "type_is", "expected": "string", "category": "schema", "severity": "major"},
                        ],
                        "save_context": {"token": "json.token"},
                    }
                ],
            },
            {
                "scenario_id": "auth_rejected",
                "name": "合法 token 应能访问用户资料",
                "setup_steps": [
                    {"step_id": "auth_setup", "step_type": "given", "text": "seed valid token", "set_context": {"token": "valid-token"}}
                ],
                "steps": [
                    {
                        "step_id": "auth_rejected_01",
                        "step_type": "when",
                        "text": "get protected profile",
                        "uses_context": ["token"],
                        "request": {"method": "GET", "url": "/profile", "auth": {"type": "bearer", "token_context": "token"}},
                        "assertions": [
                            {"source": "status_code", "op": "eq", "expected": 200, "category": "status", "severity": "critical"},
                            {"source": "json.role", "op": "eq", "expected": "admin", "category": "business", "severity": "major"},
                        ],
                    }
                ],
            },
            {
                "scenario_id": "order_id_type",
                "name": "创建订单应返回字符串 id",
                "examples": [
                    {"item": "book", "expected_id_type": "string", "run_create": True},
                    {"item": "pen", "expected_id_type": "string", "run_create": False},
                ],
                "setup_steps": [
                    {"step_id": "order_setup", "step_type": "given", "text": "seed valid token", "set_context": {"token": "valid-token"}}
                ],
                "steps": [
                    {
                        "step_id": "order_id_type_01",
                        "step_type": "when",
                        "text": "create order for example item",
                        "run_if": {"source": "context.run_create", "op": "eq", "expected": True},
                        "uses_context": ["token"],
                        "request": {
                            "method": "POST",
                            "url": "/orders",
                            "auth": {"type": "bearer", "token_context": "token"},
                            "json": {"item": "{{item}}"},
                        },
                        "assertions": [
                            {"source": "status_code", "op": "eq", "expected": 201, "category": "status", "severity": "critical"},
                            {
                                "source": "json.id",
                                "op": "type_is",
                                "expected": "{{expected_id_type}}",
                                "category": "schema",
                                "severity": "major",
                            },
                        ],
                        "save_context": {"order_id": "json.id"},
                    }
                ],
            },
            {
                "scenario_id": "order_status_wrong",
                "name": "订单详情状态应为 confirmed",
                "setup_steps": [
                    {
                        "step_id": "detail_setup",
                        "step_type": "given",
                        "text": "seed valid order id",
                        "set_context": {"token": "valid-token", "order_id": "order-1001"},
                    }
                ],
                "steps": [
                    {
                        "step_id": "order_status_wrong_01",
                        "step_type": "when",
                        "text": "get order detail",
                        "uses_context": ["token", "order_id"],
                        "request": {
                            "method": "GET",
                            "url": "/orders/{{order_id}}",
                            "auth": {"type": "bearer", "token_context": "token"},
                        },
                        "assertions": [
                            {"source": "status_code", "op": "eq", "expected": 200, "category": "status", "severity": "critical"},
                            {"source": "json.status", "op": "eq", "expected": "confirmed", "category": "business", "severity": "major"},
                        ],
                    }
                ],
            },
            {
                "scenario_id": "delete_status_error",
                "name": "删除订单应返回 204",
                "setup_steps": [
                    {
                        "step_id": "delete_setup",
                        "step_type": "given",
                        "text": "seed valid order id",
                        "set_context": {"token": "valid-token", "order_id": "order-1001"},
                    }
                ],
                "steps": [
                    {
                        "step_id": "delete_status_error_01",
                        "step_type": "when",
                        "text": "delete order",
                        "uses_context": ["token", "order_id"],
                        "request": {
                            "method": "DELETE",
                            "url": "/orders/{{order_id}}",
                            "auth": {"type": "bearer", "token_context": "token"},
                        },
                        "assertions": [
                            {"source": "status_code", "op": "eq", "expected": 204, "category": "status", "severity": "critical"}
                        ],
                    }
                ],
            },
        ],
    }


def _summarize(mode: str, result: dict[str, Any], elapsed_ms: float) -> RunSummary:
    scenarios = result.get("scenario_results") or []
    passed_scenarios = sum(1 for item in scenarios if item.get("status") == "passed")
    failed_scenarios = sum(1 for item in scenarios if item.get("status") == "failed")
    assertion_total = 0
    assertion_failed = 0
    failure_categories: dict[str, int] = {}
    for scenario in scenarios:
        for step in scenario.get("steps") or []:
            summary = step.get("assertion_summary") or {}
            assertion_total += int(summary.get("total") or 0)
            assertion_failed += int(summary.get("failed") or 0)
            if step.get("status") == "failed":
                category = str(step.get("error_category") or "assertion_error")
                failure_categories[category] = failure_categories.get(category, 0) + 1
    assertion_passed = max(assertion_total - assertion_failed, 0)
    metrics = result.get("metrics") or {}
    false_positive_count = failed_scenarios if mode == "healthy" else 0
    detected_defect_count = min(failed_scenarios, len(INJECTED_DEFECTS)) if mode == "buggy" else 0
    coverage = float(metrics.get("api_coverage_ratio") or 0.0)
    if coverage > 1:
        coverage = coverage / 100
    return RunSummary(
        mode=mode,
        status=str(result.get("status") or ""),
        scenario_count=len(scenarios),
        passed_scenarios=passed_scenarios,
        failed_scenarios=failed_scenarios,
        step_count=int(metrics.get("step_count") or 0),
        passed_steps=int(metrics.get("passed_step_count") or 0),
        failed_steps=int(metrics.get("failed_step_count") or 0),
        assertion_total=assertion_total,
        assertion_passed=assertion_passed,
        assertion_failed=assertion_failed,
        assertion_pass_rate=round(assertion_passed / assertion_total, 4) if assertion_total else 0.0,
        api_coverage_ratio=round(coverage, 4),
        avg_elapsed_ms=round(float(metrics.get("avg_elapsed_ms") or 0.0), 2),
        failure_categories=failure_categories,
        detected_defect_count=detected_defect_count,
        false_positive_count=false_positive_count,
        execution_elapsed_ms=round(elapsed_ms, 2),
    )


def _export_defects(result: dict[str, Any]) -> list[DefectExport]:
    exports: list[DefectExport] = []
    for scenario in result.get("scenario_results") or []:
        for step in scenario.get("steps") or []:
            if step.get("status") != "failed":
                continue
            assertion_summary = step.get("assertion_summary") or {}
            failures = assertion_summary.get("failure_details") or []
            first_failure = failures[0] if failures else {}
            expected = first_failure.get("expected", "")
            actual = first_failure.get("actual", "")
            category = str(step.get("error_category") or first_failure.get("failure_kind") or "assertion_error")
            exports.append(
                DefectExport(
                    title=f"{scenario.get('name')}: {step.get('text')}",
                    severity=_severity_for(category, first_failure),
                    source="defect_injection_experiment",
                    reproduction_steps=f"Run scenario `{scenario.get('name')}` step `{step.get('step_id')}`.",
                    expected_result=f"Assertion expected: {first_failure.get('source', 'step')} {first_failure.get('op', '')} {expected!r}",
                    actual_result=f"Actual result: {actual!r}; message={step.get('message', '')}",
                    scenario_name=str(scenario.get("name") or ""),
                    step_id=str(step.get("step_id") or ""),
                    error_category=category,
                )
            )
    return exports


def _severity_for(category: str, failure: dict[str, Any]) -> str:
    if category in {"auth_error", "http_server_error"}:
        return "critical"
    if str(failure.get("severity") or "").lower() == "critical":
        return "critical"
    if category in {"assertion_shape_mismatch", "context_error"}:
        return "high"
    return "medium"


def _write_csv(path: Path, rows: list[RunSummary]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            payload = asdict(row)
            payload["failure_categories"] = json.dumps(payload["failure_categories"], ensure_ascii=False)
            writer.writerow(payload)


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summaries = [RunSummary(**item) for item in payload["summaries"]]
    defects = [DefectExport(**item) for item in payload["defect_exports"]]
    buggy = next((item for item in summaries if item.mode == "buggy"), None)
    detection_rate = 0.0
    if buggy:
        detection_rate = buggy.detected_defect_count / len(INJECTED_DEFECTS)
    lines = [
        "# 缺陷注入接口测试实验报告",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 注入缺陷数：{len(INJECTED_DEFECTS)}",
        f"- 缺陷发现率：{detection_rate:.2%}",
        "",
        "## 注入缺陷",
        "",
        "| 缺陷ID | 缺陷说明 | 预期行为 |",
        "| --- | --- | --- |",
    ]
    for item in INJECTED_DEFECTS:
        lines.append(f"| {item['id']} | {item['title']} | {item['expected']} |")
    lines.extend(
        [
            "",
            "## 执行结果对比",
            "",
            "| 服务模式 | 状态 | 场景数 | 失败场景 | 步骤数 | 失败步骤 | 断言通过率 | API覆盖率 | 平均响应(ms) | 发现缺陷 | 误报数 | 失败分类 |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for item in summaries:
        lines.append(
            "| {mode} | {status} | {scenarios} | {failed_scenarios} | {steps} | {failed_steps} | {assertion:.2%} | {coverage:.2%} | {elapsed:.2f} | {detected} | {false_positive} | {categories} |".format(
                mode=item.mode,
                status=item.status,
                scenarios=item.scenario_count,
                failed_scenarios=item.failed_scenarios,
                steps=item.step_count,
                failed_steps=item.failed_steps,
                assertion=item.assertion_pass_rate,
                coverage=item.api_coverage_ratio,
                elapsed=item.avg_elapsed_ms,
                detected=item.detected_defect_count,
                false_positive=item.false_positive_count,
                categories=json.dumps(item.failure_categories, ensure_ascii=False),
            )
        )
    lines.extend(
        [
            "",
            "## 可导出缺陷",
            "",
            "| 标题 | 严重级别 | 分类 | 复现步骤 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for defect in defects:
        lines.append(
            f"| {defect.title} | {defect.severity} | {defect.error_category} | {defect.reproduction_steps} |"
        )
    lines.extend(
        [
            "",
            "## 论文使用建议",
            "",
            "- healthy 组用于证明低误报：健康服务不应产生失败缺陷。",
            "- buggy 组用于证明有效检出：同一套用例能识别字段缺失、鉴权错误、类型错误、业务值错误和服务端错误。",
            "- defect_exports 可对应缺陷管理模块的新建缺陷字段，适合截图展示“执行失败 -> 导出缺陷”的闭环。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_mode(mode: str) -> tuple[RunSummary, dict[str, Any], str]:
    server, thread, base_url = _start_server(mode)
    try:
        time.sleep(0.05)
        dsl = _build_defect_dsl(base_url)
        started = time.perf_counter()
        result = execute_test_case_dsl(dsl)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return _summarize(mode, result, elapsed_ms), result, base_url
    finally:
        server.shutdown()
        thread.join(timeout=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local defect injection experiment.")
    parser.add_argument("--output-dir", type=Path, default=_ROOT / "delivery_reports")
    args = parser.parse_args()

    healthy_summary, healthy_result, healthy_base_url = _run_mode("healthy")
    buggy_summary, buggy_result, buggy_base_url = _run_mode("buggy")
    defect_exports = _export_defects(buggy_result)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "healthy_base_url": healthy_base_url,
        "buggy_base_url": buggy_base_url,
        "injected_defects": INJECTED_DEFECTS,
        "summaries": [asdict(healthy_summary), asdict(buggy_summary)],
        "healthy_execution": healthy_result,
        "buggy_execution": buggy_result,
        "defect_exports": [asdict(item) for item in defect_exports],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"defect_injection_experiment_{stamp}.json"
    csv_path = args.output_dir / f"defect_injection_experiment_{stamp}.csv"
    md_path = args.output_dir / f"defect_injection_experiment_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(csv_path, [healthy_summary, buggy_summary])
    _write_markdown(md_path, payload)
    print(
        json.dumps(
            {
                "markdown": str(md_path),
                "json": str(json_path),
                "csv": str(csv_path),
                "healthy": asdict(healthy_summary),
                "buggy": asdict(buggy_summary),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
