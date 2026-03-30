# 前端页面规划

## 页面 1：任务列表

展示字段建议：

- `task_name`
- `task_id`
- `source_type`
- `status`
- `created_at`

交互建议：

- 搜索
- 状态筛选
- 点击进入详情

---

## 页面 2：创建任务

表单字段建议：

- `task_name`
- `source_type`
- `requirement_text`
- `source_path`
- `target_system`
- `environment`

交互建议：

- 文本输入和文件上传二选一
- 提交后自动跳转到任务详情页

---

## 页面 3：任务详情

### 基本信息区

- 任务名称
- 任务 ID
- 创建时间
- 来源类型
- 当前状态

### Tab 1：需求解析

- 目标 `objective`
- 参与者 `actors`
- 动作 `actions`
- 预期结果 `expected_results`
- 歧义项 `ambiguities`

### Tab 2：测试场景

- 场景列表
- 每个场景的步骤
- 优先级
- 前置条件
- 断言

### Tab 3：DSL / Feature

- JSON DSL
- `.feature` 文本

### Tab 4：执行监控

- 当前执行状态
- 场景执行结果
- 指标
- 日志

### Tab 5：分析报告

- 质量状态
- 统计摘要
- findings
- chart_data

### Tab 6：产物文件

- 原始需求
- 结构化需求
- 检索结果
- DSL
- feature
- validation report
- analysis report
