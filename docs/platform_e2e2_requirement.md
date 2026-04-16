# Platform E2E2 — Task Center 精简规格（网关友好）

## 文档定位

- 由 `docs/platform_e2e_requirement.md` **精简**而来，仅保留 **可机器生成 DSL 与步骤断言** 所需信息。
- **目的**：控制需求正文体积，降低 **模型网关** 超时风险；在 **`use_llm=false` + `rag_enabled=false`** 时依赖规则解析仍可产出 **可执行的 TestCase DSL**（含 `request`、`assertions`、`save_context`）。
- 完整接口语义仍以 `platform/platform-ui/api-contract.ts` 与 `GET /docs` 为准。

---

## 固定环境

| 项 | 值 |
| --- | --- |
| Base URL | `http://127.0.0.1:8001` |
| `environment` | `test` |
| `target_system` | 与 Base URL 相同（创建任务时必填，供 `api` 执行模式解析 `base_url`） |

统一响应 envelope（业务数据在 `data`）：

```json
{
  "success": true,
  "code": "SOME_CODE",
  "message": "ok",
  "data": {},
  "timestamp": "2026-04-04T15:00:00+00:00"
}
```

执行器默认请求头（对标 Apifox，未显式配置时自动补）：

- 任意请求：自动补 `Accept: application/json`
- `request.json` 存在：自动补 `Content-Type: application/json`
- `request.data` 为表单对象：自动补 `Content-Type: application/x-www-form-urlencoded`
- 若步骤中已声明同名 header（大小写不敏感），以步骤声明为准，不覆盖

需要显式声明的 header（不会自动猜测）：

- 认证类：`Authorization`、`Cookie`
- 自定义媒体类型：如 `application/vnd.xxx+json`
- 非 JSON 上传：如 `multipart/form-data`

---

## Feature: Task Center 主链路烟测

验证从创建任务、解析、拉取 DSL、执行到只读报告的 **最小闭环**。

### Scenario: 创建并解析任务

#### Step 1 — 创建任务

**Request:** `POST /api/tasks`

**Body:**

```json
{
  "task_name": "e2e2_smoke",
  "source_type": "text",
  "requirement_text": "E2E2 minimal smoke for task-center.",
  "target_system": "http://127.0.0.1:8001",
  "environment": "test"
}
```

**Expected:**

- HTTP `201`
- `code` = `TASK_CREATED`
- `data.task_id` 存在
- `data.task_context.task_id` 与 `data.task_id` 一致

**save_context:**

- `task_id` ← `json.data.task_id`
- `resource_id` ← `json.data.task_id`

#### Step 2 — 任务详情

**Request:** `GET /api/tasks/{{task_id}}`

**Expected:**

- HTTP `200`
- `code` = `TASK_DETAIL_OK`
- `data.task_id` = `{{task_id}}`
- `data.status` 存在

#### Step 3 — 触发解析（规则/RAG 轻量，利于网关）

**Request:** `POST /api/tasks/{{task_id}}/parse`

**Body:**

```json
{
  "use_llm": false,
  "rag_enabled": false,
  "retrieval_top_k": 5,
  "rerank_enabled": false
}
```

**Expected:**

- HTTP `200`
- `code` = `TASK_PARSED`
- `data.parsed_requirement` 存在
- `data.parse_metadata.parse_mode` 存在
- `data.parse_metadata.retrieval_mode` 为 `keyword` 或 `vector+keyword`

### Scenario: DSL 与执行

#### Step 4 — 获取 DSL（须含可执行步骤）

**Request:** `GET /api/tasks/{{task_id}}/dsl`

**Expected:**

- HTTP `200`
- `code` = `DSL_OK`
- `data.scenarios` 非空
- 至少一个 scenario 的 `steps` 非空
- 存在 `POST /api/tasks` 的步骤，且 `save_context` 包含  
  `task_id` = `json.data.task_id`、`resource_id` = `json.data.task_id`
- 存在 `POST /api/tasks/{{task_id}}/parse`（URL 中含任务占位符与 `/parse`）

#### Step 5 — 启动执行

**Request:** `POST /api/tasks/{{task_id}}/execute`

**Body:**

```json
{
  "execution_mode": "api",
  "environment": "test"
}
```

**Expected:**

- HTTP `200`
- `code` = `TASK_EXECUTED`

#### Step 6 — 轮询执行结果

**Request:** `GET /api/tasks/{{task_id}}/execution`（轮询直至终态）

**Expected:**

- HTTP `200`
- `code` = `EXECUTION_OK`
- `data.status` 最终为 `passed` 或 `failed`
- `data.scenario_results` 非空

#### Step 7 — 分析报告

**Request:** `GET /api/tasks/{{task_id}}/analysis-report`

**Expected:**

- HTTP `200`
- `code` = `ANALYSIS_REPORT_OK`
- `data.task_id` = `{{task_id}}`
- `data.summary` 或 `data.quality_status` 至少其一存在

#### Step 8 — 归档清理

**Request:** `DELETE /api/tasks/{{task_id}}`

**Expected:**

- HTTP `200`
- `code` = `TASK_ARCHIVED`
- `data.archived` = `true`

---

## 断言摘要（供规则/LLM 生成步骤级断言）

| 检查点 | 规则 |
| --- | --- |
| 创建 | `success` 且 `code == TASK_CREATED`，保存 `task_id` |
| 解析 | `code == TASK_PARSED`，`parse_metadata.retrieval_mode` 合法 |
| DSL | `scenarios`/`steps` 非空；含创建任务与 parse 的 HTTP 步骤 |
| 执行 | `TASK_EXECUTED` 后轮询到 `passed` 或 `failed` |
| 归档 | `TASK_ARCHIVED` 且 `archived == true` |

---

