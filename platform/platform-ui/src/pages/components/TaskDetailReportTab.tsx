import { Alert, Button, Card, Empty, List, Progress, Space, Tag, Typography } from "antd";
import type {
  AnalysisReport,
  ExecutionExplanationPayload,
  RegressionDiffPayload,
  TaskDashboardPayload,
} from "../../types";

const { Text } = Typography;

type ChartDatum = {
  key: string;
  label: string;
  value: number;
};

export function TaskDetailReportTab(props: {
  dashboardLoadError: string | null;
  taskDashboard: TaskDashboardPayload | null;
  toReadableText: (input: unknown) => string;
  onOpenRawData: (title: string, data: unknown) => void;
  explanationsLoading: boolean;
  explanationsError: string | null;
  executionExplanations: ExecutionExplanationPayload | null;
  onLoadExecutionExplanations: () => void;
  regressionLoading: boolean;
  shouldCompareLatest: boolean;
  regressionError: string | null;
  regressionDiff: RegressionDiffPayload | null;
  onLoadRegressionDiff: () => void;
  primaryAnalysisReport: AnalysisReport | null | undefined;
  qualityColor: string;
  onRefreshReportSection: () => void;
  chartItems: ChartDatum[];
  chartMax: number;
  analysisChartData: unknown;
}) {
  const {
    dashboardLoadError,
    taskDashboard,
    toReadableText,
    onOpenRawData,
    explanationsLoading,
    explanationsError,
    executionExplanations,
    onLoadExecutionExplanations,
    regressionLoading,
    shouldCompareLatest,
    regressionError,
    regressionDiff,
    onLoadRegressionDiff,
    primaryAnalysisReport,
    qualityColor,
    onRefreshReportSection,
    chartItems,
    chartMax,
    analysisChartData,
  } = props;

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      {dashboardLoadError ? <Alert type="info" showIcon message={dashboardLoadError} /> : null}
      {taskDashboard ? (
        <Card bordered={false} title="任务摘要">
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            {taskDashboard.task_summary_text ? (
              <Text>{taskDashboard.task_summary_text}</Text>
            ) : (
              <Text type="secondary">暂无任务摘要</Text>
            )}
            {taskDashboard.failure_reasons?.length ? (
              <Space wrap>
                {taskDashboard.failure_reasons.slice(0, 6).map((reason, idx) => (
                  <Tag color="volcano" key={`${toReadableText(reason)}_${idx}`}>
                    {toReadableText(reason)}
                  </Tag>
                ))}
              </Space>
            ) : null}
            <Button size="small" onClick={() => onOpenRawData("看板数据 JSON", taskDashboard)}>
              查看原始数据
            </Button>
          </Space>
        </Card>
      ) : null}
      <Card
        bordered={false}
        title="失败归因"
        extra={
          <Button size="small" loading={explanationsLoading} onClick={onLoadExecutionExplanations}>
            刷新
          </Button>
        }
      >
        {explanationsError ? <Alert type="info" showIcon message={explanationsError} /> : null}
        {executionExplanations?.failure_groups?.length ? (
          <List
            size="small"
            dataSource={executionExplanations.failure_groups}
            renderItem={(group) => (
              <List.Item>
                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                  <Space>
                    <Tag color="error">{group.category}</Tag>
                    <Text type="secondary">数量：{group.count}</Text>
                  </Space>
                  {group.recommended_actions?.length ? (
                    <Text>{group.recommended_actions.join("；")}</Text>
                  ) : (
                    <Text type="secondary">暂无建议动作</Text>
                  )}
                </Space>
              </List.Item>
            )}
          />
        ) : (
          <Text type="secondary">暂无失败归因数据</Text>
        )}
      </Card>
      <Card
        bordered={false}
        title="回归对比"
        extra={
          <Button size="small" loading={regressionLoading} onClick={onLoadRegressionDiff}>
            拉取对比
          </Button>
        }
      >
        {shouldCompareLatest ? <Alert type="info" showIcon message="已启用与最近一次执行结果自动对比" /> : null}
        {regressionError ? <Alert type="info" showIcon message={regressionError} /> : null}
        {regressionDiff ? (
          <Space direction="vertical" size={8}>
            <Space>
              <Text>结论</Text>
              <Tag
                color={
                  regressionDiff.verdict === "improved"
                    ? "success"
                    : regressionDiff.verdict === "regressed"
                      ? "error"
                      : "default"
                }
              >
                {regressionDiff.verdict || "unknown"}
              </Tag>
            </Space>
            <Button size="small" onClick={() => onOpenRawData("回归对比 JSON", regressionDiff)}>
              查看原始数据
            </Button>
          </Space>
        ) : (
          <Text type="secondary">暂无回归对比结果</Text>
        )}
      </Card>
      <Card bordered={false} title="分析报告" extra={<Button size="small" onClick={onRefreshReportSection}>刷新</Button>}>
        {primaryAnalysisReport ? (
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            <Space>
              <Text>质量状态</Text>
              <Tag color={qualityColor}>{primaryAnalysisReport.quality_status}</Tag>
            </Space>
            <Text>任务：{primaryAnalysisReport.task_name}</Text>
            <Button size="small" onClick={() => onOpenRawData("分析报告 JSON", primaryAnalysisReport)}>
              查看原始数据
            </Button>
          </Space>
        ) : (
          <Empty description="暂无分析报告" />
        )}
      </Card>

      <Card bordered={false} title="分析图表（chart_data）">
        {chartItems.length ? (
          <Space direction="vertical" size={10} style={{ width: "100%" }}>
            {chartItems.map((item) => (
              <div key={item.key}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <Text>{item.label}</Text>
                  <Text strong>{item.value}</Text>
                </div>
                <Progress percent={Math.round((item.value / chartMax) * 100)} strokeColor="#722ed1" showInfo={false} />
              </div>
            ))}
            <Button size="small" onClick={() => onOpenRawData("chart_data JSON", analysisChartData)}>
              查看原始数据
            </Button>
          </Space>
        ) : (
          <Empty description="chart_data 暂无可视化项" />
        )}
      </Card>
    </Space>
  );
}
