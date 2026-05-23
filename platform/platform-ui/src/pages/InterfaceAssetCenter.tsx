import { useEffect, useMemo, useState } from "react";
import { ApiOutlined, CloudDownloadOutlined, DeleteOutlined, EditOutlined, PlayCircleOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, Drawer, Empty, Form, Input, Modal, Row, Select, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { EnvironmentPayload, InterfaceAssetDebugPayload, InterfaceAssetPayload, TaskListItem } from "../types";
import {
  debugInterfaceAsset,
  deleteInterfaceAsset,
  fetchInterfaceAssets,
  importInterfaceAssetsFromOpenApi,
  importInterfaceAssetsFromTask,
  saveInterfaceAsset,
  updateInterfaceAsset,
} from "../api/interfaces";
import { fetchEnvironments } from "../api/system";
import { fetchTaskDetail, fetchTaskList } from "../api/tasks";
import { useAuth } from "../auth/AuthContext";
import JsonViewer from "../components/JsonViewer";
import { MetricGrid, PageHero, PageStack } from "../components/PageLayout";

const { Text } = Typography;

type InterfaceAssetFormValues = {
  method: string;
  path: string;
  name?: string;
  description?: string;
  source?: string;
  status?: string;
  version?: string;
  tags?: string[];
};

type DebugFormValues = {
  environment?: string;
  base_url?: string;
  headers?: string;
  params?: string;
  json_body?: string;
  raw_body?: string;
  timeout?: number;
};

type ExampleFormValues = {
  response_example: string;
};

type OpenApiImportFormValues = {
  source_name?: string;
  version?: string;
  overwrite_examples?: string;
  content: string;
};

type TaskImportHint = {
  environment: string;
  baseUrl: string;
};

const methodOptions = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"].map((value) => ({ value, label: value }));
const statusOptions = [
  { value: "active", label: "启用" },
  { value: "draft", label: "草稿" },
  { value: "deprecated", label: "废弃" },
];

function methodTone(method: string): string {
  const upper = method.toUpperCase();
  if (upper === "GET") return "blue";
  if (upper === "POST") return "green";
  if (upper === "DELETE") return "red";
  if (upper === "PATCH" || upper === "PUT") return "orange";
  return "default";
}

function statusLabel(status: string): string {
  return statusOptions.find((item) => item.value === status)?.label ?? status;
}

function taskExecutionHint(detail: Awaited<ReturnType<typeof fetchTaskDetail>>) {
  const context = detail.task_context as typeof detail.task_context & { environment?: string | null };
  return {
    environment: context.environment || "",
    baseUrl: context.target_system || "",
  };
}

export default function InterfaceAssetCenter() {
  const { currentProjectId } = useAuth();
  const [form] = Form.useForm<InterfaceAssetFormValues>();
  const [items, setItems] = useState<InterfaceAssetPayload[]>([]);
  const [tasks, setTasks] = useState<TaskListItem[]>([]);
  const [environments, setEnvironments] = useState<EnvironmentPayload[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [keyword, setKeyword] = useState("");
  const [method, setMethod] = useState("");
  const [status, setStatus] = useState("active");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<InterfaceAssetPayload | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importTaskHint, setImportTaskHint] = useState<TaskImportHint | null>(null);
  const [openApiForm] = Form.useForm<OpenApiImportFormValues>();
  const [openApiImportOpen, setOpenApiImportOpen] = useState(false);
  const [openApiImporting, setOpenApiImporting] = useState(false);
  const [debugForm] = Form.useForm<DebugFormValues>();
  const [debugOpen, setDebugOpen] = useState(false);
  const [debugging, setDebugging] = useState(false);
  const [debugAsset, setDebugAsset] = useState<InterfaceAssetPayload | null>(null);
  const [debugResult, setDebugResult] = useState<InterfaceAssetDebugPayload | null>(null);
  const [exampleForm] = Form.useForm<ExampleFormValues>();
  const [exampleOpen, setExampleOpen] = useState(false);
  const [exampleAsset, setExampleAsset] = useState<InterfaceAssetPayload | null>(null);
  const [savingExample, setSavingExample] = useState(false);

  const loadAssets = async () => {
    if (!currentProjectId) {
      setItems([]);
      return;
    }
    setLoading(true);
    try {
      const payload = await fetchInterfaceAssets({
        project_id: currentProjectId,
        keyword: keyword.trim() || undefined,
        method: method || undefined,
        status: status || undefined,
        page: 1,
        page_size: 200,
      });
      setItems(payload.items);
    } catch (error) {
      message.error((error as Error).message || "接口资产加载失败");
    } finally {
      setLoading(false);
    }
  };

  const loadTasks = async () => {
    if (!currentProjectId) {
      setTasks([]);
      return;
    }
    try {
      const payload = await fetchTaskList({ project_id: currentProjectId, page: 1, page_size: 100 });
      setTasks(payload.items);
    } catch {
      setTasks([]);
    }
  };

  const loadEnvironments = async () => {
    if (!currentProjectId) {
      setEnvironments([]);
      return;
    }
    try {
      setEnvironments(await fetchEnvironments(currentProjectId));
    } catch {
      setEnvironments([]);
    }
  };

  useEffect(() => {
    void loadAssets();
  }, [currentProjectId, method, status]);

  useEffect(() => {
    void loadTasks();
    void loadEnvironments();
  }, [currentProjectId]);

  useEffect(() => {
    if (!importOpen || !selectedTaskId) {
      setImportTaskHint(null);
      return;
    }
    let cancelled = false;
    void fetchTaskDetail(selectedTaskId, { detailLevel: "summary" })
      .then((detail) => {
        if (cancelled) return;
        setImportTaskHint(taskExecutionHint(detail));
      })
      .catch(() => {
        if (!cancelled) setImportTaskHint(null);
      });
    return () => {
      cancelled = true;
    };
  }, [importOpen, selectedTaskId]);

  const metrics = useMemo(() => {
    const writeCount = items.filter((item) => ["POST", "PUT", "PATCH", "DELETE"].includes(item.method)).length;
    const methods = new Set(items.map((item) => item.method)).size;
    const imported = items.filter((item) => item.source === "task_import").length;
    return { total: items.length, methods, writeCount, imported };
  }, [items]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ method: "GET", status: "active", version: "default", source: "manual" });
    setDrawerOpen(true);
  };

  const openEdit = (record: InterfaceAssetPayload) => {
    setEditing(record);
    form.setFieldsValue({
      method: record.method,
      path: record.path,
      name: record.name,
      description: record.description,
      source: record.source,
      status: record.status,
      version: record.version,
      tags: record.tags,
    });
    setDrawerOpen(true);
  };

  const openTaskImport = () => {
    setSelectedTaskId((prev) => prev || tasks[0]?.task_id || "");
    setImportOpen(true);
  };

  const openDebug = (record: InterfaceAssetPayload) => {
    const firstEnv = environments[0];
    setDebugAsset(record);
    setDebugResult(null);
    debugForm.resetFields();
    debugForm.setFieldsValue({
      environment: firstEnv?.name,
      base_url: firstEnv?.base_url || "",
      headers: "{}",
      params: "{}",
      json_body: record.method === "GET" ? "" : "{}",
      raw_body: "",
      timeout: 15,
    });
    setDebugOpen(true);
    if (record.last_seen_task_id) {
      void fetchTaskDetail(record.last_seen_task_id, { detailLevel: "summary" })
        .then((detail) => {
          const hint = taskExecutionHint(detail);
          const matchedEnv = hint.environment ? environments.find((item) => item.name === hint.environment) : undefined;
          debugForm.setFieldsValue({
            environment: matchedEnv?.name || hint.environment || firstEnv?.name,
            base_url: matchedEnv?.base_url || hint.baseUrl || firstEnv?.base_url || "",
          });
        })
        .catch(() => undefined);
    }
  };

  const openExampleEditor = (record: InterfaceAssetPayload, seed?: unknown) => {
    setExampleAsset(record);
    const value = seed ?? record.response_example ?? { status_code: 200, body: { ok: true } };
    exampleForm.resetFields();
    exampleForm.setFieldsValue({ response_example: JSON.stringify(value, null, 2) });
    setExampleOpen(true);
  };

  const parseObjectField = (label: string, value?: string): Record<string, unknown> => {
    const trimmed = String(value || "").trim();
    if (!trimmed) return {};
    const parsed = JSON.parse(trimmed);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error(`${label} 必须是 JSON 对象`);
    }
    return parsed as Record<string, unknown>;
  };

  const handleDebug = async (values: DebugFormValues) => {
    if (!debugAsset) return;
    setDebugging(true);
    try {
      const headers = parseObjectField("Headers", values.headers);
      const params = parseObjectField("Params", values.params);
      const jsonText = String(values.json_body || "").trim();
      const result = await debugInterfaceAsset(debugAsset.id, {
        project_id: currentProjectId || undefined,
        environment: values.environment,
        base_url: values.base_url,
        headers: headers as Record<string, string>,
        params,
        json_body: jsonText ? JSON.parse(jsonText) : undefined,
        raw_body: values.raw_body,
        timeout: values.timeout ?? 15,
      });
      setDebugResult(result);
    } catch (error) {
      message.error((error as Error).message || "调试失败");
    } finally {
      setDebugging(false);
    }
  };

  const handleSaveExample = async (values: ExampleFormValues) => {
    if (!exampleAsset) return;
    setSavingExample(true);
    try {
      const parsed = JSON.parse(values.response_example || "{}");
      const updated = await updateInterfaceAsset(exampleAsset.id, { response_example: parsed });
      setItems((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      if (debugAsset?.id === updated.id) {
        setDebugAsset(updated);
      }
      message.success("响应示例已保存，Mock 会优先返回该示例");
      setExampleOpen(false);
    } catch (error) {
      message.error((error as Error).message || "保存响应示例失败");
    } finally {
      setSavingExample(false);
    }
  };

  const saveDebugResponseAsExample = () => {
    if (!debugAsset || !debugResult) return;
    const body = debugResult.response.json ?? debugResult.response.body_preview;
    openExampleEditor(debugAsset, {
      status_code: debugResult.response.status_code || 200,
      headers: debugResult.response.headers,
      body,
    });
  };

  const handleSave = async (values: InterfaceAssetFormValues) => {
    if (!currentProjectId) {
      message.warning("请先选择项目");
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        await updateInterfaceAsset(editing.id, {
          name: values.name,
          description: values.description,
          source: values.source,
          status: values.status,
          version: values.version,
          tags: values.tags,
        });
      } else {
        await saveInterfaceAsset({
          project_id: currentProjectId,
          method: values.method,
          path: values.path,
          name: values.name,
          description: values.description,
          source: values.source,
          status: values.status,
          version: values.version,
          tags: values.tags,
        });
      }
      message.success("接口资产已保存");
      setDrawerOpen(false);
      await loadAssets();
    } catch (error) {
      message.error((error as Error).message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (record: InterfaceAssetPayload) => {
    Modal.confirm({
      title: "删除接口资产",
      content: `${record.method} ${record.path}`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        await deleteInterfaceAsset(record.id);
        message.success("接口资产已删除");
        await loadAssets();
      },
    });
  };

  const handleImport = async () => {
    if (!selectedTaskId) {
      message.warning("请选择任务");
      return;
    }
    setImporting(true);
    try {
      const payload = await importInterfaceAssetsFromTask(selectedTaskId, currentProjectId || undefined);
      message.success(`已导入 ${payload.imported_count} 个接口资产`);
      setImportOpen(false);
      await loadAssets();
    } catch (error) {
      message.error((error as Error).message || "导入失败");
    } finally {
      setImporting(false);
    }
  };

  const handleOpenApiImport = async (values: OpenApiImportFormValues) => {
    if (!currentProjectId) {
      message.warning("请先选择项目");
      return;
    }
    setOpenApiImporting(true);
    try {
      const payload = await importInterfaceAssetsFromOpenApi({
        project_id: currentProjectId,
        content: values.content,
        source_name: values.source_name || "openapi",
        version: values.version || "default",
        overwrite_examples: values.overwrite_examples !== "false",
      });
      message.success(`OpenAPI 已导入 ${payload.imported_count} 个接口资产`);
      setOpenApiImportOpen(false);
      await loadAssets();
    } catch (error) {
      message.error((error as Error).message || "OpenAPI 导入失败");
    } finally {
      setOpenApiImporting(false);
    }
  };

  const columns: ColumnsType<InterfaceAssetPayload> = [
    {
      title: "接口",
      dataIndex: "path",
      render: (_, record) => (
        <Space direction="vertical" size={2}>
          <Space>
            <Tag color={methodTone(record.method)}>{record.method}</Tag>
            <Text strong>{record.path}</Text>
          </Space>
          <Text type="secondary">{record.name || "未命名接口"}</Text>
        </Space>
      ),
    },
    {
      title: "来源",
      dataIndex: "source",
      width: 130,
      render: (value: string) => <Tag>{value === "task_import" ? "任务导入" : value || "manual"}</Tag>,
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 110,
      render: (value: string) => <Tag color={value === "active" ? "green" : value === "deprecated" ? "red" : "gold"}>{statusLabel(value)}</Tag>,
    },
    {
      title: "标签",
      dataIndex: "tags",
      width: 220,
      render: (tags: string[]) => (
        <Space size={[4, 4]} wrap>
          {(tags || []).map((tag) => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: "最后任务",
      dataIndex: "last_seen_task_id",
      width: 220,
      render: (value?: string | null) => <Text type="secondary">{value || "-"}</Text>,
    },
    {
      title: "操作",
      width: 150,
      render: (_, record) => (
        <Space>
          <Button icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Button icon={<PlayCircleOutlined />} onClick={() => openDebug(record)} />
          <Button onClick={() => openExampleEditor(record)}>示例</Button>
          <Button danger icon={<DeleteOutlined />} onClick={() => void handleDelete(record)} />
        </Space>
      ),
    },
  ];

  return (
    <PageStack>
      <PageHero
        eyebrow={<><ApiOutlined /> API Inventory</>}
        title="接口资产中心"
        subtitle="沉淀项目接口定义，作为后续调试、Mock、用例资产化的统一数据源。"
        actions={
          <Space wrap>
            <Button icon={<CloudDownloadOutlined />} onClick={openTaskImport} disabled={!currentProjectId}>
              从任务导入
            </Button>
            <Button icon={<CloudDownloadOutlined />} onClick={() => setOpenApiImportOpen(true)} disabled={!currentProjectId}>
              导入 OpenAPI
            </Button>
            <Button icon={<ReloadOutlined />} onClick={() => void loadAssets()}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} disabled={!currentProjectId}>
              新增接口
            </Button>
          </Space>
        }
      />

      <MetricGrid
        items={[
          { title: "接口总数", value: metrics.total },
          { title: "HTTP 方法", value: metrics.methods, color: "#2f81f7" },
          { title: "写接口", value: metrics.writeCount, color: "#f5b94c" },
          { title: "任务导入", value: metrics.imported, color: "#5865f2" },
        ]}
      />

      <Card bordered={false} className="panel-card">
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Row gutter={[12, 12]}>
            <Col xs={24} md={10}>
              <Input.Search
                allowClear
                placeholder="搜索路径、名称、说明"
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                onSearch={() => void loadAssets()}
              />
            </Col>
            <Col xs={12} md={4}>
              <Select allowClear placeholder="方法" value={method || undefined} options={methodOptions} onChange={(value) => setMethod(value || "")} style={{ width: "100%" }} />
            </Col>
            <Col xs={12} md={4}>
              <Select allowClear placeholder="状态" value={status || undefined} options={statusOptions} onChange={(value) => setStatus(value || "")} style={{ width: "100%" }} />
            </Col>
          </Row>
          <Table
            rowKey="id"
            loading={loading}
            className="platform-table"
            columns={columns}
            dataSource={items}
            pagination={{ pageSize: 12 }}
            locale={{ emptyText: <Empty description="暂无接口资产，可从任务导入或手动新增" /> }}
          />
        </Space>
      </Card>

      <Drawer
        title={editing ? "编辑接口资产" : "新增接口资产"}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={560}
        destroyOnClose
        extra={
          <Button type="primary" loading={saving} onClick={() => form.submit()}>
            保存
          </Button>
        }
      >
        <Form form={form} layout="vertical" onFinish={(values) => void handleSave(values)}>
          <Form.Item name="method" label="HTTP 方法" rules={[{ required: true, message: "请选择 HTTP 方法" }]}>
            <Select options={methodOptions} disabled={Boolean(editing)} />
          </Form.Item>
          <Form.Item name="path" label="路径" rules={[{ required: true, message: "请输入接口路径" }]}>
            <Input placeholder="/api/resource/{id}" disabled={Boolean(editing)} />
          </Form.Item>
          <Form.Item name="name" label="接口名称">
            <Input placeholder="例如：查询资源详情" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={4} placeholder="说明接口用途、资源依赖或业务含义" />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select options={statusOptions} />
          </Form.Item>
          <Form.Item name="version" label="版本">
            <Input placeholder="default / v1 / v2" />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select mode="tags" tokenSeparators={[",", "，"]} placeholder="resource、auth、核心链路" />
          </Form.Item>
          <Form.Item name="source" label="来源">
            <Input placeholder="manual / task_import / openapi" />
          </Form.Item>
        </Form>
      </Drawer>

      <Modal
        title="从任务导入接口资产"
        open={importOpen}
        onCancel={() => setImportOpen(false)}
        onOk={() => void handleImport()}
        confirmLoading={importing}
        okText="导入"
        cancelText="取消"
      >
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Text type="secondary">会从任务原始文档和生成 DSL 中提取 `METHOD /path`，按项目、方法、路径去重沉淀。</Text>
          <Select
            showSearch
            placeholder="选择最近任务"
            value={selectedTaskId || undefined}
            onChange={setSelectedTaskId}
            options={tasks.map((task) => ({ value: task.task_id, label: `${task.task_name} · ${task.task_id}` }))}
            style={{ width: "100%" }}
            optionFilterProp="label"
          />
          {selectedTaskId ? (
            <Alert
              type={importTaskHint?.baseUrl || importTaskHint?.environment ? "success" : "warning"}
              showIcon
              message="任务执行配置"
              description={
                importTaskHint?.baseUrl || importTaskHint?.environment
                  ? `环境：${importTaskHint.environment || "未设置"}；Base URL：${importTaskHint.baseUrl || "未设置"}`
                  : "该任务暂未识别到环境或 Base URL，导入后调试时仍可手动选择。"
              }
            />
          ) : null}
        </Space>
      </Modal>

      <Drawer
        title="导入 OpenAPI / Swagger"
        open={openApiImportOpen}
        onClose={() => setOpenApiImportOpen(false)}
        width={760}
        destroyOnClose
        extra={
          <Button type="primary" loading={openApiImporting} onClick={() => openApiForm.submit()}>
            导入
          </Button>
        }
      >
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Alert
            type="info"
            showIcon
            message="支持 OpenAPI 3.x / Swagger 2.0 的 paths 结构"
            description="优先支持 JSON；后端环境安装 PyYAML 时也可导入 YAML。导入后会按项目、方法、路径、版本去重。"
          />
          <Form
            form={openApiForm}
            layout="vertical"
            initialValues={{ source_name: "openapi", version: "default", overwrite_examples: "true" }}
            onFinish={(values) => void handleOpenApiImport(values)}
          >
            <Row gutter={12}>
              <Col span={8}>
                <Form.Item name="source_name" label="来源名称">
                  <Input placeholder="openapi" />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name="version" label="版本">
                  <Input placeholder="default / v1" />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name="overwrite_examples" label="覆盖示例">
                  <Select
                    options={[
                      { value: "true", label: "覆盖" },
                      { value: "false", label: "保留已有示例" },
                    ]}
                  />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item
              name="content"
              label="OpenAPI JSON/YAML"
              rules={[{ required: true, message: "请粘贴 OpenAPI 文档内容" }]}
            >
              <Input.TextArea rows={22} spellCheck={false} placeholder='{"openapi":"3.0.0","paths":{"/pets":{"get":{"summary":"List pets","responses":{"200":{"description":"ok"}}}}}}' />
            </Form.Item>
          </Form>
        </Space>
      </Drawer>

      <Drawer
        title={debugAsset ? `调试接口：${debugAsset.method} ${debugAsset.path}` : "调试接口"}
        open={debugOpen}
        onClose={() => setDebugOpen(false)}
        width={760}
        destroyOnClose
        extra={
          <Button type="primary" icon={<PlayCircleOutlined />} loading={debugging} onClick={() => debugForm.submit()}>
            发送请求
          </Button>
        }
      >
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Alert
            type="info"
            showIcon
            message="通过后端代理发送请求，可复用环境鉴权，并避开浏览器 CORS。"
          />
          <Form form={debugForm} layout="vertical" onFinish={(values) => void handleDebug(values)}>
            <Row gutter={12}>
              <Col span={12}>
                <Form.Item name="environment" label="执行环境">
                  <Select
                    allowClear
                    placeholder="选择环境"
                    options={environments.map((env) => ({ value: env.name, label: env.name }))}
                    onChange={(value) => {
                      const env = environments.find((item) => item.name === value);
                      debugForm.setFieldValue("base_url", env?.base_url || "");
                      void debugForm.validateFields(["base_url"]);
                    }}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="timeout" label="超时秒数">
                  <Input type="number" min={0.1} max={120} />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item
              name="base_url"
              label="Base URL"
              dependencies={["environment"]}
              rules={[
                ({ getFieldValue }) => ({
                  validator: async (_, value) => {
                    if (String(value || "").trim() || getFieldValue("environment")) return;
                    throw new Error("请输入 Base URL 或选择环境");
                  },
                }),
              ]}
            >
              <Input placeholder="http://127.0.0.1:8001" />
            </Form.Item>
            <Row gutter={12}>
              <Col span={12}>
                <Form.Item name="headers" label="Headers JSON">
                  <Input.TextArea rows={5} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="params" label="Query Params JSON">
                  <Input.TextArea rows={5} />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item name="json_body" label="JSON Body">
              <Input.TextArea rows={6} placeholder='{"name":"demo"}' />
            </Form.Item>
          </Form>

          {debugResult ? (
            <Card bordered={false} title="调试结果">
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                <Space wrap>
                  <Tag color={debugResult.response.ok ? "green" : "red"}>HTTP {debugResult.response.status_code || "ERR"}</Tag>
                  <Tag>{debugResult.response.elapsed_ms} ms</Tag>
                  <Text type="secondary">{debugResult.request.url}</Text>
                  <Button size="small" onClick={saveDebugResponseAsExample}>
                    保存为 Mock 示例
                  </Button>
                </Space>
                {debugResult.response.error ? <Alert type="error" showIcon message={debugResult.response.error} /> : null}
                <JsonViewer data={debugResult.response.json ?? debugResult.response.body_preview} />
              </Space>
            </Card>
          ) : null}
        </Space>
      </Drawer>

      <Drawer
        title={exampleAsset ? `响应示例：${exampleAsset.method} ${exampleAsset.path}` : "响应示例"}
        open={exampleOpen}
        onClose={() => setExampleOpen(false)}
        width={720}
        destroyOnClose
        extra={
          <Button type="primary" loading={savingExample} onClick={() => exampleForm.submit()}>
            保存示例
          </Button>
        }
      >
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Alert
            type="success"
            showIcon
            message="Mock 返回规则"
            description="建议格式为 { status_code, body, headers }。Mock 服务会优先返回 body/json 字段，没有示例时才返回默认占位响应。"
          />
          <Form form={exampleForm} layout="vertical" onFinish={(values) => void handleSaveExample(values)}>
            <Form.Item
              name="response_example"
              label="Response Example JSON"
              rules={[
                { required: true, message: "请输入响应示例 JSON" },
                {
                  validator: async (_, value) => {
                    try {
                      JSON.parse(String(value || "{}"));
                    } catch {
                      throw new Error("必须是合法 JSON");
                    }
                  },
                },
              ]}
            >
              <Input.TextArea rows={18} spellCheck={false} />
            </Form.Item>
          </Form>
        </Space>
      </Drawer>
    </PageStack>
  );
}
