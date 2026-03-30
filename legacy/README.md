# Legacy 目录说明

本目录用于收纳已经完成迁移、或不再作为当前平台主线继续演进的历史目录。

当前已收纳的旧目录包括：

- `analysis-module`
- `lavague-qa`
- `lavague-tests`（已复制归档）
- `lavague-core`
- `lavague-server`
- `lavague-gradio`
- `lavague-integrations`
- `extension_chrome`

这些目录仍可作为：

- 历史实现参考
- 底层兼容依赖来源
- 迁移回溯依据

但当前新的开发主线已经切换到：

- `platform/`
- `run_platform.py`

## 说明

`lavague-tests` 已复制归档到本目录，但根目录中的原目录仍暂时保留，原因是当前会话中文件占用导致无法完成物理移动。其职责已经迁移到：

- `platform/execution-engine/core`
