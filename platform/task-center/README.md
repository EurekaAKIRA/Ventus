# task-center

## 模块定位

平台统一入口模块。

## 核心职责

- 创建和管理测试任务
- 维护项目、环境、目标系统等基础配置
- 生成统一 `TaskContext`
- 负责主流程编排入口

## 输入

- 任务名称
- 需求文档或需求文本
- 目标地址或接口配置
- 环境参数

## 输出

- `TaskContext`
- 标准化任务配置

## 后续来源

- 可吸收 `analysis-module` 中与任务输入、产物目录相关的部分能力

## 当前状态

第一批入口编排代码已迁移到：

- `src/task_center/input_handler.py`
- `src/task_center/artifact_manager.py`
- `src/task_center/pipeline.py`
- `src/task_center/cli.py`
- `run_task_center.py`

当前已经可以通过新架构主链路串起：

- `task-center`
- `requirement-analysis`
- `case-generation`

## API 服务

当前已经基于 `docs/frontend_api_list.md` 落地 FastAPI 服务：

- `src/task_center/api.py`
- `src/task_center/api_models.py`
- `src/task_center/registry.py`
- `run_api_server.py`

可直接启动：

```powershell
python run_platform.py serve-api
```

并可通过以下命令做接口回归：

```powershell
python run_platform.py server-smoke-test
```
