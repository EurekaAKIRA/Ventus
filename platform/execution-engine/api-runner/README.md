# execution-engine/api-runner

本地接口自动化执行器。

## 负责内容

- HTTP 接口调用
- Header、Query、JSON Body 注入
- 基础断言执行
- 多步骤上下文变量传递
- 输出标准化执行结果

## 当前状态

已补充可运行的第一版执行器：

- `src/api_runner/executor.py`
- `examples/sample_test_case_dsl.json`
- `tests/api_runner_smoke_test.py`

## 当前已支持

- 真实 HTTP 请求
- JSON 请求体
- Header 注入
- 简单上下文变量替换，如 `{{token}}`
- 基于 `ContextBus` 的步骤间数据传递
- 基础断言，如：
  - `status_code`
  - `elapsed_ms`
  - `json.xxx`
  - `body_text`
  - `headers.xxx`

## 当前常用断言操作

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

## 当前仍未完成

- 更复杂的 JSONPath
- 自动从需求生成接口请求定义
- 并发执行
- 性能压测能力
