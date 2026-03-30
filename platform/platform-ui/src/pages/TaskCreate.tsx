import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card,
  Form,
  Input,
  Select,
  Button,
  Typography,
  message,
  Space,
} from "antd";
import { createTask } from "../api/tasks";

const { Title } = Typography;
const { TextArea } = Input;

export default function TaskCreate() {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const [sourceType, setSourceType] = useState("text");
  const navigate = useNavigate();

  const handleSubmit = async (values: Record<string, string>) => {
    setSubmitting(true);
    try {
      const result = await createTask({
        task_name: values.task_name,
        source_type: values.source_type,
        requirement_text:
          values.source_type === "text" ? values.requirement_text : undefined,
        source_path:
          values.source_type === "file" ? values.source_path : undefined,
        target_system: values.target_system || undefined,
        environment: values.environment || undefined,
      });
      message.success("任务创建成功");
      navigate(`/tasks/${result.task_id}`);
    } catch {
      message.error("创建失败，请重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <Title level={3}>创建任务</Title>
      <Card bordered={false} style={{ maxWidth: 720 }}>
        <Form
          form={form}
          layout="vertical"
          initialValues={{ source_type: "text", environment: "test" }}
          onFinish={handleSubmit}
        >
          <Form.Item
            name="task_name"
            label="任务名称"
            rules={[{ required: true, message: "请输入任务名称" }]}
          >
            <Input placeholder="例如：用户登录功能测试" />
          </Form.Item>

          <Form.Item
            name="source_type"
            label="需求来源类型"
            rules={[{ required: true }]}
          >
            <Select
              onChange={(v) => setSourceType(v)}
              options={[
                { value: "text", label: "文本输入" },
                { value: "file", label: "文件路径" },
              ]}
            />
          </Form.Item>

          {sourceType === "text" ? (
            <Form.Item
              name="requirement_text"
              label="需求描述"
              rules={[{ required: true, message: "请输入需求描述" }]}
            >
              <TextArea
                rows={6}
                placeholder="请输入测试需求描述，例如：用户输入正确账号密码后登录成功并进入个人中心"
              />
            </Form.Item>
          ) : (
            <Form.Item
              name="source_path"
              label="需求文件路径"
              rules={[{ required: true, message: "请输入文件路径" }]}
            >
              <Input placeholder="/docs/requirement.md" />
            </Form.Item>
          )}

          <Form.Item name="target_system" label="目标系统地址">
            <Input placeholder="http://localhost:8080" />
          </Form.Item>

          <Form.Item name="environment" label="执行环境">
            <Select
              options={[
                { value: "test", label: "测试环境" },
                { value: "staging", label: "预发布环境" },
                { value: "production", label: "生产环境" },
              ]}
            />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={submitting}>
                创建任务
              </Button>
              <Button onClick={() => navigate("/tasks")}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </>
  );
}
