from __future__ import annotations

import json

from requirement_analysis.knowledge_library import load_curated_knowledge_chunks


def test_knowledge_library_loads_generic_api_docs() -> None:
    chunks = load_curated_knowledge_chunks(
        raw_text="# Demo\n\n### Scenario: Booking lifecycle\n`POST /booking`\n`DELETE /booking/{id}`\nAuthorization: Bearer x",
        cleaned_text="# Demo\n\n### Scenario: Booking lifecycle\n`POST /booking`\n`DELETE /booking/{id}`\nAuthorization: Bearer x",
    )

    source_files = {chunk.source_file for chunk in chunks}
    assert "standards/api_requirement_spec_v1.md" in source_files
    assert "generation_rules/dependency_lifecycle.md" in source_files
    assert "generation_rules/auth_propagation.md" in source_files


def test_knowledge_library_scopes_platform_docs() -> None:
    chunks = load_curated_knowledge_chunks(
        raw_text="# Task Center\n\n`POST /api/tasks`\n`POST /api/tasks/{task_id}/execute`",
        cleaned_text="# Task Center\n\n`POST /api/tasks`\n`POST /api/tasks/{task_id}/execute`",
    )

    source_files = {chunk.source_file for chunk in chunks}
    assert "domain/platform/task_center_api.md" in source_files


def test_knowledge_library_matches_external_domain_docs_without_platform_pollution() -> None:
    chunks = load_curated_knowledge_chunks(
        raw_text="# Restful Booker\n\n`POST /auth`\n`POST /booking`\n`DELETE /booking/{id}`",
        cleaned_text="# Restful Booker\n\n`POST /auth`\n`POST /booking`\n`DELETE /booking/{id}`",
    )

    source_files = {chunk.source_file for chunk in chunks}
    assert "domain/external/restful_booker.md" in source_files
    assert "domain/platform/task_center_api.md" not in source_files


def test_knowledge_library_supports_external_registry(monkeypatch, tmp_path) -> None:
    knowledge_root = tmp_path / "extra_knowledge"
    manifests = knowledge_root / "manifests"
    docs_dir = knowledge_root / "external"
    manifests.mkdir(parents=True)
    docs_dir.mkdir(parents=True)

    registry_path = manifests / "extra_registry.json"
    doc_path = docs_dir / "custom_api.md"
    registry_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "knowledge_id": "custom_api_guidance",
                        "path": "external/custom_api.md",
                        "title": "Custom API Guidance",
                        "knowledge_type": "external_domain",
                        "domain": "custom",
                        "activation_conditions": ["api_document"],
                        "tags": ["custom", "api"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    doc_path.write_text(
        "# Custom API\n\n## Auth\nPOST /custom/auth returns token\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("REQUIREMENT_ANALYSIS_EXTRA_KNOWLEDGE_REGISTRY", str(registry_path))
    monkeypatch.setenv("REQUIREMENT_ANALYSIS_EXTRA_KNOWLEDGE_ROOT", str(knowledge_root))

    chunks = load_curated_knowledge_chunks(
        raw_text="# Custom\n\n`POST /custom/auth`",
        cleaned_text="# Custom\n\n`POST /custom/auth`",
    )

    source_files = {chunk.source_file for chunk in chunks}
    assert "external/custom_api.md" in source_files
