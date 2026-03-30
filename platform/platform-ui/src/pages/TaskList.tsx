import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  Input,
  Select,
  Button,
  Space,
  Typography,
  Card,
  Popconfirm,
  message,
} from "antd";
import {
  PlusOutlined,
  SearchOutlined,
  DeleteOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import type { TaskListItem } from "../types";
import { fetchTaskList, deleteTask } from "../api/tasks";
import StatusTag from "../components/StatusTag";

const { Title } = Typography;

const statusOptions = [
  { value: "", label: "全部状态" },
  { value: "received", label: "已接收" },
  { value: "parsed", label: "已解析" },
  { value: "scenario_generated", label: "用例已生成" },
  { value: "running", label: "执行中" },
  { value: "passed", label: "通过" },
  { value: "failed", label: "失败" },
];

export default function TaskList() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [tasks, setTasks] = useState<TaskListItem[]>([]);
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("");

  const load = () => {
    setLoading(true);
    fetchTaskList({ keyword, status: status || undefined }).then(
      ({ items }) => {
        setTasks(items);
        setLoading(false);
      },
    );
  };

  useEffect(() => {
    load();
  }, []);

  const handleDelete = async (taskId: string) => {
    await deleteTask(taskId);
    message.success("任务已删除");
    load();
  };

  const columns = [
    {
      title: "任务 ID",
      dataIndex: "task_id",
      key: "task_id",
      width: 200,
      ellipsis: true,
    },
    {
      title: "任务名称",
      dataIndex: "task_name",
      key: "task_name",
      render: (text: string, record: TaskListItem) => (
        <a onClick={() => navigate(`/tasks/${record.task_id}`)}>{text}</a>
      ),
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
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 200,
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: "操作",
      key: "actions",
      width: 140,
      render: (_: unknown, record: TaskListItem) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/tasks/${record.task_id}`)}
          >
            详情
          </Button>
          <Popconfirm
            title="确定删除此任务？"
            onConfirm={() => handleDelete(record.task_id)}
          >
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
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          任务列表
        </Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => navigate("/tasks/create")}
        >
          创建任务
        </Button>
      </div>

      <Card bordered={false}>
        <Space style={{ marginBottom: 16 }}>
          <Input
            placeholder="搜索任务名称或 ID"
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={load}
            style={{ width: 260 }}
            allowClear
          />
          <Select
            value={status}
            options={statusOptions}
            onChange={setStatus}
            style={{ width: 140 }}
          />
          <Button type="primary" onClick={load}>
            查询
          </Button>
        </Space>

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
