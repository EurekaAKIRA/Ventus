import { message } from "antd";
import { useEffect, useRef, useState } from "react";
import {
  fetchAnalysisReport,
  fetchDsl,
  fetchFeatureText,
  fetchRetrievedContext,
  fetchScenarios,
  fetchTaskArtifactContent,
  fetchTaskArtifacts,
  fetchTaskDashboard,
  fetchTaskDetail,
  fetchValidationReport,
  refreshTaskParse,
} from "../../api/tasks";
import type {
  TaskArtifactContent,
  TaskArtifactItem,
  TaskDashboardPayload,
  TaskDetailPayload,
} from "../../types";

export type ExtendedTaskDetail = TaskDetailPayload & {
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

export function useTaskDetailData(params: { taskId: string; fromCreateFlow: boolean }) {
  const { taskId, fromCreateFlow } = params;
  const requestSeqRef = useRef(0);
  const activeRequestRef = useRef(0);

  const [bootLoading, setBootLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stageState, setStageState] = useState<Record<StageKey, StageStatus>>(DEFAULT_STAGE_STATE);
  const [stageError, setStageError] = useState<string | null>(null);
  const [refreshStageText, setRefreshStageText] = useState("");
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

  const load = async (options?: { mode?: LoadMode }) => {
    const mode = options?.mode ?? "initial";
    const requestId = ++requestSeqRef.current;
    activeRequestRef.current = requestId;
    const isLatest = () => activeRequestRef.current === requestId;
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
    } else if (mode === "manual") {
      setRefreshing(true);
      setRefreshStageText(`正在刷新：${STAGE_LABELS.basic}`);
      setStageState({ basic: "process", artifacts: "wait", dashboard: "wait" });
      setStageError(null);
    }

    try {
      const detailPromise = fetchTaskDetail(taskId)
        .then((value) => {
          if (mode !== "silent") {
            updateStage("basic", "finish");
            updateStage("artifacts", "process");
          }
          return value;
        })
        .catch((error) => {
          if (mode !== "silent" && isLatest()) {
            updateStage("basic", "error");
            setStageError((error as Error).message || "任务详情加载失败");
          }
          throw error;
        });
      const artifactPromise = fetchTaskArtifacts(taskId)
        .then((value) => {
          if (mode !== "silent") {
            updateStage("artifacts", "finish");
            updateStage("dashboard", "process");
          }
          return value;
        })
        .catch((error) => {
          if (mode !== "silent" && isLatest()) {
            updateStage("artifacts", "error");
          }
          throw error;
        });
      const dashboardPromise = fetchTaskDashboard(taskId)
        .then((value) => {
          if (mode !== "silent") {
            updateStage("dashboard", "finish");
          }
          return value;
        })
        .catch((error) => {
          if (mode !== "silent" && isLatest()) {
            updateStage("dashboard", "error");
          }
          throw error;
        });

      const [detailResult, artifactResult, dashboardResult] = await Promise.allSettled([
        detailPromise,
        artifactPromise,
        dashboardPromise,
      ]);

      if (!isLatest()) {
        return;
      }

      if (detailResult.status === "fulfilled") {
        setDetail(detailResult.value as ExtendedTaskDetail);
      } else {
        throw detailResult.reason;
      }

      if (artifactResult.status === "fulfilled") {
        setArtifacts(artifactResult.value);
      } else {
        setArtifacts([]);
      }

      if (dashboardResult.status === "fulfilled") {
        setTaskDashboard(dashboardResult.value);
        setDashboardLoadError(null);
      } else {
        setDashboardLoadError("任务看板加载失败，可稍后重试");
      }
    } catch (error) {
      if (isLatest()) {
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
  };

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
    void load({ mode: "initial" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId, fromCreateFlow]);

  const refreshParsedSection = async () => {
    try {
      const [{ parsed_requirement, parse_metadata }, retrievedContext] = await Promise.all([
        refreshTaskParse(taskId),
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
