# Platform 重构骨架

本目录用于在当前项目内承载“基于 Agent 架构的通用自动化测试平台”新架构。

重构后的平台主线为：

`任务接入 -> 需求解析 -> 用例生成 -> 测试执行 -> 结果分析 -> 可视化展示`

## 目录说明

- `task-center/`
  统一任务接入、项目配置、环境管理和任务编排入口。
- `requirement-analysis/`
  负责需求文档解析、结构提取、检索增强和结构化需求输出。
- `case-generation/`
  负责测试场景拆分、断言整理、DSL/JSON 生成和 Gherkin 派生输出。
- `execution-engine/`
  统一执行引擎，负责根据测试协议调度不同执行器。
- `result-analysis/`
  负责执行结果汇总、指标分析和质量评估。
- `platform-ui/`
  负责平台前端展示和交互。
- `shared/`
  平台共用数据模型、协议定义、通用工具与基础 schema。

## 关于 LaVague

`LaVague` 在新架构中不再作为平台中心，而是被归类为：

`execution-engine/lavague-adapter`

也就是执行层中的 Web/UI 自动化执行适配器。

## 当前迁移原则

1. 先在当前仓库内建立新架构骨架，不破坏现有历史目录。
2. 旧目录暂时保留，逐步迁移能力到 `platform/`。
3. 新功能优先落到 `platform/`，避免继续在历史目录上扩散。
