"""LLM-backed task creation chat helpers."""

from __future__ import annotations

import os
from typing import Any

from platform_shared import (
    ModelEndpointConfig,
    ModelGateway,
    ModelGatewayConfig,
    ModelGatewayError,
    get_requirement_analysis_model_profile,
)


def build_llm_task_agent_chat_reply(message: str, agent_payload: dict[str, Any]) -> str | None:
    config = _TaskAgentChatLLMConfig.from_env()
    if config is None:
        return None
    prompt = {
        "user_message": str(message or "").strip(),
        "task_draft_agent_payload": _compact_agent_payload(agent_payload),
        "output_schema": {"reply": "string"},
        "constraints": [
            "Return strict JSON only",
            "Use Chinese",
            "Behave as a concise API testing assistant embedded in a task creation page",
            "Answer normal greetings and general questions naturally",
            "When relevant, use the current task draft context to discuss scenarios, assertions, risks, RAG evidence, and missing fields",
            "Do not claim the task has been created unless the user explicitly used the page creation workflow",
        ],
    }
    try:
        response = config.gateway.chat_json(
            system_prompt=(
                "You are an API automated testing agent in a task creation page. "
                "You can chat normally, understand the current task draft, and give practical testing guidance. "
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
    )
    compact = {key: agent_payload.get(key) for key in keys if key in agent_payload}
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
