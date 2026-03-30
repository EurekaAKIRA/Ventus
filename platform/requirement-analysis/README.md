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
