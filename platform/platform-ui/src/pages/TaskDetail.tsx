import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  List,
  Row,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import {
  fetchTaskDetail,
  fetchExecution,
  startExecution,
  fetchValidationReport,
  fetchAnalysisReport,
} from "../api/tasks";
import type { TaskDetailPayload } from "../types";
import StatusTag from "../components/StatusTag";
import JsonViewer from "../components/JsonViewer";
import LogPanel from "../components/LogPanel";
import MetricCard from "../components/MetricCard";

const { Title, Text } = Typography;

const artifactTypeLabels: Array<{ key: string; label: string }> = [
  { key: "raw_requirement", label: "原始需求文本" },
  { key: "parsed_requirement", label: "结构化需求" },
  { key: "retrieved_context", label: "检索上下文" },
  { key: "scenarios", label: "测试场景" },
  { key: "dsl", label: "DSL 文件" },
  { key: "feature", label: "Feature 文件" },
  { key: "validation_report", label: "校验报告" },
  { key: "analysis_report", label: "分析报告" },
];

export default function TaskDetail() {
  const { taskId = "" } = useParams();
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<TaskDetailPayload | null>(null);
  const [executing, setExecuting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const payload = await fetchTaskDetail(taskId);
      setDetail(payload);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [taskId]);

  const runExecution = async () => {
    setExecuting(true);
    try {
      await startExecution(taskId, { execution_mode: "api", environment: "test" });
      const [executionResult, validationReport, analysisReport] = await Promise.all([
        fetchExecution(taskId),
        fetchValidationReport(taskId),
        fetchAnalysisReport(taskId),
      ]);
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              execution_result: executionResult,
              validation_report: validationReport,
              analysis_report: analysisReport,
              task_context: { ...prev.task_context, status: executionResult.status },
            }
          : prev,
      );
      message.success("执行已启动并刷新结果");
    } catch {
      message.error("启动执行失败");
    } finally {
      setExecuting(false);
    }
  };

  const qualityColor = useMemo(() => {
    const status = detail?.analysis_report?.quality_status;
    if (status === "passed") return "success";
    if (status === "failed") return "error";
    return "default";
  }, [detail?.analysis_report?.quality_status]);

  if (loading) {
    return <Spin size="large" style={{ display: "block", marginTop: 120 }} />;
  }

  if (!detail) {
    return <Empty description="任务不存在或数据为空" />;
  }

  const { task_context, parsed_requirement, scenarios, test_case_dsl, execution_result } = detail;

  const scenarioPass =
    execution_result?.scenario_results.filter((s) => s.status === "passed").length ?? 0;
  const scenarioFail =
    execution_result?.scenario_results.filter((s) => s.status === "failed").length ?? 0;
  const scenarioTotal = execution_result?.scenario_results.length ?? 0;

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Title level={4} style={{ margin: 0 }}>
          任务详情
        </Title>
        <Space>
          <Button onClick={load}>刷新</Button>
          <Button type="primary" loading={executing} onClick={runExecution}>
            启动执行
          </Button>
        </Space>
      </div>

      <Card bordered={false}>
        <Descriptions title="基本信息" bordered size="small" column={{ xs: 1, md: 2, lg: 3 }}>
          <Descriptions.Item label="任务名称">{task_context.task_name}</Descriptions.Item>
          <Descriptions.Item label="任务 ID">{task_context.task_id}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <StatusTag status={task_context.status} />
          </Descriptions.Item>
          <Descriptions.Item label="来源类型">{task_context.source_type}</Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {new Date(task_context.created_at).toLocaleString()}
          </Descriptions.Item>
          <Descriptions.Item label="语言">{task_context.language}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Tabs
        items={[
          {
            key: "parsed",
            label: "需求解析",
            children: parsed_requirement ? (
              <Row gutter={[16, 16]}>
                <Col span={24}>
                  <Card bordered={false} title="结构化需求">
                    <JsonViewer data={parsed_requirement} />
                  </Card>
                </Col>
                <Col span={24}>
                  <Card bordered={false} title="检索上下文">
                    {detail.retrieved_context?.length ? (
                      <List
                        dataSource={detail.retrieved_context}
                        renderItem={(item) => (
                          <List.Item>
                            <List.Item.Meta
                              title={
                                <Space>
                                  <Tag>{item.chunk_id}</Tag>
                                  <Text>{item.section_title}</Text>
                                  <Text type="secondary">score: {item.score}</Text>
                                </Space>
                              }
                              description={
                                <Space direction="vertical" size={2}>
                                  <Text>{item.content}</Text>
                                  <Text type="secondary">{item.source_file}</Text>
                                </Space>
                              }
                            />
                          </List.Item>
                        )}
                      />
                    ) : (
                      <Empty description="暂无检索上下文" />
                    )}
                  </Card>
                </Col>
              </Row>
            ) : (
              <div className="empty-tab">
                <Empty description="暂无解析结果" />
              </div>
            ),
          },
          {
            key: "scenario",
            label: "测试场景",
            children: scenarios?.length ? (
              <Space direction="vertical" style={{ width: "100%" }}>
                {scenarios.map((scenario) => (
                  <Card
                    key={scenario.scenario_id}
                    className="scenario-card"
                    title={scenario.name}
                    extra={<Tag color="purple">{scenario.priority}</Tag>}
                    bordered={false}
                  >
                    <p>
                      <Text strong>目标：</Text>
                      {scenario.goal}
                    </p>
                    <p>
                      <Text strong>前置条件：</Text>
                      {scenario.preconditions.join("，") || "无"}
                    </p>
                    <div style={{ marginTop: 8 }}>
                      <Text strong>步骤：</Text>
                      <div style={{ marginTop: 6 }}>
                        {scenario.steps.map((step, idx) => (
                          <div key={`${scenario.scenario_id}_${idx}`} className="step-item">
                            <span className="step-keyword">{step.type}</span>
                            <span>{step.text}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </Card>
                ))}
              </Space>
            ) : (
              <div className="empty-tab">
                <Empty description="暂无场景数据" />
              </div>
            ),
          },
          {
            key: "dsl",
            label: "DSL / Feature",
            children: (
              <Space direction="vertical" style={{ width: "100%" }}>
                <Card bordered={false} title="TestCaseDSL">
                  {test_case_dsl ? (
                    <JsonViewer data={test_case_dsl} />
                  ) : (
                    <Empty description="暂无 DSL" />
                  )}
                </Card>
                <Card bordered={false} title="Feature 文本">
                  {detail.feature_text ? (
                    <pre className="feature-text">{detail.feature_text}</pre>
                  ) : (
                    <Empty description="暂无 Feature 文本" />
                  )}
                </Card>
              </Space>
            ),
          },
          {
            key: "execution",
            label: "执行监控",
            children: (
              <Space direction="vertical" style={{ width: "100%" }}>
                <div className="metric-row">
                  <MetricCard title="场景总数" value={scenarioTotal} />
                  <MetricCard title="通过场景" value={scenarioPass} color="#52c41a" />
                  <MetricCard title="失败场景" value={scenarioFail} color="#ff4d4f" />
                  <MetricCard
                    title="执行状态"
                    value={execution_result?.status ?? "未执行"}
                    color="#4f46e5"
                  />
                </div>
                <Card bordered={false} title="执行结果">
                  {execution_result ? (
                    <JsonViewer data={execution_result.scenario_results} />
                  ) : (
                    <Alert type="info" showIcon message="尚未执行，请点击右上角“启动执行”" />
                  )}
                </Card>
                <Card bordered={false} title="执行日志">
                  <LogPanel logs={execution_result?.logs ?? []} />
                </Card>
              </Space>
            ),
          },
          {
            key: "report",
            label: "分析报告",
            children: (
              <Space direction="vertical" style={{ width: "100%" }}>
                <Card bordered={false} title="质量状态">
                  {detail.analysis_report ? (
                    <Space>
                      <Text>当前质量结果：</Text>
                      <Tag color={qualityColor}>{detail.analysis_report.quality_status}</Tag>
                    </Space>
                  ) : (
                    <Empty description="暂无分析报告" />
                  )}
                </Card>
                <Card bordered={false} title="校验报告">
                  {detail.validation_report ? (
                    <JsonViewer data={detail.validation_report} />
                  ) : (
                    <Empty description="暂无校验报告" />
                  )}
                </Card>
                <Card bordered={false} title="分析详情">
                  {detail.analysis_report ? (
                    <JsonViewer data={detail.analysis_report} />
                  ) : (
                    <Empty description="暂无分析报告详情" />
                  )}
                </Card>
              </Space>
            ),
          },
          {
            key: "artifacts",
            label: "产物文件",
            children: (
              <List
                grid={{ gutter: 16, xs: 1, md: 2, lg: 3 }}
                dataSource={artifactTypeLabels}
                renderItem={(item) => (
                  <List.Item>
                    <Card className="artifact-card" bordered={false} title={item.label}>
                      <Text type="secondary">类型：{item.key}</Text>
                    </Card>
                  </List.Item>
                )}
              />
            ),
          },
        ]}
      />
    </Space>
  );
}
