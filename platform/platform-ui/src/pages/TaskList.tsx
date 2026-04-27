import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Table,
  Input,
  Select,
  Button,
  Space,
  Typography,
  Card,
  Tag,
  Popconfirm,
  message,
  Progress,
  Segmented,
  Switch,
} from "antd";
import {
  PlusOutlined,
  SearchOutlined,
  DeleteOutlined,
  EyeOutlined,
  ReloadOutlined,
  ExclamationCircleOutlined,
  HistoryOutlined,
} from "@ant-design/icons";
import type { TaskListItem } from "../types";
import { fetchTaskList, deleteTask } from "../api/tasks";
import { useAuth } from "../auth/AuthContext";
import StatusTag from "../components/StatusTag";
import {
  isFailedStatus,
  isPendingStatus,
  isRunningStatus,
  nextActionByTaskStatus,
  normalizeTaskStatus,
  progressByTaskStatus,
} from "../utils/taskFlow";

const { Title, Text } = Typography;

const statusOptions = [
  { value: "", label: "全部状态" },
  { value: "received", label: "已接收" },
  { value: "parsed", label: "已解析" },
  { value: "generated", label: "已生成" },
  { value: "running", label: "执行中" },
  { value: "failed", label: "失败" },
  { value: "stopped", label: "已停止" },
];

type FocusMode = "all" | "focus" | "failed" | "running";

export default function TaskList() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { currentProjectId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [serverTasks, setServerTasks] = useState<TaskListItem[]>([]);
  const [keyword, setKeyword] = useState(searchParams.get("keyword") ?? "");
  const [status, setStatus] = useState(searchParams.get("status") ?? "");
  const [failedReason, setFailedReason] = useState(searchParams.get("failed_reason") ?? "");
  const [focusMode, setFocusMode] = useState<FocusMode>((searchParams.get("focus") as FocusMode) || "focus");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshSeconds, setRefreshSeconds] = useState(3);
  const [refreshCountdown, setRefreshCountdown] = useState(3);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string>("");

  const load = async (
    params?: { keyword?: string; status?: string },
    options?: { silent?: boolean },
  ) => {
    if (!options?.silent) {
      setLoading(true);
    }
    try {
      const nextKeyword = params?.keyword ?? keyword;
      const nextStatus = params?.status ?? status;
      const { items } = await fetchTaskList({
        keyword: nextKeyword,
        status: nextStatus || undefined,
        project_id: currentProjectId || undefined,
      });
      setServerTasks(items);
      setLastUpdatedAt(new Date().toISOString());
      setRefreshCountdown(refreshSeconds);
    } catch (error) {
      if (!options?.silent) {
        message.error((error as Error).message || "加载任务列表失败");
      }
    } finally {
      if (!options?.silent) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load({ keyword, status });
    }, 180);
    return () => window.clearTimeout(timer);
  }, [keyword, status, currentProjectId]);

  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (keyword.trim()) next.set("keyword", keyword.trim());
    else next.delete("keyword");
    if (status) next.set("status", status);
    else next.delete("status");
    if (failedReason.trim()) next.set("failed_reason", failedReason.trim());
    else next.delete("failed_reason");
    if (focusMode !== "focus") next.set("focus", focusMode);
    else next.delete("focus");
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true });
    }
  }, [keyword, status, failedReason, focusMode, searchParams, setSearchParams]);

  useEffect(() => {
    if (!autoRefresh) {
      return;
    }
    setRefreshCountdown(refreshSeconds);
    const timer = window.setInterval(() => {
      setRefreshCountdown((prev) => {
        if (prev <= 1) {
          void load({ keyword, status }, { silent: true });
          return refreshSeconds;
        }
        return prev - 1;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, refreshSeconds, keyword, status, currentProjectId]);

  const activeTasks = useMemo(
    () =>
      serverTasks.filter((item) => {
        const s = normalizeTaskStatus(item.status);
        return s !== "passed" && s !== "archived";
      }),
    [serverTasks],
  );

  const failureReasonOptions = useMemo(() => {
    const unique = new Set<string>();
    activeTasks
      .filter((item) => isFailedStatus(item.status))
      .forEach((item) => {
        item.notes.forEach((note) => {
          const value = note.trim();
          if (value) unique.add(value);
        });
      });
    return Array.from(unique).map((value) => ({ value, label: value }));
  }, [activeTasks]);

  const tasks = useMemo(() => {
    let dataset = activeTasks;
    if (focusMode === "failed") {
      dataset = dataset.filter((item) => isFailedStatus(item.status));
    } else if (focusMode === "running") {
      dataset = dataset.filter((item) => isRunningStatus(item.status));
    } else if (focusMode === "focus") {
      dataset = dataset.filter((item) => isFailedStatus(item.status) || isRunningStatus(item.status) || isPendingStatus(item.status));
    }
    if (!failedReason.trim()) return dataset;
    const kw = failedReason.trim().toLowerCase();
    return dataset.filter(
      (item) =>
        isFailedStatus(item.status) &&
        item.notes.some((note) => note.toLowerCase().includes(kw)),
    );
  }, [activeTasks, failedReason, focusMode]);

  const handleDelete = async (taskId: string) => {
    try {
      await deleteTask(taskId);
      message.success("任务已删除");
      await load();
    } catch (error) {
      message.error((error as Error).message || "删除任务失败");
    }
  };

  const summary = useMemo(() => {
    const total = tasks.length;
    const running = tasks.filter((t) => isRunningStatus(t.status)).length;
    const failed = tasks.filter((t) => isFailedStatus(t.status)).length;
    const pending = tasks.filter((t) => isPendingStatus(t.status)).length;
    return { total, running, failed, pending };
  }, [tasks]);

  const statusStats = useMemo(() => {
    const statMap = new Map<string, number>();
    tasks.forEach((item) => {
      const normalized = normalizeTaskStatus(item.status);
      statMap.set(normalized, (statMap.get(normalized) ?? 0) + 1);
    });
    const labels: Record<string, string> = {
      received: "已接收",
      parsed: "已解析",
      generated: "已生成",
      running: "执行中",
      failed: "失败",
      stopped: "已停止",
    };
    return Object.entries(labels)
      .map(([statusKey, label]) => ({ key: statusKey, label, value: statMap.get(statusKey) ?? 0 }))
      .filter((item) => item.value > 0);
  }, [tasks]);

  const columns = [
    {
      title: "任务 ID",
      dataIndex: "task_id",
      key: "task_id",
      width: 220,
      ellipsis: true,
    },
    {
      title: "任务名称",
      dataIndex: "task_name",
      key: "task_name",
      render: (text: string, record: TaskListItem) => (
        <div className="table-primary-cell">
          <a onClick={() => navigate(`/tasks/${encodeURIComponent(record.task_id)}`)}>{text}</a>
          <Text type="secondary" className="table-secondary-text">
            {record.task_id}
          </Text>
        </div>
      ),
    },
    {
      title: "来源",
      dataIndex: "source_type",
      key: "source_type",
      width: 100,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (s: string) => <StatusTag status={s} />,
    },
    {
      title: "进度",
      key: "progress",
      width: 170,
      render: (_: unknown, record: TaskListItem) => {
        const normalized = normalizeTaskStatus(record.status);
        return (
          <Progress
            percent={progressByTaskStatus(record.status)}
            size="small"
            showInfo={false}
            status={normalized === "failed" ? "exception" : normalized === "passed" ? "success" : "active"}
          />
        );
      },
    },
    {
      title: "下一步建议",
      key: "next_action",
      width: 260,
      render: (_: unknown, record: TaskListItem) => <Text type="secondary">{nextActionByTaskStatus(record.status)}</Text>,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 200,
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: "操作",
      key: "actions",
      width: 150,
      render: (_: unknown, record: TaskListItem) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/tasks/${encodeURIComponent(record.task_id)}`)}>
            详情
          </Button>
          <Popconfirm title="确定删除此任务？" onConfirm={() => void handleDelete(record.task_id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <div className="page-hero">
        <div className="page-hero__copy">
          <Title level={3} className="page-hero__title">任务列表</Title>
        </div>
        <div className="page-hero__actions">
          <Segmented<FocusMode>
            value={focusMode}
            onChange={(value) => setFocusMode(value as FocusMode)}
            options={[
              { label: "工作台", value: "focus" },
              { label: "全部", value: "all" },
              { label: "失败", value: "failed" },
              { label: "执行中", value: "running" },
            ]}
          />
          <Space size={4}>
            <Text type="secondary">{autoRefresh ? `${refreshCountdown}s 后自动刷新` : "自动刷新已暂停"}</Text>
            {lastUpdatedAt ? <Text type="secondary">最近更新：{new Date(lastUpdatedAt).toLocaleTimeString()}</Text> : null}
          </Space>
          <Select
            value={refreshSeconds}
            style={{ width: 100 }}
            options={[
              { value: 2, label: "2 秒" },
              { value: 3, label: "3 秒" },
              { value: 5, label: "5 秒" },
            ]}
            onChange={(value) => setRefreshSeconds(Number(value))}
          />
          <Switch checked={autoRefresh} onChange={setAutoRefresh} checkedChildren="自动" unCheckedChildren="手动" />
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              setRefreshCountdown(refreshSeconds);
              void load();
            }}
          >
            刷新
          </Button>
          <Button icon={<HistoryOutlined />} onClick={() => navigate("/tasks/history")}>历史任务</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/tasks/create")}>创建任务</Button>
        </div>
      </div>

      <div className="compact-stats">
        <span className="compact-stats__item">
          <span className="compact-stats__label">待处理</span>
          <strong className="compact-stats__value">{summary.total}</strong>
        </span>
        <span className="compact-stats__item">
          <span className="compact-stats__label">执行中</span>
          <strong className="compact-stats__value">{summary.running}</strong>
        </span>
        <span className="compact-stats__item">
          <span className="compact-stats__label">失败</span>
          <strong className="compact-stats__value">{summary.failed}</strong>
        </span>
        <span className="compact-stats__item">
          <span className="compact-stats__label">待推进</span>
          <strong className="compact-stats__value">{summary.pending}</strong>
        </span>
      </div>

      <Card bordered={false} className="panel-card">
        <div className="page-toolbar">
          <div className="page-toolbar__group">
            <Input
              placeholder="搜索任务名称或 ID"
              prefix={<SearchOutlined />}
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              style={{ width: 260 }}
              allowClear
            />
            <Select value={status} options={statusOptions} onChange={setStatus} style={{ width: 150 }} />
            <Select
              value={failedReason || undefined}
              options={failureReasonOptions}
              onChange={(value) => setFailedReason(value || "")}
              placeholder="失败原因筛选"
              style={{ width: 220 }}
              allowClear
            />
            <Button
              onClick={() => {
                setKeyword("");
                setStatus("");
                setFailedReason("");
                setFocusMode("focus");
              }}
            >
              重置
            </Button>
          </div>
          <div className="page-toolbar__group">
            <span className="surface-chip">
              刷新 <strong>{autoRefresh ? `${refreshCountdown}s` : "暂停"}</strong>
            </span>
            {lastUpdatedAt ? (
              <span className="surface-chip">
                最近更新 <strong>{new Date(lastUpdatedAt).toLocaleTimeString()}</strong>
              </span>
            ) : null}
          </div>
          <Button
            icon={<ExclamationCircleOutlined />}
            danger
            onClick={() => {
              setStatus("failed");
              setFailedReason("");
            }}
          >
            仅看失败任务
          </Button>
        </div>

        {statusStats.length ? (
          <Space wrap style={{ marginBottom: 16 }}>
            <Text type="secondary">状态统计：</Text>
            {statusStats.map((item) => (
              <Tag key={item.key} color={item.key === "failed" ? "error" : item.key === "running" ? "processing" : "default"}>
                {item.label} {item.value}
              </Tag>
            ))}
          </Space>
        ) : null}

        <Table
          className="platform-table"
          dataSource={tasks}
          columns={columns}
          rowKey="task_id"
          loading={loading}
          rowClassName={(record) => {
            if (isFailedStatus(record.status)) return "task-row task-row--failed";
            if (isRunningStatus(record.status)) return "task-row task-row--running";
            if (isPendingStatus(record.status)) return "task-row task-row--pending";
            return "task-row";
          }}
          pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
        />
      </Card>
    </Space>
  );
}
