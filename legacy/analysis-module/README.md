# analysis-module

`analysis-module` 是自动化测试系统中的前置分析模块，负责把业务需求、产品说明、接口说明、流程文档等输入，整理为可审查、可追踪、可继续消费的结构化测试场景，并输出标准 Gherkin `.feature` 文件与中间产物。

当前阶段聚焦“需求理解与测试描述生成”，不负责测试执行，也不直接改动 `lavague-qa` 执行链。

## 当前状态

当前已从“模块骨架”提升为“可独立运行的半成品”：

- 支持文本或 Markdown 输入
- 支持 UTF-8/换行规范化与基础文档清洗
- 支持按章节/段落/句子进行 chunk 切分
- 支持任务级轻量检索与命中片段回捞
- 支持规则化需求解析、测试点提取与多场景拆分
- 支持 Gherkin 生成功能与基础语义告警
- 支持任务级 artifacts 落盘
- 支持最小 CLI 入口、示例输入和测试脚本

仍未完成的部分：

- PDF/Word/HTML 等复杂文档输入
- 更强的语义检索与去重
- 更细的异常场景建模
- 正式 LLM 增强实现
- 严格 schema 运行时校验

## 目录结构

```text
analysis-module/
  README.md
  requirements.md
  module_contracts.md
  docs/
    llm_enhancement.md
  examples/
    README.md
    sample_requirement.md
  prompts/
    README.md
  schemas/
    task_context.schema.json
    parsed_requirement.schema.json
    test_scenario.schema.json
    validation_report.schema.json
  generated-features/
  artifacts/
  src/
    __init__.py
    __main__.py
    cli.py
    models.py
    input_handler.py
    document_loader.py
    document_parser.py
    chunker.py
    knowledge_index.py
    retriever.py
    requirement_parser.py
    scenario_builder.py
    gherkin_generator.py
    feature_validator.py
    artifact_manager.py
    pipeline.py
  run_analysis.py
  tests/
    smoke_test.py
    component_test.py
    cli_smoke_test.py
```

## 最小运行方式

直接运行内联需求：

```powershell
python analysis-module/run_analysis.py --task-name homepage_demo --requirement-text "用户打开首页后应看到标题和搜索框"
```

运行示例文档：

```powershell
python analysis-module/run_analysis.py --task-name user_center_demo --input-file analysis-module/examples/sample_requirement.md
```

如果希望查看完整 JSON：

```powershell
python analysis-module/run_analysis.py --task-name user_center_demo --input-file analysis-module/examples/sample_requirement.md --print-json
```

## 当前处理链路

1. `input_handler` 规范化任务输入，生成 `TaskContext`
2. `document_loader` 读取文本并统一编码/换行
3. `document_parser` 清洗文本、提取大纲、关键词和候选测试点
4. `chunker` 按章节/段落/句子切分文档
5. `knowledge_index` 建立任务级轻量索引
6. `retriever` 基于关键词重叠和章节标题加权回捞片段
7. `requirement_parser` 提取角色、前置条件、动作、断言、约束和歧义
8. `scenario_builder` 将多动作需求拆分为场景
9. `gherkin_generator` 生成带优先级注释的 `.feature`
10. `feature_validator` 做结构校验与语义告警
11. `artifact_manager` 统一落盘产物

## 主要产物

每次任务默认落盘到 `analysis-module/artifacts/<task_name>_<timestamp>/`：

- `raw/requirement.txt`
- `parsed/cleaned_document.json`
- `parsed/parsed_requirement.json`
- `retrieval/retrieved_chunks.json`
- `scenarios/scenario_bundle.json`
- `validation/validation_report.json`
- `generated.feature`

其中聚合 JSON 是当前更稳定的中间接口，`.feature` 是展示和后续执行更友好的派生产物。

## LLM 预埋

当前版本保留 `use_llm` 开关，但默认仍走规则版流程。后续推荐优先增强：

- `requirement_parser`
- `scenario_builder`

设计说明见 [`docs/llm_enhancement.md`](/E:/ending/LaVague-main/analysis-module/docs/llm_enhancement.md)。

## 测试命令

```powershell
python analysis-module/tests/smoke_test.py
python analysis-module/tests/component_test.py
python analysis-module/tests/cli_smoke_test.py
```

## 约束

- 只聚焦需求分析与特征生成，不负责任何执行链逻辑
- 保持与 `lavague-qa` 低耦合，只通过产物文件衔接
- 允许降级输出，但必须记录歧义与信息缺口
- 当前优先做“可运行、可追踪、可扩展”的半成品，而不是一次性做成全黑箱方案
