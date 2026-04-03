import { Alert, Card, Progress, Space, Spin, Steps, Typography } from "antd";
import type { StageKey, StageStatus } from "../hooks/useTaskDetailData";

const { Title, Text } = Typography;

type StageLabels = Record<StageKey, string>;

export function TaskDetailBootLoadingCard(props: {
  fromCreateFlow: boolean;
  stageState: Record<StageKey, StageStatus>;
  stageError: string | null;
  stageLabels: StageLabels;
}) {
  const { fromCreateFlow, stageState, stageError, stageLabels } = props;

  const stageItems = [
    {
      title: stageLabels.basic,
      description: "任务元信息、状态、解析摘要",
      status: stageState.basic,
    },
    {
      title: stageLabels.artifacts,
      description: "DSL / Feature / 报告等产物入口",
      status: stageState.artifacts,
    },
    {
      title: stageLabels.dashboard,
      description: "执行摘要、分析图表、质量指标",
      status: stageState.dashboard,
    },
  ];

  return (
    <Card bordered={false}>
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Space direction="vertical" size={4}>
          <Title level={4} style={{ margin: 0 }}>
            任务详情加载中
          </Title>
          <Text type="secondary">
            {fromCreateFlow ? "任务已创建，正在准备详情数据。" : "正在加载任务详情，请稍候。"}
          </Text>
        </Space>
        <Steps direction="vertical" size="small" items={stageItems as unknown as Parameters<typeof Steps>[0]["items"]} />
        {stageError ? <Alert type="warning" showIcon message={stageError} /> : null}
        <Spin size="small" />
      </Space>
    </Card>
  );
}

export function TaskDetailInitialRefreshingView(props: {
  refreshStageText: string;
  stageError: string | null;
}) {
  const { stageError } = props;

  return (
    <Space
      direction="vertical"
      size={12}
      style={{ width: "100%", minHeight: "45vh", alignItems: "center", justifyContent: "center" }}
    >
      <Spin size="large" />
      {stageError ? <Text type="danger">{stageError}</Text> : null}
    </Space>
  );
}

export function TaskDetailRefreshingBanner(props: {
  refreshStatusText: string;
  refreshProgressPercent: number;
  hasStageError: boolean;
  stageError: string | null;
}) {
  const { refreshStatusText, refreshProgressPercent, hasStageError, stageError } = props;

  return (
    <Card bordered={false}>
      <Space direction="vertical" size={8} style={{ width: "100%" }}>
        <Text strong>{refreshStatusText}</Text>
        <Progress
          percent={refreshProgressPercent}
          showInfo={false}
          size="small"
          status={hasStageError ? "exception" : "active"}
          strokeColor="#722ed1"
        />
        {stageError ? <Text type="danger">{stageError}</Text> : null}
      </Space>
    </Card>
  );
}
