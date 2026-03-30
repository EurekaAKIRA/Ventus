# 前端阶段接口清单

## 1. 文档说明

本文档用于整理毕业设计平台在前端开发阶段最可能需要的接口，便于：

- 前端页面设计时统一数据来源
- 后端后续补充 REST API 时作为参考
- 联调前先完成 mock 数据与页面结构设计

当前仓库中的平台主流程为：

`任务接入 -> 需求解析 -> 用例生成 -> 测试执行 -> 结果分析 -> 前端展示`

接口设计主要依据以下内容：

- `docs/project_requirements.md`
- `platform/platform-ui/README.md`
- `platform/shared/src/platform_shared/models.py`
- `platform/task-center/src/task_center/pipeline.py`

当前代码里已经明确的核心对象包括：

- `TaskContext`
- `ParsedRequirement`
- `ScenarioModel`
- `TestCaseDSL`
- `ExecutionResult`
- `ValidationReport`
- `AnalysisReport`

---

## 2. 前端页面对应模块

建议前端第一阶段页面划分如下：

- 任务创建页
- 任务列表页
- 任务详情页
- 需求解析结果页
- 测试场景/DSL 展示页
- 执行监控页
- 分析报告页
- 历史任务页

---

## 3. 接口清单

## 3.1 任务管理接口

### 1. 创建任务

- 方法：`POST`
- 路径：`/api/tasks`
- 用途：创建一个新的测试任务

请求体建议：

```json
{
  "task_name": "用户登录功能测试",
  "source_type": "text",
  "requirement_text": "用户输入正确账号密码后登录成功并进入个人中心",
  "target_system": "http://localhost:8080",
  "environment": "test"
}
```

返回体建议：

```json
{
  "task_id": "task_20260329_001",
  "task_context": {
    "task_id": "task_20260329_001",
    "task_name": "用户登录功能测试",
    "source_type": "text",
    "source_path": null,
    "created_at": "2026-03-29T10:00:00Z",
    "language": "zh-CN",
    "status": "received",
    "notes": []
  }
}
```

### 2. 获取任务列表

- 方法：`GET`
- 路径：`/api/tasks`
- 用途：任务列表页、历史任务页

查询参数建议：

- `status`
- `keyword`
- `page`
- `page_size`

### 3. 获取任务详情

- 方法：`GET`
- 路径：`/api/tasks/{task_id}`
- 用途：任务详情页基础信息展示

### 4. 删除或归档任务

- 方法：`DELETE`
- 路径：`/api/tasks/{task_id}`
- 用途：删除任务或逻辑归档

---

## 3.2 需求解析接口

### 5. 触发需求解析

- 方法：`POST`
- 路径：`/api/tasks/{task_id}/parse`
- 用途：对任务输入的需求文档执行解析

### 6. 获取结构化需求

- 方法：`GET`
- 路径：`/api/tasks/{task_id}/parsed-requirement`
- 用途：展示需求解析结果

返回字段建议：

- `objective`
- `actors`
- `entities`
- `preconditions`
- `actions`
- `expected_results`
- `constraints`
- `ambiguities`
- `source_chunks`

### 7. 获取检索上下文

- 方法：`GET`
- 路径：`/api/tasks/{task_id}/retrieved-context`
- 用途：展示解析命中的文档片段，便于说明“为什么生成这些测试点”

---

## 3.3 用例生成接口

### 8. 生成测试场景

- 方法：`POST`
- 路径：`/api/tasks/{task_id}/scenarios/generate`
- 用途：根据结构化需求生成测试场景

### 9. 获取测试场景列表

- 方法：`GET`
- 路径：`/api/tasks/{task_id}/scenarios`
- 用途：场景列表、场景详情展示

返回内容建议包含：

- `scenario_id`
- `name`
- `goal`
- `priority`
- `preconditions`
- `steps`
- `assertions`
- `source_chunks`

### 10. 获取 DSL

- 方法：`GET`
- 路径：`/api/tasks/{task_id}/dsl`
- 用途：前端查看统一测试描述 `TestCaseDSL`

### 11. 获取 Gherkin 特性文件

- 方法：`GET`
- 路径：`/api/tasks/{task_id}/feature`
- 用途：展示 `.feature` 文本

---

## 3.4 执行管理接口

### 12. 启动执行

- 方法：`POST`
- 路径：`/api/tasks/{task_id}/execute`
- 用途：启动测试执行

请求体建议：

```json
{
  "execution_mode": "api",
  "environment": "test"
}
```

### 13. 获取执行状态

- 方法：`GET`
- 路径：`/api/tasks/{task_id}/execution`
- 用途：执行监控页获取当前执行进度与结果

建议返回内容：

- `task_id`
- `executor`
- `status`
- `scenario_results`
- `metrics`
- `logs`

### 14. 获取执行日志

- 方法：`GET`
- 路径：`/api/tasks/{task_id}/execution/logs`
- 用途：日志面板实时展示

### 15. 停止执行

- 方法：`POST`
- 路径：`/api/tasks/{task_id}/execution/stop`
- 用途：中止当前执行任务

---

## 3.5 报告与可视化接口

### 16. 获取校验报告

- 方法：`GET`
- 路径：`/api/tasks/{task_id}/validation-report`
- 用途：展示用例校验结果

建议返回内容：

- `feature_name`
- `passed`
- `errors`
- `warnings`
- `metrics`

### 17. 获取分析报告

- 方法：`GET`
- 路径：`/api/tasks/{task_id}/analysis-report`
- 用途：展示分析报告与图表

建议返回内容：

- `task_id`
- `task_name`
- `quality_status`
- `summary`
- `findings`
- `chart_data`

### 18. 获取仪表盘聚合数据

- 方法：`GET`
- 路径：`/api/tasks/{task_id}/dashboard`
- 用途：报告页一次性获取概览、图表和摘要信息

---

## 3.6 产物与历史接口

### 19. 获取任务产物列表

- 方法：`GET`
- 路径：`/api/tasks/{task_id}/artifacts`
- 用途：查看任务生成的文件和中间产物

建议包括：

- 原始需求文本
- 清洗后文本
- 结构化需求
- 场景文件
- DSL 文件
- Gherkin 文件
- 校验报告
- 分析报告

### 20. 获取单个产物内容

- 方法：`GET`
- 路径：`/api/tasks/{task_id}/artifacts/{type}`
- 用途：读取指定产物内容

### 21. 获取历史任务

- 方法：`GET`
- 路径：`/api/history/tasks`
- 用途：历史任务查询、统计、筛选

---

## 4. 前端 MVP 推荐优先级

如果当前目标是尽快把前端页面做出来，建议优先使用以下接口：

### 第一优先级

- `POST /api/tasks`
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `GET /api/tasks/{task_id}/parsed-requirement`
- `GET /api/tasks/{task_id}/scenarios`
- `GET /api/tasks/{task_id}/dsl`
- `GET /api/tasks/{task_id}/analysis-report`

### 第二优先级

- `POST /api/tasks/{task_id}/execute`
- `GET /api/tasks/{task_id}/execution`
- `GET /api/tasks/{task_id}/execution/logs`

### 第三优先级

- `GET /api/tasks/{task_id}/feature`
- `GET /api/tasks/{task_id}/validation-report`
- `GET /api/tasks/{task_id}/artifacts`
- `GET /api/history/tasks`

---

## 5. 建议的前端数据流

页面联调时建议按下面顺序调用：

1. 创建任务：`POST /api/tasks`
2. 获取任务详情：`GET /api/tasks/{task_id}`
3. 获取结构化需求：`GET /api/tasks/{task_id}/parsed-requirement`
4. 获取测试场景：`GET /api/tasks/{task_id}/scenarios`
5. 获取 DSL / Feature：`GET /api/tasks/{task_id}/dsl`、`GET /api/tasks/{task_id}/feature`
6. 启动执行：`POST /api/tasks/{task_id}/execute`
7. 轮询执行状态：`GET /api/tasks/{task_id}/execution`
8. 获取报告：`GET /api/tasks/{task_id}/analysis-report`

---

## 6. 说明

- 当前仓库已具备较清晰的数据模型与流水线产物，但尚未完整实现上述 REST API。
- 因此前端开发阶段可以先按照本文档制作页面、定义 TypeScript 类型和 mock 数据。
- 后续如果需要，可在本文档基础上继续补充 Swagger / OpenAPI 规范。
