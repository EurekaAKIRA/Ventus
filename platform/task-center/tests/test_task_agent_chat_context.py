from __future__ import annotations

from types import SimpleNamespace

from task_center.api import _build_task_agent_tracking_context, _task_ids_from_agent_conversation
from task_center.task_agent_chat import build_task_agent_contextual_reply, classify_task_agent_intent


def _task(**overrides):
    payload = {
        "task_id": "demo_task_20260523010101000000",
        "task_name": "demo task",
        "task_context": {"status": "failed"},
        "status": "failed",
        "environment": "dev",
        "target_system": "https://api.example.test",
        "pipeline_result": {
            "parsed_requirement": {"objective": "demo"},
            "test_case_dsl": {
                "scenarios": [
                    {
                        "steps": [
                            {
                                "assertions": [{"source": "status_code", "op": "eq", "expected": 200, "generated_by": "rules"}],
                                "assertion_quality": {
                                    "invalid_assertion_count": 2,
                                    "llm_error_type": "EmptyAssertionPayload",
                                },
                            }
                        ]
                    }
                ]
            },
            "validation_report": {"passed": True, "errors": [], "warnings": []},
            "analysis_report": {"failure_reasons": []},
        },
        "execution_result": {},
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_agent_extracts_failed_assertion_details() -> None:
    task = _task(
        execution_result={
            "status": "failed",
            "scenario_results": [
                {
                    "scenario_id": "scenario_001",
                    "name": "登录失败",
                    "status": "failed",
                    "steps": [
                        {
                            "step_id": "step_02",
                            "text": "调用 POST /login",
                            "status": "failed",
                            "message": "Assertion failed",
                            "assertion_summary": {
                                "total": 1,
                                "passed": 0,
                                "failed": 1,
                                "generated_by_counts": {"rules": 1},
                                "failure_details": [
                                    {
                                        "source": "status_code",
                                        "op": "eq",
                                        "expected": 200,
                                        "actual": 401,
                                        "generated_by": "rules",
                                        "failure_kind": "assertion_failed",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
    )

    tracking = _build_task_agent_tracking_context(task)
    reply = build_task_agent_contextual_reply("这个任务为什么失败", {"task_tracking": tracking})

    assert tracking["failed_assertions"][0]["source"] == "status_code"
    assert tracking["failed_assertions"][0]["expected"] == 200
    assert "status_code eq 200" in reply
    assert "401" in reply
    assert "鉴权" in reply
    assert "token" in reply.lower()


def test_agent_summarizes_assertion_quality_counts() -> None:
    task = _task(
        execution_result={
            "status": "passed",
            "scenario_results": [
                {
                    "scenario_id": "scenario_001",
                    "name": "主链路",
                    "status": "passed",
                    "steps": [
                        {
                            "step_id": "step_02",
                            "text": "调用 POST /items",
                            "status": "passed",
                            "assertion_summary": {
                                "total": 3,
                                "passed": 3,
                                "failed": 0,
                                "generated_by_counts": {"rules": 2, "llm": 1},
                                "weak_assertion": False,
                                "fallback_count": 1,
                            },
                        }
                    ],
                }
            ],
        }
    )

    tracking = _build_task_agent_tracking_context(task)
    reply = build_task_agent_contextual_reply("断言质量怎么样", {"task_tracking": tracking})

    assert tracking["assertion_quality"]["generated_by_counts"] == {"rules": 2, "llm": 1}
    assert "测试质量" in reply
    assert "rules=2" in reply
    assert "llm=1" in reply


def test_agent_treats_generic_quality_question_as_quality_review() -> None:
    assert classify_task_agent_intent("质量如何") == "general_question"

    reply = build_task_agent_contextual_reply(
        "质量如何",
        {
            "coverage_gaps": ["权限失败未覆盖"],
            "task_tracking": {
                "task_id": "quality_generic_20260523010101000000",
                "task_name": "泛质量追问",
                "execution_status": "passed",
                "stage": "execution",
                "scenario_total": 2,
                "scenario_passed": 2,
                "scenario_failed": 0,
                "assertion_quality": {
                    "total": 3,
                    "passed": 3,
                    "failed": 0,
                    "generated_by_counts": {"rules": 2, "llm": 1},
                    "weak_step_count": 1,
                    "fallback_count": 1,
                },
            },
        },
    )

    assert "测试质量：中等" in reply
    assert "覆盖提醒：权限失败未覆盖" in reply
    assert "断言质量：3/3 通过" in reply
    assert "弱断言步骤 1 个" in reply


def test_agent_does_not_force_quality_template_without_task_context() -> None:
    reply = build_task_agent_contextual_reply("质量如何", {})

    assert "缺对象" in reply
    assert "不直接套任务模板" in reply
    assert "断言质量：" not in reply


def test_agent_does_not_route_unrelated_quality_question() -> None:
    assert classify_task_agent_intent("空气质量如何") == "general_question"
    assert build_task_agent_contextual_reply("空气质量如何", {}) == ""


def test_agent_lists_weak_assertion_steps() -> None:
    task = _task(
        execution_result={
            "status": "passed",
            "scenario_results": [
                {
                    "scenario_id": "scenario_001",
                    "name": "主链路",
                    "status": "passed",
                    "steps": [
                        {
                            "step_id": "step_01",
                            "text": "调用 POST /items",
                            "status": "passed",
                            "assertion_summary": {
                                "total": 1,
                                "passed": 1,
                                "failed": 0,
                                "generated_by_counts": {"rules": 1},
                                "weak_assertion": True,
                                "quality_level": "weak",
                                "quality_reasons": ["只校验状态码", "缺少业务字段值校验"],
                            },
                        }
                    ],
                }
            ],
        }
    )

    tracking = _build_task_agent_tracking_context(task)
    reply = build_task_agent_contextual_reply("断言质量怎么样", {"task_tracking": tracking})

    assert "弱点集中在" in reply
    assert "主链路/调用 POST /items" in reply
    assert "只校验状态码" in reply


def test_agent_marks_status_code_failures_as_lower_false_positive_risk() -> None:
    reply = build_task_agent_contextual_reply(
        "断言质量怎么样",
        {
            "task_tracking": {
                "task_id": "status_risk_20260523010101000000",
                "task_name": "状态码风险",
                "execution_status": "failed",
                "scenario_total": 1,
                "scenario_passed": 0,
                "scenario_failed": 1,
                "failed_assertions": [
                    {
                        "scenario": "创建资源",
                        "step": "POST /items",
                        "source": "status_code",
                        "op": "eq",
                        "expected": 201,
                        "actual": 422,
                        "generated_by": "llm_repair",
                    }
                ],
                "assertion_quality": {
                    "total": 1,
                    "passed": 0,
                    "failed": 1,
                    "generated_by_counts": {"llm_repair": 1},
                },
            }
        },
    )

    assert "误杀风险：低到中" in reply
    assert "status_code 实际 422" in reply
    assert "不建议先删断言" in reply
    assert "下一步先修请求/鉴权/环境和测试数据" in reply
    assert "只回归同类 status_code 失败" in reply


def test_agent_status_query_includes_failure_root_cause_and_next_action() -> None:
    reply = build_task_agent_contextual_reply(
        "现在怎么样",
        {
            "task_tracking": {
                "task_id": "status_summary_20260523010101000000",
                "task_name": "状态摘要",
                "execution_status": "failed",
                "stage": "execution",
                "scenario_total": 2,
                "scenario_passed": 1,
                "scenario_failed": 1,
                "failed_assertions": [
                    {
                        "scenario": "创建资源",
                        "step": "POST /items",
                        "source": "status_code",
                        "op": "eq",
                        "expected": 201,
                        "actual": 422,
                    }
                ],
                "assertion_quality": {"total": 3, "passed": 2, "failed": 1, "generated_by_counts": {"rules": 2, "llm": 1}},
            }
        },
    )

    assert "当前失败" in reply
    assert "阶段 execution" in reply
    assert "初判是请求参数或数据契约问题" in reply
    assert "代表断言 status_code eq 201" in reply
    assert "先对照接口资产里的请求 schema" in reply
    assert "建议先问" not in reply


def test_agent_status_query_passed_includes_quality_and_coverage_gaps() -> None:
    reply = build_task_agent_contextual_reply(
        "现在怎么样",
        {
            "coverage_gaps": ["权限失败未覆盖", "删除后读取未验证"],
            "task_tracking": {
                "task_id": "status_passed_20260523010101000000",
                "task_name": "通过状态摘要",
                "execution_status": "passed",
                "stage": "execution",
                "scenario_total": 2,
                "scenario_passed": 2,
                "scenario_failed": 0,
                "assertion_quality": {
                    "total": 4,
                    "passed": 4,
                    "failed": 0,
                    "generated_by_counts": {"rules": 3, "llm": 1},
                    "weak_step_count": 1,
                    "fallback_count": 1,
                    "invalid_llm_candidate_count": 2,
                },
            },
        },
    )

    assert "已执行通过" in reply
    assert "阶段 execution" in reply
    assert "质量提醒：弱断言步骤 1 个、fallback 1 条、LLM 被过滤候选 2 条" in reply
    assert "覆盖缺口：权限失败未覆盖；删除后读取未验证" in reply
    assert "沉淀为用例资产" in reply


def test_agent_status_query_prioritizes_llm_filter_when_passed_without_weak_steps() -> None:
    reply = build_task_agent_contextual_reply(
        "现在怎么样",
        {
            "task_tracking": {
                "task_id": "passed_llm_filter_status_20260523090832695000",
                "task_name": "通过但过滤",
                "execution_status": "passed",
                "stage": "execution",
                "scenario_total": 1,
                "scenario_passed": 1,
                "scenario_failed": 0,
                "assertion_quality": {
                    "total": 3,
                    "passed": 3,
                    "failed": 0,
                    "generated_by_counts": {"rules": 2, "llm": 1},
                    "invalid_llm_candidate_count": 2,
                },
            }
        },
    )

    assert "质量提醒：LLM 被过滤候选 2 条" in reply
    assert "补齐 LLM 候选过滤明细和原因" in reply
    assert "补强弱断言" not in reply


def test_agent_task_import_uses_execution_base_url_from_dsl() -> None:
    task = _task(
        target_system="https://api.example.test",
        pipeline_result={
            "parsed_requirement": {"objective": "demo"},
            "test_case_dsl": {
                "metadata": {"execution": {"base_url": "http://127.0.0.1:8001"}},
                "scenarios": [],
            },
            "validation_report": {"passed": True, "errors": [], "warnings": []},
            "analysis_report": {"failure_reasons": []},
        },
    )

    tracking = _build_task_agent_tracking_context(task)
    reply = build_task_agent_contextual_reply("任务导入的 Base URL 自动填充了吗", {"task_tracking": tracking})

    assert tracking["execution_base_url"] == "http://127.0.0.1:8001"
    assert "Base URL 已进入执行上下文：http://127.0.0.1:8001" in reply
    assert "和执行 Base URL 不一致" in reply
    assert "缺少这些数据" not in reply


def test_agent_task_import_explains_target_system_fallback() -> None:
    reply = build_task_agent_contextual_reply(
        "任务导入的接口资产和用例资产还无法自动读取baseurl吗",
        {
            "task_tracking": {
                "task_id": "asset_import_target_20260523091832790000",
                "task_name": "资产导入兜底",
                "environment": "dev",
                "target_system": "http://127.0.0.1:8001",
                "execution_status": "not_started",
                "missing_artifacts": ["execution_result"],
            }
        },
    )

    assert "已识别任务目标系统 http://127.0.0.1:8001" in reply
    assert "metadata.execution.base_url" in reply
    assert "task.target_system 兜底" in reply
    assert "缺少这些数据" not in reply


def test_agent_task_import_uses_environment_base_url_before_target_system() -> None:
    reply = build_task_agent_contextual_reply(
        "任务导入怎么自动填 Base URL",
        {
            "task_tracking": {
                "task_id": "asset_import_env_20260523092832888000",
                "task_name": "资产导入环境 Base URL",
                "environment": "dev",
                "environment_base_url": "http://127.0.0.1:8001",
                "target_system": "https://api.example.test",
                "execution_status": "not_started",
                "missing_artifacts": ["execution_result"],
            }
        },
    )

    assert "环境 dev 已配置 Base URL：http://127.0.0.1:8001" in reply
    assert "环境管理自动带出这个地址" in reply
    assert "和环境 Base URL 不一致" in reply
    assert "metadata.execution.base_url" in reply
    assert "缺少这些数据" not in reply


def test_agent_task_import_reports_missing_base_url_when_only_environment() -> None:
    reply = build_task_agent_contextual_reply(
        "接口资产导入后为什么没自动填 Base URL",
        {
            "task_tracking": {
                "task_id": "asset_import_missing_20260523091832790000",
                "task_name": "资产导入缺 Base URL",
                "environment": "dev",
                "execution_status": "not_started",
                "missing_artifacts": ["execution_result"],
            }
        },
    )

    assert "当前只有环境 dev" in reply
    assert "没看到可执行 Base URL" in reply
    assert "环境管理配置 base_url" in reply
    assert "metadata.execution.base_url" in reply
    assert "缺少这些数据" not in reply


def test_agent_next_action_is_not_blocked_by_missing_execution_result() -> None:
    reply = build_task_agent_contextual_reply(
        "下一步我该怎么修",
        {
            "task_tracking": {
                "task_id": "next_action_unexecuted_20260523091832790000",
                "task_name": "未执行任务",
                "environment": "dev",
                "target_system": "http://127.0.0.1:8001",
                "execution_status": "not_started",
                "missing_artifacts": ["execution_result"],
            }
        },
    )

    assert "下一步先确认 Base URL/环境和 DSL 是否生成" in reply
    assert "缺少这些数据" not in reply


def test_agent_marks_llm_json_path_failures_as_high_false_positive_risk() -> None:
    reply = build_task_agent_contextual_reply(
        "断言质量怎么样",
        {
            "task_tracking": {
                "task_id": "json_path_risk_20260523010101000000",
                "task_name": "JSON 路径风险",
                "execution_status": "failed",
                "scenario_total": 1,
                "scenario_passed": 0,
                "scenario_failed": 1,
                "failed_assertions": [
                    {
                        "scenario": "详情校验",
                        "step": "读取 data.id",
                        "source": "json.data.id",
                        "op": "exists",
                        "expected": True,
                        "actual": None,
                        "generated_by": "llm",
                    }
                ],
                "assertion_quality": {
                    "total": 1,
                    "passed": 0,
                    "failed": 1,
                    "generated_by_counts": {"llm": 1},
                },
            }
        },
    )

    assert "误杀风险：高" in reply
    assert "JSON 路径/字段存在性" in reply
    assert "核对真实响应体字段路径" in reply
    assert "先打开 详情校验/读取 data.id 的实际响应体" in reply
    assert "字段存在就修断言 source" in reply


def test_agent_explains_llm_supervision_counts() -> None:
    reply = build_task_agent_contextual_reply(
        "断言有 LLM 增强吗",
        {
            "task_tracking": {
                "task_id": "llm_usage_20260523010101000000",
                "task_name": "LLM 断言监督",
                "execution_status": "passed",
                "scenario_total": 1,
                "scenario_passed": 1,
                "scenario_failed": 0,
                "assertion_quality": {
                    "total": 6,
                    "passed": 6,
                    "failed": 0,
                    "generated_by_counts": {"rules": 2, "llm": 2, "llm_repair": 1},
                    "fallback_count": 1,
                    "invalid_llm_candidate_count": 2,
                    "llm_error_type_counts": {"EmptyAssertionPayload": 1},
                },
            }
        },
    )

    assert "直接保留 2 条" in reply
    assert "修复后保留 1 条" in reply
    assert "fallback 1 条" in reply
    assert "质量门过滤 2 条" in reply
    assert "EmptyAssertionPayload=1" in reply
    assert "LLM 有参与" in reply


def test_agent_warns_when_llm_candidates_all_filtered() -> None:
    reply = build_task_agent_contextual_reply(
        "LLM 断言是不是有问题",
        {
            "task_tracking": {
                "task_id": "llm_filtered_20260523010101000000",
                "task_name": "LLM 候选过滤",
                "execution_status": "passed",
                "scenario_total": 1,
                "scenario_passed": 1,
                "scenario_failed": 0,
                "assertion_quality": {
                    "total": 2,
                    "passed": 2,
                    "failed": 0,
                    "generated_by_counts": {"rules": 2},
                    "fallback_count": 0,
                    "invalid_llm_candidate_count": 3,
                },
            }
        },
    )

    assert "直接保留 0 条" in reply
    assert "质量门过滤 3 条" in reply
    assert "LLM 产出基本没通过质量门" in reply
    assert "输入信息是否不足" in reply


def test_agent_reports_missing_llm_filter_detail_fields() -> None:
    reply = build_task_agent_contextual_reply(
        "断言有 LLM 增强吗",
        {
            "task_tracking": {
                "task_id": "llm_missing_filter_detail_20260523085832607000",
                "task_name": "LLM 过滤明细缺失",
                "execution_status": "passed",
                "scenario_total": 1,
                "scenario_passed": 1,
                "scenario_failed": 0,
                "assertion_quality": {
                    "total": 2,
                    "passed": 2,
                    "failed": 0,
                    "generated_by_counts": {"rules": 2},
                    "invalid_llm_candidate_count": 2,
                },
            }
        },
    )

    assert "过滤明细缺失" in reply
    assert "invalid_llm_candidates" in reply
    assert "llm_filter_reasons" in reply
    assert "step/source/op/reason" in reply


def test_agent_reports_invalid_llm_candidate_details_from_dsl() -> None:
    task = _task(
        pipeline_result={
            "parsed_requirement": {"objective": "demo"},
            "test_case_dsl": {
                "scenarios": [
                    {
                        "name": "创建资源",
                        "steps": [
                            {
                                "step_id": "step_01",
                                "text": "调用 POST /items",
                                "assertions": [{"source": "status_code", "op": "eq", "expected": 201, "generated_by": "rules"}],
                                "assertion_quality": {
                                    "invalid_assertion_count": 2,
                                    "llm_error_type": "InvalidAssertionShape",
                                    "fallback_reason": "candidate_missing_source",
                                    "invalid_assertions": [
                                        {
                                            "source": "",
                                            "op": "eq",
                                            "expected": "ok",
                                            "reason": "missing source",
                                        },
                                        {
                                            "source": "json.data.id",
                                            "op": "unknown",
                                            "reason": "unsupported op",
                                        },
                                    ],
                                },
                            }
                        ],
                    }
                ]
            },
            "validation_report": {"passed": True, "errors": [], "warnings": []},
            "analysis_report": {"failure_reasons": []},
        },
        execution_result={},
    )

    tracking = _build_task_agent_tracking_context(task)
    reply = build_task_agent_contextual_reply("断言有 LLM 增强吗", {"task_tracking": tracking})

    assert tracking["assertion_quality"]["invalid_llm_candidate_count"] == 2
    assert tracking["assertion_quality"]["invalid_llm_candidates"][0]["reason"] == "missing source"
    assert "过滤明细" in reply
    assert "调用 POST /items" in reply
    assert "missing source" in reply
    assert "unsupported op" in reply


def test_agent_reports_missing_execution_artifact_without_guessing() -> None:
    task = _task(execution_result={})

    tracking = _build_task_agent_tracking_context(task)
    reply = build_task_agent_contextual_reply("为什么失败", {"task_tracking": tracking})

    assert "execution_result" in tracking["missing_artifacts"]
    assert "缺少" in reply
    assert "execution_result" in reply


def test_agent_can_reuse_task_id_from_recent_conversation() -> None:
    task_ids = _task_ids_from_agent_conversation(
        [
            {"role": "user", "text": "刚才看的是 restful_booker_api_requirement_20260523015237942506"},
            {"role": "assistant", "text": "后面继续分析它的断言质量"},
        ]
    )

    assert task_ids == ["restful_booker_api_requirement_20260523015237942506"]


def test_agent_continues_assertion_focus_from_conversation_memory() -> None:
    reply = build_task_agent_contextual_reply(
        "那继续看这个",
        {
            "conversation_memory": {
                "focus_terms": ["失败", "断言"],
                "recent_messages": [
                    {"role": "user", "text": "断言质量怎么样"},
                    {"role": "assistant", "text": "刚才主要在看断言质量"},
                ],
            },
            "task_tracking": {
                "task_id": "memory_assertion_20260523010101000000",
                "task_name": "会话记忆断言",
                "execution_status": "passed",
                "scenario_total": 1,
                "scenario_passed": 1,
                "scenario_failed": 0,
                "assertion_quality": {
                    "total": 4,
                    "passed": 4,
                    "failed": 0,
                    "generated_by_counts": {"rules": 2, "llm": 2},
                    "weak_step_count": 1,
                    "weak_steps": [{"scenario": "主链路", "step": "GET /items", "reasons": ["只校验状态码"]}],
                },
            },
        },
    )

    assert "断言质量" in reply
    assert "rules=2" in reply
    assert "弱点集中在" in reply


def test_agent_continues_llm_focus_from_conversation_memory() -> None:
    reply = build_task_agent_contextual_reply(
        "这个还有问题吗",
        {
            "conversation_memory": {
                "focus_terms": ["断言", "LLM"],
                "recent_messages": [
                    {"role": "user", "text": "断言有 LLM 增强吗"},
                    {"role": "assistant", "text": "LLM 监督还在"},
                ],
            },
            "task_tracking": {
                "task_id": "memory_llm_20260523010101000000",
                "task_name": "会话记忆 LLM",
                "execution_status": "passed",
                "scenario_total": 1,
                "scenario_passed": 1,
                "scenario_failed": 0,
                "assertion_quality": {
                    "total": 3,
                    "passed": 3,
                    "failed": 0,
                    "generated_by_counts": {"rules": 1, "llm": 1, "llm_repair": 1},
                    "fallback_count": 1,
                    "invalid_llm_candidate_count": 1,
                    "llm_error_type_counts": {"InvalidAssertionShape": 1},
                },
            },
        },
    )

    assert "LLM 监督还在" in reply
    assert "直接保留 1 条" in reply
    assert "修复后保留 1 条" in reply


def test_agent_prefers_latest_user_intent_over_stale_focus_terms() -> None:
    reply = build_task_agent_contextual_reply(
        "那继续看这个",
        {
            "conversation_memory": {
                "focus_terms": ["断言", "LLM"],
                "recent_messages": [
                    {"role": "user", "text": "断言有 LLM 增强吗"},
                    {"role": "assistant", "text": "LLM 监督还在"},
                    {"role": "user", "text": "这个任务为什么失败"},
                ],
            },
            "task_tracking": {
                "task_id": "memory_conflict_20260523010101000000",
                "task_name": "会话记忆冲突",
                "execution_status": "failed",
                "scenario_total": 1,
                "scenario_passed": 0,
                "scenario_failed": 1,
                "failed_assertions": [
                    {
                        "scenario": "创建资源",
                        "step": "POST /items",
                        "source": "status_code",
                        "op": "eq",
                        "expected": 201,
                        "actual": 422,
                    }
                ],
                "assertion_quality": {
                    "total": 1,
                    "passed": 0,
                    "failed": 1,
                    "generated_by_counts": {"llm": 1},
                    "invalid_llm_candidate_count": 3,
                },
            },
        },
    )

    assert "这次主要像是请求参数或数据契约问题" in reply
    assert "LLM 监督还在" not in reply


def test_agent_classifies_request_contract_failure() -> None:
    task = _task(
        execution_result={
            "status": "failed",
            "scenario_results": [
                {
                    "scenario_id": "scenario_001",
                    "name": "创建资源",
                    "status": "failed",
                    "steps": [
                        {
                            "step_id": "step_01",
                            "text": "调用 POST /items",
                            "status": "failed",
                            "assertion_summary": {
                                "total": 1,
                                "passed": 0,
                                "failed": 1,
                                "generated_by_counts": {"llm": 1},
                                "failure_details": [
                                    {
                                        "source": "status_code",
                                        "op": "eq",
                                        "expected": 201,
                                        "actual": 422,
                                        "generated_by": "llm",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
    )

    tracking = _build_task_agent_tracking_context(task)
    reply = build_task_agent_contextual_reply("下一步怎么修", {"task_tracking": tracking})

    assert "请求参数" in reply
    assert "schema" in reply
    assert "必填字段" in reply


def test_agent_next_action_prioritizes_llm_filter_detail_on_passed_task() -> None:
    reply = build_task_agent_contextual_reply(
        "下一步怎么修",
        {
            "task_tracking": {
                "task_id": "passed_llm_filter_20260523090832695000",
                "task_name": "通过但 LLM 过滤",
                "execution_status": "passed",
                "scenario_total": 1,
                "scenario_passed": 1,
                "scenario_failed": 0,
                "assertion_quality": {
                    "total": 3,
                    "passed": 3,
                    "failed": 0,
                    "generated_by_counts": {"rules": 3},
                    "invalid_llm_candidate_count": 2,
                },
            }
        },
    )

    assert "补 LLM 候选过滤明细" in reply
    assert "invalid_llm_candidates" in reply
    assert "llm_filter_reasons" in reply
    assert "step/source/op/reason" in reply


def test_agent_next_action_prioritizes_fallback_on_passed_task() -> None:
    reply = build_task_agent_contextual_reply(
        "下一步怎么修",
        {
            "task_tracking": {
                "task_id": "passed_llm_fallback_20260523090832695000",
                "task_name": "通过但规则兜底",
                "execution_status": "passed",
                "scenario_total": 1,
                "scenario_passed": 1,
                "scenario_failed": 0,
                "assertion_quality": {
                    "total": 3,
                    "passed": 3,
                    "failed": 0,
                    "generated_by_counts": {"rules": 3},
                    "fallback_count": 1,
                },
            }
        },
    )

    assert "降低规则兜底占比" in reply
    assert "LLM" in reply
    assert "fallback 是否下降" in reply


def test_agent_classifies_context_variable_failure() -> None:
    reply = build_task_agent_contextual_reply(
        "这个任务为什么失败",
        {
            "task_tracking": {
                "task_id": "context_demo_20260523010101000000",
                "task_name": "上下文链路",
                "execution_status": "failed",
                "scenario_total": 1,
                "scenario_passed": 0,
                "scenario_failed": 1,
                "failed_assertions": [
                    {
                        "scenario": "删除后查询",
                        "step": "读取上一步 item_id",
                        "source": "context.item_id",
                        "op": "exists",
                        "expected": True,
                        "actual": None,
                    }
                ],
                "assertion_quality": {"total": 1, "passed": 0, "failed": 1, "generated_by_counts": {"rules": 1}},
            }
        },
    )

    assert "上下文变量传递问题" in reply
    assert "提取表达式" in reply


def test_agent_groups_failed_assertions_by_root_cause() -> None:
    reply = build_task_agent_contextual_reply(
        "这个任务为什么失败",
        {
            "task_tracking": {
                "task_id": "multi_failure_20260523010101000000",
                "task_name": "多失败聚类",
                "execution_status": "failed",
                "scenario_total": 3,
                "scenario_passed": 0,
                "scenario_failed": 3,
                "failed_assertions": [
                    {
                        "scenario": "详情校验",
                        "step": "读取响应字段",
                        "source": "json.data.id",
                        "op": "exists",
                        "expected": True,
                        "actual": None,
                    },
                    {
                        "scenario": "创建资源",
                        "step": "POST /items",
                        "source": "status_code",
                        "op": "eq",
                        "expected": 201,
                        "actual": 401,
                    },
                    {
                        "scenario": "删除资源",
                        "step": "DELETE /items/{id}",
                        "source": "status_code",
                        "op": "eq",
                        "expected": 204,
                        "actual": 403,
                    },
                ],
                "assertion_quality": {"total": 3, "passed": 0, "failed": 3, "generated_by_counts": {"llm": 3}},
            }
        },
    )

    assert "这次主要像是鉴权或登录态问题" in reply
    assert "失败聚类" in reply
    assert "鉴权或登录态问题 2 条" in reply
    assert "断言路径或响应结构不匹配 1 条" in reply


def test_agent_uses_logs_and_analysis_to_rank_failure_groups() -> None:
    reply = build_task_agent_contextual_reply(
        "这个任务为什么失败",
        {
            "task_tracking": {
                "task_id": "evidence_rank_20260523010101000000",
                "task_name": "证据加权",
                "execution_status": "failed",
                "scenario_total": 2,
                "scenario_passed": 0,
                "scenario_failed": 2,
                "failed_assertions": [
                    {
                        "scenario": "响应字段",
                        "step": "读取 data.id",
                        "source": "json.data.id",
                        "op": "exists",
                        "expected": True,
                        "actual": None,
                    },
                    {
                        "scenario": "创建资源",
                        "step": "POST /items",
                        "source": "status_code",
                        "op": "eq",
                        "expected": 201,
                        "actual": 401,
                    },
                ],
                "latest_logs": [
                    {"message": "HTTP 401 Unauthorized: Authorization token expired"},
                ],
                "failure_reasons": ["登录态失效，后续请求没有有效 token"],
                "assertion_quality": {"total": 2, "passed": 0, "failed": 2, "generated_by_counts": {"llm": 2}},
            }
        },
    )

    assert "这次主要像是鉴权或登录态问题" in reply
    assert "证据补充" in reply
    assert "Authorization token expired" in reply


def test_agent_prioritizes_step_scoped_failure_evidence() -> None:
    reply = build_task_agent_contextual_reply(
        "这个任务为什么失败",
        {
            "task_tracking": {
                "task_id": "step_scope_20260523010101000000",
                "task_name": "步骤证据关联",
                "execution_status": "failed",
                "scenario_total": 2,
                "scenario_passed": 0,
                "scenario_failed": 2,
                "failed_assertions": [
                    {
                        "scenario": "详情校验",
                        "step": "读取 data.id",
                        "source": "json.data.id",
                        "op": "exists",
                        "expected": True,
                        "actual": None,
                    },
                    {
                        "scenario": "创建资源",
                        "step": "POST /items",
                        "source": "status_code",
                        "op": "eq",
                        "expected": 201,
                        "actual": 422,
                    },
                ],
                "latest_logs": [
                    {
                        "scenario": "创建资源",
                        "step": "POST /items",
                        "message": "HTTP 422 validation error: required field name missing",
                    }
                ],
                "failure_reasons": ["missing field data.id from stale detail response"],
                "assertion_quality": {"total": 2, "passed": 0, "failed": 2, "generated_by_counts": {"rules": 1, "llm": 1}},
            }
        },
    )

    assert "这次主要像是请求参数或数据契约问题" in reply
    assert "关联步骤 创建资源/POST /items" in reply
    assert "HTTP 422 validation error" in reply


def test_agent_scopes_plain_text_logs_by_endpoint_token() -> None:
    reply = build_task_agent_contextual_reply(
        "这个任务为什么失败",
        {
            "task_tracking": {
                "task_id": "plain_text_scope_20260523010101000000",
                "task_name": "纯文本日志关联",
                "execution_status": "failed",
                "scenario_total": 2,
                "scenario_passed": 0,
                "scenario_failed": 2,
                "failed_assertions": [
                    {
                        "scenario": "详情校验",
                        "step": "读取 data.id",
                        "source": "json.data.id",
                        "op": "exists",
                        "expected": True,
                        "actual": None,
                    },
                    {
                        "scenario": "创建资源",
                        "step": "调用 POST /items",
                        "source": "status_code",
                        "op": "eq",
                        "expected": 201,
                        "actual": 422,
                    },
                ],
                "latest_logs": [
                    "HTTP 422 POST /items validation error: required field name missing",
                ],
                "failure_reasons": ["missing field data.id from stale detail response"],
                "assertion_quality": {"total": 2, "passed": 0, "failed": 2, "generated_by_counts": {"rules": 1, "llm": 1}},
            }
        },
    )

    assert "这次主要像是请求参数或数据契约问题" in reply
    assert "关联步骤 创建资源/调用 POST /items" in reply
    assert "HTTP 422 POST /items validation error" in reply
