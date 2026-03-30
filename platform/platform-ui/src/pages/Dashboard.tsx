import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card,
  Table,
  Typography,
  Space,
  Spin,
  Row,
  Col,
  Progress,
} from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import type { TaskListItem } from "../types";
import { fetchTaskList } from "../api/tasks";
import StatusTag from "../components/StatusTag";
import MetricCard from "../components/MetricCard";

const { Title } = Typography;

export default function Dashboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [tasks, setTasks] = useState<TaskListItem[]>([]);

  useEffect(() => {
    fetchTaskList().then(({ items }) => {
      setTasks(items);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <Spin size="large" style={{ display: "block", marginTop: 120 }} />;
  }

  const total = tasks.length;
  const passed = tasks.filter((t) => t.status === "passed").length;
  const failed = tasks.filter((t) => t.status === "failed").length;
  const running = tasks.filter((t) => t.status === "running").length;
  const passRate = total > 0 ? Math.round((passed / total) * 100) : 0;

  const columns = [
    {
      title: "任务名称",
      dataIndex: "task_name",
      key: "task_name",
      render: (text: string, record: TaskListItem) => (
        <a onClick={() => navigate(`/tasks/${record.task_id}`)}>{text}</a>
      ),
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
  ];

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Title level={4} style={{ margin: 0 }}>
        仪表盘
      </Title>

      <div className="metric-row">
        <MetricCard
          title="任务总数"
          value={total}
          prefix={<FileTextOutlined />}
        />
        <MetricCard
          title="通过"
          value={passed}
          prefix={<CheckCircleOutlined />}
          color="#52c41a"
        />
        <MetricCard
          title="失败"
          value={failed}
          prefix={<CloseCircleOutlined />}
          color="#ff4d4f"
        />
        <MetricCard
          title="执行中"
          value={running}
          prefix={<ThunderboltOutlined />}
          color="#1890ff"
        />
      </div>

      <Row gutter={24}>
        <Col xs={24} lg={16}>
          <Card title="最近任务" bordered={false}>
            <Table
              dataSource={tasks.slice(0, 5)}
              columns={columns}
              rowKey="task_id"
              pagination={false}
              size="middle"
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="通过率" bordered={false}>
            <div
              style={{
                display: "flex",
                justifyContent: "center",
                padding: "20px 0",
              }}
            >
              <Progress
                type="dashboard"
                percent={passRate}
                size={180}
                strokeColor={{
                  "0%": "#4f46e5",
                  "100%": "#52c41a",
                }}
              />
            </div>
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
