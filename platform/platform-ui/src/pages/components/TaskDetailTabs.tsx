import { Tabs } from "antd";
import type { TableProps } from "antd";
import type {
  AnalysisReport,
  ExecutionExplanationPayload,
  PreflightCheckPayload,
  RegressionDiffPayload,
  TaskArtifactItem,
  TaskDashboardPayload,
} from "../../types";
import type { ExtendedTaskDetail } from "../hooks/useTaskDetailData";
import type { ExecutionCaseRow } from "../hooks/useExecutionCaseRows";
import { TaskDetailArtifactsTab } from "./TaskDetailArtifactsTab";
import { TaskDetailDslTab } from "./TaskDetailDslTab";
import { TaskDetailExecutionTab } from "./TaskDetailExecutionTab";
import { TaskDetailParsedTab } from "./TaskDetailParsedTab";
import { TaskDetailReportTab } from "./TaskDetailReportTab";
import { TaskDetailScenarioTab } from "./TaskDetailScenarioTab";

export function TaskDetailTabs(props: {
  activeTabKey: string;
  onTabChange: (tab: string) => void;
  detail: ExtendedTaskDetail;
  hasParsedResult: boolean;
  onRefreshParsedSection: () => void;
  onRefreshScenarioSection: () => void;
  onOpenRawData: (title: string, data: unknown) => void;
  dslDisplayScenarios: NonNullable<ExtendedTaskDetail["test_case_dsl"]>["scenarios"];
  hasDslOverflow: boolean;
  dslExpanded: boolean;
  onToggleDslExpanded: () => void;
  featureText: string;
  featureDisplayLines: string[];
  hasFeatureOverflow: boolean;
  featureExpanded: boolean;
  onToggleFeatureExpanded: () => void;
  featurePreviewLines: number;
  dslPreviewScenarios: number;
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
  explanationsLoading: boolean;
  explanationsError: string | null;
  executionExplanations: ExecutionExplanationPayload | null;
  onLoadExecutionExplanations: () => void;
  dashboardLoadError: string | null;
  taskDashboard: TaskDashboardPayload | null;
  toReadableText: (input: unknown) => string;
  regressionLoading: boolean;
  shouldCompareLatest: boolean;
  regressionError: string | null;
  regressionDiff: RegressionDiffPayload | null;
  onLoadRegressionDiff: () => void;
  primaryAnalysisReport: AnalysisReport | null | undefined;
  qualityColor: string;
  onRefreshReportSection: () => void;
  chartItems: { key: string; label: string; value: number }[];
  chartMax: number;
  analysisChartData: unknown;
  artifacts: TaskArtifactItem[];
  onOpenArtifact: (item: TaskArtifactItem) => void | Promise<void>;
}) {
  const {
    activeTabKey,
    onTabChange,
    detail,
    hasParsedResult,
    onRefreshParsedSection,
    onRefreshScenarioSection,
    onOpenRawData,
    dslDisplayScenarios,
    hasDslOverflow,
    dslExpanded,
    onToggleDslExpanded,
    featureText,
    featureDisplayLines,
    hasFeatureOverflow,
    featureExpanded,
    onToggleFeatureExpanded,
    featurePreviewLines,
    dslPreviewScenarios,
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
    explanationsLoading,
    explanationsError,
    executionExplanations,
    onLoadExecutionExplanations,
    dashboardLoadError,
    taskDashboard,
    toReadableText,
    regressionLoading,
    shouldCompareLatest,
    regressionError,
    regressionDiff,
    onLoadRegressionDiff,
    primaryAnalysisReport,
    qualityColor,
    onRefreshReportSection,
    chartItems,
    chartMax,
    analysisChartData,
    artifacts,
    onOpenArtifact,
  } = props;

  return (
    <Tabs
      activeKey={activeTabKey}
      onChange={onTabChange}
      items={[
        {
          key: "parsed",
          label: "解析",
          children: (
            <TaskDetailParsedTab
              detail={detail}
              hasParsedResult={hasParsedResult}
              onRefreshParsedSection={onRefreshParsedSection}
              onOpenRawData={onOpenRawData}
            />
          ),
        },
        {
          key: "scenario",
          label: "场景",
          children: (
            <TaskDetailScenarioTab
              detail={detail}
              onRefreshScenarioSection={onRefreshScenarioSection}
              onOpenRawData={onOpenRawData}
            />
          ),
        },
        {
          key: "dsl",
          label: "DSL / Feature",
          children: (
            <TaskDetailDslTab
              detail={detail}
              dslDisplayScenarios={dslDisplayScenarios}
              hasDslOverflow={hasDslOverflow}
              dslExpanded={dslExpanded}
              onToggleDslExpanded={onToggleDslExpanded}
              onRefreshScenarioSection={onRefreshScenarioSection}
              onOpenRawData={onOpenRawData}
              featureText={featureText}
              featureDisplayLines={featureDisplayLines}
              hasFeatureOverflow={hasFeatureOverflow}
              featureExpanded={featureExpanded}
              onToggleFeatureExpanded={onToggleFeatureExpanded}
              featurePreviewLines={featurePreviewLines}
              dslPreviewScenarios={dslPreviewScenarios}
            />
          ),
        },
        {
          key: "execution",
          label: "执行",
          children: (
            <TaskDetailExecutionTab
              pollingError={pollingError}
              preflightLoading={preflightLoading}
              preflightError={preflightError}
              preflightResult={preflightResult}
              onRunPreflightCheck={onRunPreflightCheck}
              caseKeyword={caseKeyword}
              onCaseKeywordChange={onCaseKeywordChange}
              selectedTestPoint={selectedTestPoint}
              onSelectTestPoint={onSelectTestPoint}
              executionCaseRows={executionCaseRows}
              testPointGroups={testPointGroups}
              filteredExecutionCaseRows={filteredExecutionCaseRows}
              executionCaseColumns={executionCaseColumns}
              refreshing={refreshing}
              onRefresh={onRefresh}
              detail={detail}
              onOpenRawData={onOpenRawData}
              explanationsLoading={explanationsLoading}
              explanationsError={explanationsError}
              executionExplanations={executionExplanations}
              onLoadExecutionExplanations={onLoadExecutionExplanations}
            />
          ),
        },
        {
          key: "report",
          label: "报告",
          children: (
            <TaskDetailReportTab
              dashboardLoadError={dashboardLoadError}
              taskDashboard={taskDashboard}
              toReadableText={toReadableText}
              onOpenRawData={onOpenRawData}
              explanationsLoading={explanationsLoading}
              explanationsError={explanationsError}
              executionExplanations={executionExplanations}
              onLoadExecutionExplanations={onLoadExecutionExplanations}
              regressionLoading={regressionLoading}
              shouldCompareLatest={shouldCompareLatest}
              regressionError={regressionError}
              regressionDiff={regressionDiff}
              onLoadRegressionDiff={onLoadRegressionDiff}
              primaryAnalysisReport={primaryAnalysisReport}
              qualityColor={qualityColor}
              onRefreshReportSection={onRefreshReportSection}
              chartItems={chartItems}
              chartMax={chartMax}
              analysisChartData={analysisChartData}
            />
          ),
        },
        {
          key: "artifacts",
          label: "产物",
          children: <TaskDetailArtifactsTab artifacts={artifacts} onOpenArtifact={onOpenArtifact} />,
        },
      ]}
    />
  );
}
