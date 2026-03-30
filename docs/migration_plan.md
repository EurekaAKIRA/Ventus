# 目录迁移清单

## 1. 目标

本文档用于说明当前项目中的历史目录如何逐步迁移到新的 `platform/` 架构下。

## 2. 迁移映射

### `analysis-module`

迁移目标：

- `platform/requirement-analysis/`
- `platform/case-generation/`

拆分建议：

- 文档处理、检索增强、需求解析迁移到 `requirement-analysis`
- 场景生成、Gherkin 生成、校验迁移到 `case-generation`

### `lavague-qa`

迁移目标：

- `platform/execution-engine/lavague-adapter/`

迁移原则：

- 仅保留执行相关能力
- 不再作为平台入口

### `lavague-tests`

迁移目标：

- `platform/execution-engine/core/`
- 或 `platform/` 下统一测试目录

### `lavague-core`

迁移目标：

- 按需抽取到 `platform/execution-engine/lavague-adapter/`
- 未迁移部分先保留原目录

### `lavague-server`

迁移目标：

- 如保留执行服务能力，可抽取到 `platform/execution-engine/core/`

### `lavague-gradio`

迁移目标：

- 后续如仍需要 demo UI，可评估并入 `platform/platform-ui/`

### `lavague-integrations`

迁移目标：

- 后续按需要拆散到各模块适配层，不建议整体照搬

## 3. 推荐顺序

1. 先迁移 `analysis-module`
2. 再迁移 `lavague-qa`
3. 再抽取执行核心公共层
4. 最后处理 UI、server 和 integrations

## 4. 当前已完成

已完成第一批迁移：

- `analysis-module/src/models.py` -> `platform/shared/src/platform_shared/models.py`
- `analysis-module` 中需求解析相关代码 -> `platform/requirement-analysis/src/requirement_analysis/`
- `analysis-module` 中用例生成相关代码 -> `platform/case-generation/src/case_generation/`
- `analysis-module` 中任务入口与编排代码 -> `platform/task-center/src/task_center/`
- `lavague-tests` 中执行公共层代码 -> `platform/execution-engine/core/`
- `lavague-qa` 中 LaVague 执行适配代码 -> `platform/execution-engine/lavague-adapter/`

当前策略为：

- 先复制到新架构并调整依赖
- 在新目录验证可导入和可运行
- 后续再逐步把调用入口切换到 `platform/`

## 5. 旧目录归档状态

当前已归档到 `legacy/` 的目录：

- `analysis-module`
- `lavague-qa`
- `lavague-core`
- `lavague-server`
- `lavague-gradio`
- `lavague-integrations`
- `extension_chrome`
- `lavague-tests`（已复制归档）

当前仍留在根目录、但已经完成职责迁移的目录：

- `lavague-tests`

该目录仅因当前会话中的文件占用尚未完成物理移动。
