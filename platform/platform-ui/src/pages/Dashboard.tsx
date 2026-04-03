import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Empty,
  List,
  Row,
  Segmented,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { Dayjs } from "dayjs";
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  FireOutlined,
  ReloadOutlined,
  RightOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import type { ExecutionHistoryItem, HistoryTaskItem, TaskListItem } from "../types";
import { fetchExecutionHistory, fetchHistoryTasks, fetchTaskList } from "../api/tasks";
import StatusTag from "../components/StatusTag";

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;
type TimeFilterMode = "7d" | "30d" | "custom";
type TodoViewMode = "all" | "failed" | "running" | "pending";
type DashboardView = "overview" | "quality" | "risk" | "ops";
type TaskLike = TaskListItem & { finished_at?: string };

function normalizeStatus(status: string): string {
  return status === "scenario_generated" ? "generated" : status;
}

function actionByStatus(status: string): string {
  const normalized = normalizeStatus(status);
  if (normalized === "failed") return "进入详情定位失败原因并重跑";
  if (normalized === "running") return "关注执行日志与超时风险";
  if (normalized === "received") return "尽快触发解析";
  if (normalized === "parsed") return "生成场景并确认 DSL";
  if (normalized === "generated") return "启动执行并观察首轮结果";
  if (normalized === "stopped") return "确认停止原因后决定重跑";
  if (normalized === "passed") return "检查报告后归档";
  return "进入详情确认状态";
}

const statusOrder = ["received", "parsed", "generated", "running", "passed", "failed", "stopped"] as const;
const statusMeta: Record<string, { label: string; color: string }> = {
  received: { label: "已接收", color: "#8c8c8c" },
  parsed: { label: "已解析", color: "#722ed1" },
  generated: { label: "已生成", color: "#13c2c2" },
  running: { label: "执行中", color: "#2f54eb" },
  passed: { label: "通过", color: "#52c41a" },
  failed: { label: "失败", color: "#ff4d4f" },
  stopped: { label: "已停止", color: "#faad14" },
};

function toLocalDateKey(input: string): string {
  const d = new Date(input);
  const year = d.getFullYear();
  const month = `${d.getMonth() + 1}`.padStart(2, "0");
  const day = `${d.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getDateRange(days: number): string[] {
  const result: string[] = [];
  const today = new Date();
  for (let i = days - 1; i >= 0; i -= 1) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    result.push(toLocalDateKey(d.toISOString()));
  }
  return result;
}

function inferFailureReason(item: ExecutionHistoryItem): string {
  const failedSteps = Number(item.analysis_summary?.failed_steps ?? item.metrics?.failed_step_count ?? 0);
  if (failedSteps >= 5) return "失败步骤较多（>=5）";
  if (failedSteps >= 1) return "存在失败步骤（1-4）";
  return "执行失败（无细分原因）";
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [tasks, setTasks] = useState<TaskListItem[]>([]);
  const [historyTasks, setHistoryTasks] = useState<HistoryTaskItem[]>([]);
  const [executionHistory, setExecutionHistory] = useState<ExecutionHistoryItem[]>([]);
  const [trendWindow, setTrendWindow] = useState<7 | 30>(7);
  const [timeFilterMode, setTimeFilterMode] = useState<TimeFilterMode>("7d");
  const [customRange, setCustomRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [todoViewMode, setTodoViewMode] = useState<TodoViewMode>("all");
  const [dashboardView, setDashboardView] = useState<DashboardView>("overview");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshCountdown, setRefreshCountdown] = useState(10);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string>("");

  const openTaskList = (params?: Record<string, string>) => {
    const qp = new URLSearchParams();
    Object.entries(params ?? {}).forEach(([key, value]) => {
      if (value.trim()) qp.set(key, value);
    });
    navigate(`/tasks${qp.toString() ? `?${qp.toString()}` : ""}`);
  };

  const openTaskHistory = (params?: Record<string, string>) => {
    const qp = new URLSearchParams();
    Object.entries(params ?? {}).forEach(([key, value]) => {
      if (value.trim()) qp.set(key, value);
    });
    navigate(`/tasks/history${qp.toString() ? `?${qp.toString()}` : ""}`);
  };

  const openDetailReport = (taskId?: string) => {
    if (!taskId) return;
    navigate(`/tasks/${encodeURIComponent(taskId)}?tab=report&source=dashboard`);
  };

  const resolveTimeRange = () => {
    if (timeFilterMode === "custom" && customRange) {
      return {
        start: customRange[0].startOf("day").toISOString(),
        end: customRange[1].endOf("day").toISOString(),
      };
    }
    const days = timeFilterMode === "30d" ? 30 : 7;
    return {
      start: new Date(Date.now() - (days - 1) * 24 * 60 * 60 * 1000).toISOString(),
      end: new Date().toISOString(),
    };
  };

  const load = async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setLoading(true);
    }
    const { start, end } = resolveTimeRange();
    try {
      const [taskResult, historyTasksResult, historyResult] = await Promise.allSettled([
        fetchTaskList(),
        fetchHistoryTasks({ page: 1, page_size: 200, start_time: start, end_time: end }),
        fetchExecutionHistory({ page: 1, page_size: 200, start_time: start, end_time: end }),
      ]);

      if (taskResult.status === "fulfilled") {
        setTasks(taskResult.value.items);
      } else {
        message.error(taskResult.reason?.message || "加载任务列表失败");
        setTasks([]);
      }

      if (historyTasksResult.status === "fulfilled") {
        setHistoryTasks(historyTasksResult.value.items);
      } else {
        setHistoryTasks([]);
      }

      if (historyResult.status === "fulfilled") {
        const sorted = [...historyResult.value.items].sort(
          (a, b) => new Date(b.executed_at).getTime() - new Date(a.executed_at).getTime(),
        );
        setExecutionHistory(sorted);
      } else {
        message.warning("执行历史暂不可用，趋势分析已降级显示");
        setExecutionHistory([]);
      }
      setLastUpdatedAt(new Date().toISOString());
      setRefreshCountdown(10);
    } finally {
      if (!options?.silent) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    void load();
  }, [timeFilterMode, customRange]);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = window.setInterval(() => {
      setRefreshCountdown((prev) => {
        if (prev <= 1) {
          void load({ silent: true });
          return 10;
        }
        return prev - 1;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, timeFilterMode, customRange]);

  const taskDataset = useMemo<TaskLike[]>(
    () => (historyTasks.length ? (historyTasks as TaskLike[]) : (tasks as TaskLike[])),
    [historyTasks, tasks],
  );

  const stats = useMemo(() => {
    const total = taskDataset.length;
    const passed = taskDataset.filter((t) => normalizeStatus(t.status) === "passed").length;
    const failed = taskDataset.filter((t) => normalizeStatus(t.status) === "failed").length;
    const running = taskDataset.filter((t) => normalizeStatus(t.status) === "running").length;
    const pending = taskDataset.filter((t) => ["received", "parsed", "generated"].includes(normalizeStatus(t.status))).length;
    const passRate = total > 0 ? Math.round((passed / total) * 100) : 0;
    const failRate = total > 0 ? Math.round((failed / total) * 100) : 0;
    const qualityScore = Math.max(0, Math.min(100, Math.round(passRate - failRate * 0.5 + (running > 0 ? -5 : 5))));
    return { total, passed, failed, running, pending, passRate, failRate, qualityScore };
  }, [taskDataset]);

  const statusDistribution = useMemo(() => {
    const counter = new Map<string, number>();
    taskDataset.forEach((task) => {
      const key = normalizeStatus(task.status);
      counter.set(key, (counter.get(key) ?? 0) + 1);
    });
    return statusOrder.map((status) => {
      const count = counter.get(status) ?? 0;
      const percent = stats.total ? (count / stats.total) * 100 : 0;
      return { status, count, percent, ...statusMeta[status] };
    });
  }, [taskDataset, stats.total]);

  const riskReasons = useMemo(() => {
    const reasonCount = new Map<string, number>();
    taskDataset
      .filter((task) => normalizeStatus(task.status) === "failed")
      .forEach((task) => {
        const reasons = task.notes.length ? task.notes : ["未标注失败原因"];
        reasons.forEach((reason) => {
          const key = reason.trim() || "未标注失败原因";
          reasonCount.set(key, (reasonCount.get(key) ?? 0) + 1);
        });
      });
    return Array.from(reasonCount.entries())
      .map(([reason, count]) => ({ reason, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);
  }, [taskDataset]);

  const executionTrend = useMemo(() => {
    const dates = getDateRange(trendWindow);
    const counter = new Map<string, {
      total: number;
      passed: number;
      failed: number;
      running: number;
      latestTaskId?: string;
      latestExecutedAt?: string;
    }>();
    dates.forEach((date) => {
      counter.set(date, { total: 0, passed: 0, failed: 0, running: 0 });
    });

    executionHistory.forEach((item) => {
      const key = toLocalDateKey(item.executed_at);
      const bucket = counter.get(key);
      if (!bucket) return;
      bucket.total += 1;
      const status = normalizeStatus(item.status);
      if (status === "passed") bucket.passed += 1;
      else if (status === "failed") bucket.failed += 1;
      else if (status === "running") bucket.running += 1;
      if (!bucket.latestExecutedAt || new Date(item.executed_at).getTime() > new Date(bucket.latestExecutedAt).getTime()) {
        bucket.latestExecutedAt = item.executed_at;
        bucket.latestTaskId = item.task_id;
      }
    });

    return dates.map((date) => {
      const bucket = counter.get(date) ?? { total: 0, passed: 0, failed: 0, running: 0, latestTaskId: undefined };
      const passRate = bucket.total ? Math.round((bucket.passed / bucket.total) * 100) : 0;
      return { date, ...bucket, passRate };
    });
  }, [executionHistory, trendWindow]);

  const failureTop = useMemo(() => {
    const reasonCount = new Map<string, { count: number; sampleTaskId?: string; latestExecutedAt?: string }>();
    executionHistory
      .filter((item) => normalizeStatus(item.status) === "failed")
      .forEach((item) => {
        const reason = inferFailureReason(item);
        const prev = reasonCount.get(reason) ?? { count: 0, sampleTaskId: undefined, latestExecutedAt: undefined };
        prev.count += 1;
        if (!prev.latestExecutedAt || new Date(item.executed_at).getTime() > new Date(prev.latestExecutedAt).getTime()) {
          prev.latestExecutedAt = item.executed_at;
          prev.sampleTaskId = item.task_id;
        }
        reasonCount.set(reason, prev);
      });
    return Array.from(reasonCount.entries())
      .map(([reason, value]) => ({ reason, count: value.count, sampleTaskId: value.sampleTaskId }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);
  }, [executionHistory]);

  const environmentHealth = useMemo(() => {
    const envMap = new Map<string, { total: number; passed: number; failed: number; sampleTaskId?: string; latestExecutedAt?: string }>();
    executionHistory.forEach((item) => {
      const key = item.environment || "default";
      const row = envMap.get(key) ?? { total: 0, passed: 0, failed: 0, sampleTaskId: undefined, latestExecutedAt: undefined };
      row.total += 1;
      const status = normalizeStatus(item.status);
      if (status === "passed") row.passed += 1;
      if (status === "failed") row.failed += 1;
      if (!row.latestExecutedAt || new Date(item.executed_at).getTime() > new Date(row.latestExecutedAt).getTime()) {
        row.latestExecutedAt = item.executed_at;
        row.sampleTaskId = item.task_id;
      }
      envMap.set(key, row);
    });
    return Array.from(envMap.entries())
      .map(([environment, row]) => {
        const passRate = row.total ? Math.round((row.passed / row.total) * 100) : 0;
        const failRate = row.total ? Math.round((row.failed / row.total) * 100) : 0;
        return { environment, ...row, passRate, failRate };
      })
      .sort((a, b) => b.total - a.total)
      .slice(0, 6);
  }, [executionHistory]);

  const todoTasks = useMemo(
    () =>
      [...tasks]
        .filter((task) => {
          const status = normalizeStatus(task.status);
          if (todoViewMode === "failed") return status === "failed";
          if (todoViewMode === "running") return status === "running";
          if (todoViewMode === "pending") return ["received", "parsed", "generated", "stopped"].includes(status);
          return status === "failed" || status === "running" || ["received", "parsed", "generated", "stopped"].includes(status);
        })
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, 10),
    [tasks, todoViewMode],
  );

  const latestTasks = useMemo(
    () =>
      [...taskDataset]
        .sort((a, b) => {
          const ta = new Date((a.finished_at || a.created_at) as string).getTime();
          const tb = new Date((b.finished_at || b.created_at) as string).getTime();
          return tb - ta;
        })
        .slice(0, 8),
    [taskDataset],
  );

  const trendChart = useMemo(() => {
    const data = executionTrend.slice(-Math.min(executionTrend.length, 14));
    if (!data.length) {
      return { points: "", labels: [] as string[] };
    }
    const maxRate = Math.max(100, ...data.map((d) => d.passRate));
    const w = 100;
    const h = 28;
    const step = data.length > 1 ? w / (data.length - 1) : w;
    const points = data
      .map((d, i) => {
        const x = i * step;
        const y = h - (d.passRate / maxRate) * h;
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");
    return {
      points,
      labels: [data[0]?.date?.slice(5) ?? "", data[data.length - 1]?.date?.slice(5) ?? ""],
    };
  }, [executionTrend]);

  const stackedVolume = useMemo(
    () =>
      executionTrend
        .slice(-Math.min(executionTrend.length, 10))
        .map((item) => {
          const total = Math.max(1, item.total);
          return {
            date: item.date.slice(5),
            passedPct: Math.round((item.passed / total) * 100),
            failedPct: Math.round((item.failed / total) * 100),
            runningPct: Math.round((item.running / total) * 100),
            total: item.total,
          };
        }),
    [executionTrend],
  );

  const taskFunnelCumulative = useMemo(() => {
    const counts = {
      received: taskDataset.length,
      parsed: 0,
      generated: 0,
      running: 0,
      reported: 0,
    };
    taskDataset.forEach((item) => {
      const s = normalizeStatus(item.status);
      if (["parsed", "generated", "running", "passed", "failed", "stopped"].includes(s)) {
        counts.parsed += 1;
      }
      if (["generated", "running", "passed", "failed", "stopped"].includes(s)) {
        counts.generated += 1;
      }
      if (["running", "passed", "failed", "stopped"].includes(s)) {
        counts.running += 1;
      }
      if (s === "passed" || s === "failed" || s === "stopped") {
        counts.reported += 1;
      }
    });
    return [
      { key: "received", label: "接收", value: counts.received, color: "#8c8c8c" },
      { key: "parsed", label: "解析", value: counts.parsed, color: "#722ed1" },
      { key: "generated", label: "生成", value: counts.generated, color: "#13c2c2" },
      { key: "running", label: "执行", value: counts.running, color: "#2f54eb" },
      { key: "reported", label: "报告", value: counts.reported, color: "#52c41a" },
    ];
  }, [taskDataset]);

  const taskFunnelPieRows = useMemo(() => {
    const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);
    const received = Math.max(0, taskFunnelCumulative.find((item) => item.key === "received")?.value ?? 0);
    const parsed = clamp(taskFunnelCumulative.find((item) => item.key === "parsed")?.value ?? 0, 0, received);
    const generated = clamp(taskFunnelCumulative.find((item) => item.key === "generated")?.value ?? 0, 0, parsed);
    const running = clamp(taskFunnelCumulative.find((item) => item.key === "running")?.value ?? 0, 0, generated);
    const reported = clamp(taskFunnelCumulative.find((item) => item.key === "reported")?.value ?? 0, 0, running);

    const exclusive = [
      {
        key: "received",
        label: "接收",
        value: Math.max(0, received - parsed),
        cumulative: received,
        color: "#8c8c8c",
      },
      {
        key: "parsed",
        label: "解析",
        value: Math.max(0, parsed - generated),
        cumulative: parsed,
        color: "#722ed1",
      },
      {
        key: "generated",
        label: "生成",
        value: Math.max(0, generated - running),
        cumulative: generated,
        color: "#13c2c2",
      },
      {
        key: "running",
        label: "执行",
        value: Math.max(0, running - reported),
        cumulative: running,
        color: "#2f54eb",
      },
      {
        key: "reported",
        label: "报告",
        value: reported,
        cumulative: reported,
        color: "#52c41a",
      },
    ];
    const total = exclusive.reduce((sum, row) => sum + row.value, 0);
    return {
      total,
      received,
      rows: exclusive.map((row) => ({
        ...row,
        percent: total ? Math.round((row.value / total) * 100) : 0,
      })),
    };
  }, [taskFunnelCumulative]);

  const taskFunnelPieStyle = useMemo(() => {
    const total = taskFunnelPieRows.total;
    if (!total) {
      return { background: "#f0f0f0", total };
    }
    let offset = 0;
    const segments = taskFunnelPieRows.rows.map((row) => {
      const span = (row.value / total) * 100;
      const start = offset;
      const end = offset + span;
      offset = end;
      return `${row.color} ${start.toFixed(2)}% ${end.toFixed(2)}%`;
    });
    return {
      background: `conic-gradient(${segments.join(", ")})`,
      total,
    };
  }, [taskFunnelPieRows]);

  const todoColumns = [
    {
      title: "任务",
      dataIndex: "task_name",
      key: "task_name",
      render: (text: string, record: TaskListItem) => <a onClick={() => navigate(`/tasks/${record.task_id}`)}>{text}</a>,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 110,
      render: (status: string) => <StatusTag status={status} />,
    },
    {
      title: "建议动作",
      key: "action",
      width: 260,
      render: (_: unknown, record: TaskListItem) => <Text type="secondary">{actionByStatus(record.status)}</Text>,
    },
  ];

  const latestColumns = [
    {
      title: "任务",
      dataIndex: "task_name",
      key: "task_name",
      render: (text: string, record: TaskListItem) => <a onClick={() => navigate(`/tasks/${record.task_id}`)}>{text}</a>,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 110,
      render: (status: string) => <StatusTag status={status} />,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (value: string) => new Date(value).toLocaleString(),
    },
  ];

  if (loading) {
    return <Spin size="large" style={{ display: "block", marginTop: 120 }} />;
  }

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Space direction="vertical" size={2}>
          <Title level={4} style={{ margin: 0 }}>测试运营仪表盘</Title>
          <Text type="secondary">用于快速判断健康度、风险优先级和待办处理顺序</Text>
        </Space>
        <Space wrap>
          <Text type="secondary">{autoRefresh ? `${refreshCountdown}s 后自动刷新` : "自动刷新已暂停"}</Text>
          {lastUpdatedAt ? <Text type="secondary">最近更新：{new Date(lastUpdatedAt).toLocaleTimeString()}</Text> : null}
          <Segmented
            size="small"
            value={timeFilterMode}
            onChange={(value) => setTimeFilterMode(value as TimeFilterMode)}
            options={[
              { label: "近7天", value: "7d" },
              { label: "近30天", value: "30d" },
              { label: "自定义", value: "custom" },
            ]}
          />
          {timeFilterMode === "custom" ? (
            <RangePicker
              size="small"
              value={customRange}
              onChange={(value) => setCustomRange(value as [Dayjs, Dayjs] | null)}
              allowClear
            />
          ) : null}
          <Switch checked={autoRefresh} onChange={setAutoRefresh} checkedChildren="自动" unCheckedChildren="手动" />
          <Button icon={<ReloadOutlined />} onClick={() => void load()}>刷新数据</Button>
          <Button onClick={() => navigate("/tasks?focus=focus")}>进入任务列表</Button>
          <Button onClick={() => navigate("/tasks/history")}>进入历史任务</Button>
        </Space>
      </div>

      <Segmented<DashboardView>
        value={dashboardView}
        onChange={(value) => setDashboardView(value as DashboardView)}
        options={[
          { label: "总览", value: "overview" },
          { label: "质量", value: "quality" },
          { label: "风险", value: "risk" },
          { label: "运营", value: "ops" },
        ]}
      />

      {(dashboardView === "overview" || dashboardView === "quality") ? (
      <Row gutter={16}>
        <Col xs={24} sm={12} lg={6}>
          <Card className="dashboard-kpi-card" bordered={false} hoverable onClick={() => openTaskList({ focus: "all" })}>
            <Space direction="vertical" size={4}>
              <Text type="secondary">任务总数</Text>
              <Text className="dashboard-kpi-value">{stats.total}</Text>
              <Tag icon={<ClockCircleOutlined />} color="default">待处理 {stats.pending}</Tag>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="dashboard-kpi-card" bordered={false} hoverable onClick={() => openTaskHistory({ status: "passed" })}>
            <Space direction="vertical" size={4}>
              <Text type="secondary">通过率</Text>
              <Text className="dashboard-kpi-value success">{stats.passRate}%</Text>
              <Tag icon={<CheckCircleOutlined />} color="success">通过 {stats.passed}</Tag>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="dashboard-kpi-card" bordered={false} hoverable onClick={() => openTaskList({ focus: "failed" })}>
            <Space direction="vertical" size={4}>
              <Text type="secondary">失败率</Text>
              <Text className="dashboard-kpi-value danger">{stats.failRate}%</Text>
              <Tag icon={<CloseCircleOutlined />} color="error">失败 {stats.failed}</Tag>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="dashboard-kpi-card" bordered={false} hoverable onClick={() => openTaskList({ focus: "focus" })}>
            <Space direction="vertical" size={4}>
              <Text type="secondary">健康评分</Text>
              <Text className="dashboard-kpi-value">{stats.qualityScore}</Text>
              <Tag icon={<ThunderboltOutlined />} color={stats.qualityScore >= 70 ? "success" : "warning"}>
                {stats.qualityScore >= 70 ? "整体稳定" : "需重点关注"}
              </Tag>
            </Space>
          </Card>
        </Col>
      </Row>
      ) : null}

      {dashboardView === "overview" ? (
      <Row gutter={16}>
        <Col xs={24} xl={8}>
          <Card title={`质量趋势（近${trendWindow}天）`} bordered={false} className="dashboard-panel-card">
            {trendChart.points ? (
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                <svg viewBox="0 0 100 30" className="dashboard-line-svg" preserveAspectRatio="none">
                      <polyline fill="none" stroke="#722ed1" strokeWidth="2" points={trendChart.points} />
                </svg>
                <div className="dashboard-line-labels">
                  <Text type="secondary">{trendChart.labels[0]}</Text>
                  <Text strong>{stats.passRate}%</Text>
                  <Text type="secondary">{trendChart.labels[1]}</Text>
                </div>
              </Space>
            ) : (
              <Empty description="暂无趋势数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card title="每日执行量（通过/失败/执行中）" bordered={false} className="dashboard-panel-card">
            {stackedVolume.length ? (
              <Space direction="vertical" size={8} className="dashboard-scroll-list" style={{ width: "100%" }}>
                {stackedVolume.map((row) => (
                  <div key={row.date}>
                    <div className="dashboard-volume-head">
                      <Text type="secondary">{row.date}</Text>
                      <Text type="secondary">总量 {row.total}</Text>
                    </div>
                    <div className="dashboard-volume-track">
                      <div className="dashboard-volume-pass" style={{ width: `${row.passedPct}%` }} />
                      <div className="dashboard-volume-fail" style={{ width: `${row.failedPct}%` }} />
                      <div className="dashboard-volume-running" style={{ width: `${row.runningPct}%` }} />
                    </div>
                  </div>
                ))}
              </Space>
            ) : (
              <Empty description="暂无执行量数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card title="任务漏斗" bordered={false} className="dashboard-panel-card">
            <div className="dashboard-funnel-pie-layout">
              <div className="dashboard-funnel-pie-wrap">
                <div className="dashboard-funnel-pie" style={{ background: taskFunnelPieStyle.background }}>
                  <div className="dashboard-funnel-pie-center">
                    <Text type="secondary">总计</Text>
                    <Text strong>{taskFunnelPieRows.received}</Text>
                  </div>
                </div>
              </div>
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                {taskFunnelPieRows.rows.map((row) => (
                  <div key={row.key} className="dashboard-funnel-legend-row">
                    <Space size={8}>
                      <span className="dashboard-funnel-legend-dot" style={{ backgroundColor: row.color }} />
                      <Text>{row.label}</Text>
                    </Space>
                    <Space size={10}>
                      <Text type="secondary">{row.percent}%</Text>
                      <Text strong>{row.value}</Text>
                    </Space>
                  </div>
                ))}
              </Space>
            </div>
          </Card>
        </Col>
      </Row>
      ) : null}

      {(dashboardView === "overview" || dashboardView === "quality") ? (
      <Row gutter={16}>
        <Col xs={24} lg={16}>
          <Card title="任务状态分布" bordered={false} className="dashboard-panel-card">
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <div className="dashboard-status-track">
                {statusDistribution.map((item) => (
                  <div
                    key={item.status}
                    className="dashboard-status-segment"
                    style={{ width: `${item.percent}%`, backgroundColor: item.color }}
                    title={`${item.label}: ${item.count}`}
                  />
                ))}
              </div>
              <Space wrap>
                {statusDistribution.map((item) => (
                  <Tag
                    key={item.status}
                    color={item.status === "failed" ? "error" : item.status === "passed" ? "success" : "default"}
                    style={{ cursor: "pointer" }}
                    onClick={() => {
                      if (item.status === "passed") openTaskHistory({ status: "passed" });
                      else if (item.status === "failed") openTaskList({ focus: "failed", status: "failed" });
                      else if (item.status === "running") openTaskList({ focus: "running", status: "running" });
                      else openTaskList({ focus: "all", status: item.status });
                    }}
                  >
                    {item.label} {item.count}
                  </Tag>
                ))}
              </Space>
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="快速诊断入口" bordered={false} className="dashboard-panel-card">
            <Space direction="vertical" size={10} style={{ width: "100%" }}>
              <Button block danger icon={<ExclamationCircleOutlined />} onClick={() => setDashboardView("risk")}>
                查看风险诊断
              </Button>
              <Button block onClick={() => setDashboardView("ops")}>查看运营工作台</Button>
            </Space>
          </Card>
        </Col>
      </Row>
      ) : null}

      {(dashboardView === "risk") ? (
      <Row gutter={16}>
        <Col xs={24} lg={8}>
          <Card title="风险告警" bordered={false} className="dashboard-panel-card" extra={<FireOutlined style={{ color: "#ff4d4f" }} />}>
            {riskReasons.length ? (
              <List
                size="small"
                className="dashboard-scroll-list"
                dataSource={riskReasons}
                renderItem={(item) => (
                  <List.Item style={{ cursor: "pointer" }} onClick={() => openTaskList({ focus: "failed", failed_reason: item.reason })}>
                    <Space style={{ width: "100%", justifyContent: "space-between" }}>
                      <Text ellipsis={{ tooltip: item.reason }} style={{ maxWidth: 220 }}>{item.reason}</Text>
                      <Tag color="error">{item.count}</Tag>
                    </Space>
                  </List.Item>
                )}
              />
            ) : (
              <Empty description="暂无失败告警" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="失败原因 Top" bordered={false} className="dashboard-panel-card">
            {failureTop.length ? (
              <List
                size="small"
                className="dashboard-scroll-list"
                dataSource={failureTop}
                renderItem={(item, index) => (
                  <List.Item>
                    <Space style={{ width: "100%", justifyContent: "space-between" }}>
                      <Text>{index + 1}. {item.reason}</Text>
                      <Space>
                        <Tag color="volcano">{item.count}</Tag>
                        <Button type="link" size="small" disabled={!item.sampleTaskId} onClick={() => openDetailReport(item.sampleTaskId)}>
                          查看任务
                        </Button>
                        <Button type="link" size="small" onClick={() => openTaskList({ focus: "failed" })}>
                          定位列表
                        </Button>
                      </Space>
                    </Space>
                  </List.Item>
                )}
              />
            ) : (
              <Empty description="暂无失败样本" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="环境稳定性" bordered={false} className="dashboard-panel-card">
            {environmentHealth.length ? (
              <Space direction="vertical" size={10} style={{ width: "100%" }} className="dashboard-scroll-list">
                {environmentHealth.map((item) => (
                  <div key={item.environment} className="dashboard-env-row">
                    <Space style={{ width: "100%", justifyContent: "space-between" }}>
                      <Text strong>{item.environment}</Text>
                      <Space>
                        <Tag color={item.failRate >= 30 ? "error" : item.failRate > 0 ? "warning" : "success"}>
                          失败率 {item.failRate}%
                        </Tag>
                        <Button type="link" size="small" disabled={!item.sampleTaskId} onClick={() => openDetailReport(item.sampleTaskId)}>
                          查看任务
                        </Button>
                        <Button type="link" size="small" onClick={() => openTaskHistory({ status: "failed", environment: item.environment })}>
                          环境失败
                        </Button>
                      </Space>
                    </Space>
                    <Text type="secondary">执行 {item.total} 次，成功 {item.passRate}%</Text>
                  </div>
                ))}
              </Space>
            ) : (
              <Empty description="暂无环境数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
      </Row>
      ) : null}

      {(dashboardView === "quality") ? (
      <Row gutter={16}>
        <Col xs={24} xl={12}>
          <Card
            title="执行趋势"
            bordered={false}
            className="dashboard-panel-card"
            extra={
              <Segmented
                size="small"
                value={trendWindow}
                onChange={(value) => setTrendWindow(value as 7 | 30)}
                options={[
                  { label: "近7天", value: 7 },
                  { label: "近30天", value: 30 },
                ]}
              />
            }
          >
            {executionTrend.some((item) => item.total > 0) ? (
              <Space direction="vertical" size={10} style={{ width: "100%" }}>
                {executionTrend.map((item) => {
                  const failRatio = item.total ? Math.round((item.failed / item.total) * 100) : 0;
                  return (
                    <div key={item.date} className="dashboard-trend-row">
                      <Text type="secondary" className="dashboard-trend-date">{item.date.slice(5)}</Text>
                      <div className="dashboard-trend-track">
                        <div className="dashboard-trend-pass" style={{ width: `${item.passRate}%` }} />
                        <div className="dashboard-trend-fail" style={{ width: `${failRatio}%` }} />
                      </div>
                      <Button
                        type="link"
                        size="small"
                        className="dashboard-trend-meta-btn"
                        disabled={!item.latestTaskId}
                        onClick={() => openDetailReport(item.latestTaskId)}
                      >
                        {item.passed}/{item.total}
                      </Button>
                      <Button
                        type="link"
                        size="small"
                        onClick={() => openTaskHistory({ window: trendWindow === 30 ? "30d" : "7d" })}
                      >
                        进入历史
                      </Button>
                    </div>
                  );
                })}
              </Space>
            ) : (
              <Empty description="暂无执行历史" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title="质量解读" bordered={false} className="dashboard-panel-card">
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Text>近窗口通过率：<Text strong>{stats.passRate}%</Text></Text>
              <Text>近窗口失败率：<Text strong>{stats.failRate}%</Text></Text>
              <Text>执行中任务：<Text strong>{stats.running}</Text></Text>
              <Button onClick={() => setDashboardView("risk")}>切换到风险诊断</Button>
            </Space>
          </Card>
        </Col>
      </Row>
      ) : null}

      {(dashboardView === "ops" || dashboardView === "overview") ? (
      <Row gutter={16}>
        <Col xs={24} xl={16}>
          <Card
            title="待处理任务"
            bordered={false}
            className="dashboard-panel-card"
            extra={
              <Space>
                <Segmented
                  size="small"
                  value={todoViewMode}
                  onChange={(value) => setTodoViewMode(value as TodoViewMode)}
                  options={[
                    { label: "全部", value: "all" },
                    { label: "失败优先", value: "failed" },
                    { label: "执行中", value: "running" },
                    { label: "待推进", value: "pending" },
                  ]}
                />
                <Button type="link" onClick={() => navigate("/tasks?focus=focus")}>查看全部<RightOutlined /></Button>
              </Space>
            }
          >
            {todoTasks.length ? (
              <Table dataSource={todoTasks} columns={todoColumns} rowKey="task_id" pagination={false} size="middle" />
            ) : (
              <Alert type="success" showIcon message="当前无待处理任务" description="失败、执行中和待启动任务会在这里出现。" />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card title="快捷入口" bordered={false} className="dashboard-panel-card">
            <Space direction="vertical" size={10} style={{ width: "100%" }}>
              <Button block onClick={() => navigate("/tasks/create")}>创建任务</Button>
              <Button block onClick={() => openTaskList({ focus: "focus" })}>任务列表</Button>
              <Button block danger icon={<ExclamationCircleOutlined />} onClick={() => openTaskList({ focus: "failed", status: "failed" })}>排查失败任务</Button>
              <Button block type="dashed" onClick={() => navigate("/tasks/history")}>历史任务</Button>
            </Space>
          </Card>
        </Col>
      </Row>
      ) : null}

      {(dashboardView === "ops" || dashboardView === "overview") ? (
      <Card
        title="最近任务动态"
        bordered={false}
        className="dashboard-panel-card"
        extra={<Button type="link" onClick={() => navigate("/tasks")}>查看任务中心<RightOutlined /></Button>}
      >
        <Table dataSource={latestTasks} columns={latestColumns} rowKey="task_id" pagination={false} size="middle" />
      </Card>
      ) : null}
    </Space>
  );
}

