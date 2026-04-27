"""API tests for auth, profile, projects, and task ownership."""

from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[3]
    legacy = root / "legacy"
    additions = [
        root / "platform" / "shared" / "src",
        root / "platform" / "requirement-analysis" / "src",
        root / "platform" / "case-generation" / "src",
        root / "platform" / "result-analysis" / "src",
        root / "platform" / "execution-engine" / "api-runner" / "src",
        root / "platform" / "execution-engine" / "core" / "src",
        root / "platform" / "task-center" / "src",
        legacy / "lavague-core",
        legacy / "lavague-integrations" / "drivers" / "lavague-drivers-selenium",
        legacy / "lavague-integrations" / "drivers" / "lavague-drivers-playwright",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


_extend_path()


def _build_client(tmp_path, monkeypatch) -> TestClient:
    root = Path(__file__).resolve().parents[3]
    monkeypatch.setenv("TASK_CENTER_PERSISTENCE_BACKEND", "db")
    monkeypatch.setenv("TASK_CENTER_DATABASE_URL", f"sqlite+pysqlite:///{(tmp_path / 'api.db').as_posix()}")
    monkeypatch.setenv("TASK_CENTER_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("TASK_CENTER_JWT_SECRET", "test-secret-with-at-least-32-bytes")
    monkeypatch.delenv("TASK_CENTER_REDIS_URL", raising=False)

    for mod_name in list(sys.modules):
        if mod_name == "task_center.api" or mod_name.startswith("task_center."):
            sys.modules.pop(mod_name, None)

    api_module = importlib.import_module("task_center.api")
    api_module = importlib.reload(api_module)
    return TestClient(api_module.app)


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_auth_profile_and_refresh_flow(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
    assert admin_login.status_code == 200
    assert admin_login.json()["data"]["user"]["username"] == "admin"

    register = client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "password123", "email": "alice@example.com"},
    )
    assert register.status_code == 201
    assert register.json()["code"] == "AUTH_REGISTERED"

    login = client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert login.status_code == 200
    login_data = login.json()["data"]
    access_token = login_data["access_token"]
    refresh_token = login_data["refresh_token"]

    me = client.get("/api/auth/me", headers=_auth_headers(access_token))
    assert me.status_code == 200
    assert me.json()["data"]["user"]["username"] == "alice"

    updated = client.patch(
        "/api/users/me",
        json={"display_name": "Alice QA"},
        headers=_auth_headers(access_token),
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["display_name"] == "Alice QA"

    refreshed = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    assert refreshed.json()["code"] == "AUTH_REFRESHED"

    logout = client.post("/api/auth/logout", headers=_auth_headers(access_token))
    assert logout.status_code == 200

    denied = client.get("/api/auth/me", headers=_auth_headers(access_token))
    assert denied.status_code == 401


def test_project_membership_controls_task_visibility(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    for username in ("alice", "bob", "charlie"):
        res = client.post(
            "/api/auth/register",
            json={"username": username, "password": "password123", "email": f"{username}@example.com"},
        )
        assert res.status_code == 201

    alice_login = client.post("/api/auth/login", json={"username": "alice", "password": "password123"}).json()["data"]
    bob_login = client.post("/api/auth/login", json={"username": "bob", "password": "password123"}).json()["data"]
    charlie_login = client.post("/api/auth/login", json={"username": "charlie", "password": "password123"}).json()["data"]

    created_project = client.post(
        "/api/projects",
        json={"name": "Shared Project", "description": "project for visibility test"},
        headers=_auth_headers(alice_login["access_token"]),
    )
    assert created_project.status_code == 201
    project_id = created_project.json()["data"]["id"]

    add_member = client.post(
        f"/api/projects/{project_id}/members",
        json={"username": "bob", "role": "viewer"},
        headers=_auth_headers(alice_login["access_token"]),
    )
    assert add_member.status_code == 201

    task_resp = client.post(
        "/api/tasks",
        json={
            "task_name": "Shared Task",
            "source_type": "text",
            "requirement_text": "api task owned by project",
            "target_system": "https://example.com",
            "project_id": project_id,
        },
        headers=_auth_headers(alice_login["access_token"]),
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["data"]["task_id"]

    bob_list = client.get("/api/tasks", headers=_auth_headers(bob_login["access_token"]))
    assert bob_list.status_code == 200
    bob_task_ids = [item["task_id"] for item in bob_list.json()["data"]["items"]]
    assert task_id in bob_task_ids

    project_detail = client.get(
        f"/api/projects/{project_id}",
        headers=_auth_headers(alice_login["access_token"]),
    )
    assert project_detail.status_code == 200
    member_usernames = [item["username"] for item in project_detail.json()["data"]["members"]]
    assert "alice" in member_usernames
    assert "bob" in member_usernames

    search_users = client.get(
        "/api/users",
        params={"keyword": "bo"},
        headers=_auth_headers(alice_login["access_token"]),
    )
    assert search_users.status_code == 200
    searched_usernames = [item["username"] for item in search_users.json()["data"]]
    assert "bob" in searched_usernames

    charlie_detail = client.get(f"/api/tasks/{task_id}", headers=_auth_headers(charlie_login["access_token"]))
    assert charlie_detail.status_code == 403


def test_project_scoped_environment_crud(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)
    import task_center.api as api_module
    from task_center.db import Environment

    client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "password123", "email": "alice@example.com"},
    )
    alice_login = client.post("/api/auth/login", json={"username": "alice", "password": "password123"}).json()["data"]
    project_id = alice_login["projects"][0]["id"]

    create_env = client.post(
        "/api/environments",
        json={
            "name": "staging",
            "base_url": "https://staging.example.com",
            "default_headers": {"X-Test": "1", "Authorization": "Bearer demo-token"},
            "auth": {"type": "bearer", "token": "demo-token"},
            "cookies": {"session": "cookie-demo"},
            "project_id": project_id,
        },
        headers=_auth_headers(alice_login["access_token"]),
    )
    assert create_env.status_code == 201
    create_data = create_env.json()["data"]
    assert create_data["default_headers"]["Authorization"] == "***MASKED***"
    assert create_data["default_headers_masked"] is True
    assert create_data["auth"]["token"] == "***MASKED***"
    assert create_data["auth_masked"] is True
    assert create_data["cookies"]["session"] == "***MASKED***"
    assert create_data["cookies_masked"] is True

    store = api_module.registry.db_store
    assert store is not None
    with store.session() as session:
        row = session.query(Environment).filter(Environment.name == "staging").one()
        assert row.auth_json["__task_center_secure__"] is True
        assert row.cookies_json["__task_center_secure__"] is True
        assert row.default_headers_json["__task_center_secure__"] is True
        assert "demo-token" not in json.dumps(row.auth_json)
        assert "cookie-demo" not in json.dumps(row.cookies_json)

    list_env = client.get(
        "/api/environments",
        params={"project_id": project_id},
        headers=_auth_headers(alice_login["access_token"]),
    )
    assert list_env.status_code == 200
    env_names = {item["name"] for item in list_env.json()["data"]}
    assert "staging" in env_names
    assert "test" in env_names

    detail_env = client.get(
        "/api/environments/staging",
        params={"project_id": project_id},
        headers=_auth_headers(alice_login["access_token"]),
    )
    assert detail_env.status_code == 200
    detail_payload = detail_env.json()["data"]
    assert detail_payload["base_url"] == "https://staging.example.com"
    assert detail_payload["auth"]["token"] == "***MASKED***"
    assert detail_payload["cookies"]["session"] == "***MASKED***"

    update_env = client.put(
        "/api/environments/staging",
        json={**detail_payload, "name": "ignored", "base_url": "https://updated-staging.example.com", "description": "updated", "project_id": project_id},
        headers=_auth_headers(alice_login["access_token"]),
    )
    assert update_env.status_code == 200
    assert update_env.json()["data"]["base_url"] == "https://updated-staging.example.com"
    preserved = store.get_environment(name="staging", project_id=project_id)
    assert preserved is not None
    assert preserved.auth["token"] == "demo-token"
    assert preserved.cookies["session"] == "cookie-demo"
    assert preserved.default_headers["Authorization"] == "Bearer demo-token"

    audit_logs = client.get(
        "/api/audit/logs",
        params={"resource_type": "environment"},
        headers=_auth_headers(alice_login["access_token"]),
    )
    assert audit_logs.status_code == 200
    logged_actions = [item["action"] for item in audit_logs.json()["data"]["items"]]
    assert "environment.save" in logged_actions
    assert "environment.update" in logged_actions

    delete_env = client.delete(
        "/api/environments/staging",
        params={"project_id": project_id},
        headers=_auth_headers(alice_login["access_token"]),
    )
    assert delete_env.status_code == 200

    audit_logs_after_delete = client.get(
        "/api/audit/logs",
        params={"resource_type": "environment"},
        headers=_auth_headers(alice_login["access_token"]),
    )
    assert audit_logs_after_delete.status_code == 200
    logged_actions_after_delete = [item["action"] for item in audit_logs_after_delete.json()["data"]["items"]]
    assert "environment.delete" in logged_actions_after_delete


def test_environment_probe_and_audit_filters(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "password123", "email": "alice@example.com"},
    )
    alice_login = client.post("/api/auth/login", json={"username": "alice", "password": "password123"}).json()["data"]
    project_id = alice_login["projects"][0]["id"]

    import task_center.api as api_module

    monkeypatch.setattr(
        api_module,
        "run_preflight_check",
        lambda **_: {
            "task_id": "environment-probe:staging",
            "overall_status": "passed",
            "blocking": False,
            "checks": [
                {"name": "base_url_reachable", "status": "passed", "elapsed_ms": 23.5, "message": "/health reachable"},
                {"name": "auth_config_valid", "status": "passed", "elapsed_ms": 0.0, "message": "auth configuration present"},
            ],
            "blocking_issues": [],
            "suggestions": [],
            "base_url": "https://staging.example.com",
        },
    )

    probe = client.post(
        "/api/environments/probe",
        json={
            "name": "staging",
            "base_url": "https://staging.example.com",
            "default_headers": {"X-Test": "1"},
            "auth": {"type": "bearer", "token": "demo"},
            "cookies": {"session": "cookie-demo"},
            "project_id": project_id,
        },
        headers=_auth_headers(alice_login["access_token"]),
    )
    assert probe.status_code == 200
    probe_data = probe.json()["data"]
    assert probe_data["overall_status"] == "passed"
    assert probe_data["environment_name"] == "staging"

    audit_logs = client.get(
        "/api/audit/logs",
        params={"resource_type": "environment", "actor": "alice", "page": 1, "page_size": 10},
        headers=_auth_headers(alice_login["access_token"]),
    )
    assert audit_logs.status_code == 200
    payload = audit_logs.json()["data"]
    assert payload["page"] == 1
    assert payload["page_size"] == 10
    assert payload["total"] >= 1
    assert any(item["action"] == "environment.probe" for item in payload["items"])
    assert all(item["username"] == "alice" for item in payload["items"])


def test_async_analysis_progress_flow(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)
    import task_center.api as api_module

    def fake_run_analysis_pipeline(**kwargs):
        progress_callback = kwargs.get("progress_callback")
        task_id = str(kwargs["task_id"])
        task_name = str(kwargs["task_name"])
        created_at = str(kwargs.get("created_at") or "2026-04-21T00:00:00Z")
        source_type = str(kwargs.get("source_type") or "text")
        source_path = kwargs.get("source_path")
        if progress_callback is not None:
            progress_callback("input_normalized", {"stage": "input_normalized", "percent": 10, "message": "任务输入已标准化"})
            progress_callback("requirement_parsed", {"stage": "requirement_parsed", "percent": 45, "message": "需求解析完成"})
            progress_callback("scenarios_built", {"stage": "scenarios_built", "percent": 70, "message": "测试场景已生成"})
            progress_callback("analysis_report_ready", {"stage": "analysis_report_ready", "percent": 95, "message": "分析报告已生成"})
        return {
            "task_context": {
                "task_id": task_id,
                "task_name": task_name,
                "source_type": source_type,
                "source_path": source_path,
                "created_at": created_at,
                "language": "zh-CN",
                "status": "generated",
                "notes": [],
            },
            "parse_metadata": {
                "parse_mode": "rules",
                "llm_attempted": False,
                "llm_used": False,
                "rag_enabled": False,
                "rag_used": False,
                "rag_fallback_reason": "",
                "fallback_reason": "",
                "llm_error_type": "",
                "llm_provider_profile": "default",
                "retrieval_mode": "keyword",
                "retrieval_top_k": 5,
                "rerank_enabled": False,
                "document_char_count": 32,
                "cleaned_char_count": 32,
                "chunk_count": 1,
                "embedding_batch_size": 32,
                "estimated_embedding_calls": 0,
                "processing_tier": "realtime",
                "large_document_warning": "",
                "retrieval_metrics": {
                    "returned_count": 0,
                    "requested_top_k": 5,
                    "coverage_ratio": 0,
                    "duplicate_ratio": 0,
                    "score_avg": 0,
                    "rerank_applied": False,
                    "embedded_chunk_count": 0,
                    "embedding_coverage": 0,
                    "embedding_error": "",
                    "embedding_error_detail": "",
                },
                "retrieval_scoring": {
                    "lexical_weight": 4,
                    "vector_weight": 6,
                    "rerank_vector_weight": 7,
                    "rerank_lexical_weight": 2,
                    "rerank_title_boost": 0.2,
                    "rerank_content_boost": 0.2,
                },
                "performance": {
                    "elapsed_ms": 15,
                    "target_ms": 8000,
                    "within_target": True,
                    "slow_reason": "",
                },
            },
            "parsed_requirement": {
                "objective": "验证创建订单接口",
                "actors": ["用户"],
                "entities": ["订单"],
                "preconditions": [],
                "actions": ["创建订单", "查询订单详情"],
                "expected_results": ["返回订单 id"],
                "constraints": [],
                "ambiguities": [],
                "source_chunks": ["chunk_001"],
            },
            "retrieved_context": [],
            "scenarios": [
                {
                    "scenario_id": "scenario_001",
                    "name": "正常创建订单",
                    "goal": "验证创建订单接口",
                    "steps": [],
                    "assertions": [],
                    "source_chunks": ["chunk_001"],
                    "priority": "P1",
                    "preconditions": [],
                }
            ],
            "test_case_dsl": {
                "dsl_version": "0.1.0",
                "task_id": task_id,
                "task_name": task_name,
                "feature_name": task_name,
                "execution_mode": "api",
                "metadata": {"execution": {"base_url": "https://example.com"}},
                "scenarios": [],
            },
            "validation_report": {
                "feature_name": task_name,
                "passed": True,
                "errors": [],
                "warnings": [],
                "metrics": {},
            },
            "analysis_report": {
                "task_id": task_id,
                "task_name": task_name,
                "quality_status": "passed",
                "summary": {},
                "findings": [],
                "chart_data": {},
            },
            "feature_text": f"Feature: {task_name}",
            "artifact_dir": str(tmp_path / "artifacts" / task_id),
        }

    monkeypatch.setattr(api_module, "run_analysis_pipeline", fake_run_analysis_pipeline)

    client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "password123", "email": "alice@example.com"},
    )
    alice_login = client.post("/api/auth/login", json={"username": "alice", "password": "password123"}).json()["data"]
    headers = _auth_headers(alice_login["access_token"])

    task_resp = client.post(
        "/api/tasks",
        json={
            "task_name": "Async Analysis Task",
            "source_type": "text",
            "requirement_text": """
## 文档目标
验证创建订单接口。

### Scenario 1: 正常创建订单
**Request:**
`POST /orders`
{
  "sku": "sku-001",
  "count": 1
}
**Expected:**
- 返回 201
- 返回订单 id
**save_context:**
order_id ← json.id

### Scenario 2: 查询订单详情
**uses_context:**
- order_id
**Request:**
`GET /orders/{order_id}`
**Expected:**
- 返回 200
- 返回订单详情
""",
            "target_system": "https://example.com",
        },
        headers=headers,
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["data"]["task_id"]

    started = client.post(f"/api/tasks/{task_id}/analysis/start", headers=headers)
    assert started.status_code == 200
    started_data = started.json()["data"]
    assert started_data["kind"] == "analysis"
    assert started_data["status"] in {"running", "completed"}

    progress_data = started_data
    deadline = time.time() + 10
    while progress_data["status"] not in {"completed", "failed"} and time.time() < deadline:
        time.sleep(0.1)
        progress = client.get(f"/api/tasks/{task_id}/analysis/progress", headers=headers)
        assert progress.status_code == 200
        progress_data = progress.json()["data"]

    assert progress_data["status"] == "completed", progress_data
    assert progress_data["stage"] == "ready"
    assert progress_data["percent"] == 100

    full_detail = client.get(f"/api/tasks/{task_id}", headers=headers)
    assert full_detail.status_code == 200
    full_data = full_detail.json()["data"]
    assert full_data["task_context"]["status"] in {"generated", "parsed"}
    assert str(full_data["parse_metadata"]["parse_mode"]).strip()


def test_task_draft_agent_endpoint_returns_suggestions(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "password123", "email": "alice@example.com"},
    )
    login_data = client.post("/api/auth/login", json={"username": "alice", "password": "password123"}).json()["data"]
    headers = _auth_headers(login_data["access_token"])
    project_id = login_data["projects"][0]["id"]

    create_env = client.post(
        "/api/environments",
        json={
            "name": "staging",
            "base_url": "https://api.example.com",
            "project_id": project_id,
        },
        headers=headers,
    )
    assert create_env.status_code == 201

    response = client.post(
        "/api/tasks/agent/draft",
        json={
            "task_name": "",
            "requirement_text": "# 用户登录接口验证\n\nBase URL: https://api.example.com\n\n验证登录成功与失败场景。",
            "source_path": "login_requirement.md",
            "project_id": project_id,
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["suggested_task_name"] == "login_requirement"
    assert data["detected_base_url"] == "https://api.example.com"
    assert data["recommended_environment"] == "staging"
    assert data["form_patch"]["environment"] == "staging"
    assert data["summary"]["ready_to_create"] is True
    assert data["summary"]["ready_to_execute"] is True
    assert data["summary"]["highlight_count"] >= 2
    assert data["summary"]["risk_count"] >= 1
    assert data["capabilities"]["backend_ready"] is True
    assert data["capabilities"]["mcp_direct_supported"] is False
    assert data["capabilities"]["auto_analysis_supported"] is True
    assert data["capabilities"]["diagnostics_supported"] is True
    assert data["capabilities"]["document_actions_supported"] is True
    assert data["capabilities"]["knowledge_rag_supported"] is True
    assert data["summary"]["confidence_level"] in {"low", "medium", "high"}
    assert isinstance(data["summary"]["confidence_score"], int)
    fields = [item["field"] for item in data["suggestions"]]
    assert "task_name" in fields
    assert "target_system" in fields
    assert "environment" in fields
    assert any(item["name"] == "staging" and item["match_type"] == "exact_base_url" for item in data["environment_candidates"])
    assert any(item["key"] == "environment" and item["status"] == "ready" for item in data["checks"])
    assert any(item["key"] == "document_shape" and item["value"] == "自由描述" for item in data["signals"])
    assert any(item["key"] == "scenario_outlook" for item in data["signals"])
    assert data["scenario_outlook"]["estimated_scenario_count"] >= 1
    assert data["resource_groups"] == []
    assert any("目标系统" in item for item in data["highlights"])
    assert any("自动场景生成覆盖率" in item for item in data["risks"])
    assert any("`METHOD /path`" in item for item in data["document_fixes"])
    assert any(item["key"] == "method_path_template" for item in data["document_actions"])
    assert any(item["key"] == "request_expected_template" for item in data["document_actions"])
    assert data["document_preview"]["action_count"] >= 2
    assert "Base URL" in data["document_preview"]["content"]
    request_follow_up = next(item for item in data["follow_up_questions"] if item["key"] == "request_structure")
    assert request_follow_up["action_kind"] == "apply_document_action"
    assert request_follow_up["document_action_key"] == "request_expected_template"


def test_task_draft_agent_requires_auth_for_project_scope(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/tasks/agent/draft",
        json={
            "requirement_text": "Base URL: https://api.example.com",
            "project_id": "project_demo",
        },
    )
    assert response.status_code == 401


def test_task_draft_agent_follow_up_supports_inline_answers(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/tasks/agent/draft",
        json={
            "requirement_text": """
登录接口验证

需要 Bearer token 才能访问详情接口。
""",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    target_question = next(item for item in data["follow_up_questions"] if item["key"] == "target_system")
    assert target_question["answer_mode"] == "field"
    assert "https://" in target_question["answer_placeholder"]
    auth_question = next(item for item in data["follow_up_questions"] if item["key"] == "auth_confirmation")
    assert auth_question["answer_mode"] == "append_requirement"
    assert "{answer}" in auth_question["answer_template"]


def test_task_draft_agent_prefers_better_environment_match(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "password123", "email": "alice@example.com"},
    )
    login_data = client.post("/api/auth/login", json={"username": "alice", "password": "password123"}).json()["data"]
    headers = _auth_headers(login_data["access_token"])
    project_id = login_data["projects"][0]["id"]

    for name, base_url in (
        ("test", "https://wrong.example.com"),
        ("staging", "https://api.example.com"),
    ):
        response = client.post(
            "/api/environments",
            json={
                "name": name,
                "base_url": base_url,
                "project_id": project_id,
            },
            headers=headers,
        )
        assert response.status_code == 201

    response = client.post(
        "/api/tasks/agent/draft",
        json={
            "task_name": "登录接口",
            "requirement_text": "Base URL: https://api.example.com\n验证登录成功。",
            "environment": "test",
            "project_id": project_id,
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["recommended_environment"] == "staging"
    assert data["form_patch"]["environment"] == "staging"
    assert data["summary"]["ready_to_execute"] is False
    assert any("不一致" in item for item in data["warnings"])
    assert data["summary"]["risk_count"] >= 1
    assert any(item["key"] == "environment_match" and item["tone"] == "warning" for item in data["signals"])


def test_task_draft_agent_detects_resource_lifecycle_risks(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/tasks/agent/draft",
        json={
            "task_name": "",
            "requirement_text": """
## Booking patch

**Request:** `PATCH /booking/{id}`
**Expected:** 更新成功

**Request:** `GET /booking/{id}`
**Expected:** 返回最新详情
""",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["risk_count"] >= 1
    assert any("活资源" in item for item in data["risks"])
    assert any(item["key"] == "request_expected" and item["tone"] == "success" for item in data["signals"])
    assert data["scenario_outlook"]["lifecycle_chain_count"] == 0
    assert "PATCH /booking/{id}" in data["scenario_outlook"]["uncovered_live_resource_endpoints"]
    assert any(item["resource_key"] == "booking" and item["status"] == "needs_source" for item in data["resource_groups"])
    assert "PATCH /booking/{id}" in data["recognized_endpoints"]
    assert "GET /booking/{id}" in data["recognized_endpoints"]
    assert any("资源来源" in item for item in data["document_fixes"])
    assert any(item["key"] == "resource_source_template" for item in data["document_actions"])
    assert data["document_preview"]["content"]
    resource_follow_up = next(item for item in data["follow_up_questions"] if item["key"] == "resource_source")
    assert resource_follow_up["action_kind"] == "apply_document_action"
    assert resource_follow_up["document_action_key"] == "resource_source_template"
    assert resource_follow_up["answer_mode"] == "append_requirement"
    assert "{answer}" in resource_follow_up["answer_template"]


def test_task_draft_agent_includes_knowledge_hits_for_platform_doc(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/tasks/agent/draft",
        json={
            "requirement_text": """
# Task Center 主链路

`POST /api/tasks`
`GET /api/tasks/{task_id}`
`POST /api/tasks/{task_id}/execute`
""",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["rag_support"]["knowledge_applied"] is True
    assert data["rag_support"]["retrieved_hit_count"] >= 1
    assert data["rag_support"]["query_count"] >= 1
    assert data["rag_support"]["source_file_count"] >= 1
    assert data["rag_support"]["source_file_diversity"] > 0
    assert data["rag_support"]["query_variants_preview"]
    assert data["knowledge_hits"]
    assert any(int(item.get("query_match_count", 0)) >= 1 for item in data["knowledge_hits"])
    assert any("task_center_api.md" in item["source_file"] for item in data["knowledge_hits"])


def test_project_defect_management_flow(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    for username in ("alice", "bob", "charlie"):
        response = client.post(
            "/api/auth/register",
            json={"username": username, "password": "password123", "email": f"{username}@example.com"},
        )
        assert response.status_code == 201

    alice_login = client.post("/api/auth/login", json={"username": "alice", "password": "password123"}).json()["data"]
    bob_login = client.post("/api/auth/login", json={"username": "bob", "password": "password123"}).json()["data"]
    charlie_login = client.post("/api/auth/login", json={"username": "charlie", "password": "password123"}).json()["data"]
    alice_headers = _auth_headers(alice_login["access_token"])
    bob_headers = _auth_headers(bob_login["access_token"])
    charlie_headers = _auth_headers(charlie_login["access_token"])
    project_id = alice_login["projects"][0]["id"]
    bob_user_id = bob_login["user"]["id"]

    add_member = client.post(
        f"/api/projects/{project_id}/members",
        json={"username": "bob", "role": "editor"},
        headers=alice_headers,
    )
    assert add_member.status_code == 201

    task_resp = client.post(
        "/api/tasks",
        json={
            "task_name": "Checkout Task",
            "source_type": "text",
            "requirement_text": "验证订单结算失败处理。",
            "target_system": "https://api.example.com",
            "project_id": project_id,
        },
        headers=alice_headers,
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["data"]["task_id"]

    create_defect = client.post(
        "/api/defects",
        json={
            "project_id": project_id,
            "task_id": task_id,
            "title": "订单结算失败时返回 500",
            "description": "下单后进入结算接口，服务端直接报 500。",
            "severity": "high",
            "assignee_user_id": bob_user_id,
            "reproduction_steps": "1. 创建订单\n2. 调用 POST /checkout",
            "expected_result": "返回 200，并进入支付流程",
            "actual_result": "返回 500，页面提示系统错误",
        },
        headers=alice_headers,
    )
    assert create_defect.status_code == 201
    defect = create_defect.json()["data"]
    defect_id = defect["id"]
    assert defect["defect_key"].startswith("DEF-")
    assert defect["task_id"] == task_id
    assert defect["reporter_username"] == "alice"
    assert defect["assignee_username"] == "bob"

    listed = client.get(
        "/api/defects",
        params={"project_id": project_id, "status": "open"},
        headers=bob_headers,
    )
    assert listed.status_code == 200
    list_payload = listed.json()["data"]
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["id"] == defect_id

    updated = client.patch(
        f"/api/defects/{defect_id}",
        json={
            "status": "in_progress",
            "severity": "critical",
            "clear_assignee": True,
        },
        headers=bob_headers,
    )
    assert updated.status_code == 200
    updated_payload = updated.json()["data"]
    assert updated_payload["status"] == "in_progress"
    assert updated_payload["severity"] == "critical"
    assert updated_payload["assignee_user_id"] is None

    detail = client.get(f"/api/defects/{defect_id}", headers=alice_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["task_name"] == "Checkout Task"

    denied = client.get(
        "/api/defects",
        params={"project_id": project_id},
        headers=charlie_headers,
    )
    assert denied.status_code == 403
