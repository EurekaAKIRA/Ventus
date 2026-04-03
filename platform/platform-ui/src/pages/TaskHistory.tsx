import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card,
  DatePicker,
  Input,
  Select,
  Space,
  Table,
  Typography,
} from "antd";
import type { Dayjs } from "dayjs";
import { SearchOutlined } from "@ant-design/icons";
import type { HistoryTaskItem } from "../types";
import { fetchHistoryTasks } from "../api/tasks";
import StatusTag from "../components/StatusTag";

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const statusOptions = [
  { value: "", label: "全部状态" },
  { value: "passed", label: "通过" },
  { value: "failed", label: "失败" },
  { value: "stopped", label: "已停止" },
  { value: "archived", label: "已归档" },
];

export default function TaskHistory() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [tasks, setTasks] = useState<HistoryTaskItem[]>([]);
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("");
  const [range, setRange] = useState<[Dayjs, Dayjs] | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const payload = await fetchHistoryTasks({
        keyword: keyword.trim() || undefined,
        status: status || undefined,
        start_time: range ? range[0].startOf("day").toISOString() : undefined,
        end_time: range ? range[1].endOf("day").toISOString() : undefined,
        page: 1,
        page_size: 200,
      });
      setTasks(payload.items);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 250);
    return () => window.clearTimeout(timer);
  }, [keyword, status, range]);

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
      render: (text: string, record: HistoryTaskItem) => <a onClick={() => navigate(`/tasks/${record.task_id}?tab=report`)}>{text}</a>,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (value: string) => <StatusTag status={value} />,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 190,
      render: (value: string) => new Date(value).toLocaleString(),
    },
    {
      title: "完成时间",
      dataIndex: "finished_at",
      key: "finished_at",
      width: 190,
      render: (value?: string) => (value ? new Date(value).toLocaleString() : "-"),
    },
    {
      title: "操作",
      key: "actions",
      width: 220,
      render: (_: unknown, record: HistoryTaskItem) => (
        <Space>
          <a onClick={() => navigate(`/tasks/${record.task_id}?tab=report&source=history`)}>查看报告</a>
          <a onClick={() => navigate(`/tasks/${record.task_id}?tab=report&source=history&compare=latest`)}>回归对比</a>
        </Space>
      ),
    },
  ];

  const summary = useMemo(() => {
    const total = tasks.length;
    const passed = tasks.filter((t) => t.status === "passed").length;
    const failed = tasks.filter((t) => t.status === "failed").length;
    return { total, passed, failed };
  }, [tasks]);

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Space direction="vertical" size={2}>
        <Title level={4} style={{ margin: 0 }}>历史任务</Title>
        <Text type="secondary">审计层：用于按时间回溯已完成/归档任务，不承载执行控制。</Text>
      </Space>

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
            <Select value={status} options={statusOptions} onChange={setStatus} style={{ width: 140 }} />
            <RangePicker value={range} onChange={(value) => setRange(value as [Dayjs, Dayjs] | null)} allowClear />
          </Space>
          <Text type="secondary">共 {summary.total} 条，失败 {summary.failed}，通过 {summary.passed}</Text>
        </Space>

        <Table
          dataSource={tasks}
          columns={columns}
          rowKey="task_id"
          loading={loading}
          pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条` }}
        />
      </Card>
    </Space>
  );
}
