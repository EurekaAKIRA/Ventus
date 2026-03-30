# execution-engine/lavague-adapter

## 模块定位

LaVague 在新架构中的唯一归位位置。

## 职责定义

作为 Web/UI 自动化执行适配器，负责：

- 浏览器驱动控制
- 页面导航与交互
- 基于结构化步骤或 Gherkin 的 Web 执行
- 将执行过程转换为平台统一结果

## 不再承担的职责

- 平台总入口
- 需求解析主链路
- 用例生成主链路
- 平台统一编排中心
- 结果分析中心

## 迁移来源

- 主要参考 `lavague-qa`
- 视需要吸收 `lavague-core`、`lavague-server` 等可复用执行能力

## 当前状态

第一批适配器代码已迁移到：

- `src/lavague_adapter/generator.py`
- `src/lavague_adapter/prompts.py`
- `src/lavague_adapter/utils.py`
- `src/lavague_adapter/cli.py`
- `examples/features/`
- `run_lavague_adapter.py`

当前这部分已经在目录层面完成从 `lavague-qa` 到 `execution-engine/lavague-adapter` 的归位。
