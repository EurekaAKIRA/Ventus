"""Task-aware chat helpers for the task Agent."""

from __future__ import annotations

import os
import re
from typing import Any

from platform_shared import (
    ModelEndpointConfig,
    ModelGateway,
    ModelGatewayConfig,
    ModelGatewayError,
    get_requirement_analysis_model_profile,
)


TASK_AGENT_INTENTS = {
    "status_query",
    "failure_diagnosis",
    "assertion_quality",
    "llm_usage",
    "task_import",
    "next_action",
    "general_question",
}


def classify_task_agent_intent(message: str) -> str:
    normalized = str(message or "").strip().lower()
    if any(token in normalized for token in ("llm", "大模型", "模型", "增强", "候选", "过滤", "fallback")):
        return "llm_usage"
    if any(token in normalized for token in ("断言", "assertion", "校验", "检查点", "误杀", "测试质量", "用例质量", "执行质量", "质量评估")):
        return "assertion_quality"
    if any(token in normalized for token in ("导入", "资产", "接口资产", "用例资产", "baseurl", "base url")):
        return "task_import"
    if any(token in normalized for token in ("失败", "报错", "为什么", "原因", "定位", "挂了", "不通过")):
        return "failure_diagnosis"
    if any(token in normalized for token in ("下一步", "怎么修", "怎么办", "建议", "修复", "处理")):
        return "next_action"
    if any(token in normalized for token in ("状态", "进度", "现在", "当前", "执行到哪", "结果", "是否执行", "跑完")):
        return "status_query"
    return "general_question"


def _resolve_task_agent_intent(message: str, agent_payload: dict[str, Any]) -> str:
    intent = classify_task_agent_intent(message)
    if intent == "general_question" and _is_contextual_quality_question(message) and _has_task_agent_context(agent_payload):
        return "assertion_quality"
    if intent != "general_question":
        return intent
    normalized = str(message or "").strip().lower()
    if not any(token in normalized for token in ("继续", "这个", "刚才", "上面", "前面", "然后", "它", "那", "再看", "接着")):
        return intent
    memory = agent_payload.get("conversation_memory") if isinstance(agent_payload.get("conversation_memory"), dict) else {}
    focus_terms = [str(item).strip() for item in memory.get("focus_terms") or [] if str(item).strip()]
    recent_messages = [item for item in memory.get("recent_messages") or [] if isinstance(item, dict)]
    recent_user_intent = _recent_conversation_intent(recent_messages, {"user", "human"})
    if recent_user_intent != "general_question":
        return recent_user_intent
    for term in reversed(focus_terms):
        focus_intent = _intent_from_focus_term(term)
        if focus_intent != "general_question":
            return focus_intent
    recent_assistant_intent = _recent_conversation_intent(recent_messages, {"assistant", "bot"})
    if recent_assistant_intent != "general_question":
        return recent_assistant_intent
    return intent


def _recent_conversation_intent(recent_messages: list[dict[str, Any]], roles: set[str]) -> str:
    for item in reversed(recent_messages[-6:]):
        role = str(item.get("role") or "").strip().lower()
        if role not in roles:
            continue
        previous_intent = classify_task_agent_intent(str(item.get("text") or ""))
        if previous_intent != "general_question":
            return previous_intent
    return "general_question"


def _intent_from_focus_term(term: str) -> str:
    lowered = str(term or "").strip().lower()
    if any(token in lowered for token in ("llm", "大模型", "模型", "候选", "fallback", "过滤")):
        return "llm_usage"
    if any(token in lowered for token in ("断言", "assertion", "校验", "误杀", "测试质量", "用例质量", "执行质量", "质量评估")):
        return "assertion_quality"
    if any(token in lowered for token in ("失败", "报错", "failure", "错误")):
        return "failure_diagnosis"
    if any(token in lowered for token in ("导入", "资产", "baseurl", "base url")):
        return "task_import"
    if any(token in lowered for token in ("下一步", "重跑", "修复", "怎么修")):
        return "next_action"
    if any(token in lowered for token in ("状态", "进度", "当前")):
        return "status_query"
    return "general_question"


def _is_contextual_quality_question(message: str) -> bool:
    normalized = str(message or "").strip().lower()
    if "质量" not in normalized and "quality" not in normalized:
        return False
    if any(token in normalized for token in ("测试", "断言", "用例", "执行", "任务", "脚本", "生成", "报告", "case", "test", "assert")):
        return True
    compact = re.sub(r"[\s?？。！!，,；;：:]+", "", normalized)
    return compact in {"质量如何", "质量怎样", "质量怎么样", "质量好不好", "质量行不行", "质量靠谱不", "quality"}


def _has_task_agent_context(agent_payload: dict[str, Any]) -> bool:
    task_tracking = agent_payload.get("task_tracking") if isinstance(agent_payload.get("task_tracking"), dict) else {}
    if any(
        task_tracking.get(key)
        for key in (
            "task_id",
            "task_name",
            "task_status",
            "execution_status",
            "scenario_total",
            "failed_assertions",
            "failed_steps",
        )
    ):
        return True
    assertion_quality = task_tracking.get("assertion_quality") if isinstance(task_tracking.get("assertion_quality"), dict) else {}
    return bool(assertion_quality.get("total") or assertion_quality.get("generated_by_counts"))


def build_task_agent_context_summary(agent_payload: dict[str, Any], message: str = "") -> dict[str, Any]:
    task_tracking = agent_payload.get("task_tracking") if isinstance(agent_payload.get("task_tracking"), dict) else {}
    summary = agent_payload.get("summary") if isinstance(agent_payload.get("summary"), dict) else {}
    assertion_quality = task_tracking.get("assertion_quality") if isinstance(task_tracking.get("assertion_quality"), dict) else {}
    missing_artifacts = [str(item) for item in task_tracking.get("missing_artifacts") or [] if str(item).strip()]
    conversation_memory = agent_payload.get("conversation_memory") if isinstance(agent_payload.get("conversation_memory"), dict) else {}
    return {
        "intent": _resolve_task_agent_intent(message, agent_payload),
        "task": {
            "task_id": task_tracking.get("task_id"),
            "task_name": task_tracking.get("task_name") or agent_payload.get("suggested_task_name"),
            "task_status": task_tracking.get("task_status"),
            "execution_status": task_tracking.get("execution_status") or "not_started",
            "stage": task_tracking.get("stage") or _infer_stage_from_tracking(task_tracking),
            "environment": task_tracking.get("environment"),
            "target_system": task_tracking.get("target_system") or agent_payload.get("detected_base_url"),
            "execution_base_url": task_tracking.get("execution_base_url"),
            "environment_base_url": task_tracking.get("environment_base_url"),
        },
        "execution": {
            "scenario_total": int(task_tracking.get("scenario_total") or 0),
            "scenario_passed": int(task_tracking.get("scenario_passed") or 0),
            "scenario_failed": int(task_tracking.get("scenario_failed") or 0),
            "failed_steps": (task_tracking.get("failed_steps") or [])[:5],
            "failed_assertions": (task_tracking.get("failed_assertions") or [])[:8],
            "latest_logs": (task_tracking.get("latest_logs") or [])[-5:],
        },
        "assertions": {
            "total": int(assertion_quality.get("total") or 0),
            "passed": int(assertion_quality.get("passed") or 0),
            "failed": int(assertion_quality.get("failed") or 0),
            "pass_rate": assertion_quality.get("pass_rate"),
            "generated_by_counts": assertion_quality.get("generated_by_counts") or {},
            "weak_step_count": int(assertion_quality.get("weak_step_count") or 0),
            "fallback_count": int(assertion_quality.get("fallback_count") or 0),
            "invalid_llm_candidate_count": int(assertion_quality.get("invalid_llm_candidate_count") or 0),
            "invalid_llm_candidates": (assertion_quality.get("invalid_llm_candidates") or [])[:5],
            "llm_filter_reasons": assertion_quality.get("llm_filter_reasons") or {},
            "llm_error_type_counts": assertion_quality.get("llm_error_type_counts") or {},
            "weak_steps": (assertion_quality.get("weak_steps") or [])[:6],
        },
        "analysis": {
            "validation_passed": task_tracking.get("validation_passed"),
            "validation_errors": (task_tracking.get("validation_errors") or [])[:5],
            "validation_warnings": (task_tracking.get("validation_warnings") or [])[:5],
            "analysis_findings": (task_tracking.get("analysis_findings") or [])[:5],
            "failure_reasons": (task_tracking.get("failure_reasons") or [])[:5],
            "missing_artifacts": missing_artifacts,
        },
        "draft": {
            "requirement_chars": int(summary.get("requirement_chars") or 0),
            "recognized_endpoints": (agent_payload.get("recognized_endpoints") or [])[:10],
            "coverage_gaps": (agent_payload.get("coverage_gaps") or [])[:8],
            "risk_priorities": (agent_payload.get("risk_priorities") or [])[:5],
            "next_actions": (agent_payload.get("next_actions") or [])[:5],
        },
        "memory": {
            "focus_terms": (conversation_memory.get("focus_terms") or [])[-6:],
            "mentioned_task_ids": (conversation_memory.get("mentioned_task_ids") or [])[-3:],
            "recent_messages": (conversation_memory.get("recent_messages") or [])[-4:],
        },
    }


def build_task_agent_contextual_reply(message: str, agent_payload: dict[str, Any]) -> str:
    context = build_task_agent_context_summary(agent_payload, message)
    intent = context["intent"]
    task = context["task"]
    execution = context["execution"]
    assertions = context["assertions"]
    analysis = context["analysis"]
    draft = context["draft"]
    has_task_context = bool(task.get("task_id") or task.get("task_name") or execution.get("scenario_total") or assertions.get("total"))
    if intent == "general_question" and _is_contextual_quality_question(message) and not has_task_context:
        return "你问的“质量”还缺对象：是测试质量、断言质量、生成质量，还是某段代码/文档质量？给我对象后我再按证据评，不直接套任务模板。"
    if not has_task_context and intent != "general_question":
        return _reply_missing_context(intent)
    if analysis.get("missing_artifacts") and _missing_artifacts_block_reply(intent, context):
        return _reply_missing_artifacts(context)
    if intent == "status_query":
        return _reply_status(context)
    if intent == "failure_diagnosis":
        return _reply_failure_diagnosis(context)
    if intent == "assertion_quality":
        return _reply_assertion_quality(context)
    if intent == "llm_usage":
        return _reply_llm_usage(context)
    if intent == "task_import":
        return _reply_task_import(context)
    if intent == "next_action":
        return _reply_next_action(context)
    return ""


def build_llm_task_agent_chat_reply(message: str, agent_payload: dict[str, Any]) -> str | None:
    config = _TaskAgentChatLLMConfig.from_env()
    if config is None:
        return None
    context_summary = build_task_agent_context_summary(agent_payload, message)
    prompt = {
        "user_message": str(message or "").strip(),
        "task_context_summary": context_summary,
        "task_draft_agent_payload": _compact_agent_payload(agent_payload),
        "output_schema": {"reply": "string"},
        "constraints": [
            "Return strict JSON only",
            "Use Chinese",
            "Start with a clear conclusion, then evidence, then next action",
            "Use the task_context_summary as the source of truth for task status, failures, assertions, and missing artifacts",
            "Do not invent execution results, assertion failures, or LLM usage that are not present in the context",
            "When data is missing, say exactly which artifact or field is missing",
            "Avoid scripted greetings and generic customer-service wording",
            "Keep the reply to 3-6 concise points unless the user asks for detail",
            "Do not claim the task has been created unless the user explicitly used the page creation workflow",
        ],
    }
    try:
        response = config.gateway.chat_json(
            system_prompt=(
                "You are a task-aware API testing copilot. "
                "You diagnose task execution, assertion quality, LLM usage, imports, and next actions from structured evidence. "
                "Be natural, direct, and evidence-based. "
                "Return strict JSON only."
            ),
            user_payload=prompt,
            temperature=0.2,
        )
    except ModelGatewayError:
        return None
    except Exception:
        return None
    reply = str(response.get("reply") or "").strip()
    return reply or None


def _infer_stage_from_tracking(task_tracking: dict[str, Any]) -> str:
    execution_status = str(task_tracking.get("execution_status") or "").strip()
    task_status = str(task_tracking.get("task_status") or "").strip()
    if execution_status and execution_status not in {"not_started", "pending"}:
        return "execution"
    if task_status in {"generated", "passed", "failed", "stopped"}:
        return "dsl"
    if task_status == "parsed":
        return "parsed"
    if task_status == "received":
        return "received"
    return task_status or "unknown"


def _reply_missing_context(intent: str) -> str:
    if intent == "assertion_quality":
        return "我还没拿到当前任务的 DSL 或执行结果，所以不能判断断言质量。请先选中任务或传入 task_id，我需要 assertion_summary/test_case_dsl 里的 generated_by、弱断言和失败明细。"
    if intent == "failure_diagnosis":
        return "我还没拿到当前任务的 execution_result，不能编造失败原因。请先选中任务或传入 task_id，我会读取失败步骤、断言 expected/actual 和最新日志后再定位。"
    return "我还没接到具体 task_id 或任务上下文。先选中任务后再问，我就能跟踪解析、DSL、执行、断言和报告。"


def _reply_missing_artifacts(context: dict[str, Any]) -> str:
    missing = [str(item) for item in context["analysis"].get("missing_artifacts") or [] if str(item).strip()]
    stage = context["task"].get("stage") or "unknown"
    return (
        f"当前卡在 {stage} 阶段，缺少这些数据：{', '.join(missing[:4])}。"
        "我不会猜执行结论；先生成/刷新这些产物后，再看失败步骤、断言质量和修复建议。"
    )


def _missing_artifacts_block_reply(intent: str, context: dict[str, Any]) -> bool:
    execution = context["execution"]
    assertions = context["assertions"]
    task = context["task"]
    if intent == "failure_diagnosis":
        return not (execution.get("failed_assertions") or execution.get("failed_steps") or int(execution.get("scenario_failed") or 0))
    if intent == "assertion_quality":
        return int(assertions.get("total") or 0) <= 0
    if intent == "llm_usage":
        return not (
            int(assertions.get("invalid_llm_candidate_count") or 0)
            or int(assertions.get("fallback_count") or 0)
            or assertions.get("llm_error_type_counts")
            or assertions.get("llm_filter_reasons")
            or assertions.get("invalid_llm_candidates")
            or (assertions.get("generated_by_counts") or {}).get("llm")
            or (assertions.get("generated_by_counts") or {}).get("llm_repair")
        )
    if intent == "status_query":
        return False
    if intent == "task_import":
        return False
    if intent == "next_action":
        return False
    return True


def _reply_status(context: dict[str, Any]) -> str:
    task = context["task"]
    execution = context["execution"]
    assertions = context["assertions"]
    status = str(task.get("execution_status") or "not_started")
    total = int(execution.get("scenario_total") or 0)
    passed = int(execution.get("scenario_passed") or 0)
    failed = int(execution.get("scenario_failed") or 0)
    name = task.get("task_name") or task.get("task_id") or "当前任务"
    if status == "passed":
        passed_brief = _format_status_passed_brief(context)
        return f"{name} 已执行通过：阶段 {task.get('stage') or 'execution'}，场景 {passed}/{total}，断言 {assertions.get('passed')}/{assertions.get('total')}。{passed_brief}"
    if status == "failed" or failed:
        failure_brief = _format_status_failure_brief(context)
        return (
            f"{name} 当前失败：阶段 {task.get('stage') or 'execution'}，场景 {passed}/{total} 通过，失败 {failed} 个；"
            f"断言失败 {assertions.get('failed')} 条。{failure_brief}"
        )
    if status == "running":
        return f"{name} 正在执行：目前收到 {total} 个场景结果，通过 {passed} 个、失败 {failed} 个。等执行收口后再判断断言质量，避免中途日志误导。"
    return f"{name} 尚未执行：没有执行结果，阶段是 {task.get('stage') or 'unknown'}。可以先生成 DSL 并执行冒烟链路。"


def _format_status_passed_brief(context: dict[str, Any]) -> str:
    assertions = context["assertions"]
    draft = context["draft"]
    quality_notes: list[str] = []
    weak = int(assertions.get("weak_step_count") or 0)
    fallback = int(assertions.get("fallback_count") or 0)
    invalid = int(assertions.get("invalid_llm_candidate_count") or 0)
    if weak:
        quality_notes.append(f"弱断言步骤 {weak} 个")
    if fallback:
        quality_notes.append(f"fallback {fallback} 条")
    if invalid:
        quality_notes.append(f"LLM 被过滤候选 {invalid} 条")
    quality_text = "质量提醒：" + "、".join(quality_notes) + "。" if quality_notes else "质量提醒：当前没有明显失败或弱断言信号。"
    gaps = [str(item) for item in draft.get("coverage_gaps") or [] if str(item).strip()]
    if gaps:
        return f"{quality_text}覆盖缺口：{'；'.join(gaps[:2])}。下一步先补这些缺口，再沉淀为用例资产。"
    if weak or fallback or invalid:
        return f"{quality_text}{_suggest_passed_quality_next_action(weak, fallback, invalid)}"
    return f"{quality_text}下一步可以补边界参数、权限失败、资源不存在和删除后读取，再沉淀为用例资产。"


def _suggest_passed_quality_next_action(weak: int, fallback: int, invalid: int) -> str:
    if weak and (fallback or invalid):
        return "下一步先补强弱断言，并补齐 LLM 过滤/fallback 原因，再沉淀为回归资产。"
    if weak:
        return "下一步先补强弱断言，把状态码/存在性校验升级为关键字段、业务状态和上下文一致性校验。"
    if invalid:
        return "下一步先补齐 LLM 候选过滤明细和原因，再判断是 prompt 信息不足、候选格式错误还是质量门过严。"
    return "下一步先降低 fallback 占比，补响应样例、字段语义和业务预期，让 LLM 断言重新进入监督链路。"


def _format_status_failure_brief(context: dict[str, Any]) -> str:
    execution = context["execution"]
    failed_assertions = [item for item in execution.get("failed_assertions") or [] if isinstance(item, dict)]
    if not failed_assertions:
        failed_steps = [item for item in execution.get("failed_steps") or [] if isinstance(item, dict)]
        if failed_steps:
            first_step = failed_steps[0]
            detail = first_step.get("message") or first_step.get("text") or first_step.get("step_id") or "失败步骤缺少 message"
            return f"当前只有失败步骤线索：{detail}。下一步补 failure_details 后再判断根因。"
        return "当前缺失败断言明细，下一步先补 execution_result.scenario_results[*].steps[*].assertion_summary.failure_details。"
    failure_groups = _rank_failure_groups_with_context(_group_failed_assertions(failed_assertions), context)
    primary_group = failure_groups[0] if failure_groups else {"examples": failed_assertions}
    first = primary_group["examples"][0]
    kind = _classify_failure_kind(first)
    source = first.get("source") or "-"
    op = first.get("op") or "-"
    expected = first.get("expected")
    actual = first.get("actual")
    location = _failure_scope_label([first]) or "-"
    return (
        f"初判是{kind}，代表断言 {source} {op} {expected!r}，实际 {actual!r}，位置 {location}。"
        f"{_suggest_failure_fix(first)}"
    )


def _reply_failure_diagnosis(context: dict[str, Any]) -> str:
    execution = context["execution"]
    assertions = context["assertions"]
    failed_assertions = [item for item in execution.get("failed_assertions") or [] if isinstance(item, dict)]
    failed_steps = [item for item in execution.get("failed_steps") or [] if isinstance(item, dict)]
    reasons = [str(item) for item in context["analysis"].get("failure_reasons") or [] if str(item).strip()]
    if failed_assertions:
        failure_groups = _rank_failure_groups_with_context(_group_failed_assertions(failed_assertions), context)
        primary_group = failure_groups[0] if failure_groups else {"count": 1, "examples": failed_assertions}
        first = primary_group["examples"][0]
        source = first.get("source") or "-"
        op = first.get("op") or "-"
        expected = first.get("expected")
        actual = first.get("actual")
        kind = _classify_failure_kind(first)
        fix = _suggest_failure_fix(first)
        group_hint = _format_failure_group_summary(failure_groups)
        evidence_hint = _format_failure_evidence(primary_group)
        return (
            f"这次主要像是{kind}。代表断言：{source} {op} {expected!r}，实际是 {actual!r}。"
            f"位置：{first.get('scenario') or '-'} / {first.get('step') or first.get('step_name') or '-'}。"
            f"{group_hint}{evidence_hint}{fix}"
        )
    if failed_steps:
        first = failed_steps[0]
        detail = first.get("message") or first.get("text") or first.get("step_id") or "失败步骤缺少 message"
        return f"执行失败但没有拿到结构化断言明细。当前失败步骤：{detail}。下一步先打开 execution_result 的 assertion_summary.failure_details，否则只能按日志排查。"
    if reasons:
        return "失败原因摘要：" + "；".join(reasons[:3]) + "。下一步建议回到对应失败步骤核对请求、响应和断言。"
    if int(assertions.get("failed") or 0) == 0:
        return "我没看到失败断言或失败步骤。若 UI 显示失败，可能是执行状态没有刷新或缺 execution_result 明细；先刷新任务详情再看。"
    return "执行结果里显示有失败，但缺少失败步骤和断言明细。需要补全 execution_result.scenario_results[*].steps[*].assertion_summary.failure_details。"


def _reply_assertion_quality(context: dict[str, Any]) -> str:
    assertions = context["assertions"]
    total = int(assertions.get("total") or 0)
    if total <= 0:
        return "当前没有可统计的断言。需要先生成 DSL 或执行一次任务，才能看 rules/llm、弱断言和误杀风险。"
    counts = assertions.get("generated_by_counts") or {}
    failed = int(assertions.get("failed") or 0)
    weak = int(assertions.get("weak_step_count") or 0)
    invalid = int(assertions.get("invalid_llm_candidate_count") or 0)
    llm_count = int(counts.get("llm") or 0) + int(counts.get("llm_repair") or 0)
    test_quality = _format_test_quality_verdict(context, failed, weak, invalid)
    risk = _format_assertion_false_positive_risk(context, failed, llm_count)
    weak_detail = _format_weak_step_summary(assertions.get("weak_steps") or [], weak)
    next_action = _suggest_assertion_quality_next_action(context, failed, weak, invalid)
    return (
        f"{test_quality}"
        f"断言质量：{assertions.get('passed')}/{total} 通过，失败 {failed} 条。{risk}"
        f"来源分布：rules={counts.get('rules', 0)}，llm={counts.get('llm', 0)}，llm_repair={counts.get('llm_repair', 0)}，manual={counts.get('manual', 0)}。"
        f"弱断言步骤 {weak} 个，fallback {assertions.get('fallback_count', 0)} 条，LLM 被过滤候选 {invalid} 条。"
        f"{weak_detail}{next_action}"
    )


def _format_test_quality_verdict(context: dict[str, Any], failed: int, weak: int, invalid: int) -> str:
    task = context["task"]
    execution = context["execution"]
    draft = context["draft"]
    total = int(execution.get("scenario_total") or 0)
    passed = int(execution.get("scenario_passed") or 0)
    failed_scenarios = int(execution.get("scenario_failed") or 0)
    gaps = [str(item) for item in draft.get("coverage_gaps") or [] if str(item).strip()]
    fallback = int(context["assertions"].get("fallback_count") or 0)
    status = str(task.get("execution_status") or "not_started")
    quality_debits = failed_scenarios + weak + fallback + invalid + len(gaps)

    if status in {"not_started", "pending", ""} and total <= 0:
        return "测试质量：暂不能定级，当前没有执行结果；只能先看 DSL 和断言规划。"
    if failed_scenarios:
        level = "偏弱" if quality_debits >= 3 else "中等偏弱"
        reason = f"场景 {passed}/{total} 通过，仍有 {failed_scenarios} 个失败场景"
    elif weak or fallback or invalid or gaps:
        level = "中等"
        reason_parts: list[str] = []
        if total:
            reason_parts.append(f"场景 {passed}/{total} 通过")
        if weak:
            reason_parts.append(f"弱断言步骤 {weak} 个")
        if fallback:
            reason_parts.append(f"规则兜底 {fallback} 条")
        if invalid:
            reason_parts.append(f"LLM 过滤候选 {invalid} 条")
        if gaps:
            reason_parts.append(f"覆盖缺口 {len(gaps)} 项")
        reason = "，".join(reason_parts)
    else:
        level = "较好"
        reason = f"场景 {passed}/{total} 通过，暂未看到失败、弱断言或覆盖缺口" if total else "DSL 中已有断言，但还缺执行样本"

    gap_text = f"覆盖提醒：{'；'.join(gaps[:2])}。" if gaps else ""
    return f"测试质量：{level}，{reason}。{gap_text}"


def _reply_llm_usage(context: dict[str, Any]) -> str:
    assertions = context["assertions"]
    counts = assertions.get("generated_by_counts") or {}
    llm_direct = int(counts.get("llm") or 0)
    llm_repair = int(counts.get("llm_repair") or 0)
    llm_total = llm_direct + llm_repair
    invalid = int(assertions.get("invalid_llm_candidate_count") or 0)
    fallback = int(assertions.get("fallback_count") or 0)
    errors = assertions.get("llm_error_type_counts") or {}
    if llm_total or invalid or fallback or errors:
        error_text = _format_llm_error_summary(errors)
        filter_text = _format_llm_filter_detail(
            assertions.get("invalid_llm_candidates") or [],
            assertions.get("llm_filter_reasons") or {},
            invalid,
        )
        verdict = _llm_supervision_verdict(llm_total, invalid, fallback, errors)
        return (
            f"LLM 监督还在：直接保留 {llm_direct} 条，修复后保留 {llm_repair} 条，fallback {fallback} 条，质量门过滤 {invalid} 条。"
            f"{error_text}{filter_text}{verdict}"
        )
    return "当前任务里没看到 LLM 断言或 LLM 候选统计。可能是本轮未开启增强，或 DSL 里没有 assertion_quality 元数据。"


def _format_llm_error_summary(errors: dict[str, Any]) -> str:
    if not errors:
        return "错误类型统计：无。"
    parts = [f"{key}={int(value or 0)}" for key, value in sorted(errors.items()) if int(value or 0) > 0]
    return "错误类型统计：" + ("，".join(parts) if parts else "无") + "。"


def _format_llm_filter_detail(candidates: list[Any], reasons: dict[str, Any], invalid: int = 0) -> str:
    details: list[str] = []
    for item in candidates[:3]:
        if not isinstance(item, dict):
            continue
        step = item.get("step") or "-"
        source = item.get("source") or item.get("candidate") or "候选"
        reason = item.get("reason") or item.get("error_type") or item.get("message") or "未给出原因"
        details.append(f"{step}: {source} -> {reason}")
    if details:
        suffix = "等" if len(candidates) > len(details) else ""
        return "过滤明细：" + "；".join(details) + suffix + "。"
    reason_parts = [f"{key}={int(value or 0)}" for key, value in sorted(reasons.items()) if int(value or 0) > 0]
    if reason_parts:
        return "过滤原因：" + "，".join(reason_parts) + "。"
    if invalid > 0:
        return (
            "过滤明细缺失：当前只有过滤数量，缺 invalid_llm_candidates 或 llm_filter_reasons；"
            "需要上游记录 step/source/op/reason，才能判断是 prompt 信息不足、候选格式错误还是质量门过严。"
        )
    return ""


def _llm_supervision_verdict(llm_total: int, invalid: int, fallback: int, errors: dict[str, Any]) -> str:
    if invalid and llm_total:
        return "判断：LLM 有参与，但质量门拦下了部分不可信候选，适合先看过滤原因而不是关闭 LLM。"
    if invalid and not llm_total:
        return "判断：LLM 产出基本没通过质量门，优先检查 prompt 输入信息是否不足或候选格式是否不合法。"
    if fallback and not llm_total:
        return "判断：当前主要靠规则兜底，LLM 没形成可采纳断言，需要补充响应样例、字段含义或业务预期。"
    if errors:
        return "判断：LLM 调用或候选解析出现异常，先看错误类型，再决定是否重试或降级。"
    return "判断：LLM 断言已进入监督链路，目前没看到明显过滤或 fallback 风险。"


def _format_assertion_false_positive_risk(context: dict[str, Any], failed: int, llm_count: int) -> str:
    execution = context.get("execution") if isinstance(context.get("execution"), dict) else {}
    failed_assertions = [item for item in execution.get("failed_assertions") or [] if isinstance(item, dict)]
    if failed <= 0:
        return "误杀风险：低，当前没有失败断言。"
    if not failed_assertions:
        if llm_count:
            return "误杀风险：未知，缺少 failure_details，先补 source/op/expected/actual 再判断是不是 LLM 误杀。"
        return "误杀风险：未知，缺少失败断言明细。"

    llm_failed = [item for item in failed_assertions if str(item.get("generated_by") or "").lower() in {"llm", "llm_repair"}]
    path_failed = [
        item
        for item in failed_assertions
        if str(item.get("source") or "").startswith("json.") and item.get("actual") is None
    ]
    status_failed = [item for item in failed_assertions if str(item.get("source") or "").lower() == "status_code"]
    status_codes = [_coerce_status_code(item.get("actual")) for item in status_failed]
    hard_status_codes = [code for code in status_codes if code in {400, 401, 403, 404, 422} or (code is not None and code >= 500)]

    if status_failed and len(status_failed) >= len(failed_assertions) / 2 and hard_status_codes:
        code_text = "/".join(str(code) for code in sorted(set(hard_status_codes))[:4])
        return f"误杀风险：低到中，失败主要是 status_code 实际 {code_text}，更像接口、鉴权、契约或环境问题，不建议先删断言。"
    if llm_failed and path_failed:
        return f"误杀风险：高，{len(path_failed)} 条失败集中在 JSON 路径/字段存在性，且有 LLM 断言参与；先核对真实响应体字段路径。"
    if llm_failed:
        return f"误杀风险：中，失败里有 {len(llm_failed)} 条 LLM/修复断言；需要逐条核对 expected/actual 是否符合业务语义。"
    return "误杀风险：低，失败主要来自规则或手工断言，优先按接口行为和测试数据排查。"


def _suggest_assertion_quality_next_action(context: dict[str, Any], failed: int, weak: int, invalid: int) -> str:
    execution = context.get("execution") if isinstance(context.get("execution"), dict) else {}
    failed_assertions = [item for item in execution.get("failed_assertions") or [] if isinstance(item, dict)]
    if failed > 0 and not failed_assertions:
        return "下一步先补 execution_result 的 failure_details，再判断是断言误杀还是接口真实失败。"

    llm_failed = [item for item in failed_assertions if str(item.get("generated_by") or "").lower() in {"llm", "llm_repair"}]
    path_failed = [
        item
        for item in failed_assertions
        if str(item.get("source") or "").startswith("json.") and item.get("actual") is None
    ]
    status_failed = [item for item in failed_assertions if str(item.get("source") or "").lower() == "status_code"]
    status_codes = [_coerce_status_code(item.get("actual")) for item in status_failed]
    hard_status_codes = [code for code in status_codes if code in {400, 401, 403, 404, 422} or (code is not None and code >= 500)]

    if status_failed and len(status_failed) >= max(1, len(failed_assertions) / 2) and hard_status_codes:
        return "下一步先修请求/鉴权/环境和测试数据，不要先删断言；修完后只回归同类 status_code 失败。"
    if llm_failed and path_failed:
        first = path_failed[0]
        source = first.get("source") or "JSON 路径"
        location = _failure_scope_label([first]) or "失败步骤"
        return f"下一步先打开 {location} 的实际响应体，核对 {source} 是否存在或命名是否变化；字段存在就修断言 source，字段不存在再修接口或测试数据。"
    if llm_failed:
        return "下一步逐条核对 LLM/修复断言的 expected、actual 和业务语义；接口返回合理就调断言，不合理再修请求或接口。"
    if weak > 0:
        return "下一步优先看弱断言步骤是否只校验状态码/JSON 存在，再补字段值和上下文一致性。"
    if invalid > 0:
        return "下一步先看 LLM 候选过滤原因，补充响应样例、字段含义或业务预期，再重新生成断言。"
    return "下一步按失败步骤核对请求、响应和断言；通过后再补边界、权限和异常链路。"


def _format_weak_step_summary(weak_steps: list[Any], weak_count: int) -> str:
    if weak_count <= 0:
        return ""
    details: list[str] = []
    for item in weak_steps[:3]:
        if not isinstance(item, dict):
            continue
        scenario = item.get("scenario") or "-"
        step = item.get("step") or "-"
        reasons = [str(reason) for reason in item.get("reasons") or [] if str(reason).strip()]
        reason_text = f"（{'; '.join(reasons[:2])}）" if reasons else ""
        details.append(f"{scenario}/{step}{reason_text}")
    if details:
        suffix = "等" if weak_count > len(details) else ""
        return "弱点集中在：" + "；".join(details) + suffix + "。"
    return "弱断言缺少步骤明细，建议补充 assertion_summary.quality_reasons。"


def _reply_task_import(context: dict[str, Any]) -> str:
    task = context["task"]
    environment = str(task.get("environment") or "").strip()
    target_system = str(task.get("target_system") or "").strip()
    execution_base_url = str(task.get("execution_base_url") or "").strip()
    environment_base_url = str(task.get("environment_base_url") or "").strip()
    env_text = environment or "未指定"
    if execution_base_url:
        mismatch = ""
        if target_system and _normalize_base_url_text(target_system) != _normalize_base_url_text(execution_base_url):
            mismatch = f"注意：任务目标系统是 {target_system}，和执行 Base URL 不一致，执行前要确认环境选择。"
        return (
            f"Base URL 已进入执行上下文：{execution_base_url}，环境是 {env_text}。"
            "接口资产会沉淀 endpoint、请求/响应 schema；用例资产会沉淀场景、步骤、断言和上下文变量。"
            f"{mismatch}下一步可以直接导入资产并用同一环境做调试/执行。"
        )
    if environment_base_url:
        mismatch = ""
        if target_system and _normalize_base_url_text(target_system) != _normalize_base_url_text(environment_base_url):
            mismatch = f"注意：任务目标系统是 {target_system}，和环境 Base URL 不一致，导入前要确认用哪个地址。"
        return (
            f"环境 {env_text} 已配置 Base URL：{environment_base_url}，但 DSL metadata.execution.base_url 还没写入。"
            "导入资产后调试/执行可以从环境管理自动带出这个地址。"
            f"{mismatch}更稳的做法是生成/保存 DSL 时同步写入 metadata.execution.base_url。"
        )
    if _looks_like_base_url(target_system):
        return (
            f"已识别任务目标系统 {target_system}，但 DSL 执行上下文里还没看到 metadata.execution.base_url。"
            "导入资产时可以用 task.target_system 兜底，但更稳的是把它同步写入环境管理的 base_url 或 DSL metadata.execution.base_url。"
            "这样接口资产调试、用例资产执行和任务重跑会走同一地址。"
        )
    if environment:
        return (
            f"当前只有环境 {environment}，没看到可执行 Base URL。"
            "导入按钮能沉淀接口/用例资产，但自动执行还需要环境管理配置 base_url，或资产/DSL 写入 metadata.execution.base_url。"
            "否则后续接口调试和用例资产执行仍会要求手填 Base URL。"
        )
    return (
        "当前任务还没识别到环境和 Base URL。"
        "接口资产负责沉淀 endpoint、请求字段、响应字段和 Base URL；用例资产负责沉淀可执行场景、步骤、断言和上下文变量。"
        "要让导入后自动执行，先在需求、环境管理或 DSL metadata.execution.base_url 里补目标地址。"
    )


def _looks_like_base_url(value: str) -> bool:
    return bool(re.match(r"^https?://[^/\s]+", str(value or "").strip(), flags=re.IGNORECASE))


def _normalize_base_url_text(value: str) -> str:
    return str(value or "").strip().rstrip("/").lower()


def _reply_next_action(context: dict[str, Any]) -> str:
    task = context["task"]
    execution = context["execution"]
    assertions = context["assertions"]
    failed_assertions = [item for item in execution.get("failed_assertions") or [] if isinstance(item, dict)]
    if task.get("execution_status") == "failed" or int(execution.get("scenario_failed") or 0):
        if failed_assertions:
            failure_groups = _rank_failure_groups_with_context(_group_failed_assertions(failed_assertions), context)
            primary_group = failure_groups[0] if failure_groups else {"examples": failed_assertions}
            first = primary_group["examples"][0]
            return f"下一步先修第一类根因：{_classify_failure_kind(first)}。{_suggest_failure_fix(first)}修完后只回归失败场景，确认同类断言是否一起恢复。"
        return "下一步别急着重跑：先定位第一个失败步骤，核对请求参数/鉴权/响应状态，再看失败断言 expected/actual；修完后只回归失败链路。"
    if int(assertions.get("weak_step_count") or 0):
        return "下一步建议补强弱断言：把只校验状态码、JSON 存在的步骤升级为关键字段、业务状态和上下文一致性校验。"
    if int(assertions.get("invalid_llm_candidate_count") or 0):
        if assertions.get("invalid_llm_candidates") or assertions.get("llm_filter_reasons"):
            return "下一步先看 LLM 候选过滤原因：补响应样例、字段含义和业务预期，再重新生成断言，不要直接关闭 LLM 监督。"
        return "下一步先补 LLM 候选过滤明细：让上游写入 invalid_llm_candidates 或 llm_filter_reasons，至少包含 step/source/op/reason，再判断是 prompt 信息不足、候选格式错误还是质量门过严。"
    if int(assertions.get("fallback_count") or 0):
        return "下一步先降低规则兜底占比：补充响应样例、字段语义和业务预期，让 LLM 能生成可采纳断言，再回归确认 fallback 是否下降。"
    if task.get("execution_status") == "passed":
        return "下一步可以扩大覆盖：补边界参数、权限失败、资源不存在、重复提交和删除后读取验证，然后沉淀为用例资产。"
    return "下一步先确认 Base URL/环境和 DSL 是否生成；具备执行条件后先跑主链路冒烟，再根据失败结果做精修。"


def _classify_failure_kind(failure: dict[str, Any]) -> str:
    kind = str(failure.get("failure_kind") or "").lower()
    source = str(failure.get("source") or "").lower()
    actual = failure.get("actual")
    actual_code = _coerce_status_code(actual)
    if "shape" in kind or (source.startswith("json.") and actual is None):
        return "断言路径或响应结构不匹配"
    if source == "status_code":
        if actual_code in {401, 403}:
            return "鉴权或登录态问题"
        if actual_code in {400, 422}:
            return "请求参数或数据契约问题"
        if actual_code == 404:
            return "接口路径、资源 ID 或前置数据问题"
        if actual_code and actual_code >= 500:
            return "服务端异常或执行环境问题"
        return "接口状态码或环境/鉴权问题"
    if source.startswith("context."):
        return "上下文变量传递问题"
    return "业务断言不满足"


def _group_failed_assertions(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for failure in failures:
        kind = _classify_failure_kind(failure)
        group = groups.setdefault(kind, {"kind": kind, "count": 0, "examples": [], "order": len(groups)})
        group["count"] += 1
        if len(group["examples"]) < 2:
            group["examples"].append(failure)
    return sorted(groups.values(), key=lambda item: (-int(item["count"]), int(item["order"])))


def _rank_failure_groups_with_context(groups: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for group in groups:
        item = dict(group)
        evidence = _collect_failure_evidence(str(item.get("kind") or ""), context, item.get("examples") or [])
        item["evidence"] = evidence
        scoped_hits = sum(1 for value in evidence if str(value).startswith("关联步骤 "))
        item["evidence_score"] = len(evidence) + scoped_hits * 2
        ranked.append(item)
    return sorted(
        ranked,
        key=lambda item: (-int(item.get("count") or 0), -int(item.get("evidence_score") or 0), int(item.get("order") or 0)),
    )


def _collect_failure_evidence(kind: str, context: dict[str, Any], failures: list[dict[str, Any]] | None = None) -> list[str]:
    keywords = {
        "鉴权或登录态问题": ("401", "403", "unauthorized", "forbidden", "authorization", "auth", "token", "session", "鉴权", "权限", "登录态"),
        "请求参数或数据契约问题": ("400", "422", "validation", "schema", "required", "missing", "invalid", "payload", "字段", "必填", "枚举", "参数", "契约"),
        "接口路径、资源 ID 或前置数据问题": ("404", "not found", "path", "resource", "路径", "资源", "不存在", "未找到"),
        "服务端异常或执行环境问题": ("500", "502", "503", "504", "timeout", "connection", "refused", "unavailable", "超时", "连接", "环境", "服务"),
        "上下文变量传递问题": ("context", "variable", "extract", "变量", "提取", "上下文", "空值"),
        "断言路径或响应结构不匹配": ("json", "path", "field", "missing field", "null", "none", "字段", "结构", "响应"),
        "业务断言不满足": ("expected", "actual", "业务", "不一致", "预期", "实际"),
    }.get(kind, ())
    if not keywords:
        return []
    scoped_evidence: list[str] = []
    general_evidence: list[str] = []
    scoped_limit = 3
    general_limit = 3
    for item in _iter_context_evidence_items(context):
        text = _stringify_evidence_item(item)
        if not text:
            continue
        normalized = text.lower()
        if not any(keyword.lower() in normalized for keyword in keywords):
            continue
        if _evidence_matches_failure_scope(item, text, failures or []):
            scoped_evidence.append(_format_scoped_failure_evidence(item, text, failures or []))
        else:
            general_evidence.append(text[:140])
        if len(scoped_evidence) >= scoped_limit and len(general_evidence) >= general_limit:
            break
    return (scoped_evidence + general_evidence)[:3]


def _iter_context_evidence_text(context: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for item in _iter_context_evidence_items(context):
        text = _stringify_evidence_item(item)
        if text:
            texts.append(text)
    return texts


def _iter_context_evidence_items(context: dict[str, Any]) -> list[Any]:
    execution = context.get("execution") if isinstance(context.get("execution"), dict) else {}
    analysis = context.get("analysis") if isinstance(context.get("analysis"), dict) else {}
    items: list[Any] = []
    items.extend(execution.get("latest_logs") or [])
    items.extend(analysis.get("failure_reasons") or [])
    items.extend(analysis.get("analysis_findings") or [])
    items.extend(analysis.get("validation_errors") or [])
    items.extend(analysis.get("validation_warnings") or [])
    return items


def _stringify_evidence_item(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        parts: list[str] = []
        for key in ("message", "text", "detail", "reason", "error", "summary", "event"):
            value = item.get(key)
            if value not in (None, ""):
                parts.append(str(value))
        if not parts:
            parts = [f"{key}={value}" for key, value in item.items() if value not in (None, "", [])]
        return " ".join(parts).strip()
    return str(item).strip()


def _evidence_matches_failure_scope(item: Any, text: str, failures: list[dict[str, Any]]) -> bool:
    tokens = _failure_scope_tokens(failures)
    if not tokens:
        return False
    scope_text = text
    if isinstance(item, dict):
        scope_values = [
            item.get(key)
            for key in (
                "scenario",
                "scenario_name",
                "scenario_id",
                "step",
                "step_name",
                "step_id",
                "endpoint",
                "path",
                "url",
                "request",
            )
            if item.get(key) not in (None, "")
        ]
        scope_text = " ".join(str(value) for value in scope_values) + " " + text
    normalized = scope_text.lower()
    return any(token.lower() in normalized for token in tokens)


def _failure_scope_tokens(failures: list[dict[str, Any]]) -> list[str]:
    tokens: list[str] = []
    for failure in failures:
        for key in ("scenario", "scenario_name", "scenario_id", "step", "step_name", "step_id"):
            value = str(failure.get(key) or "").strip()
            if len(value) >= 3:
                tokens.append(value)
                tokens.extend(_extract_endpoint_scope_tokens(value))
    unique: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        lowered = token.lower()
        if lowered not in seen:
            unique.append(token)
            seen.add(lowered)
    return unique


def _extract_endpoint_scope_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for match in re.finditer(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/[^\s，。；;]+)", str(text), flags=re.IGNORECASE):
        method = match.group(1).upper()
        path = match.group(2).rstrip(".,;，。；")
        tokens.append(f"{method} {path}")
        tokens.append(path)
    return tokens


def _format_scoped_failure_evidence(item: Any, text: str, failures: list[dict[str, Any]]) -> str:
    label = _evidence_scope_label(item) or _failure_scope_label(failures)
    prefix = f"关联步骤 {label}: " if label else "关联步骤: "
    return (prefix + text)[:160]


def _evidence_scope_label(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    scenario = item.get("scenario") or item.get("scenario_name") or item.get("scenario_id")
    step = item.get("step") or item.get("step_name") or item.get("step_id") or item.get("endpoint") or item.get("path")
    parts = [str(value).strip() for value in (scenario, step) if str(value or "").strip()]
    return "/".join(parts[:2])


def _failure_scope_label(failures: list[dict[str, Any]]) -> str:
    if not failures:
        return ""
    first = failures[0]
    scenario = first.get("scenario") or first.get("scenario_name") or first.get("scenario_id")
    step = first.get("step") or first.get("step_name") or first.get("step_id")
    parts = [str(value).strip() for value in (scenario, step) if str(value or "").strip()]
    return "/".join(parts[:2])


def _format_failure_group_summary(groups: list[dict[str, Any]]) -> str:
    if not groups:
        return ""
    if len(groups) == 1:
        count = int(groups[0].get("count") or 0)
        return f"同类失败共 {count} 条，先按一个根因收敛。 " if count > 1 else ""
    parts = [f"{item.get('kind')} {int(item.get('count') or 0)} 条" for item in groups[:4]]
    return "失败聚类：" + "；".join(parts) + "。"


def _format_failure_evidence(group: dict[str, Any]) -> str:
    evidence = [str(item) for item in group.get("evidence") or [] if str(item).strip()]
    if not evidence:
        return ""
    return "证据补充：" + "；".join(evidence[:2]) + "。"


def _suggest_failure_fix(failure: dict[str, Any]) -> str:
    source = str(failure.get("source") or "").lower()
    actual = failure.get("actual")
    actual_code = _coerce_status_code(actual)
    if source == "status_code":
        if actual_code in {401, 403}:
            return "先检查登录步骤是否产出 token/session、Authorization 是否被后续步骤继承，以及环境账号权限是否足够。"
        if actual_code in {400, 422}:
            return "先对照接口资产里的请求 schema，检查必填字段、枚举值、Content-Type 和上下文变量是否为空。"
        if actual_code == 404:
            return "先确认 Base URL、接口路径和资源 ID 来源；如果是依赖上一步创建资源，检查上下文提取是否成功。"
        if actual_code and actual_code >= 500:
            return "先看最新服务日志和环境健康状态；这类失败更像接口或环境不稳定，不宜直接放宽断言。"
        return "先核对实际状态码对应的请求、鉴权和环境，再决定是修接口输入还是调整断言预期。"
    if source.startswith("json.") and failure.get("actual") is None:
        return "先打开实际响应体，确认字段路径是否变更；如果字段不存在，优先修断言路径或补上前置数据。"
    if source.startswith("context."):
        return "先检查上游步骤的提取表达式和变量名，确认当前步骤读取到的上下文不是空值或旧值。"
    return "先核对 expected 和 actual 的业务含义；如果接口返回合理，调整断言，如果返回不合理，回到请求数据和接口逻辑。"


def _coerce_status_code(value: Any) -> int | None:
    try:
        code = int(value)
    except (TypeError, ValueError):
        return None
    return code if 100 <= code <= 599 else None


def _compact_agent_payload(agent_payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "reply",
        "summary",
        "diagnostic_verdict",
        "suggested_task_name",
        "detected_base_url",
        "selected_environment",
        "recommended_environment",
        "recognized_endpoints",
        "scenario_outlook",
        "quality_gates",
        "assertion_suggestions",
        "execution_strategy",
        "risk_priorities",
        "agent_handoff",
        "coverage_gaps",
        "risks",
        "warnings",
        "next_actions",
        "knowledge_summary",
        "knowledge_hits",
        "task_tracking",
        "conversation_memory",
    )
    compact = {key: agent_payload.get(key) for key in keys if key in agent_payload}
    if isinstance(compact.get("task_tracking"), dict):
        compact["task_tracking"] = build_task_agent_context_summary({"task_tracking": compact["task_tracking"]})
    if isinstance(compact.get("knowledge_hits"), list):
        compact["knowledge_hits"] = compact["knowledge_hits"][:5]
    if isinstance(compact.get("quality_gates"), list):
        compact["quality_gates"] = compact["quality_gates"][:8]
    if isinstance(compact.get("assertion_suggestions"), list):
        compact["assertion_suggestions"] = compact["assertion_suggestions"][:5]
    if isinstance(compact.get("risk_priorities"), list):
        compact["risk_priorities"] = compact["risk_priorities"][:6]
    if isinstance(compact.get("execution_strategy"), dict):
        compact["execution_strategy"] = {
            **compact["execution_strategy"],
            "phases": (compact["execution_strategy"].get("phases") or [])[:5],
        }
    if isinstance(compact.get("agent_handoff"), dict):
        compact["agent_handoff"] = {
            **compact["agent_handoff"],
            "assertion_intents": (compact["agent_handoff"].get("assertion_intents") or [])[:5],
        }
    return compact


class _TaskAgentChatLLMConfig:
    def __init__(self, gateway: ModelGateway):
        self.gateway = gateway

    @classmethod
    def from_env(cls) -> "_TaskAgentChatLLMConfig | None":
        api_key = _first_env("HUNYUAN_API_KEY", "OPENAI_API_KEY")
        if not api_key:
            return None
        requested_profile = (os.getenv("TASK_AGENT_CHAT_MODEL_PROFILE") or "").strip() or None
        _, profile = get_requirement_analysis_model_profile(requested_profile)
        base_url = (_first_env("HUNYUAN_BASE_URL", "OPENAI_BASE_URL") or profile.base_url).rstrip("/")
        llm_model = (_first_env("HUNYUAN_LLM_MODEL", "OPENAI_LLM_MODEL") or profile.llm_model).strip()
        timeout = _resolve_float("TASK_AGENT_CHAT_TIMEOUT_SECONDS", default=min(profile.timeout_seconds, 30.0))
        retries = _resolve_int("TASK_AGENT_CHAT_LLM_RETRIES", default=0)
        return cls(
            gateway=ModelGateway(
                ModelGatewayConfig(
                    llm=ModelEndpointConfig(
                        provider="openai",
                        model=llm_model,
                        api_base=base_url,
                        api_key=api_key,
                        timeout=timeout,
                        retries=retries,
                    )
                )
            )
        )


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return ""


def _resolve_float(name: str, *, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _resolve_int(name: str, *, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
