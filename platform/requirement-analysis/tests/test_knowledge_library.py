from __future__ import annotations

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
