"""Feature validation helpers."""

from __future__ import annotations

from .models import ValidationReport

VAGUE_WORDS = ("正常", "正确", "相关", "对应", "适当", "成功处理")


def validate_feature_text(feature_text: str) -> dict:
    """Return a validation report for generated feature text."""
    errors: list[str] = []
    warnings: list[str] = []
    lines = [line.rstrip() for line in feature_text.splitlines() if line.strip()]

    if "Feature:" not in feature_text:
        errors.append("缺少 Feature 头部")
    if "Scenario:" not in feature_text:
        errors.append("缺少 Scenario 定义")
    if "Then " not in feature_text:
        errors.append("缺少 Then 断言步骤")

    scenario_count = 0
    step_count = 0
    scenario_step_count = 0
    has_then_in_current = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Scenario:"):
            if scenario_count > 0 and not has_then_in_current:
                errors.append("存在缺少 Then 的场景")
            scenario_count += 1
            scenario_step_count = 0
            has_then_in_current = False
            continue
        if stripped.startswith(("Given ", "When ", "Then ", "And ")):
            step_count += 1
            scenario_step_count += 1
            if len(stripped) > 80:
                warnings.append(f"步骤过长，建议拆分：{stripped[:40]}...")
            if any(word in stripped for word in VAGUE_WORDS) and stripped.startswith(("Then ", "And ")):
                warnings.append(f"断言表达偏抽象，建议改为可观察结果：{stripped}")
            if stripped.startswith("Then "):
                has_then_in_current = True
            if scenario_step_count > 8:
                warnings.append("单个场景步骤较多，建议进一步拆分")

    if scenario_count > 0 and not has_then_in_current:
        errors.append("最后一个场景缺少 Then 断言")

    report = ValidationReport(
        feature_name=_extract_feature_name(feature_text),
        passed=not errors,
        errors=_dedupe(errors),
        warnings=_dedupe(warnings),
        metrics={
            "scenario_count": scenario_count,
            "average_step_count": round((step_count / scenario_count), 2) if scenario_count else 0,
            "step_count": step_count,
        },
    )
    return report.to_dict()


def _extract_feature_name(feature_text: str) -> str:
    """Extract feature name from gherkin text."""
    for line in feature_text.splitlines():
        if line.startswith("Feature:"):
            return line.replace("Feature:", "", 1).strip()
    return "unknown_feature"


def _dedupe(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen
