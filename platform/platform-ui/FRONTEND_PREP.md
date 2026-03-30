# Frontend Prep

## 目标

本目录用于给平台前端开发提供统一的准备材料，方便在尚未完全确定前端技术栈时，先完成：

- 页面结构设计
- 路由规划
- 数据类型定义
- mock 数据联调

相关参考文档：

- `docs/frontend_api_list.md`
- `docs/project_requirements.md`
- `platform/shared/src/platform_shared/models.py`

---

## 推荐页面结构

建议前端第一期按以下页面拆分：

### 1. 仪表盘页

路径建议：

- `/dashboard`

主要展示：

- 任务总数
- 最近任务
- 成功/失败统计
- 报告图表摘要

### 2. 任务列表页

路径建议：

- `/tasks`

主要展示：

- 任务列表
- 状态筛选
- 关键词搜索
- 跳转任务详情

### 3. 创建任务页

路径建议：

- `/tasks/create`

主要功能：

- 输入任务名称
- 输入需求文本或上传需求文件
- 填写目标系统地址
- 选择环境
- 创建任务

### 4. 任务详情页

路径建议：

- `/tasks/:taskId`

建议拆成多个 tab：

- 基本信息
- 需求解析
- 场景与 DSL
- 执行过程
- 分析报告
- 产物文件

---

## 推荐路由表

```text
/dashboard
/tasks
/tasks/create
/tasks/:taskId
/tasks/:taskId/parsed
/tasks/:taskId/scenarios
/tasks/:taskId/execution
/tasks/:taskId/report
/tasks/:taskId/artifacts
```

如果想减少页面数量，也可以把后四个页面做成详情页内 tab。

---

## 推荐组件拆分

### 通用组件

- `PageHeader`
- `StatusTag`
- `EmptyState`
- `LoadingBlock`
- `JsonViewer`
- `MetricCard`
- `LogPanel`
- `SectionCard`

### 业务组件

- `TaskCreateForm`
- `TaskTable`
- `TaskBasicInfo`
- `ParsedRequirementPanel`
- `ScenarioList`
- `DslViewer`
- `ExecutionStatusPanel`
- `ExecutionLogPanel`
- `AnalysisSummaryPanel`
- `ArtifactList`

---

## 页面与接口对应关系

### 创建任务页

- `POST /api/tasks`

### 任务列表页

- `GET /api/tasks`

### 任务详情页

- `GET /api/tasks/{task_id}`

### 需求解析页

- `GET /api/tasks/{task_id}/parsed-requirement`
- `GET /api/tasks/{task_id}/retrieved-context`

### 场景/DSL 页

- `GET /api/tasks/{task_id}/scenarios`
- `GET /api/tasks/{task_id}/dsl`
- `GET /api/tasks/{task_id}/feature`

### 执行监控页

- `POST /api/tasks/{task_id}/execute`
- `GET /api/tasks/{task_id}/execution`
- `GET /api/tasks/{task_id}/execution/logs`

### 报告页

- `GET /api/tasks/{task_id}/validation-report`
- `GET /api/tasks/{task_id}/analysis-report`

---

## 联调顺序建议

建议先按下面顺序做页面：

1. 任务列表页
2. 创建任务页
3. 任务详情基础信息
4. 需求解析页
5. 场景与 DSL 页
6. 报告页
7. 执行监控页

这样即使执行相关接口还没完全实现，前面的展示型页面也可以先做完。

---

## 目录建议

如果后面使用 Vue 或 React，可参考下面的目录组织：

```text
platform-ui/
  FRONTEND_PREP.md
  page_plan.md
  api-contract.ts
  mock-data.ts
```

后续若正式初始化前端工程，可迁移为：

```text
platform-ui/
  src/
    api/
    components/
    pages/
    types/
    mocks/
    router/
```

---

## 当前建议

当前最适合的推进方式是：

- 先基于 `api-contract.ts` 定义前端类型
- 使用 `mock-data.ts` 把任务列表、详情页、报告页先跑通
- 等后端 REST API 明确后，再把 mock 请求替换为真实请求
