功能: platform_e2e_regression_8bb41a2f
  背景: 分析结果来自当前需求文档
    假如 已加载当前任务的需求说明

  # priority: P2
  场景: `POST /api/tasks`
    假如 执行完成且进入终态
    当 `POST /api/tasks`
    那么 当前 task-center API 统一使用如下响应结构：
    并且 尤其是 `GET /api/tasks/{task_id}`，当前真实返回位于 `data` 下，包含：

  # priority: P2
  场景: `GET /api/tasks/{task_id}`
    假如 执行完成且进入终态
    当 `GET /api/tasks/{task_id}`
    那么 当前 task-center API 统一使用如下响应结构：
    并且 尤其是 `GET /api/tasks/{task_id}`，当前真实返回位于 `data` 下，包含：

  # priority: P2
  场景: `POST /api/tasks/{task_id}/parse`
    假如 执行完成且进入终态
    当 `POST /api/tasks/{task_id}/parse`
    那么 当前 task-center API 统一使用如下响应结构：
    并且 尤其是 `GET /api/tasks/{task_id}`，当前真实返回位于 `data` 下，包含：

  # priority: P2
  场景: `GET /api/tasks/{task_id}/parsed-requirement`
    假如 执行完成且进入终态
    当 `GET /api/tasks/{task_id}/parsed-requirement`
    那么 当前 task-center API 统一使用如下响应结构：
    并且 尤其是 `GET /api/tasks/{task_id}`，当前真实返回位于 `data` 下，包含：

  # priority: P2
  场景: `GET /api/tasks/{task_id}/retrieved-context`
    假如 执行完成且进入终态
    当 `GET /api/tasks/{task_id}/retrieved-context`
    那么 当前 task-center API 统一使用如下响应结构：
    并且 尤其是 `GET /api/tasks/{task_id}`，当前真实返回位于 `data` 下，包含：

  # priority: P2
  场景: `POST /api/tasks/{task_id}/scenarios/generate`
    假如 执行完成且进入终态
    当 `POST /api/tasks/{task_id}/scenarios/generate`
    那么 当前 task-center API 统一使用如下响应结构：
    并且 尤其是 `GET /api/tasks/{task_id}`，当前真实返回位于 `data` 下，包含：

  # priority: P2
  场景: `GET /api/tasks/{task_id}/scenarios`
    假如 执行完成且进入终态
    当 `GET /api/tasks/{task_id}/scenarios`
    那么 当前 task-center API 统一使用如下响应结构：
    并且 尤其是 `GET /api/tasks/{task_id}`，当前真实返回位于 `data` 下，包含：

  # priority: P2
  场景: `GET /api/tasks/{task_id}/dsl`
    假如 执行完成且进入终态
    当 `GET /api/tasks/{task_id}/dsl`
    那么 当前 task-center API 统一使用如下响应结构：
    并且 尤其是 `GET /api/tasks/{task_id}`，当前真实返回位于 `data` 下，包含：
