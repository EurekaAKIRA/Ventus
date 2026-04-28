# 论文实验协议：Agent-RAG 通用 API 测试平台

本文定义论文可复现实验方案，用于证明系统在泛用性、覆盖率、实用性和诊断能力上的效果。

## 1. 实验目标

验证平台是否能够从不同 API 文档中自动生成测试场景、执行用例、分析结果，并通过 Agent/RAG 提升解析质量和失败定位效率。

## 2. 测试对象

建议固定 4 类样例：

- RESTful Booker：资源生命周期、鉴权、CRUD。
- JSONPlaceholder：只读集合、顶层数组响应、查询参数。
- Swagger Petstore：多资源、多方法、路径参数。
- 平台自身 task-center API：真实业务链路、项目/任务/执行/报告闭环。

## 3. 指标定义

| 指标 | 含义 |
| --- | --- |
| 接口覆盖率 | 已生成并执行的接口数 / 文档识别接口数 |
| 场景数量 | 生成场景总数，需避免过少和大量重复 |
| 场景重复率 | 相同接口序列或相同目标场景占比 |
| 执行通过率 | passed steps / executed steps |
| 断言强度 | 状态码、结构、字段、业务值断言综合评分 |
| RAG Recall@K | 检索结果是否命中预期知识片段 |
| 失败归因准确率 | 失败分类是否对应真实原因 |
| 修复后提升 | Agent 建议或规则修复前后的通过率/误报率变化 |

## 4. 对比实验

### 实验 A：规则解析 vs RAG 增强

对每份文档分别运行：

1. 关闭 RAG。
2. 开启 RAG keyword 模式。
3. 如果配置 embedding，再开启 vector + rerank 模式。

记录解析出的接口数、场景数、资源依赖完整性、断言强度。

### 实验 B：旧断言策略 vs 响应画像策略

对 JSONPlaceholder、DummyJSON 等响应结构差异明显的接口运行：

1. 记录误断言数量，例如 `json.posts` 误判顶层数组。
2. 使用响应画像与 `assertion_shape_mismatch` 分类后复测。
3. 对比误报率和失败归因清晰度。

### 实验 C：Agent 介入前后

选择有问题的文档或失败任务：

1. 记录初始失败类别。
2. 使用 Agent 输出的文档修复、资源依赖、断言修复建议。
3. 修改后重跑。
4. 对比通过率、失败步骤数、人工定位耗时。

## 5. 一键生成实验证据

执行：

```powershell
python platform/task-center/scripts/run_delivery_acceptance.py
```

同时单独运行 RAG benchmark：

```powershell
python platform/requirement-analysis/scripts/run_rag_benchmark.py
```

输出文件：

- `platform/delivery_reports/delivery_acceptance_*.md`
- `platform/requirement-analysis/benchmark_results/rag_benchmark.md`
- `platform/requirement-analysis/benchmark_results/rag_benchmark_summary.csv`

## 6. 论文表格建议

| 实验对象 | 识别接口数 | 生成场景数 | 执行通过率 | 接口覆盖率 | 断言强度 | 主要失败类别 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| RESTful Booker |  |  |  |  |  |  |
| JSONPlaceholder |  |  |  |  |  |  |
| Petstore |  |  |  |  |  |  |
| Task Center |  |  |  |  |  |  |

| RAG 模式 | Case Count | Recall@K | MRR | 备注 |
| --- | ---: | ---: | ---: | --- |
| keyword |  |  |  | 无需外部 embedding |
| vector_keyword |  |  |  | 需要 embedding 配置 |
| vector_keyword_rerank |  |  |  | 需要 embedding 配置 |

## 7. 结论写法建议

可以强调：

- 平台没有绑定具体业务系统，而是抽象接口契约、资源生命周期、上下文传递、断言与执行反馈。
- RAG 主要提升规范/规则召回能力，而不是替代解析器。
- Agent 主要承担诊断、修复建议和闭环验证编排，使平台从“自动生成用例”提升为“可解释、可迭代的测试助手”。
