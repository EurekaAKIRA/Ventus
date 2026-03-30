# TestCaseDSL 协议草案

## 1. 目标

`TestCaseDSL` 是平台内部统一测试协议，用于连接：

- `case-generation`
- `execution-engine`
- `result-analysis`

它的定位是执行主协议，优先级高于 Gherkin。

## 2. 设计原则

- 面向执行，而不是只面向展示
- 保留场景级和步骤级结构
- 支持接入接口执行器、压测执行器和 LaVague UI 执行器
- 允许逐步扩展上下文变量和断言能力

## 3. 顶层结构

```json
{
  "dsl_version": "0.1.0",
  "task_id": "demo_20260329",
  "task_name": "demo",
  "feature_name": "demo",
  "execution_mode": "api",
  "metadata": {
    "source_type": "text",
    "language": "zh-CN",
    "execution": {
      "base_url": "http://127.0.0.1:8010",
      "default_headers": {
        "X-Test-Client": "platform-api-runner"
      }
    }
  },
  "scenarios": []
}
```

## 4. 场景结构

```json
{
  "scenario_id": "scenario_001",
  "name": "用户点击编辑按钮",
  "goal": "验证用户中心编辑入口",
  "priority": "P1",
  "preconditions": ["用户已登录并进入用户中心"],
  "source_chunks": ["chunk_001"],
  "steps": []
}
```

## 5. 步骤结构

```json
{
  "step_id": "scenario_001_step_01",
  "step_type": "when",
  "text": "查询用户资料接口",
  "request": {
    "method": "GET",
    "url": "https://api.example.com/profile",
    "headers": {
      "Authorization": "Bearer {{token}}"
    }
  },
  "assertions": [
    {
      "source": "status_code",
      "op": "eq",
      "expected": 200
    }
  ],
  "uses_context": ["token"],
  "save_context": {},
  "saves_context": []
}
```

## 6. 当前版本约束

- `step_type` 当前与 Gherkin 保持兼容：`given`、`when`、`then`、`and`
- `execution_mode` 当前建议值：
  - `api`
  - `cloud-load`
  - `web-ui`
- `uses_context` 和 `save_context` 已可被 `api-runner` 消费，用于步骤间数据传递

## 7. 已支持的接口测试字段

- `request`
  - `method`
  - `url`
  - `headers`
  - `params`
  - `json`
  - `data`
  - `timeout`
  - `retries`
- `assertions`
  - `source`
  - `op`
  - `expected`
- `uses_context`
- `save_context`
- `metadata.execution`
  - `base_url`
  - `default_headers`

## 8. 当前项目中的落点

当前 `TestCaseDSL` 已由：

- `platform/case-generation/src/case_generation/dsl_generator.py`

生成，并由：

- `platform/task-center/src/task_center/pipeline.py`

写入产物目录：

- `scenarios/test_case_dsl.json`

当前已经可以由：

- `platform/execution-engine/api-runner/src/api_runner/executor.py`

直接消费并执行。

当前 `api-runner` 已支持的常用断言操作包括：

- `eq`
- `ne`
- `gt`
- `lt`
- `ge`
- `le`
- `exists`
- `contains`
- `not_contains`
- `startswith`
- `endswith`
- `matches`
- `len_eq`
- `len_gt`
- `len_lt`
