# requirement-analysis

## 模块定位

需求理解子系统，负责将自然语言需求与文档输入转换为结构化需求表示。

## 核心职责

- 文档加载
- 文本清洗
- 文档结构识别
- 文本切分
- 轻量检索增强
- 测试点提取
- 不确定项记录

## 输出对象

- `ParsedRequirement`
- 文档片段集合
- 检索命中结果

## 迁移来源

- 主要来自 `analysis-module` 的：
  `document_loader`
  `document_parser`
  `chunker`
  `knowledge_index`
  `retriever`
  `requirement_parser`

## 当前状态

第一批代码已迁移到：

- `src/requirement_analysis/document_loader.py`
- `src/requirement_analysis/document_parser.py`
- `src/requirement_analysis/chunker.py`
- `src/requirement_analysis/knowledge_index.py`
- `src/requirement_analysis/retriever.py`
- `src/requirement_analysis/requirement_parser.py`

当前以“先复制迁移、再逐步替换旧调用”为策略，旧目录暂未删除。

## 服务层 API

模块内提供可独立调用入口：

- `parse_requirement_bundle(...)`
- `AnalysisParseOptions.resolve(...)`

用于在不依赖 task 实体生命周期时，直接获得：

- `parsed_requirement`
- `retrieved_context`
- `validation_report`
- `parse_metadata`

## 可选增强开关

默认情况下，本模块使用规则解析 + 关键词检索。

环境变量仅保留模型 API 相关项（默认按腾讯混元 OpenAI 兼容接口）：

- `HUNYUAN_API_KEY=<your_api_key>`（必填，兼容 `OPENAI_API_KEY`）
- `HUNYUAN_BASE_URL`（默认 `https://api.hunyuan.cloud.tencent.com/v1`，兼容 `OPENAI_BASE_URL`）
- `HUNYUAN_LLM_MODEL`（默认 `hunyuan-turbos-latest`，兼容 `OPENAI_LLM_MODEL`）
- `HUNYUAN_LLM_MAX_TOKENS`（默认 `1600`，兼容 `OPENAI_LLM_MAX_TOKENS`；设置为 `off` 可不限制）
- `HUNYUAN_EMBEDDING_MODEL`（默认 `hunyuan-embedding`，兼容 `OPENAI_EMBEDDING_MODEL`）
- `HUNYUAN_VISION_MODEL`（默认 `hunyuan-vision`，兼容 `OPENAI_VISION_MODEL`）
- `HUNYUAN_TIMEOUT_SECONDS` / `HUNYUAN_RETRIES`（兼容 `OPENAI_TIMEOUT_SECONDS` / `OPENAI_RETRIES`）

其余解析策略配置已迁移到平台共享配置文件：

- `platform/shared/config/runtime_config.json`
- 包含解析默认开关、`retrieval_top_k`、rerank 开关、检索评分权重、embedding 批大小

当开关打开但密钥缺失或请求失败时，会自动回退到规则解析链路；向量检索不可用时会自动退化为关键词检索。

`rerank_enabled=true` 时，会在检索窗口内进行语义重排（向量相似度 + 关键词信号），提升关键 chunk 命中稳定性。

模型调用统一通过 `platform/shared` 的 `model_gateway` 完成，不在分析模块重复封装厂商 SDK。

## 知识库扩展

除内置知识库外，当前还支持通过环境变量注入外部知识源：

- `REQUIREMENT_ANALYSIS_EXTRA_KNOWLEDGE_REGISTRY`
  可填写一个或多个 registry JSON 路径，多个路径使用系统路径分隔符连接
- `REQUIREMENT_ANALYSIS_EXTRA_KNOWLEDGE_ROOT`
  外部知识文档根目录，registry 中相对路径会基于该目录解析

这样可以在不改代码的情况下，把新的业务域文档接入 RAG 检索链。

## RAG 评测

模块已补充离线评测入口：

- `requirement_analysis.rag_evaluator.evaluate_retrieval_cases(...)`
- `requirement_analysis.rag_benchmark.run_rag_benchmark(...)`
- `platform/requirement-analysis/scripts/run_rag_benchmark.py`

可用于固定样例集的检索评估，输出：

- `recall_at_k`
- `mrr`
- 按 source file 的命中统计
- 每个 case 的命中排名与检索模式

这部分适合直接用于论文实验或回归评测。

默认 benchmark 样例集位于：

- `platform/requirement-analysis/benchmarks/rag_benchmark_cases.json`

可直接执行：

```powershell
python platform/requirement-analysis/scripts/run_rag_benchmark.py
```

如果已配置 embedding 模型密钥，会输出三组结果：

- `keyword`
- `vector_keyword`
- `vector_keyword_rerank`

如果未配置 embedding，则仍会输出 `keyword` 基线，并对向量模式给出 `skip_reason`。

执行后默认会在以下目录生成三份结果文件：

- `platform/requirement-analysis/benchmark_results/rag_benchmark.json`
- `platform/requirement-analysis/benchmark_results/rag_benchmark_summary.csv`
- `platform/requirement-analysis/benchmark_results/rag_benchmark.md`

其中：

- `JSON` 适合保留完整原始结果
- `CSV` 适合直接导入 Excel / 绘图
- `Markdown` 适合直接贴进论文草稿或实验记录

## 当前边界与建议

- 当前能力已经可用于主链路，但解析质量仍需结合业务样例持续回归。
- 建议维护固定“黄金需求样例”并做回归测试，避免迭代导致语义漂移。
- `parse_metadata` 中已包含 `fallback_reason`、`llm_error_type`、`retrieval_metrics` 与 `retrieval_scoring`，可直接用于调参与排障。
