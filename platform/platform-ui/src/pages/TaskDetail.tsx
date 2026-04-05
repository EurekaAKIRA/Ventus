import { useEffect, useMemo, useRef } from "react";
import { useLocation, useParams, useSearchParams } from "react-router-dom";
import {
  Button,
  Col,
  Empty,
  Input,
  Progress,
  Row,
  Space,
  Table,
  Tag,
} from "antd";
import { fetchAnalysisReport } from "../api/tasks";
import LogPanel from "../components/LogPanel";
import { ExtendedTaskDetail, StageKey, StageStatus, useTaskDetailData } from "./hooks/useTaskDetailData";
import { useTaskExecution } from "./hooks/useTaskExecution";
import { ExecutionCaseRow, useExecutionCaseRows } from "./hooks/useExecutionCaseRows";
import { TaskDetailTopSection } from "./components/TaskDetailTopSection";
import { TaskDetailDrawers } from "./components/TaskDetailDrawers";
import { TaskDetailTabs } from "./components/TaskDetailTabs";
import {
  TaskDetailBootLoadingCard,
  TaskDetailInitialRefreshingView,
  TaskDetailRefreshingBanner,
} from "./components/TaskDetailLoadingViews";
import {
  ChartDatum,
  deriveExecutionStatus,
  flattenNumericEntries,
  isAnalyzingStatus,
  isTaskDetailPollingSettled,
  isValidHttpUrl,
  normalizeStatus,
  resolveTabKey,
  toReadableText,
} from "./taskDetailUtils";

const FEATURE_PREVIEW_LINES = 18;
const DSL_PREVIEW_SCENARIOS = 4;

/** 分析完成前：轻量 summary 轮询；完成后停。执行中由 useTaskExecution 轮询。 */
const PRE_SETTLED_DETAIL_POLL_MS = 12000;

const STAGE_LABELS: Record<StageKey, string> = {
  basic: "任务基础信息",
  artifacts: "任务产物索引",
  dashboard: "单任务看板数据",
};

export default function TaskDetail() {
  const { taskId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const fromCreateFlow =
    searchParams.get("from") === "create" ||
    Boolean((location.state as { fromCreate?: boolean } | null)?.fromCreate);
  const {
    bootLoading,
    refreshing,
    stageState,
    stageError,
    refreshStageText,
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
    streamStatus,
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
    if (isAnalyzingStatus(detail.task_context?.status)) {
      return;
    }
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("from");
    setSearchParams(nextParams, { replace: true });
  }, [detail, searchParams, setSearchParams]);

  if (bootLoading) {
    return (
      <TaskDetailBootLoadingCard
        fromCreateFlow={fromCreateFlow}
        stageState={stageState}
        stageError={stageError}
        stageLabels={STAGE_LABELS}
      />
    );
  }

  if (!detail && refreshing) {
    return <TaskDetailInitialRefreshingView refreshStageText={refreshStageText} stageError={stageError} />;
  }

  if (!detail) {
    return <Empty description="任务不存在或响应为空" />;
  }

  const taskStatus = taskLifecycleStatus;
  const displayTaskStatus = executionStatus === "not_started" ? taskStatus : executionStatus;
  const hasParsedResult = Boolean(detail.parsed_requirement);
  const hasScenarios = Boolean(detail.scenarios?.length);
  const hasReport = Boolean(primaryAnalysisReport);
  const preflightBlocking = Boolean(preflightResult?.blocking);
  const canExecute = isValidHttpUrl(detail.target_system) && !preflightBlocking;

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

  const scenarioPass = detail.execution_result?.scenario_results.filter((s) => s.status === "passed").length ?? 0;
  const scenarioFail = detail.execution_result?.scenario_results.filter((s) => s.status === "failed").length ?? 0;
  const scenarioTotal = detail.execution_result?.scenario_results.length ?? 0;
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
        <Tag color={value === "passed" ? "success" : value === "failed" ? "error" : value === "running" ? "processing" : "default"}>
          {value}
        </Tag>
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

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
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
        isTargetSystemValid={isValidHttpUrl(detail.target_system)}
        onToggleOverview={() => setShowTopOverview((prev) => !prev)}
        onRefresh={() => void load({ mode: "manual" })}
        onRunExecution={() => void runExecution()}
        onStopExecution={() => void stopCurrentExecution()}
      />

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

