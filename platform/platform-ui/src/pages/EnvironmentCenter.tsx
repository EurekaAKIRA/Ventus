import { useEffect, useMemo, useState } from "react";
import { Alert, Button, Card, Col, Empty, Form, Input, List, Popconfirm, Row, Space, Table, Tag, Typography, message } from "antd";
import type { EnvironmentPayload, PreflightCheckPayload } from "../types";
import { deleteEnvironment, fetchEnvironments, probeEnvironment, saveEnvironment, updateEnvironment } from "../api/system";
import { MetricGrid, PageHero, PageStack } from "../components/PageLayout";
import { useAuth } from "../auth/AuthContext";

const { Text } = Typography;
const { TextArea } = Input;

type EnvironmentFormValues = {
  name: string;
  base_url?: string;
  description?: string;
  default_headers_text?: string;
  auth_text?: string;
  cookies_text?: string;
};

function parseJsonObject(raw: string, label: string): Record<string, unknown> {
  const normalized = raw.trim();
  if (!normalized) {
    return {};
  }
  const parsed = JSON.parse(normalized) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label} 必须是 JSON 对象`);
  }
  return parsed as Record<string, unknown>;
}

function buildPayload(values: EnvironmentFormValues, projectId?: string): EnvironmentPayload {
  const defaultHeaders = parseJsonObject(String(values.default_headers_text ?? ""), "默认请求头 JSON");
  const auth = parseJsonObject(String(values.auth_text ?? ""), "鉴权 JSON");
  const cookies = parseJsonObject(String(values.cookies_text ?? ""), "Cookies JSON");
  return {
    name: values.name.trim(),
    base_url: String(values.base_url ?? "").trim(),
    description: String(values.description ?? "").trim(),
    default_headers: Object.fromEntries(Object.entries(defaultHeaders).map(([key, value]) => [key, String(value)])),
    auth,
    cookies,
    project_id: projectId || undefined,
  };
}

export default function EnvironmentCenter() {
  const [form] = Form.useForm<EnvironmentFormValues>();
  const { currentProjectId, isAuthenticated, projects } = useAuth();
  const [items, setItems] = useState<EnvironmentPayload[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [probing, setProbing] = useState(false);
  const [editingName, setEditingName] = useState<string>("");
  const [probeResult, setProbeResult] = useState<(PreflightCheckPayload & { environment_name?: string }) | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const payload = await fetchEnvironments(currentProjectId || undefined);
      setItems(payload);
    } catch (error) {
      message.error((error as Error).message || "加载环境失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isAuthenticated) {
      setItems([]);
      return;
    }
    void load();
  }, [currentProjectId, isAuthenticated]);

  const resetEditor = () => {
    setEditingName("");
    setProbeResult(null);
    form.resetFields();
  };

  const handleSave = async (values: EnvironmentFormValues) => {
    setSaving(true);
    try {
      const payload = buildPayload(values, currentProjectId || undefined);
      if (editingName) {
        await updateEnvironment(editingName, payload);
      } else {
        await saveEnvironment(payload);
      }
      resetEditor();
      await load();
      message.success(editingName ? "环境已更新" : "环境已保存");
    } catch (error) {
      message.error((error as Error).message || "保存环境失败");
    } finally {
      setSaving(false);
    }
  };

  const handleProbe = async () => {
    setProbing(true);
    try {
      const values = await form.validateFields();
      const payload = buildPayload(values, currentProjectId || undefined);
      const result = await probeEnvironment(payload);
      setProbeResult(result);
      message.success(result.blocking ? "已完成探测，存在阻断项" : "环境探测通过");
    } catch (error) {
      message.error((error as Error).message || "环境探测失败");
    } finally {
      setProbing(false);
    }
  };

  const handleEdit = (record: EnvironmentPayload) => {
    setEditingName(record.name);
    setProbeResult(null);
    form.setFieldsValue({
      name: record.name,
      base_url: record.base_url ?? "",
      description: record.description ?? "",
      default_headers_text:
        record.default_headers && Object.keys(record.default_headers).length
          ? JSON.stringify(record.default_headers, null, 2)
          : "",
      auth_text: record.auth && Object.keys(record.auth).length ? JSON.stringify(record.auth, null, 2) : "",
      cookies_text: record.cookies && Object.keys(record.cookies).length ? JSON.stringify(record.cookies, null, 2) : "",
    });
  };

  const handleDelete = async (name: string) => {
    try {
      await deleteEnvironment(name, currentProjectId || undefined);
      await load();
      message.success("环境已删除");
    } catch (error) {
      message.error((error as Error).message || "删除环境失败");
    }
  };

  const currentProject = useMemo(
    () => projects.find((project) => project.id === currentProjectId) ?? null,
    [projects, currentProjectId],
  );
  const maskedConfigs = useMemo(
    () => items.filter((item) => item.default_headers_masked || item.auth_masked || item.cookies_masked).length,
    [items],
  );
  const authEnabled = useMemo(
    () => items.filter((item) => item.auth && Object.keys(item.auth).length).length,
    [items],
  );
  const cookieEnabled = useMemo(
    () => items.filter((item) => item.cookies && Object.keys(item.cookies).length).length,
    [items],
  );

  return (
    <PageStack>
      <PageHero
        eyebrow="Environment"
        title="环境管理"
        subtitle="集中维护 Base URL、默认请求头、鉴权与 Cookie，执行前可快速探测连通性。"
        meta={
          <>
          <div className="page-meta-chip">
            <span className="page-meta-chip__label">当前项目</span>
            <span className="page-meta-chip__value">{currentProject?.name || "未选择"}</span>
          </div>
          <div className="page-meta-chip">
            <span className="page-meta-chip__label">环境数量</span>
            <span className="page-meta-chip__value">{items.length}</span>
          </div>
          </>
        }
      />

      <MetricGrid
        items={[
          { title: "环境总数", value: items.length },
          { title: "鉴权已配置", value: authEnabled, color: "#2f81f7" },
          { title: "Cookies 已配置", value: cookieEnabled, color: "#5865f2" },
          { title: "受保护配置", value: maskedConfigs, color: "#f5b94c" },
        ]}
      />

      <Card bordered={false} className="panel-card panel-card--form" title={editingName ? `编辑环境：${editingName}` : "新增环境"}>
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Row gutter={16}>
            <Col xs={24} lg={8}>
              <Form.Item name="name" label="环境名" rules={[{ required: true, message: "请输入环境名" }]}>
                <Input placeholder="例如 staging / qa / prod" disabled={Boolean(editingName)} />
              </Form.Item>
            </Col>
            <Col xs={24} lg={16}>
              <Form.Item name="base_url" label="Base URL" rules={[{ required: true, message: "请输入 Base URL" }]}>
                <Input placeholder="https://api.example.com" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="描述">
            <TextArea rows={3} placeholder="环境说明" />
          </Form.Item>
          <Row gutter={16}>
            <Col xs={24} xl={8}>
              <Form.Item name="default_headers_text" label="默认请求头 JSON">
                <TextArea rows={5} placeholder='{"Authorization":"Bearer demo"}' />
              </Form.Item>
            </Col>
            <Col xs={24} xl={8}>
              <Form.Item name="auth_text" label="鉴权 JSON">
                <TextArea rows={5} placeholder='{"type":"bearer","token":"demo-token"}' />
              </Form.Item>
            </Col>
            <Col xs={24} xl={8}>
              <Form.Item name="cookies_text" label="Cookies JSON">
                <TextArea rows={5} placeholder='{"session":"cookie-value"}' />
              </Form.Item>
            </Col>
          </Row>
          <Space wrap>
            <Button type="primary" htmlType="submit" loading={saving} disabled={!isAuthenticated || !currentProjectId}>
              {editingName ? "更新环境" : "保存环境"}
            </Button>
            <Button onClick={() => void handleProbe()} loading={probing} disabled={!isAuthenticated || !currentProjectId}>
              测试连接
            </Button>
            {editingName ? <Button onClick={resetEditor}>取消编辑</Button> : null}
          </Space>
        </Form>
      </Card>

      {probeResult ? (
        <Card bordered={false} className="panel-card" title={`环境探测结果：${probeResult.environment_name || probeResult.task_id || "当前表单"}`}>
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Space wrap>
              <Text>总体状态</Text>
              <Tag color={probeResult.blocking ? "error" : probeResult.overall_status === "warning" ? "warning" : "success"}>
                {probeResult.overall_status}
              </Tag>
              {probeResult.blocking ? <Text type="danger">存在阻断项</Text> : <Text type="secondary">当前可继续执行</Text>}
            </Space>
            <List
              size="small"
              dataSource={probeResult.checks}
              renderItem={(item) => (
                <List.Item>
                  <Space style={{ width: "100%", justifyContent: "space-between" }}>
                    <div>
                      <Text strong>{item.name}</Text>
                      {item.message ? (
                        <div>
                          <Text type="secondary">{item.message}</Text>
                        </div>
                      ) : null}
                    </div>
                    <Tag color={item.status === "passed" ? "success" : item.status === "warning" ? "warning" : "error"}>
                      {item.status}
                    </Tag>
                  </Space>
                </List.Item>
              )}
            />
            {probeResult.blocking_issues?.length ? (
              <Alert
                type="error"
                showIcon
                message="阻断项"
                description={
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {probeResult.blocking_issues.map((issue, index) => (
                      <li key={`${issue}_${index}`}>{issue}</li>
                    ))}
                  </ul>
                }
              />
            ) : null}
            {probeResult.suggestions?.length ? (
              <Alert
                type="info"
                showIcon
                message="建议项"
                description={
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {probeResult.suggestions.map((item, index) => (
                      <li key={`${item}_${index}`}>{item}</li>
                    ))}
                  </ul>
                }
              />
            ) : null}
          </Space>
        </Card>
      ) : null}

      <Card bordered={false} className="panel-card" title="环境列表">
        <Table
          className="platform-table"
          rowKey="name"
          loading={loading}
          dataSource={items}
          pagination={false}
          locale={{
            emptyText: (
              <div className="table-empty-state">
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前项目还没有环境配置" />
              </div>
            ),
          }}
          columns={[
            { title: "名称", dataIndex: "name", key: "name", width: 160 },
            { title: "Base URL", dataIndex: "base_url", key: "base_url", ellipsis: true },
            {
              title: "配置概览",
              key: "overview",
              width: 220,
              render: (_, record: EnvironmentPayload) => (
                <Space wrap>
                  <Tag>{Object.keys(record.default_headers ?? {}).length} headers</Tag>
                  <Tag color={record.default_headers_masked ? "gold" : "default"}>
                    {record.default_headers_masked ? "protected headers" : "plain headers"}
                  </Tag>
                  <Tag color={record.auth && Object.keys(record.auth).length ? "blue" : "default"}>
                    {record.auth && Object.keys(record.auth).length ? (record.auth_masked ? "auth protected" : "auth") : "no auth"}
                  </Tag>
                  <Tag color={record.cookies && Object.keys(record.cookies).length ? "cyan" : "default"}>
                    {record.cookies && Object.keys(record.cookies).length ? (record.cookies_masked ? "cookies protected" : "cookies") : "no cookies"}
                  </Tag>
                </Space>
              ),
            },
            { title: "描述", dataIndex: "description", key: "description", ellipsis: true },
            {
              title: "操作",
              key: "actions",
              width: 180,
              render: (_, record: EnvironmentPayload) => (
                <Space>
                  <Button type="link" onClick={() => handleEdit(record)}>编辑</Button>
                  <Popconfirm title="确定删除该环境？" onConfirm={() => void handleDelete(record.name)}>
                    <Button type="link" danger>删除</Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </PageStack>
  );
}
