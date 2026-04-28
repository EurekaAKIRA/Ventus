import { useEffect, useMemo, useState } from "react";
import { DeleteOutlined, EditOutlined, PlayCircleOutlined, PlusOutlined, ReloadOutlined, ScheduleOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, Drawer, Empty, Form, Input, Modal, Row, Select, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { EnvironmentPayload, TestCaseAssetPayload, TestSuiteAssetExecutionPayload, TestSuiteAssetPayload } from "../types";
import { fetchEnvironments } from "../api/system";
import { fetchTestCaseAssets } from "../api/testCases";
import { deleteTestSuiteAsset, executeTestSuiteAsset, fetchTestSuiteAssets, saveTestSuiteAsset, updateTestSuiteAsset } from "../api/testSuites";
import { useAuth } from "../auth/AuthContext";
import JsonViewer from "../components/JsonViewer";
import { MetricGrid, PageHero, PageStack } from "../components/PageLayout";

const { Text } = Typography;

type SuiteFormValues = {
  name: string;
  description?: string;
  status?: string;
  tags?: string[];
  case_ids?: string[];
};

type ExecuteFormValues = {
  environment?: string;
  base_url?: string;
  stop_on_failure?: string;
};

const statusOptions = [
  { value: "active", label: "启用" },
  { value: "draft", label: "草稿" },
  { value: "disabled", label: "禁用" },
  { value: "archived", label: "归档" },
];

function statusColor(status: string): string {
  if (status === "active") return "green";
  if (status === "draft") return "gold";
  if (status === "disabled" || status === "archived") return "red";
  return "default";
}

export default function TestSuiteAssetCenter() {
  const { currentProjectId } = useAuth();
  const [form] = Form.useForm<SuiteFormValues>();
  const [executeForm] = Form.useForm<ExecuteFormValues>();
  const [items, setItems] = useState<TestSuiteAssetPayload[]>([]);
  const [cases, setCases] = useState<TestCaseAssetPayload[]>([]);
  const [environments, setEnvironments] = useState<EnvironmentPayload[]>([]);
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("active");
  const [loading, setLoading] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<TestSuiteAssetPayload | null>(null);
  const [saving, setSaving] = useState(false);
  const [executeOpen, setExecuteOpen] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [executeSuite, setExecuteSuite] = useState<TestSuiteAssetPayload | null>(null);
  const [executeResult, setExecuteResult] = useState<TestSuiteAssetExecutionPayload | null>(null);

  const loadSuites = async () => {
    if (!currentProjectId) {
      setItems([]);
      return;
    }
    setLoading(true);
    try {
      const payload = await fetchTestSuiteAssets({
        project_id: currentProjectId,
        keyword: keyword.trim() || undefined,
        status: status || undefined,
        page: 1,
        page_size: 200,
      });
      setItems(payload.items);
    } catch (error) {
      message.error((error as Error).message || "套件加载失败");
    } finally {
      setLoading(false);
    }
  };

  const loadDependencies = async () => {
    if (!currentProjectId) {
      setCases([]);
      setEnvironments([]);
      return;
    }
    try {
      const [casePayload, envPayload] = await Promise.all([
        fetchTestCaseAssets({ project_id: currentProjectId, status: "active", page: 1, page_size: 500 }),
        fetchEnvironments(currentProjectId),
      ]);
      setCases(casePayload.items);
      setEnvironments(envPayload);
    } catch {
      setCases([]);
      setEnvironments([]);
    }
  };

  useEffect(() => {
    void loadSuites();
  }, [currentProjectId, status]);

  useEffect(() => {
    void loadDependencies();
  }, [currentProjectId]);

  const metrics = useMemo(() => {
    const caseCount = items.reduce((sum, item) => sum + (item.case_ids?.length ?? 0), 0);
    return {
      total: items.length,
      active: items.filter((item) => item.status === "active").length,
      caseCount,
      avgCases: items.length ? Math.round((caseCount / items.length) * 10) / 10 : 0,
    };
  }, [items]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ status: "active", tags: [], case_ids: [] });
    setDrawerOpen(true);
  };

  const openEdit = (record: TestSuiteAssetPayload) => {
    setEditing(record);
    form.setFieldsValue({
      name: record.name,
      description: record.description,
      status: record.status,
      tags: record.tags,
      case_ids: record.case_ids,
    });
    setDrawerOpen(true);
  };

  const handleSave = async (values: SuiteFormValues) => {
    if (!currentProjectId) {
      message.warning("请先选择项目");
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        await updateTestSuiteAsset(editing.id, {
          name: values.name,
          description: values.description,
          status: values.status,
          tags: values.tags,
          case_ids: values.case_ids,
        });
      } else {
        await saveTestSuiteAsset({
          project_id: currentProjectId,
          name: values.name,
          description: values.description,
          status: values.status,
          tags: values.tags,
          case_ids: values.case_ids,
        });
      }
      message.success("用例套件已保存");
      setDrawerOpen(false);
      await loadSuites();
    } catch (error) {
      message.error((error as Error).message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (record: TestSuiteAssetPayload) => {
    Modal.confirm({
      title: "删除用例套件",
      content: record.name,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        await deleteTestSuiteAsset(record.id);
        message.success("用例套件已删除");
        await loadSuites();
      },
    });
  };

  const openExecute = (record: TestSuiteAssetPayload) => {
    const firstEnv = environments[0];
    setExecuteSuite(record);
    setExecuteResult(null);
    executeForm.resetFields();
    executeForm.setFieldsValue({ environment: firstEnv?.name, base_url: firstEnv?.base_url || "", stop_on_failure: "false" });
    setExecuteOpen(true);
  };

  const handleExecute = async (values: ExecuteFormValues) => {
    if (!executeSuite) return;
    setExecuting(true);
    try {
      const result = await executeTestSuiteAsset(executeSuite.id, {
        execution_mode: "api",
        environment: values.environment,
        base_url: values.base_url,
        stop_on_failure: values.stop_on_failure === "true",
      });
      setExecuteResult(result);
    } catch (error) {
      message.error((error as Error).message || "套件执行失败");
    } finally {
      setExecuting(false);
    }
  };

  const exportExecutionResult = () => {
    if (!executeSuite || !executeResult) return;
    const filename = `${executeSuite.name || "test-suite"}-execution-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
    const blob = new Blob([JSON.stringify(executeResult, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  const caseNameById = useMemo(() => {
    const map = new Map<string, string>();
    cases.forEach((item) => map.set(item.id, item.name));
    return map;
  }, [cases]);

  const columns: ColumnsType<TestSuiteAssetPayload> = [
    {
      title: "套件",
      dataIndex: "name",
      render: (_, record) => (
        <Space direction="vertical" size={2}>
          <Text strong>{record.name}</Text>
          <Text type="secondary">{record.description || "暂无描述"}</Text>
        </Space>
      ),
    },
    { title: "状态", dataIndex: "status", width: 100, render: (value: string) => <Tag color={statusColor(value)}>{value}</Tag> },
    { title: "用例数", dataIndex: "case_ids", width: 100, render: (value: string[]) => <Text>{value?.length ?? 0}</Text> },
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
          <Button icon={<PlayCircleOutlined />} onClick={() => openExecute(record)} />
          <Button danger icon={<DeleteOutlined />} onClick={() => void handleDelete(record)} />
        </Space>
      ),
    },
  ];

  return (
    <PageStack>
      <PageHero
        eyebrow={<><ScheduleOutlined /> Regression Suite</>}
        title="用例套件与回归计划"
        subtitle="把多个用例资产编排成可重复执行的回归套件。"
        actions={
          <Space wrap>
            <Button icon={<ReloadOutlined />} onClick={() => void loadSuites()}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} disabled={!currentProjectId}>新增套件</Button>
          </Space>
        }
      />

      <MetricGrid
        items={[
          { title: "套件总数", value: metrics.total },
          { title: "启用套件", value: metrics.active, color: "#5865f2" },
          { title: "编排用例", value: metrics.caseCount, color: "#2f81f7" },
          { title: "平均用例数", value: metrics.avgCases, color: "#f5b94c" },
        ]}
      />

      <Card bordered={false} className="panel-card">
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Row gutter={[12, 12]}>
            <Col xs={24} md={10}>
              <Input.Search allowClear placeholder="搜索套件名称/描述" value={keyword} onChange={(event) => setKeyword(event.target.value)} onSearch={() => void loadSuites()} />
            </Col>
            <Col xs={12} md={4}>
              <Select allowClear placeholder="状态" value={status || undefined} options={statusOptions} onChange={(value) => setStatus(value || "")} style={{ width: "100%" }} />
            </Col>
          </Row>
          <Table className="platform-table" rowKey="id" loading={loading} columns={columns} dataSource={items} pagination={{ pageSize: 12 }} locale={{ emptyText: <Empty description="暂无用例套件" /> }} />
        </Space>
      </Card>

      <Drawer title={editing ? "编辑用例套件" : "新增用例套件"} open={drawerOpen} onClose={() => setDrawerOpen(false)} width={620} destroyOnClose extra={<Button type="primary" loading={saving} onClick={() => form.submit()}>保存</Button>}>
        <Form form={form} layout="vertical" onFinish={(values) => void handleSave(values)}>
          <Form.Item name="name" label="套件名称" rules={[{ required: true, message: "请输入套件名称" }]}><Input /></Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={3} /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="status" label="状态"><Select options={statusOptions} /></Form.Item></Col>
            <Col span={12}><Form.Item name="tags" label="标签"><Select mode="tags" tokenSeparators={[",", "，"]} /></Form.Item></Col>
          </Row>
          <Form.Item name="case_ids" label="用例编排" rules={[{ required: true, message: "请选择至少一条用例" }]}>
            <Select
              mode="multiple"
              optionFilterProp="label"
              options={cases.map((item) => ({ value: item.id, label: `${item.priority} · ${item.name}` }))}
              placeholder="按顺序选择用例资产"
            />
          </Form.Item>
          <Alert type="info" showIcon message="当前第一版按选择顺序执行；后续可升级拖拽排序、并发策略、定时触发。" />
        </Form>
      </Drawer>

      <Drawer title={executeSuite ? `执行套件：${executeSuite.name}` : "执行套件"} open={executeOpen} onClose={() => setExecuteOpen(false)} width={820} destroyOnClose extra={<Button type="primary" loading={executing} onClick={() => executeForm.submit()}>执行</Button>}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Form form={executeForm} layout="vertical" onFinish={(values) => void handleExecute(values)}>
            <Row gutter={12}>
              <Col span={10}>
                <Form.Item name="environment" label="执行环境">
                  <Select
                    allowClear
                    options={environments.map((env) => ({ value: env.name, label: env.name }))}
                    onChange={(value) => {
                      const env = environments.find((item) => item.name === value);
                      if (env?.base_url) executeForm.setFieldValue("base_url", env.base_url);
                    }}
                  />
                </Form.Item>
              </Col>
              <Col span={10}>
                <Form.Item name="base_url" label="Base URL" rules={[{ required: true, message: "请选择环境或填写 Base URL" }]}><Input /></Form.Item>
              </Col>
              <Col span={4}>
                <Form.Item name="stop_on_failure" label="失败即停">
                  <Select options={[{ value: "false", label: "否" }, { value: "true", label: "是" }]} />
                </Form.Item>
              </Col>
            </Row>
          </Form>
          {executeSuite ? (
            <Card bordered={false} title="执行顺序">
              <Space direction="vertical" size={6}>
                {(executeSuite.case_ids || []).map((caseId, index) => (
                  <Text key={caseId}>{index + 1}. {caseNameById.get(caseId) || caseId}</Text>
                ))}
              </Space>
            </Card>
          ) : null}
          {executeResult ? (
            <Card
              bordered={false}
              title="套件执行结果"
              extra={<Button onClick={exportExecutionResult}>导出 JSON</Button>}
            >
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                <Space wrap>
                  <Tag color={executeResult.status === "passed" ? "green" : "red"}>{executeResult.status}</Tag>
                  <Tag>通过 {executeResult.metrics.passed}</Tag>
                  <Tag>失败 {executeResult.metrics.failed}</Tag>
                  <Tag>{executeResult.metrics.duration_ms} ms</Tag>
                </Space>
                <JsonViewer data={executeResult} />
              </Space>
            </Card>
          ) : null}
        </Space>
      </Drawer>
    </PageStack>
  );
}
