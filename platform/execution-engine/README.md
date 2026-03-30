# execution-engine

## 模块定位

平台统一执行引擎，负责消费统一测试协议并调度不同执行器。

## 核心职责

- 解析统一测试描述
- 选择执行器
- 调度执行流程
- 管理执行状态
- 汇总执行结果

## 子模块

- `core/`
  执行器接口、调度逻辑、公共执行模型。
- `api-runner/`
  本地接口功能执行器。
- `cloud-load-runner/`
  云端压测适配器。
- `lavague-adapter/`
  LaVague Web/UI 自动化执行适配器。

## 架构原则

- 不直接消费原始需求文档
- 不把 Gherkin 作为唯一执行协议
- 所有执行器都应对齐统一 `TestCaseDSL`
