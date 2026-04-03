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
- `HUNYUAN_EMBEDDING_MODEL`（默认 `hunyuan-embedding`，兼容 `OPENAI_EMBEDDING_MODEL`）
- `HUNYUAN_VISION_MODEL`（默认 `hunyuan-vision`，兼容 `OPENAI_VISION_MODEL`）
- `HUNYUAN_TIMEOUT_SECONDS` / `HUNYUAN_RETRIES`（兼容 `OPENAI_TIMEOUT_SECONDS` / `OPENAI_RETRIES`）

其余解析策略配置已迁移到平台共享配置文件：

- `platform/shared/config/runtime_config.json`
- 包含解析默认开关、`retrieval_top_k`、rerank 开关、检索评分权重、embedding 批大小

当开关打开但密钥缺失或请求失败时，会自动回退到规则解析链路；向量检索不可用时会自动退化为关键词检索。

`rerank_enabled=true` 时，会在检索窗口内进行语义重排（向量相似度 + 关键词信号），提升关键 chunk 命中稳定性。

模型调用统一通过 `platform/shared` 的 `model_gateway` 完成，不在分析模块重复封装厂商 SDK。

## 当前边界与建议

- 当前能力已经可用于主链路，但解析质量仍需结合业务样例持续回归。
- 建议维护固定“黄金需求样例”并做回归测试，避免迭代导致语义漂移。
- `parse_metadata` 中已包含 `fallback_reason`、`llm_error_type`、`retrieval_metrics` 与 `retrieval_scoring`，可直接用于调参与排障。
