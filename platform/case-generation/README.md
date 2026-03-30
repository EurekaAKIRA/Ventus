# case-generation

## 模块定位

测试设计子系统，负责将结构化需求转换为统一测试场景和执行协议。

## 核心职责

- 场景拆分
- 前置条件整理
- 断言组织
- 统一 DSL/JSON 生成
- Gherkin 派生产物生成

## 输出对象

- `TestScenario`
- `TestCaseDSL`
- `.feature`

## 迁移来源

- 主要来自 `analysis-module` 的：
  `scenario_builder`
  `gherkin_generator`
  `feature_validator`

## 当前状态

第一批代码已迁移到：

- `src/case_generation/scenario_builder.py`
- `src/case_generation/gherkin_generator.py`
- `src/case_generation/feature_validator.py`

当前仍处于“从旧模块平移到新架构”的早期阶段，后续会继续引入统一 `TestCaseDSL`，并逐步降低对 Gherkin 的中心依赖。
