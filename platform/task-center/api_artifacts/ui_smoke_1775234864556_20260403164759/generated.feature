功能: ui_smoke_1775234864556
  背景: 分析结果来自当前需求文档
    假如 已加载当前任务的需求说明

  # priority: P2
  场景: `POST /api/tasks`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `POST /api/tasks`
    那么 任务归档后的可见性与一致性检查

  # priority: P2
  场景: `GET /api/tasks/{task_id}`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `GET /api/tasks/{task_id}`
    那么 从业务视角看，一次标准任务应经历以下过程：

  # priority: P2
  场景: `POST /api/tasks/{task_id}/parse`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `POST /api/tasks/{task_id}/parse`
    那么 任务结束后可归档，归档后不应继续作为活跃任务参与主流程

  # priority: P2
  场景: `GET /api/tasks/{task_id}/parsed-requirement`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `GET /api/tasks/{task_id}/parsed-requirement`
    那么 关键中间产物（解析结果、场景、DSL、Feature）应可回读

  # priority: P2
  场景: `GET /api/tasks/{task_id}/retrieved-context`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `GET /api/tasks/{task_id}/retrieved-context`
    那么 归档动作生效后，任务应从活跃视图中消失

  # priority: P2
  场景: `POST /api/tasks/{task_id}/scenarios/generate`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `POST /api/tasks/{task_id}/scenarios/generate`
    那么 返回结构需保持统一 envelope，便于前端统一处理

  # priority: P2
  场景: `GET /api/tasks/{task_id}/scenarios`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `GET /api/tasks/{task_id}/scenarios`
    那么 少量场景执行失败但不阻断整体链路

  # priority: P2
  场景: `GET /api/tasks/{task_id}/dsl`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `GET /api/tasks/{task_id}/dsl`
    那么 关键中间产物（解析结果、场景、DSL、Feature）应可回读
