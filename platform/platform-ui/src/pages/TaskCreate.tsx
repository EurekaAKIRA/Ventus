import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card,
  Form,
  Input,
  Select,
  Button,
  Upload,
  Typography,
  message,
  Space,
  Row,
  Col,
} from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { createTask } from "../api/tasks";

const { Title } = Typography;
const { TextArea } = Input;
const DEFAULT_TARGET_SYSTEM =
  (import.meta.env.VITE_PLATFORM_API_BASE as string | undefined)?.trim() || "http://127.0.0.1:8001";

export default function TaskCreate() {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const [readingFile, setReadingFile] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string>("");

  const handleSubmit = async (values: Record<string, any>) => {
    const targetSystem = String(values.target_system ?? "").trim();
    try {
      const parsed = new URL(targetSystem);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        message.error("target_system must start with http:// or https://");
        return;
      }
    } catch {
      message.error("target_system is not a valid URL");
      return;
    }

    setSubmitting(true);
    try {
      const result = await createTask({
        task_name: values.task_name,
        source_type: "text",
        requirement_text: values.requirement_text,
        target_system: targetSystem || undefined,
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
      <Card bordered={false} style={{ maxWidth: 960 }}>
        <Form
          form={form}
          layout="vertical"
          initialValues={{ requirement_text: "", environment: "test", target_system: DEFAULT_TARGET_SYSTEM }}
          onFinish={handleSubmit}
        >
          <Form.Item
            name="task_name"
            label="任务名称"
            rules={[{ required: true, message: "请输入任务名称" }]}
          >
            <Input placeholder="例如：用户登录功能测试" />
          </Form.Item>

          <Row gutter={24}>
            <Col xs={24} md={12}>
              <Form.Item
                name="requirement_text"
                label="需求描述"
                rules={[{ required: true, message: "请输入需求描述（或从右侧拖拽导入文件）" }]}
              >
                <TextArea
                  rows={10}
                  placeholder="请输入测试需求描述，例如：用户输入正确账号密码后登录成功并进入个人中心"
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <div style={{ marginTop: 32 }}>
                <Upload.Dragger
                  accept=".md,.txt"
                  multiple={false}
                  showUploadList={false}
                  disabled={readingFile}
                  beforeUpload={async (file) => {
                    try {
                      setReadingFile(true);
                      setUploadedFileName(file.name);
                      const text = await file.text();
                      form.setFieldsValue({ requirement_text: text });
                      message.success(`已导入文件：${file.name}`);
                    } catch (e) {
                      message.error("读取文件失败，请重试");
                    } finally {
                      setReadingFile(false);
                    }
                    // Prevent Upload from actually sending file anywhere.
                    return false;
                  }}
                >
                      <p className="ant-upload-drag-icon">
                        <UploadOutlined />
                      </p>
                  <p style={{ margin: 0, fontSize: 14, color: "#555" }}>
                    {readingFile ? "读取中..." : "将文档拖拽到此处，或点击选择"}
                  </p>
                  <p style={{ margin: "8px 0 0", fontSize: 12, color: "#888" }}>
                    支持 `md/txt`，导入后会自动填充到左侧“需求描述”。
                  </p>
                  {uploadedFileName ? (
                    <p style={{ marginTop: 10, fontSize: 12, color: "#666" }}>
                      当前文件：{uploadedFileName}
                    </p>
                  ) : null}
                </Upload.Dragger>
              </div>
            </Col>
          </Row>

          <Form.Item
            name="target_system"
            label="目标系统地址"
            rules={[
              { required: true, message: "请输入目标系统地址" },
              { type: "url", message: "请输入合法 URL（如 http://127.0.0.1:8001）" },
            ]}
          >
            <Input placeholder="http://127.0.0.1:8001" />
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
