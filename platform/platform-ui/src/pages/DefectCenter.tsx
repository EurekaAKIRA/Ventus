import { useEffect, useMemo, useState } from "react";
import { Alert, Button, Card, Col, Drawer, Empty, Form, Input, Row, Select, Space, Table, Tag, Typography, message } from "antd";
import type { DefectPayload, ProjectMemberPayload, TaskListItem } from "../types";
import { createDefect, fetchDefects, updateDefect } from "../api/defects";
import { fetchProject } from "../api/auth";
import { fetchTaskList } from "../api/tasks";
import { PageStack } from "../components/PageLayout";
import { useAuth } from "../auth/AuthContext";

const { TextArea } = Input;
const { Text } = Typography;

type DefectFormValues = {
  title: string;
  task_id?: string;
  severity?: string;
  status?: string;
  assignee_user_id?: string;
  description?: string;
  reproduction_steps?: string;
  expected_result?: string;
  actual_result?: string;
};

const STATUS_OPTIONS = [
  { value: "open", label: "待处理" },
  { value: "in_progress", label: "处理中" },
  { value: "resolved", label: "已解决" },
  { value: "closed", label: "已关闭" },
];

const SEVERITY_OPTIONS = [
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" },
  { value: "critical", label: "严重" },
];

function getStatusTagColor(status: string) {
  switch (status) {
    case "open":
      return "default";
    case "in_progress":
      return "processing";
    case "resolved":
      return "success";
    case "closed":
      return "purple";
    default:
      return "default";
  }
}

function getSeverityTagColor(severity: string) {
  switch (severity) {
    case "critical":
      return "error";
    case "high":
      return "volcano";
    case "medium":
      return "gold";
    case "low":
      return "blue";
    default:
      return "default";
  }
}

function getStatusLabel(status: string) {
  return STATUS_OPTIONS.find((item) => item.value === status)?.label ?? status;
}

function getSeverityLabel(severity: string) {
  return SEVERITY_OPTIONS.find((item) => item.value === severity)?.label ?? severity;
}

function compactId(value?: string | null) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  if (raw.length <= 18) return raw;
  return `${raw.slice(0, 10)}...${raw.slice(-5)}`;
}

export default function DefectCenter() {
  const [form] = Form.useForm<DefectFormValues>();
  const { currentProjectId, isAuthenticated, projects } = useAuth();
  const [items, setItems] = useState<DefectPayload[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<DefectPayload | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [taskFilter, setTaskFilter] = useState("");
  const [assigneeFilter, setAssigneeFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [members, setMembers] = useState<ProjectMemberPayload[]>([]);
  const [tasks, setTasks] = useState<TaskListItem[]>([]);

  const currentProject = useMemo(
    () => projects.find((project) => project.id === currentProjectId) ?? null,
    [projects, currentProjectId],
  );

  const loadDefects = async () => {
    if (!currentProjectId || !isAuthenticated) {
      setItems([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    try {
      const payload = await fetchDefects({
        project_id: currentProjectId,
        keyword: keyword || undefined,
        status: statusFilter || undefined,
        severity: severityFilter || undefined,
        task_id: taskFilter || undefined,
        assignee_user_id: assigneeFilter || undefined,
        page,
        page_size: pageSize,
      });
      setItems(payload.items);
      setTotal(payload.total);
    } catch (error) {
      message.error((error as Error).message || "加载缺陷失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadDefects();
    }, 180);
    return () => window.clearTimeout(timer);
  }, [currentProjectId, isAuthenticated, keyword, statusFilter, severityFilter, taskFilter, assigneeFilter, page, pageSize]);

  useEffect(() => {
    if (!currentProjectId || !isAuthenticated) {
      setMembers([]);
      setTasks([]);
      return;
    }
    void (async () => {
      try {
        const [projectPayload, taskPayload] = await Promise.all([
          fetchProject(currentProjectId),
          fetchTaskList({ project_id: currentProjectId, page: 1, page_size: 200 }),
        ]);
        setMembers(projectPayload.members);
        setTasks(taskPayload.items);
      } catch (error) {
        message.error((error as Error).message || "加载缺陷关联数据失败");
      }
    })();
  }, [currentProjectId, isAuthenticated]);

  const resetEditor = () => {
    setEditing(null);
    setEditorOpen(false);
    form.resetFields();
    form.setFieldsValue({ severity: "medium", status: "open" });
  };

  const openCreateEditor = () => {
    setEditing(null);
    setEditorOpen(true);
    form.resetFields();
    form.setFieldsValue({ severity: "medium", status: "open" });
  };

  const handleSave = async (values: DefectFormValues) => {
    if (!currentProjectId) {
      message.warning("请先选择项目");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        task_id: values.task_id || undefined,
        title: values.title.trim(),
        description: String(values.description ?? "").trim(),
        severity: values.severity || "medium",
        status: values.status || "open",
        assignee_user_id: values.assignee_user_id || undefined,
        reproduction_steps: String(values.reproduction_steps ?? "").trim(),
        expected_result: String(values.expected_result ?? "").trim(),
        actual_result: String(values.actual_result ?? "").trim(),
        source: "manual",
      };
      if (editing) {
        await updateDefect(editing.id, {
          ...payload,
          clear_task: !values.task_id,
          clear_assignee: !values.assignee_user_id,
        });
      } else {
        await createDefect({
          project_id: currentProjectId,
          ...payload,
        });
      }
      await loadDefects();
      resetEditor();
      message.success(editing ? "缺陷已更新" : "缺陷已创建");
    } catch (error) {
      message.error((error as Error).message || "保存缺陷失败");
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (record: DefectPayload) => {
    setEditing(record);
    setEditorOpen(true);
    form.setFieldsValue({
      title: record.title,
      task_id: record.task_id ?? undefined,
      severity: record.severity,
      status: record.status,
      assignee_user_id: record.assignee_user_id ?? undefined,
      description: record.description,
      reproduction_steps: record.reproduction_steps,
      expected_result: record.expected_result,
      actual_result: record.actual_result,
    });
  };

  const statusCounts = useMemo(
    () => ({
      open: items.filter((item) => item.status === "open").length,
      inProgress: items.filter((item) => item.status === "in_progress").length,
      resolved: items.filter((item) => item.status === "resolved" || item.status === "closed").length,
    }),
    [items],
  );
  const criticalCount = useMemo(
    () => items.filter((item) => item.severity === "critical" || item.severity === "high").length,
    [items],
  );

  return (
    <PageStack>
      <div className="defect-page">
      <div className="defect-page-head">
        <div>
          <Text className="defect-page-head__eyebrow">Defect Tracking</Text>
          <Typography.Title level={3} className="defect-page-head__title">
            缺陷管理
          </Typography.Title>
          <Text type="secondary">按项目跟踪缺陷状态、责任人和关联任务。</Text>
        </div>
        <Space wrap size={8} className="defect-page-head__stats">
          <span><Text type="secondary">项目</Text><strong>{currentProject?.name || "未选择"}</strong></span>
          <span><Text type="secondary">总数</Text><strong>{total}</strong></span>
          <span><Text type="secondary">待处理</Text><strong>{statusCounts.open}</strong></span>
          <span><Text type="secondary">处理中</Text><strong>{statusCounts.inProgress}</strong></span>
          <span><Text type="secondary">高优先</Text><strong>{criticalCount}</strong></span>
        </Space>
      </div>

      {!currentProjectId ? (
        <Alert type="warning" showIcon message="请先在顶部选择项目，缺陷管理按项目维度工作。" />
      ) : null}

      <Card
        bordered={false}
        className="panel-card defect-list-card"
        title={
          <Space size={8}>
            <span>缺陷列表</span>
            <Tag>{total} 条</Tag>
            <Tag color="warning">{statusCounts.open + statusCounts.inProgress} 待收口</Tag>
          </Space>
        }
        extra={
          <Space size={8}>
            <Button onClick={() => void loadDefects()}>刷新</Button>
            <Button type="primary" disabled={!currentProjectId || !isAuthenticated} onClick={openCreateEditor}>
              新建缺陷
            </Button>
          </Space>
        }
      >
        <div className="defect-toolbar">
          <div className="defect-toolbar__filters">
            <Input
              allowClear
              placeholder="搜索编号 / 标题 / 描述 / 任务"
              value={keyword}
              onChange={(e) => {
                setPage(1);
                setKeyword(e.target.value);
              }}
              className="defect-toolbar__search"
            />
            <Select
              allowClear
              placeholder="状态"
              value={statusFilter || undefined}
              onChange={(value) => {
                setPage(1);
                setStatusFilter(String(value || ""));
              }}
              className="defect-toolbar__select"
              options={STATUS_OPTIONS}
            />
            <Select
              allowClear
              placeholder="严重级别"
              value={severityFilter || undefined}
              onChange={(value) => {
                setPage(1);
                setSeverityFilter(String(value || ""));
              }}
              className="defect-toolbar__select"
              options={SEVERITY_OPTIONS}
            />
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder="关联任务"
              value={taskFilter || undefined}
              onChange={(value) => {
                setPage(1);
                setTaskFilter(String(value || ""));
              }}
              className="defect-toolbar__task"
              options={tasks.map((task) => ({
                value: task.task_id,
                label: `${task.task_name} · ${task.task_id}`,
              }))}
            />
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder="指派给"
              value={assigneeFilter || undefined}
              onChange={(value) => {
                setPage(1);
                setAssigneeFilter(String(value || ""));
              }}
              className="defect-toolbar__assignee"
              options={members.map((member) => ({
                value: member.user_id,
                label: member.display_name ? `${member.display_name} · ${member.username}` : member.username || member.user_id || "",
              }))}
            />
          </div>
        </div>
        <Drawer
          title={editing ? `编辑缺陷：${editing.defect_key}` : "新建缺陷"}
          open={editorOpen}
          width={720}
          onClose={resetEditor}
          destroyOnClose
        >
            <Form
              form={form}
              layout="vertical"
              className="defect-editor-form"
              initialValues={{ severity: "medium", status: "open" }}
              onFinish={handleSave}
            >
              <Row gutter={16}>
                <Col xs={24} xl={16}>
                  <Form.Item name="title" label="缺陷标题" rules={[{ required: true, message: "请输入缺陷标题" }]}>
                    <Input placeholder="例如：订单结算失败时返回 500" />
                  </Form.Item>
                </Col>
                <Col xs={24} xl={8}>
                  <Form.Item name="task_id" label="关联任务">
                    <Select
                      allowClear
                      showSearch
                      optionFilterProp="label"
                      placeholder="可选"
                      options={tasks.map((task) => ({
                        value: task.task_id,
                        label: `${task.task_name} · ${task.task_id}`,
                      }))}
                    />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col xs={24} md={8}>
                  <Form.Item name="severity" label="严重级别">
                    <Select options={SEVERITY_OPTIONS} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={8}>
                  <Form.Item name="status" label="状态">
                    <Select options={STATUS_OPTIONS} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={8}>
                  <Form.Item name="assignee_user_id" label="指派给">
                    <Select
                      allowClear
                      showSearch
                      optionFilterProp="label"
                      placeholder="可选"
                      options={members.map((member) => ({
                        value: member.user_id,
                        label: member.display_name ? `${member.display_name} · ${member.username}` : member.username || member.user_id || "",
                      }))}
                    />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="description" label="问题描述">
                <TextArea rows={4} placeholder="描述缺陷现象、影响范围和上下文。" />
              </Form.Item>
              <Row gutter={16}>
                <Col xs={24} xl={8}>
                  <Form.Item name="reproduction_steps" label="复现步骤">
                    <TextArea rows={5} placeholder="描述复现步骤" />
                  </Form.Item>
                </Col>
                <Col xs={24} xl={8}>
                  <Form.Item name="expected_result" label="预期结果">
                    <TextArea rows={5} placeholder="预期系统表现" />
                  </Form.Item>
                </Col>
                <Col xs={24} xl={8}>
                  <Form.Item name="actual_result" label="实际结果">
                    <TextArea rows={5} placeholder="实际观察到的问题" />
                  </Form.Item>
                </Col>
              </Row>
              <Space wrap>
                <Button type="primary" htmlType="submit" loading={saving} disabled={!currentProjectId || !isAuthenticated}>
                  {editing ? "更新缺陷" : "创建缺陷"}
                </Button>
                <Button onClick={resetEditor}>{editing ? "取消编辑" : "取消新建"}</Button>
              </Space>
            </Form>
        </Drawer>
        <Table
          className="platform-table defect-table"
          size="middle"
          rowKey="id"
          loading={loading}
          dataSource={items}
          scroll={{ x: 1080 }}
          locale={{
            emptyText: (
              <div className="table-empty-state">
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前项目还没有缺陷记录" />
              </div>
            ),
          }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (value) => `共 ${value} 条`,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPage);
              setPageSize(nextPageSize);
            },
          }}
          columns={[
            {
              title: "缺陷",
              dataIndex: "title",
              key: "title",
              width: 620,
              render: (_, record: DefectPayload) => (
                <div className="defect-title-cell">
                  <div className="defect-title-cell__line">
                    <span className="mono-inline">{record.defect_key}</span>
                    <Text strong>{record.title}</Text>
                  </div>
                  {record.description ? (
                    <Text type="secondary" className="defect-title-cell__desc">
                      {record.description}
                    </Text>
                  ) : null}
                  {record.task_name || record.task_id ? (
                    <div className="defect-title-cell__source">
                      <Text type="secondary">
                        来源任务：{record.task_name || "未命名任务"}
                        {record.task_id ? ` · ${compactId(record.task_id)}` : ""}
                      </Text>
                    </div>
                  ) : null}
                </div>
              ),
            },
            {
              title: "严重级别",
              dataIndex: "severity",
              key: "severity",
              width: 100,
              render: (value: string) => <Tag color={getSeverityTagColor(value)}>{getSeverityLabel(value)}</Tag>,
            },
            {
              title: "状态",
              dataIndex: "status",
              key: "status",
              width: 110,
              render: (value: string) => <Tag color={getStatusTagColor(value)}>{getStatusLabel(value)}</Tag>,
            },
            {
              title: "负责人",
              key: "assignee",
              width: 150,
              render: (_, record: DefectPayload) => (
                <Text ellipsis>{record.assignee_display_name || record.assignee_username || "未指派"}</Text>
              ),
            },
            {
              title: "更新时间",
              dataIndex: "updated_at",
              key: "updated_at",
              width: 170,
              render: (value?: string | null) => (value ? new Date(value).toLocaleString() : "-"),
            },
            {
              title: "操作",
              key: "actions",
              width: 120,
              render: (_, record: DefectPayload) => (
                <Button type="link" onClick={() => handleEdit(record)}>
                  编辑
                </Button>
              ),
            },
          ]}
        />
      </Card>
      </div>
    </PageStack>
  );
}
