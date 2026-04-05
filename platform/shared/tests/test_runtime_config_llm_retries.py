from __future__ import annotations

from platform_shared.runtime_config import get_requirement_analysis_model_profile


def test_default_model_profile_uses_single_llm_retry() -> None:
    _, profile = get_requirement_analysis_model_profile("default")
    assert profile.llm_retries == 1
