import { Alert, Button, Card, Space, Steps, Tag, Typography } from "antd";
import MetricCard from "../../components/MetricCard";
import StatusTag from "../../components/StatusTag";
import { formatDateTime } from "../../utils/dateFormat";
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
  const parsedBaseUrl = detail.parse_metadata?.detected_base_url || "-";
  const effectiveDslBaseUrl =
    ((detail.test_case_dsl?.metadata as Record<string, any> | undefined)?.execution as Record<string, any> | undefined)?.base_url ||
    "-";
  const activeStatus = uiExecutionStatus === "running" ? "running" : displayTaskStatus;
  const baseUrlReady = parsedBaseUrl !== "-" || effectiveDslBaseUrl !== "-" || Boolean(detail.target_system);
  const overviewItems = [
    { label: "任务 ID", value: detail.task_context.task_id || "-" },
    { label: "来源类型", value: detail.task_context.source_type || "-" },
    { label: "创建时间", value: formatDateTime(detail.task_context.created_at) || "-" },
    { label: "环境", value: detail.environment || "-" },
    { label: "目标系统", value: detail.target_system || "-" },
    { label: "解析 Base URL", value: parsedBaseUrl },
    { label: "执行 Base URL", value: effectiveDslBaseUrl },
    { label: "文档路径", value: detail.task_context.source_path || "-" },
  ];

  return (
    <Space direction="vertical" size={18} style={{ width: "100%" }}>
      <div className="task-detail-hero">
        <div className="task-detail-hero__copy">
          <Text className="page-hero__eyebrow">Task Detail</Text>
          <Title level={3} className="task-detail-hero__title">
            {detail.task_context.task_name || "任务详情"}
          </Title>
          <Space wrap size={[8, 10]} className="task-detail-hero__chips">
            <StatusTag status={activeStatus} />
            <Tag bordered={false} className="status-pill status-pill--neutral">
              {detail.task_context.task_id || "-"}
            </Tag>
            <Tag bordered={false} className="status-pill status-pill--neutral">
              {detail.environment || "default"}
            </Tag>
            {baseUrlReady ? (
              <Tag bordered={false} className="status-pill status-pill--success">
                Base URL 就绪
              </Tag>
            ) : (
              <Tag bordered={false} className="status-pill status-pill--warning">
                Base URL 待补充
              </Tag>
            )}
            {preflightBlocking ? (
              <Tag bordered={false} className="status-pill status-pill--danger">
                前置检查阻断
              </Tag>
            ) : null}
          </Space>
        </div>
        <div className="task-detail-hero__actions">
          <Button onClick={onToggleOverview}>{showTopOverview ? "收起详情" : "展开详情"}</Button>
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
        </div>
      </div>

      <div className="metric-row task-detail-metrics">
        <MetricCard title="当前状态" value={activeStatus} color="#3ecf8e" />
        <MetricCard title="解析状态" value={hasParsedResult ? "已完成" : "待生成"} color={hasParsedResult ? "#3ecf8e" : "#f5b94c"} />
        <MetricCard title="场景数量" value={detail.scenarios?.length ?? 0} color={hasScenarios ? "#4f8cff" : "#8da2b8"} />
        <MetricCard title="执行门槛" value={preflightBlocking ? "阻断" : canExecute ? "可执行" : "待配置"} color={preflightBlocking ? "#ff6b6b" : canExecute ? "#3ecf8e" : "#f5b94c"} />
      </div>

      {showTopOverview ? (
        <div className="task-detail-overview-grid">
          <Card bordered={false} className="panel-card" title="流程进度">
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              <Steps items={steps} size="small" />
              {!isTargetSystemValid ? (
                <Alert
                  type="warning"
                  showIcon
                  message="执行受阻"
                  description={
                    detail.parse_metadata?.detected_base_url
                      ? "前端未检测到显式 target_system，但文档已解析出 Base URL，可直接查看解析结果并执行。"
                      : "target_system 缺失或不合法，且文档中也未解析出 Base URL，请先补充有效的 http(s) 地址。"
                  }
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

          <Card bordered={false} className="panel-card" title="运行上下文">
            <div className="task-detail-meta-grid">
              {overviewItems.map((item) => (
                <div key={item.label} className="task-detail-meta-item">
                  <span className="task-detail-meta-item__label">{item.label}</span>
                  <strong className="task-detail-meta-item__value">{item.value}</strong>
                </div>
              ))}
            </div>
          </Card>
        </div>
      ) : null}
    </Space>
  );
}
