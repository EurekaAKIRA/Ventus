import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useParams, useSearchParams } from "react-router-dom";
import { Button, Card, Empty, Progress, Space, Tag, Typography } from "antd";
import { chatWithTaskAgent } from "../api/tasks";
import TaskAgentPanel from "../components/TaskAgentPanel";
import type { TaskAgentTrackingContext, TaskDraftAgentPayload } from "../types";
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

const PRE_SETTLED_DETAIL_POLL_MS = 12000;

function buildTaskAgentTrackingContext(params: {
  detail: ExtendedTaskDetail;
  uiExecutionStatus: string;
  preflightBlocking: boolean;
  preflightResult: ReturnType<typeof useTaskExecution>["preflightResult"];
  executionExplanations: ReturnType<typeof useTaskExecution>["executionExplanations"];
  primaryAnalysisReport: ExtendedTaskDetail["analysis_report"] | undefined;
}): TaskAgentTrackingContext {
  const { detail, uiExecutionStatus, preflightBlocking, preflightResult, executionExplanations, primaryAnalysisReport } = params;
  const scenarioResults = detail.execution_result?.scenario_results ?? [];
  const failedScenarios = scenarioResults.filter((item) => item.status === "failed");
  const failedSteps = failedScenarios.flatMap((scenario) =>
    (scenario.steps ?? [])
      .filter((step) => step.status === "failed")
      .map((step) => ({
        scenario: scenario.scenario_name || scenario.name || scenario.scenario_id,
        step_id: step.step_id,
        text: step.text,
        message: step.message,
        error_category: step.error_category,
      })),
  );
  return {
    task_id: detail.task_context.task_id,
    task_name: detail.task_context.task_name,
    task_status: detail.task_context.status,
    execution_status: uiExecutionStatus,
    environment: detail.environment,
    target_system: detail.target_system,
    scenario_total: scenarioResults.length,
    scenario_passed: scenarioResults.filter((item) => item.status === "passed").length,
    scenario_failed: failedScenarios.length,
    failed_scenarios: failedScenarios.slice(0, 5).map((item) => ({
      scenario_id: item.scenario_id,
      name: item.scenario_name || item.name,
      failed_steps: item.failed_steps,
      duration_ms: item.duration_ms,
    })),
    failed_steps: failedSteps.slice(0, 5),
    latest_logs: (detail.execution_result?.logs ?? []).slice(-5),
    validation_passed: detail.validation_report?.passed,
    validation_errors: detail.validation_report?.errors ?? [],
    validation_warnings: detail.validation_report?.warnings ?? [],
    analysis_findings: primaryAnalysisReport?.findings ?? [],
    failure_reasons: ((primaryAnalysisReport as { failure_reasons?: string[] } | undefined)?.failure_reasons ?? []),
    preflight_blocking: preflightBlocking,
    preflight_issues: preflightResult?.blocking_issues ?? [],
    execution_explanations: executionExplanations ?? undefined,
  };
}

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
    not_started: "未执行",
  };
  return labels[status] || status || "-";
}

function taskAgentStatusColor(status: string) {
  if (status === "passed") return "success";
  if (status === "failed" || status === "stopped") return "error";
  if (status === "running") return "processing";
  if (status === "not_started" || status === "pending") return "default";
  return "warning";
}

function buildTaskAgentExecutionSummary(params: {
  taskName: string;
  executionStatus: string;
  scenarioTotal: number;
  scenarioPass: number;
  scenarioFail: number;
  preflightBlocking: boolean;
  canExecute: boolean;
  failureReasons: string[];
}): string {
  const { taskName, executionStatus, scenarioTotal, scenarioPass, scenarioFail, preflightBlocking, canExecute, failureReasons } = params;
  const displayName = taskName ? `“${taskName}”` : "当前任务";
  if (executionStatus === "running") {
    return [
      `我正在跟踪任务 ${displayName}。`,
      `执行状态：执行中。当前已收到 ${scenarioTotal} 个场景结果，通过 ${scenarioPass} 个，失败 ${scenarioFail} 个。`,
      "执行结束后我会继续根据失败步骤、最新日志和断言结果给你定位建议。",
    ].join("\n");
  }
  if (executionStatus === "passed") {
    return [
      `我正在跟踪任务 ${displayName}。`,
      `执行状态：已执行，结果通过。共 ${scenarioTotal} 个场景，通过 ${scenarioPass} 个，失败 ${scenarioFail} 个。`,
      "下一步可以补充边界、权限和异常参数覆盖，或把关键断言沉淀为回归用例。",
    ].join("\n");
  }
  if (executionStatus === "failed") {
    return [
      `我正在跟踪任务 ${displayName}。`,
      `执行状态：已执行，结果失败。共 ${scenarioTotal} 个场景，通过 ${scenarioPass} 个，失败 ${scenarioFail} 个。`,
      failureReasons.length ? `优先排查：${failureReasons.slice(0, 3).join("；")}。` : "你可以问我“失败原因”，我会结合失败步骤、日志和断言结果排查。",
    ].join("\n");
  }
  if (executionStatus === "stopped") {
    return [
      `我正在跟踪任务 ${displayName}。`,
      `执行状态：已停止。停止前已收到 ${scenarioTotal} 个场景结果，通过 ${scenarioPass} 个，失败 ${scenarioFail} 个。`,
      "下一步建议先确认停止原因，再决定继续执行或重跑冒烟链路。",
    ].join("\n");
  }
  return [
    `我正在跟踪任务 ${displayName}。`,
    "执行状态：尚未执行，因此还没有执行结果。",
    preflightBlocking
      ? "当前前置检查存在阻断项，建议先处理环境、鉴权或连通性问题。"
      : canExecute
        ? "当前看起来可以启动执行。你可以先跑前置检查，再执行主链路冒烟。"
        : "当前还不能判断可执行性，请先确认目标系统地址、环境配置和 DSL 是否已生成。",
  ].join("\n");
}

function taskAgentStageClass(status: string) {
  if (status === "finish") return " is-done";
  if (status === "process") return " is-current";
  if (status === "error") return " is-error";
  return "";
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
  const [taskAgentFloatingOpen, setTaskAgentFloatingOpen] = useState(false);
  const [taskAgentPayload, setTaskAgentPayload] = useState<TaskDraftAgentPayload | null>(null);
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
  const taskAgentTrackingContext = buildTaskAgentTrackingContext({
    detail,
    uiExecutionStatus,
    preflightBlocking,
    preflightResult,
    executionExplanations,
    primaryAnalysisReport,
  });
  const taskAgentRequirementText = (() => {
    const parsed = detail.parsed_requirement;
    if (!parsed) {
      return "";
    }
    return [
      parsed.objective,
      ...(parsed.actions ?? []),
      ...(parsed.expected_results ?? []),
      ...(parsed.constraints ?? []),
    ]
      .map((item) => String(item ?? "").trim())
      .filter(Boolean)
      .slice(0, 12)
      .join("\n");
  })();

  const handleTaskAgentChat = async (messageText: string) => {
    const result = await chatWithTaskAgent({
      message: messageText,
      task_id: detail.task_context.task_id,
      task_name: detail.task_context.task_name,
      requirement_text: taskAgentRequirementText,
      source_path: detail.task_context.source_path ?? undefined,
      target_system: resolvedBaseUrl || undefined,
      environment: detail.environment,
      project_id: detail.task_context.project_id,
      task_tracking: taskAgentTrackingContext,
    });
    if (result.agent_payload) {
      setTaskAgentPayload(result.agent_payload);
    }
    return { reply: result.reply, payload: result.agent_payload };
  };

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
  const taskAgentFailureReasons = (primaryAnalysisReport as { failure_reasons?: string[] } | undefined)?.failure_reasons ?? [];
  const taskAgentExecutionSummary = buildTaskAgentExecutionSummary({
    taskName: detail.task_context.task_name,
    executionStatus: uiExecutionStatus,
    scenarioTotal,
    scenarioPass,
    scenarioFail,
    preflightBlocking,
    canExecute,
    failureReasons: taskAgentFailureReasons,
  });
  const taskAgentEvidence = [
    hasParsedResult ? "需求解析结果" : "",
    hasScenarios ? `测试场景 ${detail.scenarios?.length ?? 0} 个` : "",
    detail.test_case_dsl?.scenarios?.length ? `DSL 场景 ${detail.test_case_dsl.scenarios.length} 个` : "",
    scenarioTotal ? `执行结果 ${scenarioPass}/${scenarioTotal}` : "",
    taskAgentFailureReasons.length ? `失败原因 ${taskAgentFailureReasons.length} 条` : "",
    preflightResult ? `前置检查：${preflightResult.overall_status}` : "",
    executionExplanations?.top_reasons?.length ? `失败归因 ${executionExplanations.top_reasons.length} 条` : "",
  ].filter(Boolean);
  const taskAgentQuickActions = [
    { label: "是否执行", message: "这个任务是否执行了，结果如何" },
    { label: "下一步", message: "当前任务下一步应该做什么" },
    { label: "失败原因", message: "当前任务失败原因是什么，如何修复", disabled: uiExecutionStatus !== "failed" && scenarioFail === 0 },
    { label: "补断言", message: "基于当前任务结果，还需要补哪些断言" },
    { label: "证据来源", message: "你判断当前任务状态和结果时参考了哪些依据" },
    { label: "重跑建议", message: "如果我要重跑这个任务，应该先处理哪些问题" },
  ];
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

      <div className={`create-task-agent-float task-detail-agent-float${taskAgentFloatingOpen ? " is-open" : ""}`}>
        {taskAgentFloatingOpen ? (
          <div className="create-task-agent-float__panel">
            <div className="create-task-agent-float__head">
              <Space size={8}>
                <Text strong>Agent 跟踪</Text>
                <Tag color={taskAgentStatusColor(uiExecutionStatus)}>
                  {executionStatusLabel(uiExecutionStatus)}
                </Tag>
                {scenarioTotal ? <Tag color={scenarioFail ? "error" : "success"}>{scenarioPass}/{scenarioTotal}</Tag> : null}
              </Space>
              <Button type="text" size="small" onClick={() => setTaskAgentFloatingOpen(false)}>
                收起
              </Button>
            </div>
            <div className="create-task-agent-float__body">
              <div className="task-detail-agent-brief">
                <div className="task-detail-agent-brief__status">
                  <div>
                    <span>当前结论</span>
                    <strong>{executionStatusLabel(uiExecutionStatus)}</strong>
                  </div>
                  {scenarioTotal ? (
                    <div>
                      <span>执行结果</span>
                      <strong>{scenarioPass}/{scenarioTotal}</strong>
                    </div>
                  ) : (
                    <div>
                      <span>执行结果</span>
                      <strong>暂无</strong>
                    </div>
                  )}
                </div>
                <div className="task-detail-agent-flow">
                  {steps.map((item) => (
                    <span key={item.title} className={`task-detail-agent-flow__item${taskAgentStageClass(String(item.status))}`}>
                      {item.title}
                    </span>
                  ))}
                </div>
                <div className="task-detail-agent-actions">
                  <Button size="small" loading={refreshing} onClick={() => void load({ mode: "manual" })}>
                    刷新状态
                  </Button>
                  <Button size="small" loading={preflightLoading} onClick={() => void runPreflightCheck()}>
                    前置检查
                  </Button>
                  <Button size="small" type="primary" loading={executing} disabled={!canExecute || uiExecutionStatus === "running"} onClick={() => void runExecution()}>
                    启动执行
                  </Button>
                  <Button size="small" danger loading={stopping} disabled={uiExecutionStatus !== "running" || stopping || executing} onClick={() => void stopCurrentExecution()}>
                    停止执行
                  </Button>
                  <Button
                    size="small"
                    onClick={() => {
                      const nextParams = new URLSearchParams(searchParams);
                      nextParams.set("tab", "execution");
                      setSearchParams(nextParams, { replace: true });
                    }}
                  >
                    查看执行
                  </Button>
                  <Button
                    size="small"
                    onClick={() => {
                      const nextParams = new URLSearchParams(searchParams);
                      nextParams.set("tab", "report");
                      setSearchParams(nextParams, { replace: true });
                    }}
                  >
                    查看报告
                  </Button>
                  <Button
                    size="small"
                    disabled={uiExecutionStatus !== "failed" && scenarioFail === 0}
                    loading={explanationsLoading}
                    onClick={() => {
                      void loadExecutionExplanations();
                      const nextParams = new URLSearchParams(searchParams);
                      nextParams.set("tab", "report");
                      setSearchParams(nextParams, { replace: true });
                    }}
                  >
                    失败归因
                  </Button>
                </div>
                {taskAgentEvidence.length ? (
                  <div className="task-detail-agent-evidence">
                    <span>依据</span>
                    <div>
                      {taskAgentEvidence.map((item) => (
                        <Tag key={item}>{item}</Tag>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
              <TaskAgentPanel
                payload={taskAgentPayload}
                onSendMessage={handleTaskAgentChat}
                initialMessage={taskAgentExecutionSummary}
                quickActions={taskAgentQuickActions}
              />
            </div>
          </div>
        ) : (
          <button
            type="button"
            className={`create-task-agent-float__toggle${uiExecutionStatus === "running" || scenarioFail ? " has-badge" : ""}`}
            onClick={() => setTaskAgentFloatingOpen(true)}
          >
            <span>{executionStatusLabel(uiExecutionStatus)}</span>
            {scenarioFail ? <strong>{scenarioFail}</strong> : uiExecutionStatus === "running" ? <strong>RUN</strong> : null}
          </button>
        )}
      </div>

    </Space>
  );
}
