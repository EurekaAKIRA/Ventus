"""Feature validation helpers."""

from __future__ import annotations

from platform_shared.models import ValidationReport

VAGUE_WORDS = ("正常", "正确", "相关", "对应", "适当", "成功处理")


def validate_feature_text(feature_text: str) -> dict:
    """Return a validation report for generated feature text."""
    errors: list[str] = []
    warnings: list[str] = []
    lines = [line.rstrip() for line in feature_text.splitlines() if line.strip()]

    if ("功能:" not in feature_text) and ("Feature:" not in feature_text):
        errors.append("缺少 功能（Feature）头部")
    if ("场景:" not in feature_text) and ("Scenario:" not in feature_text):
        errors.append("缺少 场景（Scenario）定义")
    if ("那么 " not in feature_text) and ("Then " not in feature_text):
        errors.append("缺少 那么（Then）断言步骤")

    scenario_count = 0
    step_count = 0
    scenario_step_count = 0
    has_then_in_current = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("场景:", "Scenario:")):
            if scenario_count > 0 and not has_then_in_current:
                errors.append("存在缺少 那么（Then） 的场景")
            scenario_count += 1
            scenario_step_count = 0
            has_then_in_current = False
            continue
        if stripped.startswith(("假如 ", "当 ", "那么 ", "并且 ", "Given ", "When ", "Then ", "And ")):
            step_count += 1
            scenario_step_count += 1
            if len(stripped) > 80:
                warnings.append(f"步骤过长，建议拆分：{stripped[:40]}...")
            if any(word in stripped for word in VAGUE_WORDS) and stripped.startswith(("那么 ", "并且 ", "Then ", "And ")):
                warnings.append(f"断言表达偏抽象，建议改为可观察结果：{stripped}")
            if stripped.startswith(("那么 ", "Then ")):
                has_then_in_current = True
            if scenario_step_count > 8:
                warnings.append("单个场景步骤较多，建议进一步拆分")

    if scenario_count > 0 and not has_then_in_current:
        errors.append("最后一个场景缺少 那么（Then） 断言")

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
        if line.startswith("功能:"):
            return line.replace("功能:", "", 1).strip()
        if line.startswith("Feature:"):
            return line.replace("Feature:", "", 1).strip()
    return "unknown_feature"


def _dedupe(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen
