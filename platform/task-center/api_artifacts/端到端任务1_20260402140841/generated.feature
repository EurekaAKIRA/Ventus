功能: 端到端任务1
  背景: 分析结果来自当前需求文档
    假如 已加载当前任务的需求说明

  # priority: P0
  场景: 调用 `POST /api/tasks` 创建任务，请求体包含 `task_name`、`source_type`、`requirement_text`、`en
    假如 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    当 调用 `POST /api/tasks` 创建任务，请求体包含 `task_name`、`source_type`、`requirement_text`、`environment`、`target_system` 字段，其中 `target_system` 固定为 `http://127.0.0.1:8001`
    那么 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在

  # priority: P2
  场景: 调用 `POST /api/tasks/{task_id}/parse` 执行解析，请求体包含 `use_llm`、`rag_enabled`、`retriev
    假如 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    当 调用 `POST /api/tasks/{task_id}/parse` 执行解析，请求体包含 `use_llm`、`rag_enabled`、`retrieval_top_k`、`rerank_enabled` 字段
    那么 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    并且 解析后 `parse_metadata.retrieval_mode` 应为 `vector+keyword` 或 `keyword`

  # priority: P2
  场景: 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    假如 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    当 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    那么 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在

  # priority: P2
  场景: 调用 `GET /api/tasks/{task_id}/parsed-requirement` 获取结构化需求，确认包含 `objective`、`actio
    假如 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    当 调用 `GET /api/tasks/{task_id}/parsed-requirement` 获取结构化需求，确认包含 `objective`、`actions`、`expected_results`
    那么 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在

  # priority: P2
  场景: 调用 `GET /api/tasks/{task_id}/scenarios` 获取场景，确认至少存在 1 个场景且步骤完整
    假如 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    当 调用 `GET /api/tasks/{task_id}/scenarios` 获取场景，确认至少存在 1 个场景且步骤完整
    那么 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在

  # priority: P2
  场景: 调用 `GET /api/tasks/{task_id}/dsl` 获取 DSL，确认包含 `scenarios` 和 `steps`
    假如 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    当 调用 `GET /api/tasks/{task_id}/dsl` 获取 DSL，确认包含 `scenarios` 和 `steps`
    那么 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在

  # priority: P2
  场景: 调用 `GET /api/tasks/{task_id}/feature` 获取 feature 文本，确认包含 `Feature:` 和 `Scenario:
    假如 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    当 调用 `GET /api/tasks/{task_id}/feature` 获取 feature 文本，确认包含 `Feature:` 和 `Scenario:`
    那么 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在

  # priority: P2
  场景: 调用 `POST /api/tasks/{task_id}/execute` 启动执行，请求体包含 `execution_mode`、`environment`
    假如 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    当 调用 `POST /api/tasks/{task_id}/execute` 启动执行，请求体包含 `execution_mode`、`environment` 字段
    那么 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
