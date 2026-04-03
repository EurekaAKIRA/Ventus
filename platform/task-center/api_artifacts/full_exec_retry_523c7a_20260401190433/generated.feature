Feature: full_exec_retry_523c7a
  Background: 分析结果来自当前需求文档
    Given 已加载当前任务的需求说明

  # priority: P0
  Scenario: 调用 `POST /api/tasks` 创建任务，请求体包含 `task_name`、`source_type`、`requirement_text`、`en
    Given 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    When 调用 `POST /api/tasks` 创建任务，请求体包含 `task_name`、`source_type`、`requirement_text`、`environment` 字段
    Then 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在

  # priority: P2
  Scenario: 调用 `POST /api/tasks/{task_id}/parse` 执行解析，请求体包含 `use_llm`、`rag_enabled`、`retriev
    Given 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    When 调用 `POST /api/tasks/{task_id}/parse` 执行解析，请求体包含 `use_llm`、`rag_enabled`、`retrieval_top_k`、`rerank_enabled` 字段
    Then 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    And 解析后 `parse_metadata.retrieval_mode` 应为 `vector+keyword` 或 `keyword`

  # priority: P2
  Scenario: 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    Given 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    When 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    Then 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在

  # priority: P2
  Scenario: 调用 `GET /api/tasks/{task_id}/parsed-requirement` 获取结构化需求，确认包含 `objective`、`actio
    Given 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    When 调用 `GET /api/tasks/{task_id}/parsed-requirement` 获取结构化需求，确认包含 `objective`、`actions`、`expected_results`
    Then 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在

  # priority: P2
  Scenario: 调用 `GET /api/tasks/{task_id}/scenarios` 获取场景，确认至少存在 1 个场景且步骤完整
    Given 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    When 调用 `GET /api/tasks/{task_id}/scenarios` 获取场景，确认至少存在 1 个场景且步骤完整
    Then 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在

  # priority: P2
  Scenario: 调用 `GET /api/tasks/{task_id}/dsl` 获取 DSL，确认包含 `scenarios` 和 `steps`
    Given 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    When 调用 `GET /api/tasks/{task_id}/dsl` 获取 DSL，确认包含 `scenarios` 和 `steps`
    Then 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在

  # priority: P2
  Scenario: 调用 `GET /api/tasks/{task_id}/feature` 获取 feature 文本，确认包含 `Feature:` 和 `Scenario:
    Given 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    When 调用 `GET /api/tasks/{task_id}/feature` 获取 feature 文本，确认包含 `Feature:` 和 `Scenario:`
    Then 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在

  # priority: P2
  Scenario: 调用 `POST /api/tasks/{task_id}/execute` 启动执行，请求体包含 `execution_mode`、`environment`
    Given 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
    When 调用 `POST /api/tasks/{task_id}/execute` 启动执行，请求体包含 `execution_mode`、`environment` 字段
    Then 解析成功后，调用 `GET /api/tasks/{task_id}` 获取任务详情，并确认 `parse_metadata` 存在
