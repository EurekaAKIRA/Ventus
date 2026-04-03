# requirement-analysis RAG + LLM 设计说明

## 1. 目标

在不破坏既有主链路的前提下，将需求解析能力升级为：

- 模块可独立调用（服务层 API）
- 对外仍由 `task-center` 聚合暴露
- 模型调用统一收敛到 `platform/shared` 网关
- LLM 不可用时自动回退规则解析，不中断主流程

## 2. 架构分层

当前解析链路为：

`task-center(api) -> requirement-analysis(service) -> shared(model_gateway)`

其中：

- `task-center` 负责 API 入参、参数优先级、兼容旧接口
- `requirement-analysis` 负责文档处理、RAG 检索、结构化解析、验证
- `shared/model_gateway` 负责统一模型调用（llm/embedding/vision 预留）

## 3. 统一模型网关

位置：`platform/shared/src/platform_shared/model_gateway.py`

核心能力：

- 统一配置模型端点（provider/model/api_base/api_key/timeout/retries）
- 统一重试与错误分类
- 统一 JSON 返回处理
- 当前默认使用腾讯混元 OpenAI 兼容接口（LLM + Embedding），并兼容 OpenAI 风格调用
- `vision` 先预留配置位，后续执行层可接入

## 4. 模块级 API（服务层）

位置：`platform/requirement-analysis/src/requirement_analysis/service.py`

入口：

- `parse_requirement_bundle(...)`

输出：

- `parsed_requirement`
- `retrieved_context`
- `validation_report`
- `parse_metadata`

## 5. 对外接口

新增：

- `POST /api/analysis/parse`

兼容保留：

- `POST /api/tasks/{task_id}/parse`

两者都支持增强参数（可选）：

- `use_llm`
- `rag_enabled`
- `retrieval_top_k`
- `rerank_enabled`

## 6. 参数优先级

固定顺序：

1. 请求参数
2. `platform/shared/config/runtime_config.json`（共享默认策略）
3. 系统内置默认值（兜底）

默认值：

- `use_llm=false`
- `rag_enabled=true`
- `retrieval_top_k=5`
- `rerank_enabled=false`
- `model_profile=default`

说明：

- 模型 API 凭证与显式模型覆盖仍可通过环境变量传入（如 `HUNYUAN_API_KEY`、`HUNYUAN_BASE_URL`、`HUNYUAN_LLM_MODEL`）。
- 非 API 策略参数不再依赖环境变量。

## 7. fallback 规范

当 LLM 不可用、超时、异常、返回非 JSON 时：

- 解析链路回退到规则模式
- 不抛出 500 终止主流程
- 在 `parse_metadata` 中写入：
  - `parse_mode=rules`
  - `fallback_reason`
  - `llm_error_type`（可选）

当向量检索不可用（如密钥缺失、embedding 请求失败）时：

- 自动退化为关键词检索
- `parse_metadata.rag_fallback_reason` 记录退化原因

## 8. 产物扩展

新增解析元数据：

- `parsed/parse_metadata.json`
- `scenario_bundle.json` 中新增 `parse_metadata`

同时 `artifacts` 新增：

- `parse-metadata`

## 9. 性能口径

输出中记录 `parse_metadata.performance`：

- `elapsed_ms`
- `target_ms`
- `within_target`
- `slow_reason`

阈值：

- baseline（规则）<= 8s
- enhanced（llm + rag）<= 20s（不含外部模型异常波动）
