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
  Switch,
} from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { createTask, DEFAULT_REQUIREMENT_RAG_ENABLED } from "../api/tasks";

const { Title } = Typography;
const { TextArea } = Input;
const DEFAULT_TARGET_SYSTEM =
  (import.meta.env.VITE_PLATFORM_API_BASE as string | undefined)?.trim() || "http://127.0.0.1:8001";

function deriveTaskNameFromFileName(fileName: string): string {
  const trimmed = String(fileName || "").trim();
  if (!trimmed) {
    return "";
  }
  const lastDotIndex = trimmed.lastIndexOf(".");
  if (lastDotIndex <= 0) {
    return trimmed;
  }
  return trimmed.slice(0, lastDotIndex).trim();
}

function extractBaseUrlFromRequirementText(text: string): string {
  const content = String(text || "").trim();
  if (!content) {
    return "";
  }

  const labeledPatterns = [
    /(?:base\s*url|baseurl|服务地址|服务域名|接口地址|接口域名|请求地址|环境地址)\s*[:：|]\s*`?(https?:\/\/[^\s)`>"']+)`?/im,
    /^\s*[-*]?\s*(?:默认\s*)?(?:base\s*url|baseurl|服务地址|服务域名|接口地址|接口域名|请求地址|环境地址)\s+`?(https?:\/\/[^\s)`>"']+)`?\s*$/im,
  ];
  for (const pattern of labeledPatterns) {
    const match = content.match(pattern);
    if (match?.[1]) {
      return match[1].replace(/\/+$/, "");
    }
  }

  const absoluteUrls = Array.from(content.matchAll(/https?:\/\/[^\s)`>"']+/gim))
    .map((item) => item[0].replace(/\/+$/, ""))
    .filter(Boolean);
  if (absoluteUrls.length === 1) {
    return absoluteUrls[0];
  }
  return "";
}

function shouldAutoFillTargetSystem(currentValue: string): boolean {
  const normalized = String(currentValue || "").trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return normalized === DEFAULT_TARGET_SYSTEM.trim().toLowerCase();
}

export default function TaskCreate() {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const [readingFile, setReadingFile] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string>("");

  const handleSubmit = async (values: Record<string, any>) => {
    const targetSystem = String(values.target_system ?? "").trim();
    if (targetSystem) {
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
    }

    setSubmitting(true);
    try {
      const normalizedTaskName = String(values.task_name ?? "").trim();
      const sourcePath = uploadedFileName || undefined;
      const result = await createTask({
        task_name: normalizedTaskName,
        source_type: sourcePath ? "file" : "text",
        requirement_text: values.requirement_text,
        source_path: sourcePath,
        target_system: targetSystem || undefined,
        environment: values.environment || undefined,
        rag_enabled: Boolean(values.rag_enabled),
      });
      message.success("任务创建成功");
      navigate(`/tasks/${result.task_id}?from=create`, {
        state: {
          fromCreate: true,
          taskName: result.task_name,
        },
      });
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
          initialValues={{
            requirement_text: "",
            environment: "test",
            target_system: DEFAULT_TARGET_SYSTEM,
            rag_enabled: DEFAULT_REQUIREMENT_RAG_ENABLED,
          }}
          onFinish={handleSubmit}
        >
          <Form.Item
            name="task_name"
            label="任务名称"
            extra="可留空。若已导入文档，系统会默认使用文档文件名作为任务名称。"
          >
            <Input placeholder="例如：用户登录功能测试；留空则自动取文档文件名" />
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
                      const currentTaskName = String(form.getFieldValue("task_name") ?? "").trim();
                      const currentTargetSystem = String(form.getFieldValue("target_system") ?? "").trim();
                      const nextTaskName = currentTaskName || deriveTaskNameFromFileName(file.name);
                      const detectedBaseUrl = extractBaseUrlFromRequirementText(text);
                      const nextValues: Record<string, string> = {
                        requirement_text: text,
                        task_name: nextTaskName,
                      };
                      if (detectedBaseUrl && shouldAutoFillTargetSystem(currentTargetSystem)) {
                        nextValues.target_system = detectedBaseUrl;
                      }
                      form.setFieldsValue(nextValues);
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
                    支持 `md/txt`，导入后会自动填充到左侧“需求描述”，并可用文件名作为默认任务名。
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
            extra="可选。若文档中已写明 Base URL，前端和后端都会优先复用解析结果。"
            rules={[{ type: "url", message: "请输入合法 URL（如 http://127.0.0.1:8001）" }]}
          >
            <Input placeholder="http://127.0.0.1:8001；留空则尝试使用文档中的 Base URL" />
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

          <Form.Item
            name="rag_enabled"
            label="需求解析 RAG"
            valuePropName="checked"
            extra="仅控制是否做向量检索与向量打分；关不影响是否执行 LLM 增强，LLM 仍会收到关键词检索到的片段（与规则解析一致）。"
          >
            <Switch checkedChildren="开" unCheckedChildren="关" />
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
