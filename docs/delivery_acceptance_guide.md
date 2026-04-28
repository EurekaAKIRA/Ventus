# 通用测试平台交付验收指南

本文用于项目交付前的最小验收，目标是证明系统主链路可运行、关键指标可导出、失败原因可定位。

## 1. 验收范围

本轮验收覆盖：

- 需求解析与 RAG 检索基准。
- 场景与 DSL 生成回归。
- API 执行器、断言增强与响应画像。
- task-center 异步执行、执行前检查、失败归因接口。
- 缺陷管理闭环：失败步骤导出、项目权限、缺陷创建/查询/更新。
- 前端生产构建。

不覆盖：

- 第三方公网 API 的实时稳定性。
- 大规模并发压测。
- 生产级密钥轮换与灾备。

## 2. 一键验收

在仓库根目录执行：

```powershell
python platform/task-center/scripts/run_delivery_acceptance.py
```

如只验证后端链路：

```powershell
python platform/task-center/scripts/run_delivery_acceptance.py --skip-frontend
```

脚本会输出：

- `platform/delivery_reports/delivery_acceptance_*.json`
- `platform/delivery_reports/delivery_acceptance_*.md`

这些报告默认不提交到 Git，可作为论文实验或交付验收附件。

## 3. 人工验收流程

1. 启动后端：`python run_api_server.py`。
2. 启动前端：`cd platform/platform-ui && npm run dev`。
3. 使用默认账号登录：`admin / 123456`。
4. 创建任务并上传符合规范的 API 文档。
5. 确认详情页可以看到解析结果、场景、DSL、断言。
6. 执行任务，观察执行页逐步骤状态。
7. 执行失败时导出缺陷，并查看失败归因。
8. 查看报告页的覆盖率、断言强度、失败类别。

## 4. 交付标准

建议以以下条件作为“可交付”门槛：

- 验收脚本全部通过。
- 至少 3 类 API 文档可成功生成 DSL。
- 执行页能展示逐步骤状态与断言。
- 报告能展示接口覆盖率、执行通过率、断言强度。
- 缺陷导出能从失败步骤生成缺陷记录。
- RAG benchmark 至少能在 keyword 模式稳定命中知识规则。

## 5. 常见失败处理

- 前端构建失败：先执行 `cd platform/platform-ui && npm install`。
- RAG vector 模式跳过：没有配置 embedding API key 时属于正常降级。
- task-center 测试失败：检查是否有本地端口占用或数据库环境变量污染。
- 执行任务状态不刷新：确认后端已重启，SSE 事件和前端构建均为最新代码。
