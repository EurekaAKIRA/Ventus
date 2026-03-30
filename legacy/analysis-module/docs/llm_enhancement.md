# analysis-module LLM 增强预埋说明

本文档用于说明当前阶段推荐的 LLM 接入方式。目标不是把整条链路改成黑箱，而是在规则版 baseline 可运行的前提下，为后续增强保留清晰挂点。

## 1. 设计原则

- 保留规则版流程作为默认路径。
- LLM 只作为可选增强，不替换 `document_loader`、`chunker`、`knowledge_index`、`retriever`、`feature_validator`、`artifact_manager`。
- 所有增强结果必须继续落到现有 schema 与中间产物结构中。
- 任一增强步骤失败时，必须回退到规则结果，并记录 fallback 原因。

## 2. 推荐接入点

### 2.1 `requirement_parser`

推荐用途：

- 补充角色、对象、动作、约束、歧义提取
- 将长段需求压缩为结构化 `ParsedRequirement`

输入约束：

- 原始需求文本
- 检索命中片段摘要
- 当前规则解析结果

输出约束：

- 必须映射回 `ParsedRequirement`
- 不允许输出自由格式长文本作为唯一结果

### 2.2 `scenario_builder`

推荐用途：

- 辅助拆分多目标需求
- 优化场景名称、断言粒度与优先级建议

输入约束：

- `ParsedRequirement`
- 来源片段标识

输出约束：

- 必须映射回 `ScenarioModel[]`
- 每个场景必须保留 `source_chunks`

### 2.3 `gherkin_generator`

当前阶段不建议优先接入，仅在规则版已能稳定产出后再考虑。

## 3. Prompt 结构建议

推荐采用固定结构，而不是自由问答：

1. 任务目标
2. 原始需求
3. 检索补充上下文
4. 规则版结果
5. 输出 schema 约束
6. 不允许编造信息的约束
7. fallback 规则

## 4. Fallback 策略

- LLM 超时或返回非结构化结果时，直接回退规则版。
- LLM 输出字段缺失时，用规则结果补齐，而不是让流程中断。
- 若 LLM 结果与原始需求冲突，优先保留原始需求，并将冲突记录到 `ambiguities`。

## 5. 与当前流水线的衔接方式

- 在 `run_analysis_pipeline(..., use_llm=True)` 中传递增强开关。
- `requirement_parser` 与 `scenario_builder` 先消费该开关，当前阶段仅记录“已请求增强但回退到规则版”。
- 后续如需正式接入模型，可增加独立的 `llm_adapter.py` 或 `llm_enhancer.py`，保持业务规则与模型调用解耦。
