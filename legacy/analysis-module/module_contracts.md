# analysis-module 模块契约说明

本文档补充 `README.md` 与 `requirements.md`，集中说明 `src/` 下各子模块的职责边界、输入输出、可选增强点与低耦合约束。

## 1. 设计目标

模块契约的核心目标不是把每个模块写得很复杂，而是提前明确：

- 谁负责生成什么结构
- 谁只消费上游结果，不重新承担上游职责
- 哪些字段必须保留，才能保证分析过程可追踪

## 2. 子模块职责与输入输出

### 2.1 `input_handler`

职责：

- 创建任务级上下文
- 规范化任务名、来源类型与原始需求文本
- 保存原始输入副本

输入：

- `task_name`
- `requirement_text`
- `source_type`
- `source_path`

输出：

- `task_context`
- `raw_requirement`

### 2.2 `document_loader`

职责：

- 从文件或内联文本读取原始内容
- 统一 UTF-8、BOM 与换行风格

输入：

- `source_path` 或 `inline_text`

输出：

- 原始文本字符串

### 2.3 `document_parser`

职责：

- 清洗文本
- 识别标题、列表、编号结构
- 提取关键词、候选测试点与最小大纲

输入：

- 原始文本

输出：

- `cleaned_text`
- `outline`
- `keywords`
- `candidate_test_points`

### 2.4 `chunker`

职责：

- 将清洗后的文档切成可追踪片段
- 优先按章节、段落切分，超长段落再按句子切开
- 为片段补充来源、区块编号与关键词

输入：

- `cleaned_text`
- `source_file`

输出：

- `DocumentChunk[]`

### 2.5 `knowledge_index`

职责：

- 基于 `DocumentChunk[]` 形成任务级轻量索引
- 保留 chunk 列表和关键词倒排索引

输入：

- `DocumentChunk[]`

输出：

- 检索索引对象

### 2.6 `retriever`

职责：

- 接收查询词并回捞最相关片段
- 基于关键词重叠、chunk 关键词和章节标题加权
- 保留命中分数与来源信息

输入：

- 索引对象
- 查询词

输出：

- `RetrievedChunk[]`

### 2.7 `requirement_parser`

职责：

- 融合原始需求与检索结果
- 提取目标、角色、动作、前置条件、断言、约束和歧义
- 保留 `use_llm` 增强开关，当前默认回退规则版

输入：

- `raw_requirement`
- `RetrievedChunk[]`
- `use_llm`

输出：

- `ParsedRequirement`

### 2.8 `scenario_builder`

职责：

- 将 `ParsedRequirement` 拆成结构化场景
- 控制场景粒度和优先级
- 将多动作需求拆分为多个场景候选

输入：

- `ParsedRequirement`
- `use_llm`

输出：

- `ScenarioModel[]`

### 2.9 `gherkin_generator`

职责：

- 将 `ScenarioModel[]` 渲染为 `.feature`
- 不重新承担需求推断

输入：

- `feature_name`
- `ScenarioModel[]`

输出：

- Gherkin 字符串

### 2.10 `feature_validator`

职责：

- 校验 `.feature` 的结构与最小语义质量
- 输出错误、警告和基础统计

输入：

- Gherkin 字符串

输出：

- `ValidationReport`

### 2.11 `artifact_manager`

职责：

- 组织任务目录
- 保存中间 JSON 与最终 `.feature` 产物

输入：

- 任务目录
- 文件名
- 文本或 JSON 载荷

输出：

- 落盘后的文件路径

### 2.12 `pipeline`

职责：

- 负责阶段编排，而不是承担额外业务理解
- 汇总所有中间结果，形成当前阶段的聚合输出

输入：

- 任务名
- 原始需求文本或来源路径
- `use_llm`

输出：

- `PipelineResult`

### 2.13 `cli`

职责：

- 提供最小独立运行入口
- 接收文档路径或内联需求
- 打印摘要结果或完整 JSON

输入：

- `--task-name`
- `--input-file` 或 `--requirement-text`
- `--artifacts-dir`
- `--use-llm`

输出：

- 控制台结果
- 任务级产物目录

## 3. 低耦合约束

- 不让 `gherkin_generator` 直接读取源文档
- 不让 `feature_validator` 回写场景定义
- 不让 `artifact_manager` 参与业务推断
- 不让分析模块直接调用 `lavague-qa` 执行能力

## 4. LLM 增强边界

当前阶段推荐的增强挂点只有两个：

- `requirement_parser`
- `scenario_builder`

明确不建议先整体改成 LLM 驱动的模块：

- `document_loader`
- `chunker`
- `knowledge_index`
- `retriever`
- `feature_validator`
- `artifact_manager`

LLM 增强规则：

- 规则链必须可单独运行
- LLM 失败时必须回退到规则结果
- 输出必须继续遵守现有 schema
- 冲突信息必须记录在 `ambiguities` 或校验告警中
