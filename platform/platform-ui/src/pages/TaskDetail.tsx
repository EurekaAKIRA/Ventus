import { useEffect, useMemo, useRef } from "react";
import { useLocation, useParams, useSearchParams } from "react-router-dom";
import { Card, Empty, Progress, Space, Tag, Typography } from "antd";
import { ExtendedTaskDetail, StageKey, StageStatus, useTaskDetailData } from "./hooks/useTaskDetailData";
import { useTaskExecution } from "./hooks/useTaskExecution";
import { ExecutionCaseRow, useExecutionCaseRows } from "./hooks/useExecutionCaseRows";
import { TaskDetailTopSection } from "./components/TaskDetailTopSection";
import { TaskDetailDrawers } from "./components/TaskDetailDrawers";
import { TaskDetailTabs } from "./components/TaskDetailTabs";
import {
  TaskDetailBootLoadingCard,
  TaskDetailCreateProgressCard,
  TaskDetailInitialRefreshingView,
  TaskDetailRefreshingBanner,
} from "./components/TaskDetailLoadingViews";
import { deriveExecutionStatus, flattenNumericEntries, isTaskDetailPollingSettled, isValidHttpUrl, normalizeStatus, resolveTabKey, toReadableText } from "./taskDetailUtils";

const FEATURE_PREVIEW_LINES = 18;
const DSL_PREVIEW_SCENARIOS = 4;
const { Text } = Typography;

/** 分析完成前：轻量 summary 轮询；完成后停。执行中由 useTaskExecution 轮询。 */
const PRE_SETTLED_DETAIL_POLL_MS = 12000;

function executionStatusColor(status: string) {
  if (status === "passed") return "success";
  if (status === "failed") return "error";
  if (["running", "requesting", "response_received", "asserting"].includes(status)) return "processing";
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
    queued: "排队中",
    pending: "待执行",
  };
  return labels[status] || status || "-";
}

const STAGE_LABELS: Record<StageKey, string> = {
  basic: "任务基础信息",
  artifacts: "任务产物索引",
  dashboard: "单任务看板数据",
};

const CREATE_FLOW_STAGE_LABELS: Record<StageKey, string> = {
  basic: "任务已创建",
  artifacts: "需求解析与场景生成",
  dashboard: "报告与详情装载",
};

export default function TaskDetail() {
  const { taskId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const fromCreateFlow = searchParams.get("from") === "create";
  const {
    bootLoading,
    refreshing,
    stageState,
    stageError,
    refreshStageText,
    analysisProgress,
    detail,
    taskDashboard,
    dashboardLoadError,
    artifacts,
    artifactLoading,
    artifactDrawerOpen,
    activeArtifact,
    rawDrawerOpen,
    rawDrawerTitle,
    rawDrawerData,
    featureExpanded,
    dslExpanded,
    caseKeyword,
    selectedTestPoint,
    showTopOverview,
    load,
    silentPollBeforeSettled,
    refreshParsedSection,
    refreshScenarioSection,
    refreshReportSection,
    openArtifact,
    openRawData,
    setDetail,
    setTaskDashboard,
    setDashboardLoadError,
    setArtifactDrawerOpen,
    setRawDrawerOpen,
    setFeatureExpanded,
    setDslExpanded,
    setCaseKeyword,
    setSelectedTestPoint,
    setShowTopOverview,
  } = useTaskDetailData({ taskId, fromCreateFlow });
  const executionStatus = deriveExecutionStatus(detail);
  const taskLifecycleStatus = normalizeStatus(detail?.task_context?.status);
  const activeTabKey = resolveTabKey(searchParams.get("tab"));
  const shouldCompareLatest = searchParams.get("compare") === "latest";
  const {
    executing,
    stopping,
    pollingError,
    preflightLoading,
    preflightResult,
    preflightError,
    explanationsLoading,
    executionExplanations,
    explanationsError,
    regressionLoading,
    regressionDiff,
    regressionError,
    streamEvents,
    runPreflightCheck,
    loadExecutionExplanations,
    loadRegressionDiff,
    runExecution,
    stopCurrentExecution,
  } = useTaskExecution({
    taskId,
    detail,
    setDetail,
    setTaskDashboard,
    setDashboardLoadError,
    executionStatus,
    activeTabKey,
    shouldCompareLatest,
  });
  const uiExecutionStatus = executing ? "running" : executionStatus;
  const { executionCaseRows, testPointGroups, filteredExecutionCaseRows } = useExecutionCaseRows({
    detail,
    streamEvents,
    uiExecutionStatus,
    selectedTestPoint,
    caseKeyword,
  });

  const onTabChange = (tab: string) => {
    const nextTab = resolveTabKey(tab);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("tab", nextTab);
    setSearchParams(nextParams, { replace: true });
  };

  /** 分析完成前且非执行中：分段轮询（summary 优先，按需 full/产物）。 */
  const shouldPollDetailBeforeSettled =
    detail !== null && !isTaskDetailPollingSettled(detail) && executionStatus !== "running";

  const silentPollRef = useRef(silentPollBeforeSettled);
  silentPollRef.current = silentPollBeforeSettled;
  const refreshingRef = useRef(refreshing);
  refreshingRef.current = refreshing;

  useEffect(() => {
    if (!shouldPollDetailBeforeSettled || !taskId) {
      return;
    }
    const timer = window.setInterval(() => {
      if (refreshingRef.current) {
        return;
      }
      void silentPollRef.current();
    }, PRE_SETTLED_DETAIL_POLL_MS);
    return () => window.clearInterval(timer);
  }, [shouldPollDetailBeforeSettled, taskId]);

  const primaryAnalysisReport = taskDashboard?.analysis_report ?? detail?.analysis_report;

  const qualityColor = useMemo(() => {
    const status = primaryAnalysisReport?.quality_status;
    if (status === "passed") return "success";
    if (status === "failed") return "error";
    return "default";
  }, [primaryAnalysisReport?.quality_status]);

  useEffect(() => {
    if (!detail) {
      return;
    }
    if (searchParams.get("from") !== "create") {
      return;
    }
    const analysisCompleted =
      analysisProgress?.status === "completed" || analysisProgress?.status === "failed";
    const detailFullyReady =
      isTaskDetailPollingSettled(detail) &&
      (stageState.dashboard === "finish" || stageState.dashboard === "error");
    if (!analysisCompleted || !detailFullyReady) {
      return;
    }
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("from");
    setSearchParams(nextParams, { replace: true });
  }, [analysisProgress?.status, detail, searchParams, setSearchParams, stageState.dashboard]);

  if (bootLoading && !detail) {
    return (
      <TaskDetailBootLoadingCard
        fromCreateFlow={fromCreateFlow}
        stageState={stageState}
        stageError={stageError}
        stageLabels={fromCreateFlow ? CREATE_FLOW_STAGE_LABELS : STAGE_LABELS}
        analysisProgress={analysisProgress}
      />
    );
  }

  if (!detail && refreshing) {
    return <TaskDetailInitialRefreshingView refreshStageText={refreshStageText} stageError={stageError} />;
  }

  if (!detail) {
    return (
      <div className="task-detail-empty">
        <Empty description="任务不存在或响应为空" />
      </div>
    );
  }

  const detectedBaseUrl = detail.parse_metadata?.detected_base_url?.trim() || "";
  const effectiveDslBaseUrl =
    (((detail.test_case_dsl?.metadata as Record<string, unknown> | undefined)?.execution as Record<string, unknown> | undefined)
      ?.base_url as string | undefined)?.trim() || "";
  const resolvedBaseUrl = detectedBaseUrl || effectiveDslBaseUrl || detail.target_system || "";

  const taskStatus = taskLifecycleStatus;
  const displayTaskStatus = executionStatus === "not_started" ? taskStatus : executionStatus;
  const hasParsedResult = Boolean(detail.parsed_requirement);
  const hasScenarios = Boolean(detail.scenarios?.length);
  const hasReport = Boolean(primaryAnalysisReport);
  const preflightBlocking = Boolean(preflightResult?.blocking);
  const canExecute = isValidHttpUrl(resolvedBaseUrl) && !preflightBlocking;

  const steps = [
    {
      title: "已接收",
      status: taskStatus !== "received" ? "finish" : "process",
    },
    {
      title: "已解析",
      status: hasParsedResult ? "finish" : taskStatus === "received" ? "wait" : "process",
    },
    {
      title: "已生成场景",
      status: hasScenarios ? "finish" : hasParsedResult ? "process" : "wait",
    },
    {
      title: "执行",
      status:
        uiExecutionStatus === "passed"
          ? "finish"
          : uiExecutionStatus === "failed" || uiExecutionStatus === "stopped"
            ? "error"
            : uiExecutionStatus === "running"
              ? "process"
              : hasScenarios
                ? "process"
                : "wait",
    },
    {
      title: "报告",
      status: hasReport ? "finish" : uiExecutionStatus === "passed" || uiExecutionStatus === "failed" ? "process" : "wait",
    },
  ] as const;

  const scenarioResults = detail.execution_result?.scenario_results ?? [];
  const scenarioPass = scenarioResults.filter((s) => s.status === "passed").length;
  const scenarioFail = scenarioResults.filter((s) => s.status === "failed").length;
  const scenarioTotal = scenarioResults.length;
  const analysisChartData = taskDashboard?.chart_data ?? primaryAnalysisReport?.chart_data;
  const chartItems = flattenNumericEntries(analysisChartData)
    .filter((item) => item.value >= 0)
    .slice(0, 8);
  const chartMax = chartItems.length ? Math.max(...chartItems.map((item) => item.value), 1) : 1;

  const featureText = detail.feature_text ?? "";
  const featureLines = featureText ? featureText.split("\n") : [];
  const hasFeatureOverflow = featureLines.length > FEATURE_PREVIEW_LINES;
  const featureDisplayText = featureExpanded
    ? featureText
    : featureLines.slice(0, FEATURE_PREVIEW_LINES).join("\n");
  const featureDisplayLines = featureDisplayText
    ? featureDisplayText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
    : [];
  const dslScenarios = detail.test_case_dsl?.scenarios ?? [];
  const hasDslOverflow = dslScenarios.length > DSL_PREVIEW_SCENARIOS;
  const dslDisplayScenarios = dslExpanded ? dslScenarios : dslScenarios.slice(0, DSL_PREVIEW_SCENARIOS);
  const showTopRefreshBanner = refreshing && Boolean(refreshStageText);
  const finishedStageCount = (Object.values(stageState) as StageStatus[]).filter((item) => item === "finish").length;
  const processingStage = (Object.entries(stageState).find(([, value]) => value === "process")?.[0] as StageKey | undefined) ?? null;
  const hasStageError = (Object.values(stageState) as StageStatus[]).some((item) => item === "error");
  const refreshProgressPercent = Math.min(95, Math.round(((finishedStageCount + (processingStage ? 0.5 : 0)) / 3) * 100));
  const refreshStatusText =
    refreshStageText ||
    (processingStage ? `正在刷新：${STAGE_LABELS[processingStage]}` : hasStageError ? "刷新过程出现异常" : "正在刷新");
  const showCreateFlowProgressCard =
    fromCreateFlow &&
    Boolean(detail) &&
    Boolean(analysisProgress) &&
    (analysisProgress?.status !== "completed" || stageState.dashboard !== "finish") &&
    !refreshing;
  const shouldShowCreateFlowProgressPage =
    showCreateFlowProgressCard ||
    (fromCreateFlow &&
      Boolean(analysisProgress) &&
      (analysisProgress?.status !== "completed" ||
        stageState.artifacts === "process" ||
        stageState.dashboard === "process" ||
        stageState.dashboard === "wait"));
  const hasSummaryOnlyDetail =
    !detail.parsed_requirement &&
    !detail.retrieved_context?.length &&
    !detail.scenarios?.length &&
    !detail.test_case_dsl &&
    !detail.validation_report &&
    !detail.analysis_report &&
    !detail.feature_text &&
    !detail.execution_result &&
    !taskDashboard &&
    artifacts.length === 0;
  const executionCaseColumns = [
    { title: "ID", dataIndex: "id", key: "id", width: 180 },
    { title: "用例名称", dataIndex: "name", key: "name", ellipsis: true },
    { title: "测试点", dataIndex: "testPoint", key: "testPoint", ellipsis: true, width: 220 },
    {
      title: "优先级",
      dataIndex: "priority",
      key: "priority",
      width: 100,
      render: (value: string) => <Tag color={value === "P0" ? "red" : value === "P1" ? "gold" : "default"}>{value}</Tag>,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (value: string) => (
        <Tag color={executionStatusColor(value)}>{executionStatusLabel(value)}</Tag>
      ),
    },
    {
      title: "耗时",
      dataIndex: "durationMs",
      key: "durationMs",
      width: 110,
      render: (value: number) => `${value} ms`,
    },
    {
      title: "步骤进度",
      dataIndex: "stepProgress",
      key: "stepProgress",
      width: 180,
      render: (value: number, row: ExecutionCaseRow) => (
        <Space direction="vertical" size={2} style={{ width: "100%" }}>
          <Progress percent={value} size="small" showInfo={false} />
          <span style={{ color: "rgba(0,0,0,0.45)" }}>{row.stepProgressText}</span>
        </Space>
      ),
    },
    { title: "当前步骤", dataIndex: "currentStep", key: "currentStep", ellipsis: true, width: 260 },
    { title: "失败步骤", dataIndex: "failedSteps", key: "failedSteps", width: 110 },
  ];

  if (shouldShowCreateFlowProgressPage) {
    return (
      <Space direction="vertical" size={20} style={{ width: "100%" }} className="task-detail-page">
        <TaskDetailCreateProgressCard
          stageState={stageState}
          stageError={stageError}
          stageLabels={CREATE_FLOW_STAGE_LABELS}
          analysisProgress={analysisProgress}
        />
      </Space>
    );
  }

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }} className="task-detail-page">
      {showTopRefreshBanner ? (
        <TaskDetailRefreshingBanner
          refreshStatusText={refreshStatusText}
          refreshProgressPercent={refreshProgressPercent}
          hasStageError={hasStageError}
          stageError={stageError}
        />
      ) : null}
      <TaskDetailTopSection
        detail={detail}
        steps={steps as any}
        displayTaskStatus={displayTaskStatus}
        uiExecutionStatus={uiExecutionStatus}
        hasParsedResult={hasParsedResult}
        hasScenarios={hasScenarios}
        preflightBlocking={preflightBlocking}
        refreshing={refreshing}
        showTopOverview={showTopOverview}
        executing={executing}
        stopping={stopping}
        preflightLoading={preflightLoading}
        canExecute={canExecute}
        isTargetSystemValid={isValidHttpUrl(resolvedBaseUrl)}
        onToggleOverview={() => setShowTopOverview((prev) => !prev)}
        onRefresh={() => void load({ mode: "manual" })}
        onRunExecution={() => void runExecution()}
        onStopExecution={() => void stopCurrentExecution()}
      />

      {hasSummaryOnlyDetail ? (
        <Card bordered={false} className="panel-card task-detail-loading-card">
          <Space direction="vertical" size={10} style={{ width: "100%" }}>
            <Text strong>详情补充中</Text>
            <Text type="secondary">基础信息已经可见，场景、DSL、报告和产物正在后台继续装载。</Text>
            <Progress percent={Math.max(refreshProgressPercent, 20)} showInfo={false} status="active" />
          </Space>
        </Card>
      ) : (
        <TaskDetailTabs
          activeTabKey={activeTabKey}
          onTabChange={onTabChange}
          detail={detail}
          hasParsedResult={hasParsedResult}
          onRefreshParsedSection={() => void refreshParsedSection()}
          onRefreshScenarioSection={() => void refreshScenarioSection()}
          onOpenRawData={openRawData}
          dslDisplayScenarios={dslDisplayScenarios}
          hasDslOverflow={hasDslOverflow}
          dslExpanded={dslExpanded}
          onToggleDslExpanded={() => setDslExpanded((prev) => !prev)}
          featureText={featureText}
          featureDisplayLines={featureDisplayLines}
          hasFeatureOverflow={hasFeatureOverflow}
          featureExpanded={featureExpanded}
          onToggleFeatureExpanded={() => setFeatureExpanded((prev) => !prev)}
          featurePreviewLines={FEATURE_PREVIEW_LINES}
          dslPreviewScenarios={DSL_PREVIEW_SCENARIOS}
          pollingError={pollingError}
          preflightLoading={preflightLoading}
          preflightError={preflightError}
          preflightResult={preflightResult}
          onRunPreflightCheck={() => void runPreflightCheck()}
          caseKeyword={caseKeyword}
          onCaseKeywordChange={setCaseKeyword}
          selectedTestPoint={selectedTestPoint}
          onSelectTestPoint={setSelectedTestPoint}
          executionCaseRows={executionCaseRows}
          testPointGroups={testPointGroups}
          filteredExecutionCaseRows={filteredExecutionCaseRows}
          executionCaseColumns={executionCaseColumns}
          refreshing={refreshing}
          onRefresh={() => void load({ mode: "manual" })}
          explanationsLoading={explanationsLoading}
          explanationsError={explanationsError}
          executionExplanations={executionExplanations}
          onLoadExecutionExplanations={() => void loadExecutionExplanations()}
          dashboardLoadError={dashboardLoadError}
          taskDashboard={taskDashboard}
          toReadableText={toReadableText}
          regressionLoading={regressionLoading}
          shouldCompareLatest={shouldCompareLatest}
          regressionError={regressionError}
          regressionDiff={regressionDiff}
          onLoadRegressionDiff={() => void loadRegressionDiff()}
          primaryAnalysisReport={primaryAnalysisReport}
          qualityColor={qualityColor}
          onRefreshReportSection={() => void refreshReportSection()}
          chartItems={chartItems}
          chartMax={chartMax}
          analysisChartData={analysisChartData}
          artifacts={artifacts}
          onOpenArtifact={openArtifact}
        />
      )}

      <TaskDetailDrawers
        artifactDrawerOpen={artifactDrawerOpen}
        activeArtifact={activeArtifact}
        artifactLoading={artifactLoading}
        onCloseArtifactDrawer={() => setArtifactDrawerOpen(false)}
        rawDrawerTitle={rawDrawerTitle}
        rawDrawerOpen={rawDrawerOpen}
        rawDrawerData={rawDrawerData}
        onCloseRawDrawer={() => setRawDrawerOpen(false)}
      />

    </Space>
  );
}
