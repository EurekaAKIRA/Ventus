功能: 5
  背景: 分析结果来自当前需求文档
    假如 已加载当前任务的需求说明

  # priority: P2
  场景: `POST /api/tasks`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `POST /api/tasks`
    那么 POST /api/tasks/{task_id}/preflight-check 在执行前校验环境与依赖，返回可读原因与建议，减少无效执行

  # priority: P2
  场景: `GET /api/tasks/{task_id}`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `GET /api/tasks/{task_id}`
    那么 POST /api/tasks/{task_id}/preflight-check 在执行前校验环境与依赖，返回可读原因与建议，减少无效执行

  # priority: P2
  场景: `POST /api/tasks/{task_id}/parse`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `POST /api/tasks/{task_id}/parse`
    那么 POST /api/tasks/{task_id}/preflight-check 在执行前校验环境与依赖，返回可读原因与建议，减少无效执行

  # priority: P2
  场景: `GET /api/tasks/{task_id}/parsed-requirement`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `GET /api/tasks/{task_id}/parsed-requirement`
    那么 POST /api/tasks/{task_id}/preflight-check 在执行前校验环境与依赖，返回可读原因与建议，减少无效执行

  # priority: P2
  场景: `GET /api/tasks/{task_id}/retrieved-context`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `GET /api/tasks/{task_id}/retrieved-context`
    那么 POST /api/tasks/{task_id}/preflight-check 在执行前校验环境与依赖，返回可读原因与建议，减少无效执行

  # priority: P2
  场景: `POST /api/tasks/{task_id}/scenarios/generate`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `POST /api/tasks/{task_id}/scenarios/generate`
    那么 POST /api/tasks/{task_id}/preflight-check 在执行前校验环境与依赖，返回可读原因与建议，减少无效执行

  # priority: P2
  场景: `GET /api/tasks/{task_id}/scenarios`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `GET /api/tasks/{task_id}/scenarios`
    那么 POST /api/tasks/{task_id}/preflight-check 在执行前校验环境与依赖，返回可读原因与建议，减少无效执行

  # priority: P2
  场景: `GET /api/tasks/{task_id}/dsl`
    假如 当前平台已进入联调阶段，研发、测试与前端需要基于统一口径确认以下事项：
    当 `GET /api/tasks/{task_id}/dsl`
    那么 关键中间产物（解析结果、场景、DSL、Feature）应可回读
    并且 POST /api/tasks/{task_id}/preflight-check 在执行前校验环境与依赖，返回可读原因与建议，减少无效执行
