"""Requirement parsing helpers with API-oriented cues."""

from __future__ import annotations

import json
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
    r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[\w/\-{}:.?=&%]+)",
    re.IGNORECASE,
)
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_STEP_BLOCK_RE = re.compile(r"^####\s*Step[^\n]*\n(?P<body>.*?)(?=^####\s*Step|\Z)", re.MULTILINE | re.DOTALL)
_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.IGNORECASE | re.DOTALL)
_SAVE_CONTEXT_RE = re.compile(r"-\s*`?[a-zA-Z_][a-zA-Z0-9_]*`?\s*(?:<-|←)\s*`?(json\.[a-zA-Z0-9_.]+)`?")
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
    for method, path, description in _extract_endpoint_pairs_from_interface_blocks(text):
        key = f"{method} {path}"
        if key not in seen:
            seen.add(key)
            endpoints.append({"method": method, "path": path, "description": description or description_map.get(key, "")})
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


def _extract_endpoint_pairs_from_interface_blocks(text: str) -> list[tuple[str, str, str]]:
    pairs: list[tuple[str, str, str]] = []
    in_interface_section = False
    current_name = ""
    current_method = ""
    current_path = ""
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        heading_match = _LINE_HEADING_RE.match(stripped)
        if heading_match:
            title = heading_match.group(2).strip()
            level = len(heading_match.group(1))
            if level == 2:
                if in_interface_section and current_method and current_path:
                    pairs.append((current_method.upper(), current_path, current_name))
                in_interface_section = title == "接口清单"
                current_name = ""
                current_method = ""
                current_path = ""
                continue
            if not in_interface_section:
                continue
            if level == 3 and title.startswith("接口："):
                if current_method and current_path:
                    pairs.append((current_method.upper(), current_path, current_name))
                current_name = title.split("：", 1)[1].strip()
                current_method = ""
                current_path = ""
                continue
            if in_interface_section and level <= 3:
                if current_method and current_path:
                    pairs.append((current_method.upper(), current_path, current_name))
                current_name = ""
                current_method = ""
                current_path = ""
            continue
        if not in_interface_section:
            continue
        line = stripped.strip("-* ").strip()
        if line.startswith("方法："):
            current_method = line.split("：", 1)[1].strip().strip("`").upper()
        elif line.startswith("路径："):
            current_path = line.split("：", 1)[1].strip().strip("`")
    if in_interface_section and current_method and current_path:
        pairs.append((current_method.upper(), current_path, current_name))
    return pairs


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
    field_hints = _extract_endpoint_field_hints(text)
    interface_hints = _extract_interface_contract_hints(text)
    for ep in endpoints:
        path = str(ep.get("path", ""))
        method = str(ep.get("method", "")).upper()
        if not ep.get("group"):
            ep["group"] = section_map.get(path) or _infer_endpoint_group(path)
        if not ep.get("depends_on"):
            ep["depends_on"] = _infer_depends_on(path, all_paths)
        key = f"{method} {path}"
        hinted = field_hints.get(key, {})
        contract = interface_hints.get(key, {})
        ep["request_body_fields"] = _merge_field_specs(ep.get("request_body_fields"), hinted.get("request_body_fields"))
        ep["response_fields"] = _merge_field_specs(ep.get("response_fields"), hinted.get("response_fields"))
        ep["request_body_fields"] = _merge_field_specs(ep.get("request_body_fields"), contract.get("request_body_fields"))
        if contract.get("description_suffix"):
            desc = str(ep.get("description", "")).strip()
            suffix = str(contract.get("description_suffix", "")).strip()
            if suffix and suffix.lower() not in desc.lower():
                ep["description"] = f"{desc}；{suffix}".strip("；")
    return endpoints


def _merge_field_specs(existing: Any, hinted: Any) -> list[dict[str, Any]]:
    def _names(value: Any) -> list[str]:
        output: list[str] = []
        for item in value or []:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
            else:
                name = str(item).strip()
            if name:
                output.append(name)
        return output

    merged: list[str] = []
    for name in _names(existing) + _names(hinted):
        if name not in merged:
            merged.append(name)
    return [{"name": name, "field_type": "string", "required": True, "description": ""} for name in merged]


def _extract_endpoint_field_hints(text: str) -> dict[str, dict[str, list[dict[str, Any]]]]:
    hints: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for block_match in _STEP_BLOCK_RE.finditer(text):
        block = block_match.group("body")
        endpoint_match = _EXPLICIT_ENDPOINT_RE.search(block)
        if not endpoint_match:
            continue
        method = endpoint_match.group(1).upper()
        path = endpoint_match.group(2)
        key = f"{method} {path}"
        request_fields: list[str] = []
        response_fields: list[str] = []

        json_match = _JSON_BLOCK_RE.search(block)
        if json_match:
            try:
                payload = json.loads(json_match.group(1))
                request_fields.extend(_flatten_json_field_names(payload))
            except Exception:
                pass

        lowered_block = block.lower()
        expected_idx = lowered_block.find("**expected:**")
        if expected_idx >= 0:
            expected_part = block[expected_idx:]
            for token in _INLINE_CODE_RE.findall(expected_part):
                candidate = str(token).strip()
                if not candidate:
                    continue
                lowered = candidate.lower()
                if lowered.startswith("http ") or lowered in {"http", "json"}:
                    continue
                if candidate.isdigit() or "/" in candidate or "{{" in candidate:
                    continue
                if lowered.startswith("json."):
                    candidate = candidate[5:]
                response_fields.append(candidate)
            for save_match in _SAVE_CONTEXT_RE.finditer(expected_part):
                path_expr = save_match.group(1).strip()
                if path_expr.lower().startswith("json."):
                    response_fields.append(path_expr[5:])

        hints[key] = {
            "request_body_fields": [{"name": name, "field_type": "string", "required": True, "description": ""} for name in _dedupe(request_fields)],
            "response_fields": [{"name": name, "field_type": "string", "required": True, "description": ""} for name in _dedupe(response_fields)],
        }
    return hints


def _flatten_json_field_names(payload: Any, prefix: str = "") -> list[str]:
    if not isinstance(payload, dict):
        return []
    names: list[str] = []
    for key, value in payload.items():
        token = str(key).strip()
        if not token:
            continue
        full = f"{prefix}.{token}" if prefix else token
        names.append(full)
        if isinstance(value, dict):
            names.extend(_flatten_json_field_names(value, full))
    return names


_SECTION_HEADING_RE = re.compile(r"^#{1,4}\s+(.+)", re.MULTILINE)
_LINE_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$")
_SCENARIO_HEADING_RE = re.compile(r"^scenario\s*:", re.IGNORECASE)

_METADATA_SECTION_TITLES = (
    "文档定位",
    "环境信息",
    "鉴权与全局约束",
    "资源依赖说明",
    "接口清单",
    "预期效果",
    "成功标准",
    "可选增强信息",
)
_STRUCTURED_META_PREFIXES = (
    "涉及接口",
    "关键依赖",
    "资源来源",
    "接口：",
    "方法：",
    "路径：",
    "功能：",
    "鉴权：",
    "请求语义：",
    "结果语义：",
    "资源前置条件：",
    "鉴权接口：",
    "令牌字段：",
    "注入方式：",
    "默认请求头：",
    "全局 query 参数：",
    "全局响应 envelope：",
    "特殊状态码规则：",
    "轮询或异步规则：",
)


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


def _normalize_heading_title(title: str) -> str:
    lowered = str(title or "").strip().lower()
    lowered = re.sub(r"^[#\s]+", "", lowered)
    return lowered


def _extract_markdown_sections(text: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in text.splitlines():
        heading_match = _LINE_HEADING_RE.match(raw_line.strip())
        if heading_match:
            if current is not None:
                current["body"] = "\n".join(current["lines"]).strip()
                current.pop("lines", None)
                sections.append(current)
            current = {
                "level": len(heading_match.group(1)),
                "title": heading_match.group(2).strip(),
                "lines": [],
            }
            continue
        if current is None:
            continue
        current["lines"].append(raw_line)
    if current is not None:
        current["body"] = "\n".join(current["lines"]).strip()
        current.pop("lines", None)
        sections.append(current)
    return sections


def _extract_scenario_text(text: str) -> str:
    scenario_bodies: list[str] = []
    for section in _extract_markdown_sections(text):
        title = str(section.get("title", "")).strip()
        if _SCENARIO_HEADING_RE.match(title):
            body = str(section.get("body", "")).strip()
            summary_lines: list[str] = []
            for raw_line in body.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                if any(line.startswith(prefix) or line.startswith(f"**{prefix}") for prefix in _STRUCTURED_META_PREFIXES):
                    continue
                summary_lines.append(line)
            parts = [title]
            if summary_lines:
                parts.append("\n".join(summary_lines))
            scenario_bodies.append("\n".join(parts))
    return "\n\n".join(part for part in scenario_bodies if part)


def _extract_scenario_titles(text: str) -> list[str]:
    titles: list[str] = []
    for section in _extract_markdown_sections(text):
        title = str(section.get("title", "")).strip()
        if _SCENARIO_HEADING_RE.match(title):
            titles.append(title)
    return titles


def _extract_expectation_text(text: str) -> str:
    blocks: list[str] = []
    for section in _extract_markdown_sections(text):
        title = _normalize_heading_title(section.get("title", ""))
        if title in {"预期效果", "成功标准"}:
            body = str(section.get("body", "")).strip()
            if body:
                blocks.append(body)
    return "\n".join(blocks)


def _extract_global_auth_injection(text: str) -> str:
    in_auth_section = False
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        heading_match = _LINE_HEADING_RE.match(stripped)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            if level == 2:
                in_auth_section = title == "鉴权与全局约束"
                continue
        if not in_auth_section:
            continue
        line = stripped.strip("-* ").strip()
        if line.startswith("注入方式："):
            return line.split("：", 1)[1].strip()
    return ""


def _extract_auth_header_hints(text: str) -> list[str]:
    headers: list[str] = []
    in_auth_section = False
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        heading_match = _LINE_HEADING_RE.match(stripped)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            if level == 2:
                in_auth_section = title == "鉴权与全局约束"
                continue
        if not in_auth_section:
            continue
        line = stripped.strip("-* ").strip().strip("`")
        header_match = re.search(r"\b([A-Za-z][A-Za-z0-9-]*)\s*:\s*\{\{", line)
        if header_match:
            header_name = header_match.group(1).strip()
            if header_name and header_name not in headers:
                headers.append(header_name)
    return headers


def _extract_interface_contract_hints(text: str) -> dict[str, dict[str, Any]]:
    hints: dict[str, dict[str, Any]] = {}
    global_injection = _extract_global_auth_injection(text).lower()
    auth_header_hints = _extract_auth_header_hints(text)
    in_interface_section = False
    current: dict[str, str] = {}

    def flush_current() -> None:
        if not current:
            return
        method = current.get("method", "").upper().strip()
        path = current.get("path", "").strip()
        auth_value = current.get("auth", "").strip()
        if not method or not path:
            current.clear()
            return
        key = f"{method} {path}"
        request_fields: list[str] = []
        desc_parts: list[str] = []
        auth_required = auth_value.lower().startswith(("是", "yes", "true"))
        if auth_required and "cookie" in global_injection and "token" in global_injection:
            request_fields.append("Cookie")
            desc_parts.append("需要显式携带 Cookie token")
        if auth_required:
            for header_name in auth_header_hints:
                lowered_header = header_name.lower()
                if lowered_header == "x-auth-token" and "/secret/note" not in path.lower():
                    continue
                if lowered_header == "authorization" and "/secret/note" not in path.lower():
                    continue
                if header_name not in request_fields:
                    request_fields.append(header_name)
        if request_fields or desc_parts:
            hints[key] = {
                "request_body_fields": [{"name": name, "field_type": "string", "required": True, "description": ""} for name in request_fields],
                "description_suffix": "；".join(desc_parts),
            }
        current.clear()

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        heading_match = _LINE_HEADING_RE.match(stripped)
        if heading_match:
            title = heading_match.group(2).strip()
            level = len(heading_match.group(1))
            if level == 2:
                flush_current()
                in_interface_section = title == "接口清单"
                continue
            if not in_interface_section:
                continue
            if level == 3 and title.startswith("接口："):
                flush_current()
                current = {}
                continue
            if in_interface_section and level <= 3:
                flush_current()
            continue
        if not in_interface_section or not current and not stripped.startswith("-"):
            continue
        line = stripped.strip("-* ").strip()
        if line.startswith("方法："):
            current["method"] = line.split("：", 1)[1].strip().strip("`")
        elif line.startswith("路径："):
            current["path"] = line.split("：", 1)[1].strip().strip("`")
        elif line.startswith("鉴权："):
            current["auth"] = line.split("：", 1)[1].strip()
    flush_current()
    return hints


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
            if normalized and not _is_non_executable_action(normalized):
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
    if any(normalized.startswith(prefix) for prefix in _STRUCTURED_META_PREFIXES):
        return True
    if normalized.startswith("**") and any(prefix in normalized for prefix in _STRUCTURED_META_PREFIXES):
        return True
    if normalized.startswith("## "):
        return True
    if normalized.startswith("### "):
        return True
    if normalized.startswith("#### "):
        return True
    if title := normalized.lstrip("#").strip():
        if title in _METADATA_SECTION_TITLES:
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
CONSTRAINT_CUES = ("must", "cannot", "only", "require", "必须", "只能", "不可", "不能", "限制", "预期返回", "expected", "应返回", "可能返回")
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

    def _priority(item: dict[str, Any], index: int) -> tuple[float, float, int]:
        title = str(item.get("section_title", "") or "")
        lowered_title = title.lower()
        content = str(item.get("content", "") or "")
        doc_type = str(item.get("doc_type", "") or "")
        score = 0.0
        if not doc_type:
            score += 2.0
        if "接口" in title or "scenario" in lowered_title or "鉴权" in title or "资源" in title:
            score += 2.0
        if _EXPLICIT_ENDPOINT_RE.search(content) or "路径：" in content or "**涉及接口:**" in content:
            score += 1.5
        if title in {"文档定位", "预期效果"}:
            score -= 1.0
        return (score, float(item.get("score", 0.0) or 0.0), -index)

    ranked = sorted(enumerate(retrieved_context), key=lambda pair: _priority(pair[1], pair[0]), reverse=True)
    for _, item in ranked[:4]:
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

    When ``llm_retrieved_context`` is not None, only the LLM enhancement step uses it;
    rule extraction still uses ``retrieved_context``. Default ``None`` means both use the
    same retrieved list.
    """
    base_text = requirement_text.strip()
    scenario_text = _extract_scenario_text(base_text)
    scenario_titles = _extract_scenario_titles(base_text)
    expectation_text = _extract_expectation_text(base_text)
    action_source_text = scenario_text or base_text
    retrieved_context = retrieved_context or []
    merged_text = _merge_context(base_text, retrieved_context)
    candidate_points = extract_candidate_test_points(action_source_text or merged_text)
    objective = _derive_objective(base_text or merged_text, candidate_points)
    rule_endpoints = _extract_api_endpoints(base_text)
    explicit_endpoint_actions = _extract_explicit_endpoint_actions(action_source_text)

    actions = [item["text"] for item in candidate_points if item["type"] == "action" and not _TABLE_ROW_RE.match(item["text"])]
    actions.extend(scenario_titles)
    actions.extend(explicit_endpoint_actions)
    expectations = [item["text"] for item in candidate_points if item["type"] == "expectation"]
    preconditions = [item["text"] for item in candidate_points if item["type"] == "precondition"]
    if expectation_text:
        expectations.extend(
            line.strip("-* ").strip()
            for line in expectation_text.splitlines()
            if line.strip().startswith(("-", "*"))
        )
    constraints = [sentence for sentence in re.split(r"[\n。；;]+", base_text) if any(cue in sentence.lower() for cue in CONSTRAINT_CUES)]

    if not actions:
        for sentence in re.split(r"[\n。；;]+", action_source_text):
            sentence = sentence.strip()
            if _TABLE_ROW_RE.match(sentence):
                continue
            if sentence and any(verb in sentence.lower() or verb in sentence for verb in ACTION_VERBS):
                actions.append(sentence)
    actions = _filter_actions(actions, explicit_endpoint_actions=explicit_endpoint_actions, api_endpoints=rule_endpoints)

    if not expectations:
        for sentence in re.split(r"[\n。；;]+", expectation_text or base_text):
            sentence = sentence.strip()
            if sentence and any(cue in sentence.lower() or cue in sentence for cue in EXPECTATION_CUES):
                expectations.append(sentence)

    if not preconditions:
        for sentence in re.split(r"[\n。；;]+", scenario_text or base_text):
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
                enhancement_phase_ms: dict[str, float] = {}
                llm_response_diagnostics: dict[str, Any] = {}
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
                    out_phase_timings_ms=enhancement_phase_ms,
                    out_response_diagnostics=llm_response_diagnostics,
                )
                diagnostics["enhancement_phase_timings_ms"] = enhancement_phase_ms
                if llm_response_diagnostics:
                    diagnostics["llm_response_diagnostics"] = llm_response_diagnostics
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
