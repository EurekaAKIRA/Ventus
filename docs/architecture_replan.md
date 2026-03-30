# 自动化测试平台重构架构方案

## 1. 重构目标

本次重构的目标不是继续围绕 `LaVague` 组织整个仓库，而是将项目调整为一个以“自动化测试平台” 为核心的分层架构。

平台主线应围绕以下闭环展开：

`需求输入 -> 需求解析 -> 用例生成 -> 测试执行 -> 结果分析 -> 可视化展示`

在这个架构中：

- `LaVague` 不再是平台中心
- `LaVague` 被归类为执行测试层中的一个执行适配器
- 平台的核心控制权应放在统一任务编排与测试引擎层

## 2. 新架构总原则

### 2.1 平台优先

仓库应首先表达“这是一个通用自动化测试平台”，而不是“这是若干 LaVague 相关子项目的集合”。

### 2.2 分层清晰

每层只负责一类问题：

- 上层负责理解需求和组织任务
- 中层负责生成统一测试描述
- 下层负责真正执行测试
- 末层负责分析结果和展示

### 2.3 执行能力可插拔

执行层不应只绑定 `LaVague`。未来应允许同时接入：

- 接口功能执行器
- 云端压测执行器
- LaVague Web/UI 执行器

### 2.4 中间协议统一

所有执行器都应消费统一的测试描述协议，而不是各自直接绑定原始需求文档或 Gherkin 文件。

## 3. 目标分层架构

建议将项目规划为五层架构。

### 第一层：接入与任务层

负责统一接收任务与配置。

包含职责：

- 创建测试任务
- 管理项目、环境和目标系统
- 保存任务元数据
- 触发平台主流程

建议模块名：

- `task-center`

### 第二层：需求理解层

负责把自然语言需求、接口文档、业务文档转成结构化需求表示。

包含职责：

- 文档加载
- 文本清洗
- 结构解析
- 检索增强
- 测试点提取

建议模块名：

- `requirement-analysis`

当前仓库映射：

- `analysis-module` 的大部分能力迁移到这里

### 第三层：测试设计层

负责把结构化需求转换成统一测试场景和执行协议。

包含职责：

- 场景拆分
- 前置条件整理
- 断言生成
- 统一 DSL/JSON 生成
- Gherkin 作为派生产物输出

建议模块名：

- `case-generation`

### 第四层：执行引擎层

负责真正执行测试，是平台的运行核心。

包含职责：

- 消费统一测试协议
- 调度不同执行器
- 管理执行状态
- 汇总执行产物

建议模块名：

- `execution-engine`

其下再拆成多个执行适配器：

- `api-runner`
- `cloud-load-runner`
- `lavague-adapter`

这里的核心变化是：

`LaVague` 被明确归入 `lavague-adapter`

也就是说，`LaVague` 只是执行引擎中的一个子模块，负责 Web/UI 自动化执行，不再承担平台架构中心角色。

### 第五层：分析与展示层

负责结果分析、统计和前端展示。

包含职责：

- 执行结果聚合
- 质量评估
- 图表数据生成
- 前端界面展示

建议模块名：

- `result-analysis`
- `platform-ui`

## 4. LaVague 的新定位

### 4.1 定位结论

建议将 `LaVague` 明确定位为：

`执行测试模块中的 Web/UI 自动化执行适配器`

### 4.2 不再承担的职责

重构后，`LaVague` 不应继续承担以下平台级职责：

- 平台总入口
- 需求理解主链路
- 用例生成主链路
- 统一任务编排中心
- 结果分析中心

### 4.3 保留职责

`LaVague` 适合保留的职责如下：

- 浏览器驱动控制
- Web 页面自动操作
- Gherkin 或结构化测试步骤执行
- 页面行为结果回传

### 4.4 论文中的表达方式

在毕业设计语境里，可以把它表述为：

`平台在执行层采用可插拔执行器架构，其中 LaVague 作为 Web/UI 自动化执行适配器，用于完成浏览器侧测试任务。`

## 5. 推荐目录结构

建议后续逐步收敛为如下结构：

```text
LaVague-main/
  docs/
    project_requirements.md
    architecture_replan.md
    dsl_spec.md
  platform/
    task-center/
    requirement-analysis/
    case-generation/
    execution-engine/
      core/
      api-runner/
      cloud-load-runner/
      lavague-adapter/
    result-analysis/
    platform-ui/
    shared/
      schemas/
      models/
      utils/
  legacy/
    lavague-core/
    lavague-gradio/
    lavague-integrations/
    lavague-server/
    lavague-tests/
```

## 6. 当前仓库的迁移建议

### 6.1 `analysis-module`

建议拆分为两部分：

- `requirement-analysis`
- `case-generation`

其中：

- 文档解析、检索增强进入 `requirement-analysis`
- 场景构建、Gherkin 生成进入 `case-generation`

### 6.2 `lavague-qa`

建议整体降级并迁移到：

- `execution-engine/lavague-adapter`

重构后的职责只保留“执行”相关能力。

### 6.3 `lavague-tests`

建议作为执行验证或测试基建能力保留，后续可按需要迁移到：

- `execution-engine/core`
- 或 `platform/tests`

### 6.4 `lavague-core`、`lavague-server`、`lavague-gradio`、`lavague-integrations`

这些目录当前更像历史依赖和能力来源，而不是毕业设计平台的主模块。建议短期先标记为：

- `legacy`

后续按实际依赖逐步抽取可复用部分，而不是把它们直接当成平台骨架。

## 7. 平台核心数据流

建议统一数据流如下：

1. `task-center` 创建任务
2. `requirement-analysis` 输出 `ParsedRequirement`
3. `case-generation` 输出 `TestCaseDSL`
4. `execution-engine` 根据 DSL 选择执行器
5. 各执行器输出统一 `ExecutionResult`
6. `result-analysis` 生成 `AnalysisReport`
7. `platform-ui` 展示任务与结果

建议统一关键对象：

- `TaskContext`
- `ParsedRequirement`
- `TestScenario`
- `TestCaseDSL`
- `ExecutionResult`
- `AnalysisReport`

## 8. Gherkin 的定位调整

重构后不建议让 Gherkin 成为平台唯一中间协议。

更合理的定位是：

- `DSL/JSON` 是执行主协议
- `Gherkin` 是可读性强的展示产物和兼容产物

这样可以避免执行层被 `.feature` 文件结构过度绑定。

## 9. 建议的实施顺序

### 第一阶段：文档先行

- 完成平台总需求文档
- 完成架构重规划文档
- 完成统一 DSL 协议草案

### 第二阶段：目录定型

- 建立新的 `platform/` 目录骨架
- 给各模块建立 README 和边界说明

### 第三阶段：迁移分析链路

- 拆分 `analysis-module`
- 迁移到 `requirement-analysis` 与 `case-generation`

### 第四阶段：迁移执行链路

- 将 `lavague-qa` 收口为 `execution-engine/lavague-adapter`
- 设计统一执行器接口

### 第五阶段：补齐平台能力

- 新建 `task-center`
- 新建 `result-analysis`
- 新建 `platform-ui`

## 10. 最终架构结论

这次重规划后，项目的正确中心应是：

`自动化测试平台`

而不是：

`LaVague 生态仓库`

对应地：

- `analysis-module` 是平台前半段能力
- `LaVague` 是执行层能力
- `平台任务流、统一协议、结果分析与展示` 才是整个项目的主骨架

这会让你的项目：

- 更符合开题报告
- 更容易继续拆模块开发
- 更容易在论文中清晰表达系统架构
- 更方便后续增加接口测试、压测和 UI 自动化等不同执行能力
