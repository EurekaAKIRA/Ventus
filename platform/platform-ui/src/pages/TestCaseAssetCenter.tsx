import { useEffect, useMemo, useState } from "react";
import { CloudDownloadOutlined, DeleteOutlined, EditOutlined, FileDoneOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, Drawer, Empty, Form, Input, Modal, Row, Select, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { EnvironmentPayload, TaskListItem, TestCaseAssetExecutionPayload, TestCaseAssetPayload } from "../types";
import { deleteTestCaseAsset, executeTestCaseAsset, fetchTestCaseAssets, importTestCaseAssetsFromTask, saveTestCaseAsset, updateTestCaseAsset } from "../api/testCases";
import { fetchTaskDetail, fetchTaskList } from "../api/tasks";
import { fetchEnvironments } from "../api/system";
import { useAuth } from "../auth/AuthContext";
import JsonViewer from "../components/JsonViewer";
import { MetricGrid, PageHero, PageStack } from "../components/PageLayout";

const { Text } = Typography;

type CaseFormValues = {
  case_key?: string;
  name: string;
  description?: string;
  priority?: string;
  status?: string;
  tags?: string[];
  assertions?: string;
  dsl_scenario?: string;
};

type ExecuteFormValues = {
  environment?: string;
  base_url?: string;
};

type TaskImportHint = {
  environment: string;
  baseUrl: string;
};

const statusOptions = [
  { value: "active", label: "启用" },
  { value: "draft", label: "草稿" },
  { value: "disabled", label: "禁用" },
  { value: "archived", label: "归档" },
];
const priorityOptions = ["P0", "P1", "P2", "P3"].map((value) => ({ value, label: value }));

function statusColor(status: string): string {
  if (status === "active") return "green";
  if (status === "disabled" || status === "archived") return "red";
  if (status === "draft") return "gold";
  return "default";
}

function taskExecutionHint(detail: Awaited<ReturnType<typeof fetchTaskDetail>>) {
  const context = detail.task_context as typeof detail.task_context & { environment?: string | null };
  return {
    environment: context.environment || "",
    baseUrl: context.target_system || "",
  };
}

export default function TestCaseAssetCenter() {
  const { currentProjectId } = useAuth();
  const [form] = Form.useForm<CaseFormValues>();
  const [items, setItems] = useState<TestCaseAssetPayload[]>([]);
  const [tasks, setTasks] = useState<TaskListItem[]>([]);
  const [environments, setEnvironments] = useState<EnvironmentPayload[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("active");
  const [loading, setLoading] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<TestCaseAssetPayload | null>(null);
  const [saving, setSaving] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importTaskHint, setImportTaskHint] = useState<TaskImportHint | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState<unknown>(null);
  const [executeForm] = Form.useForm<ExecuteFormValues>();
  const [executeOpen, setExecuteOpen] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [executeCase, setExecuteCase] = useState<TestCaseAssetPayload | null>(null);
  const [executeResult, setExecuteResult] = useState<TestCaseAssetExecutionPayload | null>(null);

  const loadCases = async () => {
    if (!currentProjectId) {
      setItems([]);
      return;
    }
    setLoading(true);
    try {
      const payload = await fetchTestCaseAssets({
        project_id: currentProjectId,
        keyword: keyword.trim() || undefined,
        status: status || undefined,
        page: 1,
        page_size: 200,
      });
      setItems(payload.items);
    } catch (error) {
      message.error((error as Error).message || "用例资产加载失败");
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
    void loadCases();
  }, [currentProjectId, status]);

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
    return {
      total: items.length,
      active: items.filter((item) => item.status === "active").length,
      p0: items.filter((item) => item.priority === "P0").length,
      imported: items.filter((item) => item.source === "task_import").length,
    };
  }, [items]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      priority: "P1",
      status: "active",
      tags: [],
      assertions: "[]",
      dsl_scenario: "{}",
    });
    setDrawerOpen(true);
  };

  const openEdit = (record: TestCaseAssetPayload) => {
    setEditing(record);
    form.setFieldsValue({
      case_key: record.case_key,
      name: record.name,
      description: record.description,
      priority: record.priority,
      status: record.status,
      tags: record.tags,
      assertions: JSON.stringify(record.assertions || [], null, 2),
      dsl_scenario: JSON.stringify(record.dsl_scenario || {}, null, 2),
    });
    setDrawerOpen(true);
  };

  const openTaskImport = () => {
    setSelectedTaskId((prev) => prev || tasks[0]?.task_id || "");
    setImportOpen(true);
  };

  const parseJson = (label: string, text?: string): unknown => {
    const trimmed = String(text || "").trim();
    if (!trimmed) return label === "assertions" ? [] : {};
    return JSON.parse(trimmed);
  };

  const handleSave = async (values: CaseFormValues) => {
    if (!currentProjectId) {
      message.warning("请先选择项目");
      return;
    }
    setSaving(true);
    try {
      const dslScenario = parseJson("dsl_scenario", values.dsl_scenario);
      const assertions = parseJson("assertions", values.assertions);
      if (!Array.isArray(assertions)) {
        throw new Error("assertions 必须是 JSON 数组");
      }
      if (editing) {
        await updateTestCaseAsset(editing.id, {
          name: values.name,
          description: values.description,
          priority: values.priority,
          status: values.status,
          tags: values.tags,
          dsl_scenario: dslScenario,
          assertions,
        });
      } else {
        await saveTestCaseAsset({
          project_id: currentProjectId,
          case_key: values.case_key,
          name: values.name,
          description: values.description,
          priority: values.priority,
          status: values.status,
          tags: values.tags,
          dsl_scenario: dslScenario,
          assertions,
        });
      }
      message.success("用例资产已保存");
      setDrawerOpen(false);
      await loadCases();
    } catch (error) {
      message.error((error as Error).message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleImport = async () => {
    if (!selectedTaskId) {
      message.warning("请选择任务");
      return;
    }
    setImporting(true);
    try {
      const payload = await importTestCaseAssetsFromTask(selectedTaskId, currentProjectId || undefined);
      message.success(`已导入 ${payload.imported_count} 条用例资产`);
      setImportOpen(false);
      await loadCases();
    } catch (error) {
      message.error((error as Error).message || "导入失败");
    } finally {
      setImporting(false);
    }
  };

  const handleDelete = async (record: TestCaseAssetPayload) => {
    Modal.confirm({
      title: "删除用例资产",
      content: `${record.case_key} · ${record.name}`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        await deleteTestCaseAsset(record.id);
        message.success("用例资产已删除");
        await loadCases();
      },
    });
  };

  const openExecute = (record: TestCaseAssetPayload) => {
    const firstEnv = environments[0];
    setExecuteCase(record);
    setExecuteResult(null);
    executeForm.resetFields();
    executeForm.setFieldsValue({ environment: firstEnv?.name, base_url: firstEnv?.base_url || "" });
    setExecuteOpen(true);
    if (record.source_task_id) {
      void fetchTaskDetail(record.source_task_id, { detailLevel: "summary" })
        .then((detail) => {
          const hint = taskExecutionHint(detail);
          const matchedEnv = hint.environment ? environments.find((item) => item.name === hint.environment) : undefined;
          executeForm.setFieldsValue({
            environment: matchedEnv?.name || hint.environment || firstEnv?.name,
            base_url: matchedEnv?.base_url || hint.baseUrl || firstEnv?.base_url || "",
          });
        })
        .catch(() => undefined);
    }
  };

  const handleExecute = async (values: ExecuteFormValues) => {
    if (!executeCase) return;
    setExecuting(true);
    try {
      const result = await executeTestCaseAsset(executeCase.id, {
        execution_mode: "api",
        environment: values.environment,
        base_url: values.base_url,
      });
      setExecuteResult(result);
    } catch (error) {
      message.error((error as Error).message || "用例执行失败");
    } finally {
      setExecuting(false);
    }
  };

  const columns: ColumnsType<TestCaseAssetPayload> = [
    {
      title: "用例",
      dataIndex: "name",
      render: (_, record) => (
        <Space direction="vertical" size={2}>
          <Space>
            <Tag>{record.case_key}</Tag>
            <Text strong>{record.name}</Text>
          </Space>
          <Text type="secondary">{record.description || "暂无描述"}</Text>
        </Space>
      ),
    },
    { title: "优先级", dataIndex: "priority", width: 90, render: (value: string) => <Tag color={value === "P0" ? "red" : "blue"}>{value}</Tag> },
    { title: "状态", dataIndex: "status", width: 100, render: (value: string) => <Tag color={statusColor(value)}>{value}</Tag> },
    { title: "来源", dataIndex: "source", width: 120, render: (value: string) => <Tag>{value === "task_import" ? "任务导入" : value}</Tag> },
    {
      title: "断言",
      dataIndex: "assertions",
      width: 90,
      render: (value: unknown[]) => <Text>{value?.length ?? 0}</Text>,
    },
    {
      title: "标签",
      dataIndex: "tags",
      width: 180,
      render: (tags: string[]) => (
        <Space size={[4, 4]} wrap>
          {(tags || []).map((tag) => <Tag key={tag}>{tag}</Tag>)}
        </Space>
      ),
    },
    {
      title: "操作",
      width: 190,
      render: (_, record) => (
        <Space>
          <Button icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Button onClick={() => openExecute(record)}>执行</Button>
          <Button onClick={() => { setPreviewData(record.dsl_scenario); setPreviewOpen(true); }}>DSL</Button>
          <Button danger icon={<DeleteOutlined />} onClick={() => void handleDelete(record)} />
        </Space>
      ),
    },
  ];

  return (
    <PageStack>
      <PageHero
        eyebrow={<><FileDoneOutlined /> Test Case Assets</>}
        title="用例资产中心"
        subtitle="把任务生成的 DSL 场景沉淀为可维护、可编辑、可复用的测试资产。"
        actions={
          <Space wrap>
            <Button icon={<CloudDownloadOutlined />} onClick={openTaskImport} disabled={!currentProjectId}>从任务导入</Button>
            <Button icon={<ReloadOutlined />} onClick={() => void loadCases()}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} disabled={!currentProjectId}>新增用例</Button>
          </Space>
        }
      />

      <MetricGrid
        items={[
          { title: "用例总数", value: metrics.total },
          { title: "启用用例", value: metrics.active, color: "#5865f2" },
          { title: "P0 用例", value: metrics.p0, color: "#ff6b6b" },
          { title: "任务导入", value: metrics.imported, color: "#2f81f7" },
        ]}
      />

      <Card bordered={false} className="panel-card">
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Row gutter={[12, 12]}>
            <Col xs={24} md={10}>
              <Input.Search allowClear placeholder="搜索用例名、Key、来源任务" value={keyword} onChange={(event) => setKeyword(event.target.value)} onSearch={() => void loadCases()} />
            </Col>
            <Col xs={12} md={4}>
              <Select allowClear placeholder="状态" value={status || undefined} options={statusOptions} onChange={(value) => setStatus(value || "")} style={{ width: "100%" }} />
            </Col>
          </Row>
          <Table className="platform-table" rowKey="id" loading={loading} columns={columns} dataSource={items} pagination={{ pageSize: 12 }} locale={{ emptyText: <Empty description="暂无用例资产，可从任务导入" /> }} />
        </Space>
      </Card>

      <Drawer title={editing ? "编辑用例资产" : "新增用例资产"} open={drawerOpen} onClose={() => setDrawerOpen(false)} width={760} destroyOnClose extra={<Button type="primary" loading={saving} onClick={() => form.submit()}>保存</Button>}>
        <Alert type="info" showIcon message="断言可视化第一阶段" description="当前先以 JSON 数组方式编辑断言，后续可升级为字段选择器和 JSONPath 表单。" style={{ marginBottom: 16 }} />
        <Form form={form} layout="vertical" onFinish={(values) => void handleSave(values)}>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="case_key" label="Case Key"><Input disabled={Boolean(editing)} placeholder="可不填，系统自动生成" /></Form.Item></Col>
            <Col span={12}><Form.Item name="name" label="用例名称" rules={[{ required: true, message: "请输入用例名称" }]}><Input /></Form.Item></Col>
          </Row>
          <Row gutter={12}>
            <Col span={8}><Form.Item name="priority" label="优先级"><Select options={priorityOptions} /></Form.Item></Col>
            <Col span={8}><Form.Item name="status" label="状态"><Select options={statusOptions} /></Form.Item></Col>
            <Col span={8}><Form.Item name="tags" label="标签"><Select mode="tags" tokenSeparators={[",", "，"]} /></Form.Item></Col>
          </Row>
          <Form.Item name="description" label="描述"><Input.TextArea rows={3} /></Form.Item>
          <Form.Item name="assertions" label="断言 JSON 数组"><Input.TextArea rows={8} spellCheck={false} /></Form.Item>
          <Form.Item name="dsl_scenario" label="DSL Scenario JSON"><Input.TextArea rows={14} spellCheck={false} /></Form.Item>
        </Form>
      </Drawer>

      <Modal title="从任务导入用例资产" open={importOpen} onCancel={() => setImportOpen(false)} onOk={() => void handleImport()} confirmLoading={importing} okText="导入" cancelText="取消">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Text type="secondary">会把任务生成的 DSL scenarios 按场景逐条沉淀为用例资产，并提取步骤断言。</Text>
          <Select showSearch placeholder="选择最近任务" value={selectedTaskId || undefined} onChange={setSelectedTaskId} options={tasks.map((task) => ({ value: task.task_id, label: `${task.task_name} · ${task.task_id}` }))} style={{ width: "100%" }} optionFilterProp="label" />
          {selectedTaskId ? (
            <Alert
              type={importTaskHint?.baseUrl || importTaskHint?.environment ? "success" : "warning"}
              showIcon
              message="任务执行配置"
              description={
                importTaskHint?.baseUrl || importTaskHint?.environment
                  ? `环境：${importTaskHint.environment || "未设置"}；Base URL：${importTaskHint.baseUrl || "未设置"}`
                  : "该任务暂未识别到环境或 Base URL，导入后执行时仍可手动选择。"
              }
            />
          ) : null}
        </Space>
      </Modal>

      <Modal title="DSL 预览" open={previewOpen} onCancel={() => setPreviewOpen(false)} footer={null} width={760}>
        <JsonViewer data={previewData} />
      </Modal>

      <Drawer
        title={executeCase ? `执行用例：${executeCase.name}` : "执行用例"}
        open={executeOpen}
        onClose={() => setExecuteOpen(false)}
        width={760}
        destroyOnClose
        extra={<Button type="primary" loading={executing} onClick={() => executeForm.submit()}>执行</Button>}
      >
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Alert type="info" showIcon message="单用例资产执行" description="会把当前用例资产的 DSL Scenario 包装成最小 DSL，并复用现有 API Runner 执行。" />
          <Form form={executeForm} layout="vertical" onFinish={(values) => void handleExecute(values)}>
            <Row gutter={12}>
              <Col span={12}>
                <Form.Item name="environment" label="执行环境">
                  <Select
                    allowClear
                    options={environments.map((env) => ({ value: env.name, label: env.name }))}
                    onChange={(value) => {
                      const env = environments.find((item) => item.name === value);
                      executeForm.setFieldValue("base_url", env?.base_url || "");
                      void executeForm.validateFields(["base_url"]);
                    }}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  name="base_url"
                  label="Base URL"
                  dependencies={["environment"]}
                  rules={[
                    ({ getFieldValue }) => ({
                      validator: async (_, value) => {
                        if (String(value || "").trim() || getFieldValue("environment")) return;
                        throw new Error("请选择环境或填写 Base URL");
                      },
                    }),
                  ]}
                >
                  <Input placeholder="http://127.0.0.1:8001" />
                </Form.Item>
              </Col>
            </Row>
          </Form>
          {executeResult ? (
            <Card bordered={false} title="执行结果">
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                <Space>
                  <Tag color={executeResult.execution_result.status === "passed" ? "green" : "red"}>
                    {executeResult.execution_result.status}
                  </Tag>
                  <Text type="secondary">{executeResult.executed_at}</Text>
                </Space>
                <JsonViewer data={executeResult.execution_result} />
              </Space>
            </Card>
          ) : null}
        </Space>
      </Drawer>
    </PageStack>
  );
}
