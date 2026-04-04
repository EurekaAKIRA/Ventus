功能: platform_e2e_regression_d26de49e
  背景: 分析结果来自当前需求文档
    假如 已加载当前任务的需求说明

  # priority: P0
  场景: HTTP `200`
- `code = TASK_ARCHIVED`
- `data.task_id = {task_id}`
- `data.archive
    假如 从有效的 API 入口开始执行
    当 HTTP `200`
- `code = TASK_ARCHIVED`
- `data.task_id = {task_id}`
- `data.archived = true`
POST /api/tasks 创建任务
    那么 成功时响应 data 中含 task_id，用于后续查询与执行

  # priority: P2
  场景: `GET /api/tasks/{task_id}`
    假如 从有效的 API 入口开始执行
    当 `GET /api/tasks/{task_id}`
    那么 成功时响应 data 中含 task_id，用于后续查询与执行

  # priority: P2
  场景: `POST /api/tasks/{task_id}/parse`
    假如 从有效的 API 入口开始执行
    当 `POST /api/tasks/{task_id}/parse`
    那么 成功时响应 data 中含 task_id，用于后续查询与执行

  # priority: P2
  场景: `GET /api/tasks/{task_id}/dsl`
    假如 从有效的 API 入口开始执行
    当 `GET /api/tasks/{task_id}/dsl`
    那么 成功时响应 data 中含 task_id，用于后续查询与执行

  # priority: P2
  场景: `POST /api/tasks/{task_id}/execute`
    假如 从有效的 API 入口开始执行
    当 `POST /api/tasks/{task_id}/execute`
    那么 成功时响应 data 中含 task_id，用于后续查询与执行

  # priority: P2
  场景: `GET /api/tasks/{task_id}/execution`
    假如 从有效的 API 入口开始执行
    当 `GET /api/tasks/{task_id}/execution`
    那么 成功时响应 data 中含 task_id，用于后续查询与执行

  # priority: P2
  场景: `GET /api/tasks/{task_id}/analysis-report`
    假如 从有效的 API 入口开始执行
    当 `GET /api/tasks/{task_id}/analysis-report`
    那么 成功时响应 data 中含 task_id，用于后续查询与执行

  # priority: P0
  场景: `DELETE /api/tasks/{task_id}`
    假如 从有效的 API 入口开始执行
    当 `DELETE /api/tasks/{task_id}`
    那么 成功时响应 data 中含 task_id，用于后续查询与执行
