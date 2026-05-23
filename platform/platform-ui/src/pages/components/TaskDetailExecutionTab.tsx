import { type Key, useEffect, useMemo, useState } from "react";
import { Alert, Button, Card, Input, List, Select, Space, Table, Tag, Typography, message } from "antd";
import type { TableProps } from "antd";
import type { ExecutionExplanationPayload, PreflightCheckPayload } from "../../types";
import { createDefect } from "../../api/defects";
import LogPanel from "../../components/LogPanel";
import type { ExecutionCaseRow, ExecutionCaseStepRow } from "../hooks/useExecutionCaseRows";
import type { ExtendedTaskDetail } from "../hooks/useTaskDetailData";

type FailedExecutionStepRow = {
  key: string;
  scenarioId: string;
  scenarioName: string;
  stepId: string;
  stepText: string;
  message: string;
  category: string;
  statusCode: string;
  requestText: string;
  expectedText: string;
  actualText: string;
};

const SEVERITY_OPTIONS = [
  { value: "medium", label: "中" },
  { value: "high", label: "高" },
  { value: "critical", label: "严重" },
  { value: "low", label: "低" },
];

function stringifyCompact(input: unknown) {
  if (input === undefined || input === null || input === "") {
    return "-";
  }
  if (typeof input === "string") {
    return input;
  }
  try {
    return JSON.stringify(input, null, 2);
  } catch {
    return String(input);
  }
}

function severityFromCategory(category: string) {
  if (["server_error", "upstream_error", "auth_error", "tls_error"].includes(category)) {
    return "high";
  }
  if (["timeout", "network_error", "missing_context"].includes(category)) {
    return "high";
  }
  if (["request_validation_error", "client_error"].includes(category)) {
    return "medium";
  }
  return "medium";
}

function executionStatusColor(status: string) {
  if (status === "passed") return "success";
  if (status === "failed") return "error";
  if (["running", "requesting", "response_received", "asserting"].includes(status)) return "processing";
  if (status === "queued") return "default";
  return "default";
}

function executionStatusLabel(status: string) {
  const labels: Record<string, string> = {
    passed: "通过",
    failed: "失败",
    running: "执行中",
    requesting: "请求中",
    response_received: "已响应",
    asserting: "断言中",
    context_saved: "上下文已保存",
    queued: "排队中",
    pending: "待执行",
  };
  return labels[status] || status || "-";
}

function buildFailedStepRows(detail: ExtendedTaskDetail): FailedExecutionStepRow[] {
  const rows: FailedExecutionStepRow[] = [];
  const scenarios = detail.execution_result?.scenario_results ?? [];
  scenarios.forEach((scenario) => {
    const scenarioName = scenario.name || scenario.scenario_name || scenario.scenario_id || "未命名场景";
    const steps = scenario.steps ?? [];
    steps
      .filter((step) => step.status && step.status !== "passed")
      .forEach((step, index) => {
        const response = step.response ?? {};
        const request = step.request ?? {};
        const assertionFailures = step.assertion_failures ?? [];
        const category = String(step.error_category || response.error_category || "execution_error");
        const statusCode = String(response.status_code ?? "-");
        const method = String(request.method ?? "");
        const url = String(request.url ?? "");
        const requestText = [method, url].filter(Boolean).join(" ") || stringifyCompact(step.request_summary || request);
        rows.push({
          key: `${scenario.scenario_id || "scenario"}::${step.step_id || index}`,
          scenarioId: scenario.scenario_id || "-",
          scenarioName,
          stepId: step.step_id || `step_${index + 1}`,
          stepText: step.text || "-",
          message: step.message || "-",
          category,
          statusCode,
          requestText,
          expectedText:
            assertionFailures.length > 0
              ? assertionFailures.map((item) => `${item.source ?? "assertion"} ${item.op ?? ""} ${stringifyCompact(item.expected)}`).join("\n")
              : "接口按用例断言返回预期状态、结构和业务值",
          actualText: [
            `失败信息：${step.message || "-"}`,
            `失败类别：${category}`,
            `HTTP 状态：${statusCode}`,
            response.error ? `响应错误：${response.error}` : "",
            assertionFailures.length ? `断言失败：${assertionFailures.map((item) => item.message).filter(Boolean).join("；")}` : "",
          ]
            .filter(Boolean)
            .join("\n"),
        });
      });
    if (!steps.length && scenario.status === "failed") {
      rows.push({
        key: `${scenario.scenario_id || "scenario"}::scenario_failed`,
        scenarioId: scenario.scenario_id || "-",
        scenarioName,
        stepId: "-",
        stepText: "场景执行失败，缺少步骤明细",
        message: "场景执行失败",
        category: "execution_error",
        statusCode: "-",
        requestText: "-",
        expectedText: "场景应全部通过",
        actualText: `场景 ${scenarioName} 执行失败`,
      });
    }
  });
  return rows;
}

export function TaskDetailExecutionTab(props: {
  pollingError: string | null;
  preflightLoading: boolean;
  preflightError: string | null;
  preflightResult: PreflightCheckPayload | null;
  onRunPreflightCheck: () => void;
  caseKeyword: string;
  onCaseKeywordChange: (value: string) => void;
  selectedTestPoint: string;
  onSelectTestPoint: (value: string) => void;
  executionCaseRows: ExecutionCaseRow[];
  testPointGroups: string[];
  filteredExecutionCaseRows: ExecutionCaseRow[];
  executionCaseColumns: TableProps<ExecutionCaseRow>["columns"];
  refreshing: boolean;
  onRefresh: () => void;
  detail: ExtendedTaskDetail;
  onOpenRawData: (title: string, data: unknown) => void;
  explanationsLoading: boolean;
  explanationsError: string | null;
  executionExplanations: ExecutionExplanationPayload | null;
  onLoadExecutionExplanations: () => void;
}) {
  const {
    pollingError,
    preflightLoading,
    preflightError,
    preflightResult,
    onRunPreflightCheck,
    caseKeyword,
    onCaseKeywordChange,
    selectedTestPoint,
    onSelectTestPoint,
    executionCaseRows,
    testPointGroups,
    filteredExecutionCaseRows,
    executionCaseColumns,
    refreshing,
    onRefresh,
    detail,
    onOpenRawData,
    explanationsLoading,
    explanationsError,
    executionExplanations,
    onLoadExecutionExplanations,
  } = props;
  const [selectedFailedStepKeys, setSelectedFailedStepKeys] = useState<Key[]>([]);
  const [defectSeverity, setDefectSeverity] = useState("medium");
  const [exportingDefects, setExportingDefects] = useState(false);
  const failedStepRows = useMemo(() => buildFailedStepRows(detail), [detail]);
  const selectedFailedStepRows = useMemo(
    () => failedStepRows.filter((item) => selectedFailedStepKeys.includes(item.key)),
    [failedStepRows, selectedFailedStepKeys],
  );
  const exportFailedStepRows = selectedFailedStepRows.length ? selectedFailedStepRows : failedStepRows;

  useEffect(() => {
    setSelectedFailedStepKeys(failedStepRows.map((item) => item.key));
  }, [failedStepRows]);

  const handleExportSelectedDefects = async () => {
    if (!exportFailedStepRows.length) {
      message.warning("当前没有可导出的失败步骤");
      return;
    }
    setExportingDefects(true);
    try {
      await Promise.all(
        exportFailedStepRows.map((row) =>
          createDefect({
            project_id: detail.task_context.project_id,
            task_id: detail.task_context.task_id,
            title: `[${row.category}] ${row.scenarioName} / ${row.stepText}`.slice(0, 180),
            description: [
              `来源任务：${detail.task_context.task_name}`,
              `任务 ID：${detail.task_context.task_id}`,
              `场景：${row.scenarioName} (${row.scenarioId})`,
              `步骤：${row.stepText} (${row.stepId})`,
              `失败类别：${row.category}`,
              `HTTP 状态：${row.statusCode}`,
              "",
              "失败信息：",
              row.message,
            ].join("\n"),
            severity: defectSeverity || severityFromCategory(row.category),
            status: "open",
            source: "execution_export",
            reproduction_steps: [
              "1. 打开任务详情页并进入执行页签",
              "2. 使用当前任务 DSL 与环境执行接口测试",
              `3. 执行场景：${row.scenarioName}`,
              `4. 执行步骤：${row.stepText}`,
              `5. 请求：${row.requestText}`,
            ].join("\n"),
            expected_result: row.expectedText,
            actual_result: row.actualText,
          }),
        ),
      );
      message.success(`已导出 ${exportFailedStepRows.length} 条缺陷`);
      setSelectedFailedStepKeys([]);
    } catch (error) {
      message.error((error as Error).message || "导出缺陷失败");
    } finally {
      setExportingDefects(false);
    }
  };

  const failedStepColumns: TableProps<FailedExecutionStepRow>["columns"] = [
    { title: "场景", dataIndex: "scenarioName", key: "scenarioName", ellipsis: true },
    { title: "步骤", dataIndex: "stepText", key: "stepText", ellipsis: true },
    {
      title: "类别",
      dataIndex: "category",
      key: "category",
      width: 150,
      render: (value: string) => (
        <Tag color={["assertion_error", "assertion_failed", "assertion_shape_mismatch"].includes(value) ? "gold" : "error"}>{value}</Tag>
      ),
    },
    { title: "HTTP", dataIndex: "statusCode", key: "statusCode", width: 90 },
    { title: "失败信息", dataIndex: "message", key: "message", ellipsis: true },
  ];

  const executionStepColumns: TableProps<ExecutionCaseStepRow>["columns"] = [
    { title: "步骤", dataIndex: "stepId", key: "stepId", width: 130 },
    { title: "说明", dataIndex: "text", key: "text", ellipsis: true },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 110,
      render: (value: string) => <Tag color={executionStatusColor(value)}>{executionStatusLabel(value)}</Tag>,
    },
    { title: "请求", dataIndex: "requestText", key: "requestText", ellipsis: true, width: 260 },
    { title: "响应", dataIndex: "responseText", key: "responseText", ellipsis: true, width: 180 },
    {
      title: "断言",
      dataIndex: "assertionsText",
      key: "assertionsText",
      width: 320,
      render: (value: string) => <pre className="execution-assertions-cell">{value}</pre>,
    },
    { title: "信息", dataIndex: "message", key: "message", ellipsis: true, width: 260 },
  ];

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      {pollingError ? <Alert type="warning" showIcon message="状态同步异常" description={pollingError} /> : null}
      <Card
        className="panel-card"
        bordered={false}
        title="执行前检查"
        extra={
          <Button size="small" loading={preflightLoading} onClick={onRunPreflightCheck}>
            重新检查
          </Button>
        }
      >
        {preflightError ? <Alert type="warning" showIcon message={preflightError} /> : null}
        {preflightResult ? (
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            <Space>
              <Text>检查结果</Text>
              <Tag color={preflightResult.blocking ? "error" : preflightResult.overall_status === "warning" ? "warning" : "success"}>
                {preflightResult.overall_status}
              </Tag>
              {preflightResult.blocking ? <Text type="danger">存在阻断项</Text> : <Text type="secondary">可执行</Text>}
            </Space>
            <List
              size="small"
              dataSource={preflightResult.checks}
              renderItem={(item) => (
                <List.Item>
                  <Space style={{ width: "100%", justifyContent: "space-between" }}>
                    <Text>{item.name}</Text>
                    <Tag color={item.status === "passed" ? "success" : item.status === "warning" ? "warning" : "error"}>
                      {item.status}
                    </Tag>
                  </Space>
                </List.Item>
              )}
            />
            {preflightResult.blocking_issues?.length ? (
              <Alert
                type="error"
                showIcon
                message="阻断项"
                description={
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {preflightResult.blocking_issues.map((issue, index) => (
                      <li key={`${issue}_${index}`}>{issue}</li>
                    ))}
                  </ul>
                }
              />
            ) : null}
            {preflightResult.suggestions?.length ? (
              <Alert
                type="info"
                showIcon
                message="建议项"
                description={
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {preflightResult.suggestions.map((item, index) => (
                      <li key={`${item}_${index}`}>{item}</li>
                    ))}
                  </ul>
                }
              />
            ) : null}
          </Space>
        ) : (
          <Text type="secondary">尚未执行前置检查。建议先检查再启动执行。</Text>
        )}
      </Card>

      <Card bordered={false} className="panel-card" title="执行用例（按测试点）">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Input
            allowClear
            placeholder="搜索 ID / 用例名称"
            value={caseKeyword}
            onChange={(event) => onCaseKeywordChange(event.target.value)}
          />
          <div className="execution-split-view">
            <div className="execution-point-sidebar">
              <div
                className={`execution-point-item ${selectedTestPoint === "all" ? "active" : ""}`}
                onClick={() => onSelectTestPoint("all")}
              >
                <span>全部测试点</span>
                <Tag>{executionCaseRows.length}</Tag>
              </div>
              {testPointGroups.map((point) => (
                <div
                  key={point}
                  className={`execution-point-item ${selectedTestPoint === point ? "active" : ""}`}
                  onClick={() => onSelectTestPoint(point)}
                >
                  <span>{point}</span>
                  <Tag>{executionCaseRows.filter((item) => item.testPoint === point).length}</Tag>
                </div>
              ))}
            </div>
            <div className="execution-case-table-wrap">
              <Table<ExecutionCaseRow>
                rowKey="key"
                size="small"
                columns={executionCaseColumns}
                dataSource={filteredExecutionCaseRows}
                pagination={{ pageSize: 8, showSizeChanger: false }}
                scroll={{ x: 1200 }}
                expandable={{
                  expandedRowRender: (record) => (
                    <Table<ExecutionCaseStepRow>
                      rowKey="key"
                      size="small"
                      columns={executionStepColumns}
                      dataSource={record.steps}
                      pagination={false}
                      scroll={{ x: 1400 }}
                    />
                  ),
                  rowExpandable: (record) => record.steps.length > 0,
                }}
                locale={{ emptyText: "暂无可展示的执行用例" }}
              />
            </div>
          </div>
        </Space>
      </Card>

      <Card
        className="panel-card"
        bordered={false}
        title="执行摘要"
        extra={
          <Button size="small" loading={refreshing} disabled={refreshing} onClick={onRefresh}>
            刷新
          </Button>
        }
      >
        {detail.execution_result ? (
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            <Text>执行器：{detail.execution_result.executor || "-"}</Text>
            <Text>执行状态：{detail.execution_result.status || "-"}</Text>
            <Text>场景结果数：{detail.execution_result.scenario_results?.length ?? 0}</Text>
            <Button size="small" onClick={() => onOpenRawData("执行结果 JSON", detail.execution_result)}>
              查看原始数据
            </Button>
          </Space>
        ) : (
          <Alert type="info" showIcon message="暂无执行结果" />
        )}
      </Card>

      <Card
        className="panel-card"
        bordered={false}
        title="缺陷导出"
        extra={
          <Space>
            <Select
              size="small"
              value={defectSeverity}
              style={{ width: 120 }}
              options={SEVERITY_OPTIONS}
              onChange={setDefectSeverity}
            />
            <Button
              size="small"
              type="primary"
              loading={exportingDefects}
              disabled={!failedStepRows.length}
              onClick={() => void handleExportSelectedDefects()}
            >
              {selectedFailedStepRows.length ? "导出选中缺陷" : "导出全部缺陷"}
            </Button>
          </Space>
        }
      >
        {detail.execution_result ? (
          failedStepRows.length ? (
            <Space direction="vertical" size={10} style={{ width: "100%" }}>
              <Alert
                type="info"
                showIcon
                message={`已发现 ${failedStepRows.length} 个失败步骤，默认全选；也可以取消勾选后只导出部分缺陷。`}
              />
              <Table<FailedExecutionStepRow>
                rowKey="key"
                size="small"
                columns={failedStepColumns}
                dataSource={failedStepRows}
                pagination={{ pageSize: 6, showSizeChanger: false }}
                rowSelection={{
                  selectedRowKeys: selectedFailedStepKeys,
                  onChange: setSelectedFailedStepKeys,
                }}
                scroll={{ x: 900 }}
              />
            </Space>
          ) : (
            <Alert type="success" showIcon message="当前执行结果未发现失败步骤，暂不需要导出缺陷。" />
          )
        ) : (
          <Alert type="info" showIcon message="执行完成后，可在这里选择失败步骤导出为缺陷。" />
        )}
      </Card>

      <Card
        className="panel-card"
        bordered={false}
        title="失败归因"
        extra={
          <Button size="small" loading={explanationsLoading} onClick={onLoadExecutionExplanations}>
            刷新
          </Button>
        }
      >
        {explanationsError ? <Alert type="info" showIcon message={explanationsError} /> : null}
        {executionExplanations?.llm_metadata ? (
          <Alert
            type={executionExplanations.llm_metadata.used ? "success" : "info"}
            showIcon
            message={
              executionExplanations.llm_metadata.used
                ? "LLM 已参与失败诊断"
                : `LLM 未参与诊断：${executionExplanations.llm_metadata.fallback_reason || "未启用"}`
            }
          />
        ) : null}
        {executionExplanations?.llm_diagnosis ? (
          <Card size="small" className="subtle-card" title="智能诊断">
            <Space direction="vertical" size={6} style={{ width: "100%" }}>
              <Text>{executionExplanations.llm_diagnosis.summary || "-"}</Text>
              {executionExplanations.llm_diagnosis.root_cause ? (
                <Text type="secondary">根因判断：{executionExplanations.llm_diagnosis.root_cause}</Text>
              ) : null}
              {executionExplanations.llm_diagnosis.next_actions?.length ? (
                <Text type="secondary">建议：{executionExplanations.llm_diagnosis.next_actions.join("；")}</Text>
              ) : null}
            </Space>
          </Card>
        ) : null}
        {executionExplanations?.defect_summaries?.length ? (
          <Card size="small" className="subtle-card" title="缺陷摘要建议">
            <List
              size="small"
              dataSource={executionExplanations.defect_summaries.slice(0, 5)}
              renderItem={(item) => (
                <List.Item>
                  <Space direction="vertical" size={4} style={{ width: "100%" }}>
                    <Space>
                      <Tag color={item.generated_by === "llm" ? "processing" : "default"}>{item.generated_by || "rules"}</Tag>
                      <Tag color={item.severity === "critical" ? "error" : item.severity === "high" ? "warning" : "default"}>
                        {item.severity || "medium"}
                      </Tag>
                      <Text strong>{item.title}</Text>
                    </Space>
                    {item.actual_result ? <Text type="secondary">{item.actual_result}</Text> : null}
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        ) : null}
        {executionExplanations?.failure_groups?.length ? (
          <List
            size="small"
            dataSource={executionExplanations.failure_groups}
            renderItem={(group) => (
              <List.Item>
                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                  <Space>
                    <Tag color="error">{group.category}</Tag>
                    <Text type="secondary">数量：{group.count}</Text>
                  </Space>
                  {group.recommended_actions?.length ? (
                    <Text>{group.recommended_actions.join("；")}</Text>
                  ) : (
                    <Text type="secondary">暂无建议动作</Text>
                  )}
                </Space>
              </List.Item>
            )}
          />
        ) : (
          <Text type="secondary">暂无失败归因数据</Text>
        )}
      </Card>

      <Card bordered={false} className="panel-card" title="执行日志">
        <LogPanel logs={detail.execution_result?.logs ?? []} />
      </Card>
    </Space>
  );
}
const { Text } = Typography;
