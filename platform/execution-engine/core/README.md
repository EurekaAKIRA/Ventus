# execution-engine/core

统一执行引擎核心层。

后续用于放置：

- 执行器抽象接口
- 调度器
- 运行时上下文
- 标准 `ExecutionResult`
- 执行日志模型

## 当前状态

第一批执行公共能力已迁移到：

- `src/execution_engine_core/runner.py`
- `src/execution_engine_core/config.py`
- `src/execution_engine_core/setup.py`
- `src/execution_engine_core/test.py`
- `src/execution_engine_core/cli.py`
- `contexts/`
- `examples/sites/`
- `run_execution_tests.py`

当前仍保留对既有 LaVague 运行库的依赖，但目录归属已经切换到新架构。
