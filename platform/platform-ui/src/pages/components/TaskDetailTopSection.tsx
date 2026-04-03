import { Alert, Button, Card, Descriptions, Space, Steps, Tag, Typography } from "antd";
import MetricCard from "../../components/MetricCard";
import StatusTag from "../../components/StatusTag";
import type { ExtendedTaskDetail } from "../hooks/useTaskDetailData";

const { Title, Text } = Typography;

type StepItems = Parameters<typeof Steps>[0]["items"];

export function TaskDetailTopSection(props: {
  detail: ExtendedTaskDetail;
  steps: StepItems;
  displayTaskStatus: string;
  uiExecutionStatus: string;
  hasParsedResult: boolean;
  hasScenarios: boolean;
  preflightBlocking: boolean;
  refreshing: boolean;
  showTopOverview: boolean;
  executing: boolean;
  stopping: boolean;
  preflightLoading: boolean;
  canExecute: boolean;
  isTargetSystemValid: boolean;
  onToggleOverview: () => void;
  onRefresh: () => void;
  onRunExecution: () => void;
  onStopExecution: () => void;
}) {
  const {
    detail,
    steps,
    displayTaskStatus,
    uiExecutionStatus,
    hasParsedResult,
    hasScenarios,
    preflightBlocking,
    refreshing,
    showTopOverview,
    executing,
    stopping,
    preflightLoading,
    canExecute,
    isTargetSystemValid,
    onToggleOverview,
    onRefresh,
    onRunExecution,
    onStopExecution,
  } = props;

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Title level={4} style={{ margin: 0 }}>
          任务详情
        </Title>
        <Space>
          <Button onClick={onToggleOverview}>{showTopOverview ? "收起概览" : "展开概览"}</Button>
          <Button loading={refreshing} disabled={refreshing} onClick={onRefresh}>
            刷新
          </Button>
          <Button type="primary" loading={executing} onClick={onRunExecution} disabled={!canExecute || preflightLoading}>
            启动执行
          </Button>
          <Button
            danger
            loading={stopping}
            onClick={onStopExecution}
            disabled={uiExecutionStatus !== "running" || stopping || executing}
          >
            停止执行
          </Button>
        </Space>
      </div>

      <Card bordered={false} bodyStyle={{ paddingTop: 12, paddingBottom: 12 }}>
        <Space wrap size={[12, 8]}>
          <Text type="secondary">当前状态</Text>
          <StatusTag status={uiExecutionStatus === "running" ? "running" : displayTaskStatus} />
          <Text type="secondary">场景数</Text>
          <Tag color="processing">{detail.scenarios?.length ?? 0}</Tag>
          {!isTargetSystemValid ? <Tag color="warning">target_system 待配置</Tag> : null}
          {preflightBlocking ? <Tag color="error">前置检查阻断</Tag> : null}
        </Space>
      </Card>

      {showTopOverview ? (
        <>
          <Card bordered={false}>
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              <Steps items={steps} size="small" />
              {!isTargetSystemValid ? (
                <Alert
                  type="warning"
                  showIcon
                  message="执行受阻"
                  description="target_system 缺失或不合法，请先配置有效的 http(s) 地址"
                />
              ) : null}
              {preflightBlocking ? (
                <Alert
                  type="error"
                  showIcon
                  message="执行已被前置检查阻断"
                  description="请先处理阻断项后再尝试启动执行"
                />
              ) : null}
            </Space>
          </Card>

          <div className="metric-row">
            <MetricCard title="任务状态" value={uiExecutionStatus === "running" ? "running" : displayTaskStatus} color="#722ed1" />
            <MetricCard title="解析结果" value={hasParsedResult ? "已完成" : "待生成"} color={hasParsedResult ? "#52c41a" : "#d48806"} />
            <MetricCard title="场景数量" value={detail.scenarios?.length ?? 0} color={hasScenarios ? "#52c41a" : "#d48806"} />
            <MetricCard title="执行状态" value={uiExecutionStatus} color={uiExecutionStatus === "failed" ? "#ff4d4f" : "#722ed1"} />
          </div>

          <Card bordered={false}>
            <Descriptions title="任务信息" bordered size="small" column={{ xs: 1, md: 2, lg: 3 }}>
              <Descriptions.Item label="任务名称">{detail.task_context.task_name}</Descriptions.Item>
              <Descriptions.Item label="任务 ID">{detail.task_context.task_id}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <StatusTag status={uiExecutionStatus === "running" ? "running" : displayTaskStatus} />
              </Descriptions.Item>
              <Descriptions.Item label="来源类型">{detail.task_context.source_type}</Descriptions.Item>
              <Descriptions.Item label="创建时间">{new Date(detail.task_context.created_at).toLocaleString()}</Descriptions.Item>
              <Descriptions.Item label="语言">{detail.task_context.language}</Descriptions.Item>
              <Descriptions.Item label="target_system">{detail.target_system || "-"}</Descriptions.Item>
              <Descriptions.Item label="environment">{detail.environment || "-"}</Descriptions.Item>
            </Descriptions>
          </Card>
        </>
      ) : null}
    </>
  );
}
