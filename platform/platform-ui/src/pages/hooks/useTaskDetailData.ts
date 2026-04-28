import { message } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchAnalysisReport,
  fetchDsl,
  fetchFeatureText,
  fetchRetrievedContext,
  fetchScenarios,
  fetchTaskAnalysisProgress,
  fetchTaskArtifactContent,
  fetchTaskArtifacts,
  fetchTaskDashboard,
  fetchTaskDetail,
  fetchValidationReport,
  refreshTaskParse,
  startTaskAnalysis,
  DEFAULT_REQUIREMENT_RAG_ENABLED,
} from "../../api/tasks";
import type {
  AnalysisProgressPayload,
  TaskArtifactContent,
  TaskArtifactItem,
  TaskDashboardPayload,
  TaskDetailPayload,
} from "../../types";
import {
  fingerprintFromSummaryPayload,
  heavyContentSnapshot,
  mergeTaskDetailFromSummaryPreserveHeavy,
  normalizeStatus,
  shallowVisibleTaskDetailEqual,
} from "../taskDetailUtils";

export type ExtendedTaskDetail = TaskDetailPayload & {
  status?: string;
  target_system?: string;
  environment?: string;
};

export type LoadMode = "initial" | "manual" | "silent";
export type StageKey = "basic" | "artifacts" | "dashboard";
export type StageStatus = "wait" | "process" | "finish" | "error";

const STAGE_LABELS: Record<StageKey, string> = {
  basic: "任务基础信息",
  artifacts: "任务产物索引",
  dashboard: "单任务看板数据",
};

const DEFAULT_STAGE_STATE: Record<StageKey, StageStatus> = {
  basic: "wait",
  artifacts: "wait",
  dashboard: "wait",
};

const ANALYSIS_PROGRESS_POLL_MS = 250;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function isAnalysisCompleted(progress: AnalysisProgressPayload | null | undefined): boolean {
  if (!progress) {
    return false;
  }
  return progress.status === "completed" || progress.stage === "ready" || progress.percent >= 100;
}

function deriveCreateFlowStageState(progress: AnalysisProgressPayload | null | undefined): Record<StageKey, StageStatus> {
  if (!progress) {
    return { basic: "process", artifacts: "wait", dashboard: "wait" };
  }

  if (progress.status === "failed") {
    if (["queued", "input_normalized", "idle"].includes(progress.stage)) {
      return { basic: "error", artifacts: "wait", dashboard: "wait" };
    }
    if (["requirement_parsed", "scenarios_built", "dsl_ready"].includes(progress.stage)) {
      return { basic: "finish", artifacts: "error", dashboard: "wait" };
    }
    return { basic: "finish", artifacts: "finish", dashboard: "error" };
  }

  if (["analysis_report_ready", "ready"].includes(progress.stage) || isAnalysisCompleted(progress)) {
    return { basic: "finish", artifacts: "finish", dashboard: "process" };
  }

  if (["requirement_parsed", "scenarios_built", "dsl_ready"].includes(progress.stage)) {
    return { basic: "finish", artifacts: "process", dashboard: "wait" };
  }

  return { basic: "process", artifacts: "wait", dashboard: "wait" };
}

export function useTaskDetailData(params: { taskId: string; fromCreateFlow: boolean }) {
  const { taskId, fromCreateFlow } = params;
  const mountedRef = useRef(true);
  const requestSeqRef = useRef(0);
  const activeRequestRef = useRef(0);
  const detailRef = useRef<ExtendedTaskDetail | null>(null);
  const lastSilentSummaryFpRef = useRef("");
  const lastSilentHeavySnapRef = useRef("");
  const lastSilentArtifactsFpRef = useRef("");

  const [bootLoading, setBootLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stageState, setStageState] = useState<Record<StageKey, StageStatus>>(DEFAULT_STAGE_STATE);
  const [stageError, setStageError] = useState<string | null>(null);
  const [refreshStageText, setRefreshStageText] = useState("");
  const [analysisProgress, setAnalysisProgress] = useState<AnalysisProgressPayload | null>(null);
  const [detail, setDetail] = useState<ExtendedTaskDetail | null>(null);
  const [taskDashboard, setTaskDashboard] = useState<TaskDashboardPayload | null>(null);
  const [dashboardLoadError, setDashboardLoadError] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<TaskArtifactItem[]>([]);
  const [artifactLoading, setArtifactLoading] = useState(false);
  const [artifactDrawerOpen, setArtifactDrawerOpen] = useState(false);
  const [activeArtifact, setActiveArtifact] = useState<TaskArtifactContent | null>(null);
  const [rawDrawerOpen, setRawDrawerOpen] = useState(false);
  const [rawDrawerTitle, setRawDrawerTitle] = useState("原始数据");
  const [rawDrawerData, setRawDrawerData] = useState<unknown>(null);
  const [featureExpanded, setFeatureExpanded] = useState(false);
  const [dslExpanded, setDslExpanded] = useState(false);
  const [caseKeyword, setCaseKeyword] = useState("");
  const [selectedTestPoint, setSelectedTestPoint] = useState("all");
  const [showTopOverview, setShowTopOverview] = useState(false);

  useEffect(() => {
    detailRef.current = detail;
  }, [detail]);

  useEffect(
    () => {
      mountedRef.current = true;
      return () => {
        mountedRef.current = false;
        activeRequestRef.current = 0;
      };
    },
    [],
  );

  const resetSilentPollRefs = useCallback(() => {
    lastSilentSummaryFpRef.current = "";
    lastSilentHeavySnapRef.current = "";
    lastSilentArtifactsFpRef.current = "";
  }, []);

  const load = useCallback(async (options?: { mode?: LoadMode }) => {
    const mode = options?.mode ?? "initial";
    if (mode === "initial" || mode === "manual") {
      resetSilentPollRefs();
    }
    const requestId = ++requestSeqRef.current;
    activeRequestRef.current = requestId;
    const isLatest = () => mountedRef.current && activeRequestRef.current === requestId;
    const updateStage = (key: StageKey, status: StageStatus) => {
      if (!isLatest()) return;
      setStageState((prev) => ({ ...prev, [key]: status }));
      if (mode === "manual" && status === "process") {
        setRefreshStageText(`正在刷新：${STAGE_LABELS[key]}`);
      }
    };

    if (mode === "initial") {
      setBootLoading(fromCreateFlow);
      setRefreshing(!fromCreateFlow);
      setStageState({ basic: "process", artifacts: "wait", dashboard: "wait" });
      setStageError(null);
      setAnalysisProgress(null);
    } else if (mode === "manual") {
      setRefreshing(true);
      setRefreshStageText(`正在刷新：${STAGE_LABELS.basic}`);
      setStageState({ basic: "process", artifacts: "wait", dashboard: "wait" });
      setStageError(null);
    }

    try {
      if (mode === "initial" && fromCreateFlow) {
        const summary = (await fetchTaskDetail(taskId, { detailLevel: "summary" })) as ExtendedTaskDetail;
        if (!isLatest()) {
          return;
        }
        setDetail(summary);
        setBootLoading(false);
        setStageState({ basic: "finish", artifacts: "wait", dashboard: "wait" });

        setAnalysisProgress({
          task_id: taskId,
          kind: "analysis",
          stage: "queued",
          percent: 5,
          status: "running",
          message: "正在连接后台解析任务",
          updated_at: new Date().toISOString(),
        });

        let progress =
          (await fetchTaskAnalysisProgress(taskId).catch(() => null)) ??
          (await startTaskAnalysis(taskId));
        if (progress.status === "idle") {
          progress = await startTaskAnalysis(taskId);
        }
        if (!isLatest()) {
          return;
        }
        setAnalysisProgress(progress);
        setStageState(deriveCreateFlowStageState(progress));

        while (isLatest() && progress.status !== "failed" && !isAnalysisCompleted(progress)) {
          await delay(ANALYSIS_PROGRESS_POLL_MS);
          if (!isLatest()) {
            return;
          }
          try {
            progress = await fetchTaskAnalysisProgress(taskId);
          } catch (error) {
            if (isLatest()) {
              setStageError((error as Error).message || "解析进度加载失败，正在重试");
            }
            continue;
          }
          if (!isLatest()) {
            return;
          }
          setStageError(null);
          setAnalysisProgress(progress);
          setStageState(deriveCreateFlowStageState(progress));
        }

        if (!isLatest()) {
          return;
        }

        if (progress.status === "failed") {
          setStageError(progress.message || "任务解析失败");
          setStageState(deriveCreateFlowStageState(progress));
          return;
        }

        setAnalysisProgress({
          ...progress,
          message: "解析完成，正在装载详情页",
        });
        setStageState({ basic: "finish", artifacts: "process", dashboard: "wait" });

        void fetchTaskDetail(taskId, { detailLevel: "full" })
          .then((fullValue) => {
            if (!isLatest()) {
              return;
            }
            setDetail((prev) => ({ ...(prev ?? {}), ...fullValue }) as ExtendedTaskDetail);
          })
          .catch((error) => {
            if (!isLatest()) {
              return;
            }
            setStageError((prev) => prev ?? ((error as Error)?.message || "任务详情装载失败"));
          });

        void fetchTaskArtifacts(taskId, { shallow: true })
          .then((artifactList) => {
            if (!isLatest()) {
              return;
            }
            setArtifacts(artifactList);
            setStageState((prev) => ({
              ...prev,
              artifacts: "finish",
              dashboard: prev.dashboard === "wait" ? "process" : prev.dashboard,
            }));
          })
          .catch((error) => {
            if (!isLatest()) {
              return;
            }
            setArtifacts([]);
            setStageState((prev) => ({
              ...prev,
              artifacts: "error",
              dashboard: prev.dashboard === "wait" ? "process" : prev.dashboard,
            }));
            setStageError((prev) => prev ?? ((error as Error)?.message || "产物索引加载失败"));
          });

        void fetchTaskDashboard(taskId)
          .then((dashboardValue) => {
            if (!isLatest()) {
              return;
            }
            setTaskDashboard(dashboardValue);
            setDashboardLoadError(null);
            setStageState((prev) => ({ ...prev, dashboard: "finish" }));
          })
          .catch((error) => {
            if (!isLatest()) {
              return;
            }
            setDashboardLoadError("任务看板加载失败，可稍后重试");
            setStageState((prev) => ({ ...prev, dashboard: "error" }));
            setStageError((prev) => prev ?? ((error as Error)?.message || "任务看板加载失败"));
          });
        return;
      }

      const detailPromise = fetchTaskDetail(taskId, { detailLevel: "summary" }).catch((error) => {
        if (mode !== "silent" && isLatest()) {
          updateStage("basic", "error");
          setStageError((error as Error).message || "任务详情加载失败");
        }
        throw error;
      });
      const artifactPromise = fetchTaskArtifacts(taskId, { shallow: true }).catch((error) => {
        if (mode !== "silent" && isLatest()) {
          updateStage("artifacts", "error");
        }
        throw error;
      });

      const summary = (await detailPromise) as ExtendedTaskDetail;
      if (!isLatest()) {
        return;
      }

      setDetail(summary);
      if (mode !== "silent") {
        updateStage("basic", "finish");
      }

      void fetchTaskDetail(taskId, { detailLevel: "full" })
        .then((full) => {
          if (!isLatest()) {
            return;
          }
          setDetail((prev) => ({ ...(prev ?? {}), ...full }) as ExtendedTaskDetail);
        })
        .catch(() => undefined);

      if (mode !== "silent") {
        updateStage("dashboard", "process");
      }

      void fetchTaskDashboard(taskId)
        .then((value) => {
          if (!isLatest()) {
            return;
          }
          setTaskDashboard(value);
          setDashboardLoadError(null);
          if (mode !== "silent") {
            updateStage("dashboard", "finish");
          }
        })
        .catch(() => {
          if (!isLatest()) {
            return;
          }
          setDashboardLoadError("任务看板加载失败，可稍后重试");
          if (mode !== "silent") {
            updateStage("dashboard", "error");
          }
        });

      try {
        const artifactList = await artifactPromise;
        if (!isLatest()) {
          return;
        }
        setArtifacts(artifactList);
        if (mode !== "silent") {
          updateStage("artifacts", "finish");
        }
      } catch {
        if (!isLatest()) {
          return;
        }
        setArtifacts([]);
        if (mode !== "silent") {
          updateStage("artifacts", "error");
        }
      }
    } catch (error) {
      if (isLatest()) {
        setStageError((error as Error).message || "任务详情加载失败");
        message.error((error as Error).message || "任务详情加载失败");
      }
    } finally {
      if (!isLatest()) {
        return;
      }
      if (mode === "initial") {
        setBootLoading(false);
      }
      if (mode === "manual" || mode === "initial") {
        setRefreshing(false);
        setRefreshStageText("");
      }
    }
  }, [taskId, fromCreateFlow, resetSilentPollRefs]);

  const silentPollBeforeSettled = useCallback(async () => {
    if (!taskId) {
      return;
    }
    const prev = detailRef.current;
    if (!prev) {
      return;
    }

    let summary: ExtendedTaskDetail;
    try {
      summary = await fetchTaskDetail(taskId, { detailLevel: "summary" });
    } catch {
      return;
    }

    const fp = fingerprintFromSummaryPayload(summary);
    const fpChanged = fp !== lastSilentSummaryFpRef.current;
    const merged = mergeTaskDetailFromSummaryPreserveHeavy(prev, summary);
    const normalizedLife = normalizeStatus(merged.task_context?.status);
    const needsHeavy =
      fpChanged ||
      normalizedLife === "parsed" ||
      (normalizedLife === "generated" && !(merged.scenarios?.length));

    lastSilentSummaryFpRef.current = fp;

    if (!needsHeavy) {
      if (!shallowVisibleTaskDetailEqual(prev, merged)) {
        setDetail(merged);
      }
      return;
    }

    let full: ExtendedTaskDetail;
    try {
      full = await fetchTaskDetail(taskId, { detailLevel: "full" });
    } catch {
      if (!shallowVisibleTaskDetailEqual(prev, merged)) {
        setDetail(merged);
      }
      return;
    }

    const next = { ...merged, ...full } as ExtendedTaskDetail;
    const snap = heavyContentSnapshot(next);
    const redundant = snap === lastSilentHeavySnapRef.current && shallowVisibleTaskDetailEqual(prev, next);
    if (!redundant) {
      lastSilentHeavySnapRef.current = snap;
      setDetail(next);
    }

    try {
      const arts = await fetchTaskArtifacts(taskId, { shallow: true });
      const artsFp = arts.map((a) => a.type).join(",");
      if (artsFp !== lastSilentArtifactsFpRef.current) {
        lastSilentArtifactsFpRef.current = artsFp;
        setArtifacts(arts);
      }
    } catch {
    }
  }, [taskId]);

  useEffect(() => {
    setFeatureExpanded(false);
    setDslExpanded(false);
    setCaseKeyword("");
    setSelectedTestPoint("all");
    setShowTopOverview(false);
    setStageState(DEFAULT_STAGE_STATE);
    setStageError(null);
    setBootLoading(fromCreateFlow);
    setRefreshing(false);
    setRefreshStageText("");
    setAnalysisProgress(null);
    setDetail(null);
    setTaskDashboard(null);
    setDashboardLoadError(null);
    setArtifacts([]);
    resetSilentPollRefs();
    void load({ mode: "initial" });
  }, [taskId, fromCreateFlow, load, resetSilentPollRefs]);

  const refreshParsedSection = async () => {
    try {
      const meta = detail?.parse_metadata;
      const rag_enabled =
        meta?.rag_enabled ??
        meta?.rag_used ??
        detail?.task_context?.rag_enabled ??
        DEFAULT_REQUIREMENT_RAG_ENABLED;
      const [{ parsed_requirement, parse_metadata }, retrievedContext] = await Promise.all([
        refreshTaskParse(taskId, { rag_enabled }),
        fetchRetrievedContext(taskId),
      ]);
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              parsed_requirement,
              parse_metadata: parse_metadata ?? prev.parse_metadata,
              retrieved_context: retrievedContext,
            }
          : prev,
      );
      message.success("解析信息已刷新");
    } catch (error) {
      message.error((error as Error).message || "刷新解析信息失败");
    }
  };

  const refreshScenarioSection = async () => {
    try {
      const [scenariosData, dsl, feature] = await Promise.all([
        fetchScenarios(taskId),
        fetchDsl(taskId),
        fetchFeatureText(taskId),
      ]);
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              scenarios: scenariosData,
              test_case_dsl: dsl,
              feature_text: feature,
            }
          : prev,
      );
      setFeatureExpanded(false);
      setDslExpanded(false);
      message.success("场景与 DSL 已刷新");
    } catch (error) {
      message.error((error as Error).message || "刷新场景与 DSL 失败");
    }
  };

  const refreshReportSection = async () => {
    try {
      const [validationReport, analysisReport] = await Promise.all([
        fetchValidationReport(taskId),
        fetchAnalysisReport(taskId),
      ]);
      const dashboardResult = await fetchTaskDashboard(taskId).catch(() => null);
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              validation_report: validationReport,
              analysis_report: analysisReport,
            }
          : prev,
      );
      if (dashboardResult) {
        setTaskDashboard(dashboardResult);
        setDashboardLoadError(null);
      }
      message.success("报告数据已刷新");
    } catch (error) {
      message.error((error as Error).message || "刷新报告数据失败");
    }
  };

  const openArtifact = async (artifact: TaskArtifactItem) => {
    setArtifactDrawerOpen(true);
    setArtifactLoading(true);
    try {
      const content = await fetchTaskArtifactContent(taskId, artifact.type);
      setActiveArtifact(content);
    } catch {
      setActiveArtifact({
        type: artifact.type,
        content: "产物内容加载失败",
      });
    } finally {
      setArtifactLoading(false);
    }
  };

  const openRawData = (title: string, data: unknown) => {
    setRawDrawerTitle(title);
    setRawDrawerData(data);
    setRawDrawerOpen(true);
  };

  return {
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
  };
}
