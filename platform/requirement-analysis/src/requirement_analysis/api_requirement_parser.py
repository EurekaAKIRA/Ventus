"""Requirement parsing helpers with API-oriented cues."""

from __future__ import annotations

import re
from typing import Any

from platform_shared.endpoint_policy import filter_executable_api_endpoints
from platform_shared.models import ParsedRequirement

from .document_parser import extract_candidate_test_points, extract_keywords
from .openai_enhancement import (
    OpenAIEnhancementConfig,
    enhance_parsed_requirement_with_metadata,
)

_EXPLICIT_ENDPOINT_RE = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[\w/\-{}:.]+)",
    re.IGNORECASE,
)
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_NON_EXECUTABLE_ACTION_PATTERNS = (
    "签收最终结论",
    "确认验收范围",
    "保障主链路可运行",
    "验证页面主路径",
    "执行回归流程",
    "输出问题清单",
    "保障测试环境地址",
    "网络和依赖可达",
    "角色与职责",
    "背景与目的",
    "适用范围",
    "验收关注点",
    "非功能与治理要求",
    "风险与已知限制",
    "环境前置条件",
    "输出物要求",
    "文档维护原则",
)
_NON_EXECUTABLE_ACTION_HINTS = (
    "负责人",
    "研发",
    "工程师",
    "运维",
    "环境负责人",
    "验收",
    "签收",
    "职责",
    "治理",
    "风险",
    "限制",
    "输出物",
    "回归记录",
    "问题清单",
)


def _extract_api_endpoints(text: str) -> list[dict]:
    """Extract explicit HTTP method + path pairs from requirement text."""
    description_map = _extract_endpoint_descriptions(text)
    seen: set[str] = set()
    endpoints: list[dict] = []
    for method, path in _extract_endpoint_pairs_from_tables(text):
        key = f"{method} {path}"
        if key not in seen:
            seen.add(key)
            endpoints.append({"method": method, "path": path, "description": description_map.get(key, "")})
    for m in _EXPLICIT_ENDPOINT_RE.finditer(text):
        method = m.group(1).upper()
        path = m.group(2)
        key = f"{method} {path}"
        if key not in seen:
            seen.add(key)
            endpoints.append({"method": method, "path": path, "description": description_map.get(key, "")})
    return _enrich_endpoints(endpoints, text)


def _infer_endpoint_group(path: str) -> str:
    """Derive a functional group label from the path structure."""
    segments = [s for s in path.strip("/").split("/") if s and not s.startswith("{")]
    if len(segments) >= 3:
        return segments[1]
    if len(segments) >= 2:
        return segments[1]
    if segments:
        return segments[0]
    return "default"


def _infer_depends_on(path: str, all_paths: list[str]) -> list[str]:
    """Find parent endpoints that this path depends on (sub-resource relationship)."""
    deps: list[str] = []
    norm = path.rstrip("/")
    for candidate in all_paths:
        cand_norm = candidate.rstrip("/")
        if cand_norm != norm and norm.startswith(cand_norm + "/"):
            deps.append(candidate)
    return deps


def _enrich_endpoints(endpoints: list[dict], text: str) -> list[dict]:
    """Add group, depends_on, and field placeholders to raw endpoint dicts."""
    all_paths = [str(ep.get("path", "")) for ep in endpoints]
    section_map = _map_paths_to_sections(text)
    for ep in endpoints:
        path = str(ep.get("path", ""))
        if not ep.get("group"):
            ep["group"] = section_map.get(path) or _infer_endpoint_group(path)
        if not ep.get("depends_on"):
            ep["depends_on"] = _infer_depends_on(path, all_paths)
        ep.setdefault("request_body_fields", [])
        ep.setdefault("response_fields", [])
    return endpoints


_SECTION_HEADING_RE = re.compile(r"^#{1,4}\s+(.+)", re.MULTILINE)


def _map_paths_to_sections(text: str) -> dict[str, str]:
    """Map endpoint paths to their enclosing markdown section heading."""
    mapping: dict[str, str] = {}
    current_heading = ""
    for line in text.splitlines():
        heading_match = _SECTION_HEADING_RE.match(line.strip())
        if heading_match:
            current_heading = heading_match.group(1).strip().strip("#").strip()
            continue
        if not current_heading:
            continue
        for m in _EXPLICIT_ENDPOINT_RE.finditer(line):
            mapping.setdefault(m.group(2), current_heading)
        if _TABLE_ROW_RE.match(line.strip()):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3:
                path = cells[2].strip().strip("`").strip()
                if path.startswith("/"):
                    mapping.setdefault(path, current_heading)
    return mapping


def _extract_endpoint_descriptions(text: str) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    descriptions.update(_extract_endpoint_descriptions_from_sentences(lines))
    descriptions.update(_extract_endpoint_descriptions_from_tables(lines))
    return descriptions


def _extract_endpoint_pairs_from_tables(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for raw_line in lines:
        if not _TABLE_ROW_RE.match(raw_line):
            continue
        cells = [cell.strip() for cell in raw_line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        method = cells[1].strip().strip("`").strip().upper()
        path = cells[2].strip().strip("`").strip()
        if method in {"GET", "POST", "PUT", "PATCH", "DELETE"} and path.startswith("/"):
            pairs.append((method, path))
    return pairs


def _extract_endpoint_descriptions_from_tables(lines: list[str]) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for raw_line in lines:
        if not _TABLE_ROW_RE.match(raw_line):
            continue
        cells = [cell.strip() for cell in raw_line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        method_candidate = cells[1].strip().strip("`").strip().upper()
        path_candidate = cells[2].strip().strip("`").strip()
        if method_candidate not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            continue
        if not path_candidate.startswith("/"):
            continue
        description = cells[0].strip("` ").strip()
        descriptions[f"{method_candidate} {path_candidate}"] = description
    return descriptions


def _extract_endpoint_descriptions_from_sentences(lines: list[str]) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for index, raw_line in enumerate(lines):
        for match in _EXPLICIT_ENDPOINT_RE.finditer(raw_line):
            method = match.group(1).upper()
            path = match.group(2)
            key = f"{method} {path}"
            description = _derive_description_from_sentence(raw_line, method, path)
            if not description and index > 0:
                description = _derive_description_from_sentence(lines[index - 1], method, path)
            if description:
                descriptions.setdefault(key, description)
    return descriptions


def _derive_description_from_sentence(sentence: str, method: str, path: str) -> str:
    cleaned = _INLINE_CODE_RE.sub(r"\1", sentence)
    cleaned = cleaned.replace(f"{method} {path}", " ").replace(path, " ")
    cleaned = re.sub(r"^\d+[.)、\s]*", "", cleaned)
    cleaned = re.sub(r"\b(GET|POST|PUT|PATCH|DELETE)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:：;；,.。")
    if len(cleaned) <= 2:
        return ""
    return cleaned[:40]


def _extract_explicit_endpoint_actions(text: str) -> list[str]:
    """Treat explicit METHOD /path sentences as actionable steps."""
    action_sentences: list[str] = []
    for sentence in re.split(r"[\n。；;]+", text):
        sentence = sentence.strip()
        if not sentence or _TABLE_ROW_RE.match(sentence):
            continue
        if _EXPLICIT_ENDPOINT_RE.search(sentence):
            normalized = _normalize_statement(sentence)
            if normalized:
                action_sentences.append(normalized)
    return action_sentences


def _is_meta_documentation_reference_action(text: str) -> bool:
    """Prose that cites GET /docs / Swagger for contract reference, not an executable step."""
    lowered = text.lower()
    if "/docs" not in text and "get /docs" not in lowered and "`/docs`" not in text:
        return False
    return any(
        k in text
        for k in ("契约", "为准", "参考", "openapi", "swagger", "替代物", "不是完整", "api-contract")
    )


def _is_non_executable_action(text: str) -> bool:
    normalized = _normalize_statement(text)
    lowered = normalized.lower()
    if not normalized:
        return True
    if _is_meta_documentation_reference_action(normalized):
        return True
    if normalized.startswith("**") and "：" in normalized:
        return True
    if any(pattern in normalized for pattern in _NON_EXECUTABLE_ACTION_PATTERNS):
        return True
    if any(hint in normalized for hint in _NON_EXECUTABLE_ACTION_HINTS):
        return True
    if lowered.startswith(("说明", "note", "备注")):
        return True
    return False


def _filter_actions(actions: list[str], *, explicit_endpoint_actions: list[str], api_endpoints: list[dict[str, str]]) -> list[str]:
    explicit_set = {_normalize_statement(item) for item in explicit_endpoint_actions}
    filtered: list[str] = []
    for action in actions:
        normalized = _normalize_statement(action)
        if not normalized:
            continue
        if normalized in explicit_set:
            filtered.append(normalized)
            continue
        if _is_non_executable_action(normalized):
            continue
        filtered.append(normalized)
    if api_endpoints and explicit_endpoint_actions:
        seen = {_normalize_statement(a) for a in explicit_endpoint_actions}
        merged = list(explicit_endpoint_actions)
        for action in filtered:
            if _normalize_statement(action) not in seen:
                merged.append(action)
        return merged
    return filtered


ACTION_VERBS = (
    "click",
    "input",
    "select",
    "submit",
    "open",
    "enter",
    "create",
    "delete",
    "update",
    "search",
    "save",
    "view",
    "login",
    "query",
    "request",
    "call",
    "invoke",
    "post",
    "get",
    "put",
    "点击",
    "输入",
    "提交",
    "打开",
    "创建",
    "删除",
    "更新",
    "查询",
    "查看",
    "登录",
)
EXPECTATION_CUES = (
    "should",
    "returns",
    "return",
    "response",
    "status",
    "contains",
    "success",
    "failed",
    "显示",
    "返回",
    "提示",
    "成功",
    "失败",
)
CONSTRAINT_CUES = ("must", "cannot", "only", "require", "必须", "只能", "不可", "不能", "限制")
PRECONDITION_CUES = ("precondition", "before", "authenticated", "existing", "前提", "已登录", "登录后", "准备好", "存在")
ACTOR_HINTS = ("admin", "reviewer", "guest", "user", "operator", "service", "管理员", "审核员", "访客", "用户", "运营")


def _normalize_statement(text: str) -> str:
    normalized = text.strip()
    normalized = re.sub(r"^#+\s*", "", normalized)
    normalized = re.sub(r"^[-*]\s*", "", normalized)
    normalized = re.sub(r"^\d+[.)、\s]*", "", normalized)
    return normalized.strip(" 。；;")


def _derive_objective(requirement_text: str, candidate_points: list[dict]) -> str:
    heading_match = re.search(r"^\s*#\s+(.+)$", requirement_text, re.MULTILINE)
    if heading_match:
        return heading_match.group(1).strip()
    for item in candidate_points:
        if item["type"] in {"action", "expectation"}:
            return _normalize_statement(item["text"])
    for line in requirement_text.splitlines():
        normalized = _normalize_statement(line)
        if normalized:
            return normalized
    return "需求目标待补充"


def _merge_context(requirement_text: str, retrieved_context: list[dict]) -> str:
    parts = [requirement_text.strip()]
    for item in retrieved_context[:3]:
        content = item.get("content", "").strip()
        if content and content not in parts:
            parts.append(content)
    return "\n".join(part for part in parts if part)


def _extract_actors(text: str) -> list[str]:
    lowered = text.lower()
    actors = [actor for actor in ACTOR_HINTS if actor in lowered or actor in text]
    return actors or ["用户"]


def _dedupe(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        normalized = _normalize_statement(item)
        if normalized and normalized not in seen:
            seen.append(normalized)
    return seen


def _endpoint_key(ep: dict) -> str:
    return f"{str(ep.get('method', '')).strip().upper()} {str(ep.get('path', '')).strip()}"


def _union_endpoints(llm_endpoints: list[dict], rule_endpoints: list[dict]) -> list[dict]:
    """Merge LLM and rule-based endpoints by (method, path). LLM entries take priority; rule entries fill gaps."""
    if not llm_endpoints:
        return list(rule_endpoints)
    if not rule_endpoints:
        return list(llm_endpoints)
    rule_by_key = {_endpoint_key(ep): ep for ep in rule_endpoints}
    merged: list[dict] = []
    seen: set[str] = set()
    for ep in llm_endpoints:
        key = _endpoint_key(ep)
        seen.add(key)
        rule_ep = rule_by_key.get(key, {})
        combined = dict(rule_ep)
        combined.update({k: v for k, v in ep.items() if v})
        merged.append(combined)
    for ep in rule_endpoints:
        key = _endpoint_key(ep)
        if key and key not in seen:
            merged.append(ep)
            seen.add(key)
    return merged


def _union_strings(primary: list[str], secondary: list[str]) -> list[str]:
    """Merge two string lists, keeping order and deduplicating by normalized text."""
    if not primary:
        return list(secondary)
    if not secondary:
        return list(primary)
    merged = list(primary)
    seen = {_normalize_statement(s) for s in primary}
    for item in secondary:
        norm = _normalize_statement(item)
        if norm and norm not in seen:
            merged.append(item)
            seen.add(norm)
    return merged


def parse_requirement(
    requirement_text: str,
    retrieved_context: list[dict] | None = None,
    use_llm: bool = False,
    llm_config: OpenAIEnhancementConfig | None = None,
    out_diagnostics: dict[str, Any] | None = None,
    *,
    llm_retrieved_context: list[dict] | None = None,
) -> dict:
    """Parse requirement text into a structured, test-oriented representation.

    When ``llm_retrieved_context`` is not None, only the LLM enhancement step uses it
    (e.g. empty list to skip RAG snippets in the model prompt); rule extraction still
    uses ``retrieved_context``.
    """
    base_text = requirement_text.strip()
    retrieved_context = retrieved_context or []
    merged_text = _merge_context(base_text, retrieved_context)
    candidate_points = extract_candidate_test_points(base_text or merged_text)
    objective = _derive_objective(base_text or merged_text, candidate_points)
    rule_endpoints = _extract_api_endpoints(base_text)
    explicit_endpoint_actions = _extract_explicit_endpoint_actions(base_text)

    actions = [item["text"] for item in candidate_points if item["type"] == "action" and not _TABLE_ROW_RE.match(item["text"])]
    actions.extend(explicit_endpoint_actions)
    expectations = [item["text"] for item in candidate_points if item["type"] == "expectation"]
    preconditions = [item["text"] for item in candidate_points if item["type"] == "precondition"]
    constraints = [sentence for sentence in re.split(r"[\n。；;]+", base_text) if any(cue in sentence.lower() for cue in CONSTRAINT_CUES)]

    if not actions:
        for sentence in re.split(r"[\n。；;]+", base_text):
            sentence = sentence.strip()
            if _TABLE_ROW_RE.match(sentence):
                continue
            if sentence and any(verb in sentence.lower() or verb in sentence for verb in ACTION_VERBS):
                actions.append(sentence)
    actions = _filter_actions(actions, explicit_endpoint_actions=explicit_endpoint_actions, api_endpoints=rule_endpoints)

    if not expectations:
        for sentence in re.split(r"[\n。；;]+", base_text):
            sentence = sentence.strip()
            if sentence and any(cue in sentence.lower() or cue in sentence for cue in EXPECTATION_CUES):
                expectations.append(sentence)

    if not preconditions:
        for sentence in re.split(r"[\n。；;]+", base_text):
            sentence = sentence.strip()
            if sentence and any(cue in sentence.lower() or cue in sentence for cue in PRECONDITION_CUES):
                preconditions.append(sentence)

    if not actions:
        actions.append("执行核心业务动作")
    if not expectations:
        expectations.append("系统返回符合需求的可观察结果")

    ambiguities: list[str] = []
    if len(base_text) < 12:
        ambiguities.append("需求文本较短，建议补充业务目标、接口路径和断言细节")
    if not retrieved_context:
        ambiguities.append("未命中检索上下文，本次结果仅基于原始需求推断")
    llm_merged: dict[str, Any] = {}
    diagnostics = {
        "llm_attempted": bool(use_llm),
        "llm_applied": False,
        "fallback_reason": "",
        "llm_error_type": "",
    }
    context_for_llm = retrieved_context if llm_retrieved_context is None else llm_retrieved_context

    if use_llm:
        if llm_config is None:
            ambiguities.append("已启用 LLM 增强，但缺少 OPENAI_API_KEY 或相关配置")
            diagnostics["fallback_reason"] = "llm_config_missing"
            diagnostics["llm_error_type"] = "configuration_error"
        else:
            try:
                llm_payload, fallback_reason, llm_error_type = enhance_parsed_requirement_with_metadata(
                    requirement_text=base_text or merged_text,
                    retrieved_context=context_for_llm,
                    rule_based_result={
                        "objective": objective,
                        "actors": _extract_actors(merged_text),
                        "entities": extract_keywords(merged_text, limit=10),
                        "preconditions": _dedupe(preconditions),
                        "actions": _dedupe(actions),
                        "expected_results": _dedupe(expectations),
                        "constraints": _dedupe(constraints),
                        "ambiguities": _dedupe(ambiguities),
                    },
                    config=llm_config,
                )
                if llm_payload:
                    llm_merged = llm_payload
                    diagnostics["llm_applied"] = True
                else:
                    diagnostics["fallback_reason"] = fallback_reason or "llm_fallback_to_rules"
                    diagnostics["llm_error_type"] = llm_error_type or "llm_unavailable"
            except Exception:
                ambiguities.append("LLM 增强请求失败，已回退到规则解析")
                diagnostics["fallback_reason"] = "llm_runtime_error"
                diagnostics["llm_error_type"] = "unexpected_exception"

    merged_endpoints = filter_executable_api_endpoints(
        _union_endpoints(
            llm_merged.get("api_endpoints") or [],
            rule_endpoints,
        )
    )
    merged_actions = _union_strings(
        llm_merged.get("actions") or [],
        _dedupe(actions),
    )
    parsed = ParsedRequirement(
        objective=str(llm_merged.get("objective") or objective),
        actors=list(llm_merged.get("actors") or _extract_actors(merged_text)),
        entities=list(llm_merged.get("entities") or extract_keywords(merged_text, limit=10)),
        preconditions=list(llm_merged.get("preconditions") or _dedupe(preconditions)),
        actions=merged_actions or _dedupe(actions),
        expected_results=list(llm_merged.get("expected_results") or _dedupe(expectations)),
        constraints=list(llm_merged.get("constraints") or _dedupe(constraints)),
        ambiguities=_dedupe(list(llm_merged.get("ambiguities") or []) + ambiguities),
        source_chunks=[item.get("chunk_id", "") for item in retrieved_context if item.get("chunk_id")],
        api_endpoints=merged_endpoints or filter_executable_api_endpoints(list(rule_endpoints)),
    )
    if out_diagnostics is not None:
        out_diagnostics.update(diagnostics)
    return parsed.to_dict()
