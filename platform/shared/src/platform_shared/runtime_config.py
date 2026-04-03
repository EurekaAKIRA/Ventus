"""Platform-level runtime configuration loader."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RequirementAnalysisDefaults:
    use_llm: bool = False
    rag_enabled: bool = True
    retrieval_top_k: int = 5
    rerank_enabled: bool = False


@dataclass(frozen=True, slots=True)
class RequirementAnalysisRetrievalScoring:
    lexical_weight: float = 4.0
    vector_weight: float = 6.0
    rerank_vector_weight: float = 7.0
    rerank_lexical_weight: float = 2.0
    rerank_title_boost: float = 0.2
    rerank_content_boost: float = 0.2


@dataclass(frozen=True, slots=True)
class ContractKnowledgeConfig:
    """Curated platform API / OpenAPI snippets merged into RAG index."""

    enabled: bool = True
    official_score_boost: float = 2.0
    min_retrieval_score: float = 0.0
    openapi_spec_url: str = ""
    openapi_fetch_timeout_seconds: float = 8.0
    openapi_max_operations: int = 80


@dataclass(frozen=True, slots=True)
class RequirementAnalysisModelProfile:
    base_url: str = "https://api.hunyuan.cloud.tencent.com/v1"
    llm_model: str = "hunyuan-turbos-latest"
    embedding_model: str = "hunyuan-embedding"
    vision_model: str = "hunyuan-vision"
    timeout_seconds: float = 20.0
    retries: int = 1


@dataclass(frozen=True, slots=True)
class RequirementAnalysisRuntimeConfig:
    defaults: RequirementAnalysisDefaults = RequirementAnalysisDefaults()
    retrieval_scoring: RequirementAnalysisRetrievalScoring = RequirementAnalysisRetrievalScoring()
    contract_knowledge: ContractKnowledgeConfig = ContractKnowledgeConfig()
    embedding_batch_size: int = 32
    default_model_profile: str = "default"
    model_profiles: dict[str, RequirementAnalysisModelProfile] = field(
        default_factory=lambda: {"default": RequirementAnalysisModelProfile()}
    )


@dataclass(frozen=True, slots=True)
class PlatformRuntimeConfig:
    requirement_analysis: RequirementAnalysisRuntimeConfig = RequirementAnalysisRuntimeConfig()


_CACHED_PLATFORM_RUNTIME_CONFIG: PlatformRuntimeConfig | None = None


def get_platform_runtime_config() -> PlatformRuntimeConfig:
    global _CACHED_PLATFORM_RUNTIME_CONFIG
    if _CACHED_PLATFORM_RUNTIME_CONFIG is None:
        _CACHED_PLATFORM_RUNTIME_CONFIG = _load_platform_runtime_config()
    return _CACHED_PLATFORM_RUNTIME_CONFIG


def get_requirement_analysis_runtime_config() -> RequirementAnalysisRuntimeConfig:
    return get_platform_runtime_config().requirement_analysis


def get_requirement_analysis_model_profile(profile_name: str | None) -> tuple[str, RequirementAnalysisModelProfile]:
    config = get_requirement_analysis_runtime_config()
    requested = (profile_name or "").strip() or config.default_model_profile
    if requested in config.model_profiles:
        return requested, config.model_profiles[requested]
    return config.default_model_profile, config.model_profiles.get(
        config.default_model_profile,
        RequirementAnalysisModelProfile(),
    )


def _load_platform_runtime_config() -> PlatformRuntimeConfig:
    raw = _read_runtime_config_json()
    section = raw.get("requirement_analysis", {})
    defaults = section.get("defaults", {})
    scoring = section.get("retrieval_scoring", {})
    contract = section.get("contract_knowledge", {}) if isinstance(section.get("contract_knowledge"), dict) else {}
    raw_profiles = section.get("model_profiles", {})
    parsed_profiles: dict[str, RequirementAnalysisModelProfile] = {}
    if isinstance(raw_profiles, dict):
        for name, payload in raw_profiles.items():
            if not isinstance(payload, dict):
                continue
            key = str(name).strip()
            if not key:
                continue
            parsed_profiles[key] = RequirementAnalysisModelProfile(
                base_url=str(payload.get("base_url", "https://api.hunyuan.cloud.tencent.com/v1")).strip()
                or "https://api.hunyuan.cloud.tencent.com/v1",
                llm_model=str(payload.get("llm_model", "hunyuan-turbos-latest")).strip() or "hunyuan-turbos-latest",
                embedding_model=str(payload.get("embedding_model", "hunyuan-embedding")).strip() or "hunyuan-embedding",
                vision_model=str(payload.get("vision_model", "hunyuan-vision")).strip() or "hunyuan-vision",
                timeout_seconds=_as_float(payload.get("timeout_seconds"), default=20.0, min_value=1.0, max_value=120.0),
                retries=_as_int(payload.get("retries"), default=1, min_value=0, max_value=5),
            )
    if not parsed_profiles:
        parsed_profiles = {"default": RequirementAnalysisModelProfile()}
    default_profile = str(section.get("default_model_profile", "default")).strip() or "default"
    if default_profile not in parsed_profiles:
        default_profile = "default" if "default" in parsed_profiles else next(iter(parsed_profiles))
    return PlatformRuntimeConfig(
        requirement_analysis=RequirementAnalysisRuntimeConfig(
            defaults=RequirementAnalysisDefaults(
                use_llm=_as_bool(defaults.get("use_llm"), default=False),
                rag_enabled=_as_bool(defaults.get("rag_enabled"), default=True),
                retrieval_top_k=_as_int(defaults.get("retrieval_top_k"), default=5, min_value=1, max_value=20),
                rerank_enabled=_as_bool(defaults.get("rerank_enabled"), default=False),
            ),
            retrieval_scoring=RequirementAnalysisRetrievalScoring(
                lexical_weight=_as_float(scoring.get("lexical_weight"), default=4.0, min_value=0.0, max_value=20.0),
                vector_weight=_as_float(scoring.get("vector_weight"), default=6.0, min_value=0.0, max_value=20.0),
                rerank_vector_weight=_as_float(scoring.get("rerank_vector_weight"), default=7.0, min_value=0.0, max_value=20.0),
                rerank_lexical_weight=_as_float(scoring.get("rerank_lexical_weight"), default=2.0, min_value=0.0, max_value=20.0),
                rerank_title_boost=_as_float(scoring.get("rerank_title_boost"), default=0.2, min_value=0.0, max_value=5.0),
                rerank_content_boost=_as_float(scoring.get("rerank_content_boost"), default=0.2, min_value=0.0, max_value=5.0),
            ),
            contract_knowledge=ContractKnowledgeConfig(
                enabled=_as_bool(contract.get("enabled"), default=True),
                official_score_boost=_as_float(
                    contract.get("official_score_boost"),
                    default=2.0,
                    min_value=0.0,
                    max_value=20.0,
                ),
                min_retrieval_score=_as_float(
                    contract.get("min_retrieval_score"),
                    default=0.0,
                    min_value=0.0,
                    max_value=20.0,
                ),
                openapi_spec_url=str(contract.get("openapi_spec_url", "") or "").strip(),
                openapi_fetch_timeout_seconds=_as_float(
                    contract.get("openapi_fetch_timeout_seconds"),
                    default=8.0,
                    min_value=1.0,
                    max_value=60.0,
                ),
                openapi_max_operations=_as_int(
                    contract.get("openapi_max_operations"),
                    default=80,
                    min_value=1,
                    max_value=500,
                ),
            ),
            embedding_batch_size=_as_int(
                section.get("embedding_batch_size"),
                default=32,
                min_value=1,
                max_value=256,
            ),
            default_model_profile=default_profile,
            model_profiles=parsed_profiles,
        )
    )


def _read_runtime_config_json() -> dict[str, Any]:
    primary = Path(__file__).resolve().parents[2] / "config" / "runtime_config.json"
    legacy = Path(__file__).resolve().parents[3] / "requirement-analysis" / "config" / "runtime_config.json"
    for path in (primary, legacy):
        if not path.exists():
            continue
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            continue
    return {}


def _as_bool(raw: Any, *, default: bool) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        value = raw.strip().lower()
        if value in {"1", "true", "yes", "on"}:
            return True
        if value in {"0", "false", "no", "off"}:
            return False
    return default


def _as_int(raw: Any, *, default: int, min_value: int, max_value: int) -> int:
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, str) and raw.strip().isdigit():
        value = int(raw.strip())
    else:
        value = default
    return max(min_value, min(max_value, value))


def _as_float(raw: Any, *, default: float, min_value: float, max_value: float) -> float:
    value: float
    if isinstance(raw, (int, float)):
        value = float(raw)
    elif isinstance(raw, str):
        try:
            value = float(raw.strip())
        except ValueError:
            value = default
    else:
        value = default
    return max(min_value, min(max_value, value))
