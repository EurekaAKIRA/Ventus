import { Alert, Button, Card, Input, List, Space, Table, Tag, Typography } from "antd";
import type { TableProps } from "antd";
import type { ExecutionExplanationPayload, PreflightCheckPayload } from "../../types";
import LogPanel from "../../components/LogPanel";
import type { ExecutionCaseRow } from "../hooks/useExecutionCaseRows";
import type { ExtendedTaskDetail } from "../hooks/useTaskDetailData";

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

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      {pollingError ? <Alert type="warning" showIcon message="状态同步异常" description={pollingError} /> : null}
      <Card
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

      <Card bordered={false} title="执行用例（按测试点）">
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
                locale={{ emptyText: "暂无可展示的执行用例" }}
              />
            </div>
          </div>
        </Space>
      </Card>

      <Card
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
        bordered={false}
        title="失败归因"
        extra={
          <Button size="small" loading={explanationsLoading} onClick={onLoadExecutionExplanations}>
            刷新
          </Button>
        }
      >
        {explanationsError ? <Alert type="info" showIcon message={explanationsError} /> : null}
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

      <Card bordered={false} title="执行日志">
        <LogPanel logs={detail.execution_result?.logs ?? []} />
      </Card>
    </Space>
  );
}
const { Text } = Typography;
