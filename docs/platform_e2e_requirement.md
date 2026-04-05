# 平台 Task Center 主链路开发需求说明

## 1. 文档定位

本文档描述 **task-center 主链路** 在当前实现下的 **功能需求、接口基线与数据语义**，供后端实现对照、前端联调与产品对齐使用。

- **不是**自动化测试用例步骤书；测试场景可另文维护。
- **不是**完整 OpenAPI 替代物；字段级契约以 `platform/platform-ui/api-contract.ts` 与运行中的 `GET /docs` 为准。
- 与 `docs/frontend_api_list.md` 接口列表 **对齐**；本文侧重 **功能说明 + Base URL + 分组接口表**。

---

## 2. 服务地址与配置

| 项 | 说明 |
| --- | --- |
| **默认 Base URL（本地 task-center）** | `http://127.0.0.1:8001` |
| **OpenAPI / Swagger UI** | `{BASE_URL}/docs` |
| **健康检查** | `GET {BASE_URL}/health` |
| **版本信息** | `GET {BASE_URL}/version` |
| **前端环境变量** | `VITE_PLATFORM_API_BASE`（未配置时前端默认 `http://127.0.0.1:8001`，见 `platform-ui` 请求封装） |

所有下文接口路径均为 **相对 Base URL** 的路径（例如 `/api/tasks` 表示 `http://127.0.0.1:8001/api/tasks`）。

---

## 3. 统一响应结构

task-center 对外 REST 接口（除部分流式端点外）采用统一 **envelope**。业务数据均在 `data` 内，客户端应通过 `success`、`code`、`message` 判断结果，从 `data` 读取载荷。

```json
{
  "success": true,
  "code": "SOME_CODE",
  "message": "human readable message",
  "data": {},
  "timestamp": "2026-04-04T15:00:00+00:00"
}
```

**开发约定**：列表类接口的数组字段放在 `data` 的子结构中（如分页的 `items`）；勿假设业务字段平铺在 envelope 顶层。

---

## 4. 功能范围与业务目标

### 4.1 本阶段应支持的能力

| 能力域 | 功能目标（产品/研发视角） |
| --- | --- |
| **任务生命周期** | 用户可创建任务、查看列表与详情、按状态筛选；任务可归档（删除/归档语义以接口为准），归档后不再出现在活跃列表。 |
| **需求解析** | 将原始需求转为结构化 `ParsedRequirement`，并可查看检索增强得到的 `retrieved_context`；支持独立「仅解析」链路（不绑定任务）。 |
| **生成物** | 在解析基础上生成测试场景、可执行 DSL、Gherkin Feature 文本；产物可单独查询，也可在任务详情中聚合展示。 |
| **环境与执行** | 可配置命名环境（基址、头、鉴权等）；任务可在指定模式下触发执行，产生结构化 `execution_result`、步骤级结果与日志。 |
| **分析与展示** | 基于校验结果与执行结果生成分析报告；提供任务级 **Dashboard** 聚合数据供前端看板使用。 |
| **产物与追溯** | 按类型枚举或获取任务产物内容；支持历史任务与历史执行记录查询，便于审计与回放。 |
| **体验增强（已部分落地）** | 执行前预检、失败解释、回归对比、执行过程流式推送等（详见 `docs/ux_service_api_contract_draft.md`）。 |

### 4.2 本阶段明确不纳入

- 云平台正式压测与容量承诺。
- 多租户隔离与完整权限模型。
- `web-ui` 执行模式作为默认交付路径（可保留接口，产品上不强制验收）。
- 生产级高可用与持久化 SLA（当前为 MVP 级持久化策略）。

---

## 5. 核心业务流（实现应对齐的端到端故事）

以下顺序描述 **一条任务从创建到可观测结果** 的主路径，便于前后端划分阶段与错误处理，**不**等价于单接口文档。

1. **创建任务**：提交任务名称、来源类型、需求文本或文件路径等 → 返回 `task_id` 与 `task_context`（含状态，如 `received`）。
2. **解析（可选显式触发）**：对任务触发解析 → 更新结构化需求与 `parse_metadata`；解析策略可通过请求体控制（如 LLM、RAG、top_k 等）。
3. **生成场景 / DSL / Feature**：在解析结果之上生成场景列表、DSL 与 Feature；前端可分布拉取或依赖详情接口聚合字段。
4. **环境选择与预检（可选）**：用户选择环境 → 可调用预检接口验证目标可达性等再执行。
5. **执行**：触发执行 → 轮询或通过流式接口观察进度；读取 `execution`、`execution/logs`。
6. **报告与看板**：读取校验报告、分析报告及 `dashboard` 聚合数据，用于结果页与图表。
7. **归档**：删除/归档任务后，活跃列表不再展示该任务；历史接口可按约定查询已归档记录。

---

## 6. 接口分组与功能说明

下表 **Method + Path** 为当前 task-center 实现中的路由（与代码一致）。**功能说明** 描述该接口在系统中的职责；**主要 data 语义** 为开发常用字段提示，完整字段以契约与 OpenAPI 为准。

### 6.1 服务元数据

| Method | Path | 功能说明 |
| --- | --- | --- |
| GET | `/health` | 存活探测，供编排与前端简单检查。 |
| GET | `/version` | 返回服务名、版本号等，便于排障与对齐发布。 |

### 6.2 任务 CRUD 与详情

| Method | Path | 功能说明 | 主要 `data` 语义（摘要） |
| --- | --- | --- | --- |
| POST | `/api/tasks` | **创建任务**：持久化任务记录，生成 `task_id`。 | `task_id`、`task_context`（内含 `task_id`、`task_name`、`status`、`created_at` 等）。任务名称优先读 `task_context.task_name`。 |
| GET | `/api/tasks` | **任务列表**：支持分页与筛选（如 `status`、`keyword`、`environment`、`page`、`page_size`）。 | 分页结构含 `items`（摘要字段）、`total` 等。 |
| GET | `/api/tasks/{task_id}` | **任务详情**：单任务全量视图；支持 `detail_level=summary` 首包瘦身（大字段为 `null`、执行结果无日志/无步骤明细），前端可与 `detail_level=full` 合并。 | 默认 `full`：`task_context`、`parse_metadata`、`parsed_requirement`、`retrieved_context`、`scenarios`、`test_case_dsl`、`validation_report`、`analysis_report`、`feature_text`、`execution_result`、`artifact_dir` 等。**非列表接口**。 |
| DELETE | `/api/tasks/{task_id}` | **归档任务**：逻辑删除/归档，活跃列表不再出现。 | 含 `task_id`、`archived` 等确认字段。 |

### 6.3 解析（任务绑定）

| Method | Path | 功能说明 | 主要 `data` 语义（摘要） |
| --- | --- | --- | --- |
| POST | `/api/tasks/{task_id}/parse` | **触发/刷新解析**：按可选 body 中的解析选项执行需求分析流水线，更新任务内 pipeline 状态与产物。 | `task_id`、`status`、`parsed_requirement`、`parse_metadata`。 |
| GET | `/api/tasks/{task_id}/parsed-requirement` | 仅返回结构化需求对象。 | `ParsedRequirement` 形态 JSON。 |
| GET | `/api/tasks/{task_id}/retrieved-context` | 返回 RAG/检索命中列表。 | 数组或约定结构。 |

### 6.4 独立解析（无任务）

| Method | Path | 功能说明 |
| --- | --- | --- |
| POST | `/api/analysis/parse` | **不创建任务** 的解析：传入 `requirement_text` 或 `source_path` 等，返回解析包（结构化需求、检索上下文、校验报告、parse_metadata 等），用于分析页或工具链。 |

### 6.5 场景、DSL、Feature

| Method | Path | 功能说明 | 主要 `data` 语义（摘要） |
| --- | --- | --- | --- |
| POST | `/api/tasks/{task_id}/scenarios/generate` | 基于当前解析结果生成/刷新场景，并更新任务状态（如进入 `generated`）。 | `scenario_count`、`scenarios`。 |
| GET | `/api/tasks/{task_id}/scenarios` | 返回场景列表。 | 场景数组。 |
| GET | `/api/tasks/{task_id}/dsl` | 返回可执行 DSL 文档结构。 | `TestCaseDSL` 形态 JSON。 |
| GET | `/api/tasks/{task_id}/feature` | 返回 Gherkin Feature 文本包装对象。 | 如 `{ "feature_text": "..." }`。 |

### 6.6 环境管理

| Method | Path | 功能说明 |
| --- | --- | --- |
| GET | `/api/environments` | 列出已配置环境（名称、基址、默认头等）。 |
| POST | `/api/environments` | 创建或初始化环境配置。 |
| GET | `/api/environments/{environment_name}` | 查询单个环境。 |
| PUT | `/api/environments/{environment_name}` | 更新指定环境。 |
| DELETE | `/api/environments/{environment_name}` | 删除指定环境。 |

### 6.7 预检与执行

| Method | Path | 功能说明 |
| --- | --- | --- |
| POST | `/api/tasks/{task_id}/preflight-check` | 执行前检查（目标环境、连通性等），body 可指定 `environment`。 |
| POST | `/api/tasks/{task_id}/execute` | 触发任务执行；body 含执行模式、环境等（与 `ExecuteTaskRequest` 一致）。 |
| POST | `/api/tasks/{task_id}/execution/stop` | 请求停止当前执行（若支持）。 |
| GET | `/api/tasks/{task_id}/execution` | 读取结构化执行结果（状态、步骤结果、指标等）。 |
| GET | `/api/tasks/{task_id}/execution/logs` | 读取执行日志列表或聚合。 |
| GET | `/api/tasks/{task_id}/execution/stream` | **SSE/流式**：推送执行过程事件（客户端按流式协议解析，非标准 JSON envelope）。 |
| GET | `/api/tasks/{task_id}/execution/explanations` | 失败步骤等解释信息（体验增强）。 |
| GET | `/api/tasks/{task_id}/regression-diff` | 与历史或基线的回归对比数据（体验增强）。 |

**执行模式（与实现对齐的产品说明）**

| 模式 | 说明 |
| --- | --- |
| `api` | 当前主执行路径，前后端联调与默认功能演示应优先使用该模式。 |
| `cloud-load` | 本地并发压测模拟，不作为主功能交付默认路径。 |
| `web-ui` | 适配中，不纳入本阶段默认通过标准。 |

### 6.8 校验、分析与看板

| Method | Path | 功能说明 |
| --- | --- | --- |
| GET | `/api/tasks/{task_id}/validation-report` | DSL/Feature 等校验结果的详细报告。 |
| GET | `/api/tasks/{task_id}/analysis-report` | 面向可读性与 Dashboard 的分析报告（可能含图表数据、摘要文案等）。 |
| GET | `/api/tasks/{task_id}/dashboard` | **看板聚合接口**：在一次响应中组合任务摘要、分析报告子集、执行概览、DSL/校验引用等，供任务详情页「总览/图表」减少多次往返。**实现上可能触发报告再计算与持久化，性能优化属实现细节。** |

### 6.9 产物索引与按类型读取

| Method | Path | 功能说明 |
| --- | --- | --- |
| GET | `/api/tasks/{task_id}/artifacts` | 返回任务下标准产物类型的列表；每项含 `type` 与 `content`（当前实现为内嵌完整内容，体量大时注意前端按需加载策略）。 |
| GET | `/api/tasks/{task_id}/artifacts/{artifact_type}` | 按类型获取单一产物内容；`artifact_type` 取值需与后端 `DEFAULT_ARTIFACT_TYPES` 一致（如 `raw`、`parsed-requirement`、`scenarios`、`dsl`、`feature`、`validation-report`、`analysis-report` 等）。 |

### 6.10 历史与审计

| Method | Path | 功能说明 |
| --- | --- | --- |
| GET | `/api/history/tasks` | 历史任务列表，支持时间范围、状态、关键字、分页等查询。 |
| GET | `/api/history/executions` | 历史执行记录列表，支持按任务、环境、状态等过滤。 |

---

## 7. 解析选项默认值（稳定联调基线）

以下默认值用于 **降低环境波动** 时的联调成本；产品若启用 LLM 增强，需接受时延与结果波动。

| 选项 | 建议默认（稳定基线） |
| --- | --- |
| `use_llm` | `false` |
| `rag_enabled` | `false` |
| `retrieval_top_k` | `5` |
| `rerank_enabled` | `false` |

显式 `use_llm=true` 时，允许模型增强、fallback 与更长耗时，不作为「最小稳定基线」的唯一依据。

---

## 8. 非功能与工程约束

| 类别 | 要求 |
| --- | --- |
| **可追踪性** | 同一 `task_id` 应能关联创建参数、解析产物、执行结果、报告与历史记录。 |
| **一致性** | 状态枚举、错误码、`code` 字段与前端 `normalizeStatus` 等逻辑保持一致；时间字段使用 ISO-8601。 |
| **可配置性** | 环境基址、鉴权信息禁止硬编码在业务代码路径中，应走环境配置 API 或部署配置。 |
| **性能意识** | 任务详情 + artifacts + dashboard 并行请求时 payload 较大；已实现 `detail_level=summary`、产物 `shallow`、分析报告缓存与 **GZip**（约 ≥512B 响应）等减负手段；大任务仍建议分 Tab 按需拉取。 |

---

## 9. 质量与验收参考（非测试步骤）

以下用于发布前 **快速对齐是否「主链路可用」**，具体用例可由测试单独维护。

- 单任务从创建 → 解析 → 生成 → 执行 → 可读报告/看板 可端到端走通。
- 关键产物均可通过详情或 `artifacts`/`artifacts/{type}` 回读。
- 归档后活跃列表不可见，历史接口行为符合约定。
- 统一 envelope 未被破坏，前端可统一处理错误与成功分支。

当前阶段允许少量场景执行失败 **不阻断**「链路走通」类验收，但须在报告中可观测。

---

## 10. 相关文档与代码索引

| 用途 | 路径 |
| --- | --- |
| 前端接口总表与页面映射 | `docs/frontend_api_list.md` |
| 体验增强契约（预检、解释、回归、SSE） | `docs/ux_service_api_contract_draft.md` |
| TypeScript 类型与响应形状 | `platform/platform-ui/api-contract.ts` |
| 前端请求封装 | `platform/platform-ui/src/api/tasks.ts` |
| 后端路由实现 | `platform/task-center/src/task_center/api.py` |
| 本地启动 | `docs/platform_quickstart.md` |

---

## 11. 文档维护

- 接口路径或 `data` 语义变更时，同步更新 **第 6 节** 与 `api-contract.ts` / OpenAPI。
- Base URL 默认值变更时，同步 **第 2 节** 与前端 `VITE_PLATFORM_API_BASE` 说明。
- 本文保持 **开发需求 + 接口基线** 定位；若需机器可读 strict spec，建议独立维护，避免与本说明混写为冗长断言列表。
