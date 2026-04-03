# 前端开发指南（platform-ui）

## 1. 背景问题

`TaskDetail.tsx` 当前承担了数据加载、轮询、SSE、多 Tab 联动、执行状态管理、可视化渲染与交互文案等多重职责，单文件复杂度高、改动回归面大。

本指南目标：

- 建立前端单一可信开发基线（UTF-8、无历史乱码残留、无重复旧稿）。
- 给出 `TaskDetail` 的可直接实施拆分蓝图，支撑高频迭代下的低风险改动。
- 在不改变后端契约与页面行为的前提下，约束前端改动边界与验证流程。

统一入口仍为：`docs/frontend_api_list.md` 的 **§1.1 前端参考文档索引**。本文件不重复维护接口长表，仅保留架构与工程约束。

---

## 2. 架构分层

### 2.1 Data Layer（任务数据层）

建议模块：`useTaskData`（后续提取）

输入：

- `taskId`
- URL 查询参数（如 `tab`、`compare`）
- API 能力层（`fetchTaskDetail`、`fetchParsedRequirement`、`fetchScenarios`、`fetchDsl`、`fetchAnalysisReport` 等）

输出：

- `TaskDataState`（只读聚合结果）
- 数据加载状态（`idle/loading/success/error`）
- 非执行链路错误信息

不负责什么：

- 不维护执行态轮询/SSE生命周期
- 不直接控制按钮可点状态
- 不做视图渲染细节判断

### 2.2 Execution Layer（执行运行时层）

建议模块：`useTaskExecution`（后续提取）

输入：

- `taskId`
- `activeTabKey`
- 最小必要任务上下文（`target_system`、执行相关字段）
- API 能力层（`startExecution`、`stopExecution`、`fetchExecution`、`fetchExecutionExplanations`、`fetchRegressionDiff`）

输出：

- `ExecutionRuntimeState`
- 执行动作（`runExecution`、`stopCurrentExecution`）
- 运行时副作用状态（轮询/SSE/预检/回归对比）

不负责什么：

- 不直接拼装 UI 展示文案
- 不承担解析/场景/DSL等静态数据加载
- 不在层内管理具体组件展开折叠状态

### 2.3 View Layer（视图渲染层）

建议模块：`TaskDetailView` + 子组件（`TaskTabs`、`ExecutionPanel`、`ReportPanel` 等）

输入：

- `TaskDetailViewModel`（聚合只读视图模型）
- 事件回调（开始执行、停止执行、切换 Tab、重试等）

输出：

- 纯渲染结果
- 用户交互事件上抛

不负责什么：

- 不直接发起 API 请求
- 不维护轮询/SSE连接
- 不更新跨 Tab 共享可变对象

---

## 3. 状态流

### 3.1 状态来源优先级

执行相关状态统一按以下优先级消费：

1. `execution_result`（后端权威快照）
2. SSE 事件流（增量更新，用于提升实时感）
3. 轮询回退（SSE 不可用或中断时兜底）
4. URL Tab 状态（仅用于视图路由，不得覆盖执行权威状态）

### 3.2 Tab 级触发规则（强约束）

- 仅 `execution` Tab 允许：
  - 执行前预检（`preflight-check`）
  - SSE 连接尝试（`execution/stream`）
- 仅 `report` Tab 允许：
  - 回归对比自动拉取（如 `compare=latest` 触发）
- 其它 Tab：
  - 禁止隐式启动执行链路副作用（轮询/SSE/预检/对比）

### 3.3 写入边界与冲突处理

- Data Layer 只写入 `TaskDataState`。
- Execution Layer 只写入 `ExecutionRuntimeState`。
- View Layer 不直接写入前两者内部结构，只通过事件调用动作函数。
- SSE 与轮询结果冲突时，以最新 `execution_result` 快照为准。
- URL 参数变化只能驱动可见性，不得隐式重置执行状态机。

---

## 4. 迁移步骤

1. 提取 `useTaskData`
- 迁出解析/场景/DSL/报告等静态数据拉取与缓存。
- 页面行为保持一致，不改 Tab 交互。

2. 提取 `useTaskExecution`
- 迁出执行启动/停止、轮询、SSE、失败解释、回归对比。
- 保持执行按钮行为与状态展示一致。

3. 拆分视图组件
- 将 `TaskDetail` 渲染拆为 `TaskDetailView` 与 Tab 子组件。
- 页面仅做路由参数解析与依赖装配。

---

## 5. 验收清单

### 5.1 文档质量验收

- 全文 UTF-8 可读。
- 无乱码旧稿残留。
- 无重复历史段落。
- 章节顺序固定：背景问题 -> 架构分层 -> 状态流 -> 迁移步骤 -> 验收清单。

### 5.2 可实施性验收

- 仅依据本文可产出首个重构 PR（提取 `useTaskData`，UI 行为不变）。
- 每个模块均有“输入/输出/不负责什么”三元定义。

### 5.3 迭代安全验收

最小回归必跑：

- `npm run typecheck`（等价于 `tsc --noEmit`）
- 手测路径：
  - 启动执行
  - SSE 失败后轮询回退
  - Tab 切换稳定性
  - 停止执行

---

## 6. 附录

### 6.1 文档层内部契约（冻结）

```ts
type TaskDataState = {
  taskId: string;
  detail: ExtendedTaskDetail | null;
  parsedRequirement: ParsedRequirementPayload | null;
  scenarios: ScenarioPayload | null;
  dsl: DslPayload | null;
  analysisReport: AnalysisReportPayload | null;
  loading: boolean;
  error: string | null;
};

type ExecutionRuntimeState = {
  executionStatus: "not_started" | "running" | "passed" | "failed" | "stopped";
  executing: boolean;
  pollingError: string | null;
  streamStatus: "idle" | "connected" | "fallback";
  streamEvents: Array<{ event: string; data: string; at: string }>;
  preflight: PreflightCheckPayload | null;
  regressionDiff: RegressionDiffPayload | null;
  explanations: ExecutionExplanationPayload | null;
};

type TaskDetailViewModel = {
  activeTabKey: "parsed" | "scenario" | "dsl" | "execution" | "report" | "artifacts";
  taskName: string;
  displayTaskStatus: string;
  qualityScore?: number;
  data: TaskDataState;
  execution: ExecutionRuntimeState;
};
```

约束：

- `TaskDetailViewModel` 为只读聚合模型，视图层禁止反向写入。
- 契约字段只允许向后兼容新增，不允许重命名或移除既有字段。

### 6.2 高频迭代改动门禁

- 单次提交只允许改一条链路：数据链路 / 运行时链路 / 视图链路。
- 优先小 diff，禁止大块脚本替换 TSX。
- 高风险文件（`TaskDetail.tsx`）只做局部可验证修改。
- 禁止页面组件直接发起多源副作用。
- 禁止跨 Tab 共享可变对象并被多个副作用直接写入。
- 禁止文案硬编码混入状态机判断逻辑。

### 6.3 本轮约束声明

- 本轮不改后端契约，不新增 API。
- 本文仅定义前端核心文档与改造蓝图。
- 与 `docs/frontend_api_list.md` 的关系：该文件仍是对外文档总入口，本文只承载工程架构与实施约束。
