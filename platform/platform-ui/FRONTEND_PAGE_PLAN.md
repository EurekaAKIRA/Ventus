# 前端页面规划（platform-ui）

## 1. 背景问题

本文件用于定义 `platform-ui` 页面级职责边界，避免将接口细节、状态机逻辑和渲染细节混写在同一层。

目标：

- 让页面职责与 `TaskDetail` 拆分蓝图一一对应。
- 让跨 Tab 的共享状态可控，避免副作用互相污染。
- 让后续重构 PR 按固定顺序落地，不与视觉改动混改。

统一文档入口：`docs/frontend_api_list.md` 的 **§1.1 前端参考文档索引**。

---

## 2. 架构分层

### 2.1 页面层职责总览

- `/dashboard`
  - 负责：趋势与风险总览、任务入口导航
  - 不负责：执行控制、复杂编辑
- `/tasks`
  - 负责：当前任务筛选、排序、快速跳转
  - 不负责：执行状态机管理、报告深度分析
- `/tasks/create`
  - 负责：创建参数输入与基础校验
  - 不负责：创建后执行链路控制
- `/tasks/:taskId`
  - 负责：多 Tab 联动、执行入口、报告与产物查看
  - 不负责：在单组件中混合全部副作用实现
- `/tasks/history`
  - 负责：历史检索与复盘跳转（如 `tab=report&compare=latest`）
  - 不负责：实时执行控制

### 2.2 TaskDetail 页内模块分层

- Data Layer：`useTaskData`
- Execution Layer：`useTaskExecution`
- View Layer：`TaskDetailView` + Tab 子面板

### 2.3 Tab 与模块映射

- `parsed` -> `ParsedRequirementPanel`（`TaskDataState.parsedRequirement`）
- `scenario` -> `ScenarioPanel`（`TaskDataState.scenarios`）
- `dsl` -> `DslPanel`（`TaskDataState.dsl`）
- `execution` -> `ExecutionPanel`（`ExecutionRuntimeState` + `TaskDataState.detail`）
- `report` -> `ReportPanel`（`analysisReport` + `explanations` + `regressionDiff`）
- `artifacts` -> `ArtifactsPanel`（任务产物数据）

---

## 3. 状态流

### 3.1 页内状态流（文本图）

```text
TaskDetailPage
  ├─ useTaskData(taskId, urlParams) -> TaskDataState
  ├─ useTaskExecution(taskId, activeTabKey, minimalContext) -> ExecutionRuntimeState + actions
  └─ TaskDetailView(viewModel, actions)
       ├─ TaskTabs
       ├─ ParsedRequirementPanel
       ├─ ScenarioPanel
       ├─ DslPanel
       ├─ ExecutionPanel
       ├─ ReportPanel
       └─ ArtifactsPanel
```

### 3.2 跨 Tab 共享状态约束

可共享只读状态：

- `taskId`
- `activeTabKey`
- `TaskDetailViewModel`

禁止共享可变状态：

- SSE 事件缓存对象被多个 Tab 直接写入
- 轮询计时器句柄在多个组件间传递并修改
- 执行按钮临时态与报告卡片临时态复用同一可变引用

### 3.3 触发规则与禁止项

- `execution` Tab 外不得触发执行链路副作用。
- `report` Tab 外不得触发回归对比自动拉取。
- 禁止页面组件直接发起多源副作用（轮询 + SSE + 多 API）。
- 禁止文案硬编码混入状态机逻辑。

---

## 4. 迁移步骤

1. 按层先拆 `useTaskData`，保持 UI 行为不变。
2. 再拆 `useTaskExecution`，收拢执行链路副作用。
3. 最后拆 `TaskDetailView` 与 Tab 子组件。
4. 视觉与交互优化放在拆分完成后单独提交。

---

## 5. 验收清单

### 5.1 文档质量验收

- 全文 UTF-8 可读。
- 无乱码旧稿残留。
- 无重复历史段落。
- 章节顺序固定：背景问题 -> 架构分层 -> 状态流 -> 迁移步骤 -> 验收清单。

### 5.2 可实施性验收

- 仅依据本文可拆出首个页面重构 PR（`useTaskData` 先行）。
- 模块边界清晰，页面职责不再混叠。

### 5.3 迭代安全验收

- `npm run typecheck` 可通过。
- 关键手测路径稳定：启动执行、SSE失败回退、Tab切换、停止执行。

---

## 6. 附录

- `docs/frontend_api_list.md`：前端文档总入口与接口总表。
- `FRONTEND_DEVELOPMENT_GUIDE.md`：架构约束、内部契约、门禁与迁移细则。
- 本文件：页面职责与模块落位，不重复维护接口长表。
