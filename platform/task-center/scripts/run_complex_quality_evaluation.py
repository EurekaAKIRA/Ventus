"""Run a broader complex-quality evaluation for thesis charts.

This report intentionally evaluates harder inputs than the green regression
suite, so the result reflects practical robustness instead of only release
readiness.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
for item in [
    ROOT / "platform" / "shared" / "src",
    ROOT / "platform" / "requirement-analysis" / "src",
    ROOT / "platform" / "case-generation" / "src",
]:
    value = str(item)
    if value not in sys.path:
        sys.path.insert(0, value)

from case_generation import build_scenarios, build_test_case_dsl  # noqa: E402
from platform_shared.models import ScenarioModel, TaskContext  # noqa: E402
from requirement_analysis import parse_requirement  # noqa: E402


@dataclass(frozen=True)
class QualityCase:
    case_id: str
    title: str
    category: str
    text: str
    expected_paths: tuple[str, ...]
    expect_context: bool = False


CASES: tuple[QualityCase, ...] = (
    QualityCase("C01", "登录后查询资料", "标准接口文档", "POST /auth/login 返回 token。GET /auth/me 使用 Bearer {{token}} 查询用户资料。", ("/auth/login", "/auth/me"), True),
    QualityCase("C02", "Booking 闭环", "标准接口文档", "POST /auth 获取 token；POST /booking 创建资源；GET /booking/{{booking_id}} 查询；DELETE /booking/{{booking_id}} 删除。", ("/auth", "/booking", "/booking/{{booking_id}}"), True),
    QualityCase("C03", "订单创建查询", "标准接口文档", "POST /store/order 创建订单返回 order_id。GET /store/order/{{order_id}} 查询订单。", ("/store/order", "/store/order/{{order_id}}"), True),
    QualityCase("C04", "支付状态查询", "标准接口文档", "POST /payments 创建支付记录，GET /payments/{{payment_id}} 查询支付状态。", ("/payments", "/payments/{{payment_id}}"), True),
    QualityCase("C05", "Token 刷新", "标准接口文档", "POST /auth/login 返回 access_token 和 refresh_token。POST /auth/refresh 使用 refreshToken={{refresh_token}}。", ("/auth/login", "/auth/refresh"), True),
    QualityCase("C06", "商品搜索", "标准接口文档", "GET /products/search?q=phone&page=1&size=20 返回 products、total 和 page。", ("/products/search?q=phone&page=1&size=20",)),
    QualityCase("C07", "用户更新", "标准接口文档", "PUT /users/{{user_id}} 更新用户资料。GET /users/{{user_id}} 查询更新结果。", ("/users/{{user_id}}",), True),
    QualityCase("C08", "优惠券停用", "标准接口文档", "POST /coupons 创建优惠券返回 coupon_id。PATCH /coupons/{{coupon_id}} 修改 status=disabled。", ("/coupons", "/coupons/{{coupon_id}}"), True),
    QualityCase("C09", "导出任务", "中等复杂文档", "POST /exports 创建导出任务返回 export_id。GET /exports/{{export_id}}/status 轮询状态。GET /exports/{{export_id}}/download 下载文件。", ("/exports", "/exports/{{export_id}}/status", "/exports/{{export_id}}/download"), True),
    QualityCase("C10", "负向登录", "中等复杂文档", "POST /auth/login 使用错误 password，期望 401 和 error message。", ("/auth/login",)),
    QualityCase("C11", "评论子资源", "中等复杂文档", "GET /posts/{{post_id}} 读取帖子。POST /posts/{{post_id}}/comments 新增评论。GET /posts/{{post_id}}/comments/{{comment_id}} 查询评论。", ("/posts/{{post_id}}", "/posts/{{post_id}}/comments", "/posts/{{post_id}}/comments/{{comment_id}}"), True),
    QualityCase("C12", "Markdown 表格", "中等复杂文档", "| 方法 | 路径 | 说明 |\n| --- | --- | --- |\n| POST | /tickets | 创建工单 |\n| GET | /tickets/{{ticket_id}} | 查询工单 |\n| PATCH | /tickets/{{ticket_id}} | 更新工单 |", ("/tickets", "/tickets/{{ticket_id}}"), True),
    QualityCase("C13", "删除状态码", "中等复杂文档", "DELETE /files/{{file_id}} 删除文件。Expected: HTTP 204。GET /files/{{file_id}} 应返回 404。", ("/files/{{file_id}}",), True),
    QualityCase("C14", "GraphQL 单入口", "边界输入", "POST /graphql 查询订单，operationName=queryOrder，请求体包含 query 和 variables.orderId。", ("/graphql",)),
    QualityCase("C15", "弱文档订单流程", "边界输入", "用户需要创建订单、查询订单详情、取消订单，文档未明确 HTTP 方法，只说明要校验金额和状态。", ("/orders",), True),
    QualityCase("C16", "OpenAPI 片段", "边界输入", "paths:\n  /inventory/items:\n    get:\n      summary: list\n    post:\n      summary: create\n  /inventory/items/{item_id}:\n    patch:\n      summary: update", ("/inventory/items", "/inventory/items/{item_id}"), True),
    QualityCase("C17", "缺少方法的清单", "边界输入", "接口清单包括 /reports、/reports/{report_id}/download。需求是先生成报告，再下载报告文件。", ("/reports", "/reports/{report_id}/download"), True),
    QualityCase("C18", "Webhook 回调", "边界输入", "外部系统回调 POST /webhooks/payment，body 包含 event_id、type、payload，系统返回 200。", ("/webhooks/payment",)),
    QualityCase("C19", "混合自然语言审批", "困难输入", "审批人提交后进入复核，复核通过后生成归档记录，需要能查询归档详情。文档只提到审批 API，没有写路径。", ("/approvals", "/archives"), True),
    QualityCase("C20", "多租户隐含鉴权", "困难输入", "租户管理员登录后创建项目，再把成员加入项目。后续请求必须带 tenant header，但文档未写字段名。", ("/tenants/login", "/projects", "/members"), True),
    QualityCase("C21", "批量导入", "困难输入", "上传 CSV 后创建导入任务，系统异步校验并返回错误行下载链接。接口以导入服务为准，路径未完全给出。", ("/imports", "/imports/{import_id}/errors"), True),
    QualityCase("C22", "跨服务库存锁定", "困难输入", "下单前需要锁库存，支付失败后释放库存。涉及库存服务和订单服务，文档没有明确接口路径。", ("/inventory/locks", "/orders"), True),
    QualityCase("C23", "回调幂等", "困难输入", "支付平台重复回调时应按 event_id 幂等处理，若签名错误返回 401。只明确回调地址 /callback/pay。", ("/callback/pay",)),
    QualityCase("C24", "复杂过滤查询", "困难输入", "列表查询需要支持时间范围、状态数组、关键字、分页和排序，接口大致为报表查询。", ("/reports/search",)),
)


def _task_context(case_id: str) -> TaskContext:
    return TaskContext(task_id=f"complex_{case_id}", task_name=f"Complex {case_id}", source_type="text")


def _steps(dsl: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for scenario in dsl.get("scenarios") or []:
        output.extend([step for step in scenario.get("steps") or [] if isinstance(step, dict) and step.get("request")])
    return output


def _normalize_path(path: str) -> str:
    return path.replace("{{", "{").replace("}}", "}").split("?", 1)[0].rstrip("/")


def _covers(urls: list[str], expected: str) -> bool:
    target = _normalize_path(expected)
    return any(_normalize_path(url) == target or _normalize_path(url).startswith(target + "/") for url in urls)


def _assertion_count(steps: list[dict[str, Any]]) -> int:
    return sum(len([a for a in step.get("assertions") or [] if isinstance(a, dict)]) for step in steps)


def _has_context(steps: list[dict[str, Any]]) -> bool:
    for step in steps:
        request = step.get("request") or {}
        if step.get("save_context") or step.get("uses_context") or request.get("auth"):
            return True
        if "{{" in json.dumps(request, ensure_ascii=False):
            return True
    return False


def evaluate(case: QualityCase) -> dict[str, Any]:
    parsed = parse_requirement(case.text, use_llm=False)
    scenarios = [ScenarioModel(**item) for item in build_scenarios(parsed, use_llm=False)]
    dsl = build_test_case_dsl(_task_context(case.case_id), scenarios, parsed_requirement=parsed)
    steps = _steps(dsl)
    parsed_paths = [str(item.get("path")) for item in parsed.get("api_endpoints") or [] if item.get("path")]
    urls = [str((step.get("request") or {}).get("url") or "") for step in steps]
    expected_coverage = sum(1 for expected in case.expected_paths if _covers(urls, expected))

    checks = {
        "需求解析": bool(parsed_paths) and any(_covers(parsed_paths, expected) for expected in case.expected_paths),
        "场景生成": bool(scenarios),
        "DSL生成": bool(steps),
        "接口覆盖": expected_coverage >= max(1, round(len(case.expected_paths) * 0.6)),
        "断言规划": _assertion_count(steps) > 0,
        "上下文传递": (not case.expect_context) or _has_context(steps),
    }
    passed = sum(1 for value in checks.values() if value)
    return {
        "case_id": case.case_id,
        "title": case.title,
        "category": case.category,
        "passed_checks": passed,
        "total_checks": len(checks),
        "check_pass_rate": round(passed / len(checks), 4),
        "case_passed": passed >= 5,
        "parsed_endpoint_count": len(parsed_paths),
        "scenario_count": len(scenarios),
        "dsl_step_count": len(steps),
        "assertion_count": _assertion_count(steps),
        **checks,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_checks = sum(row["total_checks"] for row in rows)
    passed_checks = sum(row["passed_checks"] for row in rows)
    by_category: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = by_category.setdefault(row["category"], {"case_count": 0, "passed_cases": 0, "passed_checks": 0, "total_checks": 0})
        bucket["case_count"] += 1
        bucket["passed_cases"] += int(row["case_passed"])
        bucket["passed_checks"] += row["passed_checks"]
        bucket["total_checks"] += row["total_checks"]
    for bucket in by_category.values():
        bucket["case_pass_rate"] = round(bucket["passed_cases"] / bucket["case_count"], 4)
        bucket["check_pass_rate"] = round(bucket["passed_checks"] / bucket["total_checks"], 4)
    dimensions = ["需求解析", "场景生成", "DSL生成", "接口覆盖", "断言规划", "上下文传递"]
    dimension_summary = {
        name: {
            "passed": sum(1 for row in rows if row[name]),
            "total": len(rows),
            "pass_rate": round(sum(1 for row in rows if row[name]) / len(rows), 4),
        }
        for name in dimensions
    }
    return {
        "total_cases": len(rows),
        "passed_cases": sum(1 for row in rows if row["case_passed"]),
        "case_pass_rate": round(sum(1 for row in rows if row["case_passed"]) / len(rows), 4),
        "passed_checks": passed_checks,
        "total_checks": total_checks,
        "check_pass_rate": round(passed_checks / total_checks, 4),
        "by_category": by_category,
        "dimension_summary": dimension_summary,
    }


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, str]:
    output_dir = ROOT / "platform" / "delivery_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    base = output_dir / f"complex_quality_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    json_path = base.with_suffix(".json")
    csv_path = base.with_suffix(".csv")
    md_path = base.with_suffix(".md")
    json_path.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Complex Quality Evaluation",
        "",
        f"- total_cases: {summary['total_cases']}",
        f"- passed_cases: {summary['passed_cases']}",
        f"- case_pass_rate: {summary['case_pass_rate']:.2%}",
        f"- passed_checks: {summary['passed_checks']}/{summary['total_checks']}",
        f"- check_pass_rate: {summary['check_pass_rate']:.2%}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "md": str(md_path)}


def main() -> None:
    rows = [evaluate(case) for case in CASES]
    summary = summarize(rows)
    outputs = write_outputs(rows, summary)
    print(json.dumps({"summary": summary, "outputs": outputs}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
