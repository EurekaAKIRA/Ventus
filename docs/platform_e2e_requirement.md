# Platform 主链路联调需求说明（当前实现对齐版）

## 1. 背景与目的

当前平台已经具备 task-center 主链路的联调能力，研发、测试与前端需要基于统一口径确认以下事项：

- 平台主流程是否可在同一任务生命周期内闭环完成；
- 关键中间产物是否可追踪、可复核、可回放；
- 执行与分析结果是否满足当前阶段演示与验收所需的最小可信度；
- 文档描述是否与当前项目真实接口输入输出保持一致。

本文档用于指导当前版本的平台端到端联调与验收。  
它是开发文档和验收口径说明，不是接口手册，也不是自动化脚本逐步说明书。

## 2. 适用范围

### 2.1 本次纳入

- 任务接入与任务状态流转；
- 需求解析与检索增强；
- 场景、DSL、Feature 的产物生成；
- API 执行、日志、报告与历史查询能力；
- 任务归档后的可见性与一致性检查。

### 2.2 本次不纳入

- 压测云平台对接能力；
- 多租户与权限边界；
- 生产级高并发与容量基准；
- 第三方系统稳定性背书；
- `web-ui` 执行模式的正式验收。

## 3. 角色与职责

- **产品/项目负责人**：确认验收范围、签收最终结论。
- **后端研发**：保障主链路可运行，处理阻断性缺陷。
- **前端研发**：验证页面主路径与真实接口数据一致性。
- **测试工程师**：执行回归流程并输出问题清单。
- **运维或环境负责人**：保障测试环境地址、网络和依赖可达。

## 4. 业务过程描述（非接口步骤版）

从业务视角看，一次标准任务应经历以下过程：

1. 用户提交待分析的需求内容并形成任务实体；
2. 系统完成需求结构化，补充检索上下文，形成后续生成的语义基础；
3. 系统输出可执行场景及 DSL，并生成可阅读的 Feature 文本用于审阅；
4. 系统在指定环境中执行任务，输出过程日志与结果状态；
5. 系统聚合校验与分析报告，支持从任务维度查看历史与产物；
6. 任务结束后可归档，归档后不再作为活跃任务参与主流程。

> 说明：上述过程强调业务闭环，不要求阅读者记忆具体路径与方法名。

## 5. 接口基线（来源：`docs/frontend_api_list.md`）

为避免联调过程出现“口径不一致”，本需求文档采用 `docs/frontend_api_list.md` 作为接口基线。  
本次端到端验收默认至少覆盖以下接口组。

### 5.1 任务与解析（必测）

- `POST /api/tasks`
- `GET /api/tasks/{task_id}`
- `POST /api/tasks/{task_id}/parse`
- `GET /api/tasks/{task_id}/parsed-requirement`
- `GET /api/tasks/{task_id}/retrieved-context`

### 5.2 场景与 DSL（必测）

- `POST /api/tasks/{task_id}/scenarios/generate`
- `GET /api/tasks/{task_id}/scenarios`
- `GET /api/tasks/{task_id}/dsl`
- `GET /api/tasks/{task_id}/feature`

### 5.3 执行与结果（必测）

- `POST /api/tasks/{task_id}/execute`
- `GET /api/tasks/{task_id}/execution`
- `GET /api/tasks/{task_id}/execution/logs`
- `GET /api/tasks/{task_id}/validation-report`
- `GET /api/tasks/{task_id}/analysis-report`

### 5.4 产物与历史（建议纳入）

- `GET /api/tasks/{task_id}/artifacts`
- `GET /api/tasks/{task_id}/artifacts/{type}`
- `GET /api/history/tasks`
- `GET /api/history/executions`
- `DELETE /api/tasks/{task_id}`（归档）

### 5.5 环境与扩展能力（按需）

- `GET /api/environments`
- `POST /api/environments`
- `PUT /api/environments/{environment_name}`
- `DELETE /api/environments/{environment_name}`
- `POST /api/analysis/parse`（独立解析链路）
- `GET /health`
- `GET /version`

### 5.6 执行模式说明（与当前项目现状一致）

- `execution_mode=api`：当前主执行路径，联调与验收优先使用。
- `execution_mode=cloud-load`：当前为本地并发压测模拟，不作为本轮主验收路径。
- `execution_mode=web-ui`：适配中，默认不纳入本轮通过标准。

## 6. 当前实现口径补充

本节用于明确“当前项目真实输入输出”，避免开发文档与实际实现偏离。

### 6.1 统一响应 envelope

当前 task-center API 统一使用如下响应结构：

```json
{
  "success": true,
  "code": "SOME_CODE",
  "message": "some message",
  "data": {},
  "timestamp": "2026-04-04T15:00:00+00:00"
}
```

联调时应默认按统一 envelope 理解接口输出。  
涉及业务字段时，优先从 `data.*` 下查找，不应假设所有字段都平铺在顶层。

### 6.2 关键 detail 接口的实际返回语义

当前项目中，任务详情、分析报告详情和执行结果详情这几类“详情查询接口”返回的是“单对象详情”，不是列表；对应接口基线见第 5 节。

其中任务详情响应当前真实返回位于 `data` 下，包含：

- `data.task_id`
- `data.task_name`
- `data.status`
- `data.task_context`
- `data.parse_metadata`
- `data.parsed_requirement`
- `data.retrieved_context`
- `data.scenarios`
- `data.test_case_dsl`
- `data.validation_report`
- `data.analysis_report`
- `data.feature_text`
- `data.execution_result`

因此，联调和断言设计中不应把任务详情查询接口当作列表接口，也不应假设存在 `data.tasks`。

### 6.3 任务创建接口的实际返回语义

当前任务创建接口的成功返回重点字段是：

- `data.task_id`
- `data.task_context`
- `data.task_context.task_id`
- `data.task_context.task_name`

当前实现中，不应把任务创建接口的返回简单理解为 `data.task_name` 平铺存在。  
如果需要读取任务名称，应优先以 `data.task_context.task_name` 为准。

### 6.4 解析接口的实际返回语义

当前解析接口的成功返回重点字段是：

- `data.task_id`
- `data.status`
- `data.parsed_requirement`
- `data.parse_metadata`

当前默认稳定联调路径推荐：

- `use_llm=false`
- `rag_enabled=true`
- `retrieval_top_k=5`
- `rerank_enabled=false`

如果显式启用 `use_llm=true`，允许出现模型增强、fallback 和额外时延，不应把它作为默认稳定基线。

### 6.5 执行接口的当前验收口径

当前执行接口能触发真实执行链路并生成结构化执行结果。  
但在当前项目阶段，端到端验收更关注“是否走通并产出结构化结果”，而不是要求所有自动生成场景都必须通过。

因此当前验收允许：

- 执行完成且进入终态；
- `GET /execution`、`GET /analysis-report` 可正常读取；
- 少量场景失败但不阻断主链路闭环。

## 7. 验收关注点

### 7.1 必须满足

- 单任务从“提交到报告”应可完整走通；
- 关键中间产物（解析结果、场景、DSL、Feature）应可回读；
- 报告数据与执行数据口径基本一致，不出现明显自相矛盾；
- 归档动作生效后，任务应从活跃视图中消失；
- 返回结构保持统一 envelope，便于前端统一处理；
- 开发文档中描述的关键输入输出与当前实现一致。

### 7.2 可接受但需记录

- 少量场景执行失败但不阻断整体链路；
- 检索策略在不同输入下出现回退；
- 报告存在提示级告警（如步骤表达偏长）；
- 启用 LLM 增强后耗时明显上升或结果出现回退。

## 8. 非功能与治理要求

- **可追踪性**：同一任务 ID 可串联输入、产物、执行、报告与历史。
- **可解释性**：解析结果应能说明来自哪些上下文片段。
- **一致性**：前后端对状态字段、错误消息、时间字段含义保持一致。
- **可维护性**：配置项通过统一配置管理，不在流程中硬编码环境地址。

## 9. 风险与已知限制

- 同步执行模式下，长任务会占用请求时长；
- 复杂断言与字段映射仍存在误判空间；
- 当前自动场景/断言生成对“开发文档”类文本的理解仍可能比“精确可执行规格”更宽泛；
- 当前持久化方案偏向 MVP，尚未达到生产级可靠性；
- 在外部依赖波动情况下，检索与执行耗时可能明显抖动。

## 10. 环境前置条件

- 默认联调基地址使用 `http://127.0.0.1:8001`；
- 执行时应提供明确目标系统来源（任务目标地址或环境配置）；
- 测试数据需避免依赖不可控的外部实时状态；
- 若启用模型增强能力，应提前完成密钥与模型配置核验；
- 联调前应确认当前服务进程已重启，避免沿用旧版本逻辑。

## 11. 输出物要求

验收结束后需至少沉淀以下内容：

- 一份执行结论（通过 / 有条件通过 / 不通过）；
- 一份问题清单（按阻断、主要、次要分级）；
- 一份回归记录（包含环境、版本、时间窗口、任务样本）；
- 对未闭环项给出下一迭代处理建议与责任人。

## 12. 文档维护原则

后续更新本文件时，应遵循以下原则：

- 保持“开发文档 / 验收口径说明”定位，不将其改写成纯自动化脚本；
- 描述当前真实接口行为，而不是未来预期结构；
- 当接口真实返回字段发生变化时，优先同步本文件的“当前实现口径补充”章节；
- 如果需要机器可执行的严格版本，应单独维护独立 spec，而不是挤占本文件的开发文档定位。
