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
import StatusTag from "../components/StatusTag";
import MetricCard from "../components/MetricCard";
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
      const { items } = await fetchTaskList({ keyword: nextKeyword, status: nextStatus || undefined });
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
  }, [keyword, status]);

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
  }, [autoRefresh, refreshSeconds, keyword, status]);

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
      render: (text: string, record: TaskListItem) => <a onClick={() => navigate(`/tasks/${record.task_id}`)}>{text}</a>,
    },
    {
      title: "来源",
      dataIndex: "source_type",
      key: "source_type",
      width: 100,
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
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/tasks/${record.task_id}`)}>
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
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Space direction="vertical" size={2}>
          <Title level={4} style={{ margin: 0 }}>任务列表</Title>
          <Text type="secondary">执行层：用于处理当前进行中的任务（不含已通过与已归档）。</Text>
        </Space>
        <Space>
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
        </Space>
      </div>

      <div className="metric-row">
        <MetricCard title="当前待处理任务" value={summary.total} />
        <MetricCard title="执行中" value={summary.running} color="#1677ff" />
        <MetricCard title="失败" value={summary.failed} color="#ff4d4f" />
        <MetricCard title="待推进" value={summary.pending} color="#d48806" />
      </div>

      <Card bordered={false}>
        <Space style={{ marginBottom: 16, width: "100%", justifyContent: "space-between" }} wrap>
          <Space>
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
          </Space>
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
        </Space>

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
          dataSource={tasks}
          columns={columns}
          rowKey="task_id"
          loading={loading}
          pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
        />
      </Card>
    </Space>
  );
}
