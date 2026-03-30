# Platform Quick Start

## 当前默认主线

当前项目已经切换到新的 `platform/` 架构，建议优先关注以下目录：

- `platform/task-center`
- `platform/requirement-analysis`
- `platform/case-generation`
- `platform/execution-engine`
- `platform/result-analysis`
- `platform/shared`
- `docs/dsl_spec.md`

历史目录主要用于迁移参考和兼容依赖，其中大部分已经归档到：

- `legacy/`

## 快速运行

### 运行新的任务分析主链路

```powershell
python run_platform.py pipeline --task-name demo --requirement-text "用户打开首页后应看到标题和搜索框"
```

### 运行新的任务链路 smoke test

```powershell
python run_platform.py smoke-test
```

### 运行接口执行器 smoke test

```powershell
python run_platform.py api-smoke-test
```

### 运行后端 API 服务

```powershell
python run_platform.py serve-api
```

默认地址：

- `http://127.0.0.1:8001`
- OpenAPI 文档：`http://127.0.0.1:8001/docs`

### 运行 API 服务 smoke test

```powershell
python run_platform.py server-smoke-test
```

### 查看执行引擎公共层帮助

```powershell
python run_platform.py execution-help
```

## 当前架构定位

- `task-center`：统一任务入口和编排
- `requirement-analysis`：需求解析和检索增强
- `case-generation`：测试场景、Gherkin 和 TestCaseDSL 生成
- `execution-engine/core`：执行公共层和 DSL 运行时
- `execution-engine/api-runner`：真实接口自动化执行器
- `execution-engine/lavague-adapter`：LaVague Web/UI 执行适配器
- `result-analysis`：分析报告与质量评估
- `shared/context_bus`：多步骤上下文数据管理

## 建议开发顺序

1. 优先在 `platform/` 下继续开发
2. 优先从 `task-center` 主链路接入新功能
3. 先把接口自动化做扎实，再考虑 UI 自动化扩展
4. 不再把 `lavague-qa` 当作平台中心
