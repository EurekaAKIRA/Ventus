import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useParams, useSearchParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Empty,
  Input,
  List,
  Progress,
  Row,
  Space,
  Spin,
  Steps,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import {
  fetchExecutionExplanations,
  fetchAnalysisReport,
  fetchDsl,
  fetchExecution,
  fetchFeatureText,
  fetchPreflightCheck,
  fetchRegressionDiff,
  fetchRetrievedContext,
  fetchScenarios,
  fetchTaskArtifactContent,
  fetchTaskArtifacts,
  fetchTaskDetail,
  fetchTaskDashboard,
  fetchValidationReport,
  refreshTaskParse,
  startExecution,
  stopExecution,
} from "../api/tasks";
import type {
  ExecutionExplanationPayload,
  PreflightCheckPayload,
  RegressionDiffPayload,
  TaskArtifactContent,
  TaskArtifactItem,
  TaskDashboardPayload,
  TaskDetailPayload,
} from "../types";
import JsonViewer from "../components/JsonViewer";
import LogPanel from "../components/LogPanel";
import MetricCard from "../components/MetricCard";
import StatusTag from "../components/StatusTag";

const { Title, Text } = Typography;
const FEATURE_PREVIEW_LINES = 18;
const DSL_PREVIEW_SCENARIOS = 4;
const API_BASE_URL = (import.meta.env.VITE_PLATFORM_API_BASE as string | undefined)?.trim() || "http://127.0.0.1:8001";
const TAB_KEYS = ["parsed", "scenario", "dsl", "execution", "report", "artifacts"] as const;
type TaskDetailTabKey = (typeof TAB_KEYS)[number];

type ExtendedTaskDetail = TaskDetailPayload & {
  target_system?: string;
  environment?: string;
};

type ChartDatum = {
  key: string;
  label: string;
  value: number;
};

type ParsedFeatureLine = {
  badge?: string;
  color?: string;
  content: string;
  secondary?: string;
  strong?: boolean;
  priority?: string;
  hideMarker?: boolean;
};

type ExecutionCaseRow = {
  key: string;
  id: string;
  name: string;
  testPoint: string;
  priority: string;
  status: string;
  durationMs: number;
  failedSteps: number;
  stepProgress: number;
  stepProgressText: string;
  currentStep: string;
};

type StreamStepTracker = {
  completedStepIds: Set<string>;
  currentStepId?: string;
  currentStepMessage?: string;
  scenarioStatus?: string;
};

type LoadMode = "initial" | "manual" | "silent";
type StageKey = "basic" | "artifacts" | "dashboard";
type StageStatus = "wait" | "process" | "finish" | "error";

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

function isValidHttpUrl(value: string | undefined | null): boolean {
  if (!value) {
    return false;
  }
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

function normalizeStatus(status: string | undefined): string {
  if (!status) {
    return "received";
  }
  return status === "scenario_generated" ? "generated" : status;
}

function flattenNumericEntries(input: unknown, prefix = ""): ChartDatum[] {
  if (!input || typeof input !== "object") {
    return [];
  }
  const entries = Object.entries(input as Record<string, unknown>);
  const result: ChartDatum[] = [];
  entries.forEach(([key, value]) => {
    const nextKey = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "number" && Number.isFinite(value)) {
      result.push({ key: nextKey, label: nextKey, value });
      return;
    }
    if (value && typeof value === "object" && !Array.isArray(value)) {
      result.push(...flattenNumericEntries(value, nextKey));
    }
  });
  return result;
}

function parseFeatureLine(rawLine: string): ParsedFeatureLine {
  const line = rawLine.trim();
  if (!line) {
    return { content: " " };
  }

  const featureMatch = line.match(/^Feature:\s*(.+)$/i);
  if (featureMatch) {
    return {
      badge: "功能",
      color: "blue",
      content: featureMatch[1],
      strong: true,
    };
  }

  const backgroundMatch = line.match(/^Background:\s*(.+)$/i);
  if (backgroundMatch) {
    return {
      badge: "背景",
      color: "geekblue",
      content: backgroundMatch[1],
      strong: true,
    };
  }

  const scenarioMatch = line.match(/^Scenario:\s*(.+)$/i);
  if (scenarioMatch) {
    return {
      badge: "场景",
      color: "purple",
      content: scenarioMatch[1],
      strong: true,
    };
  }

  const scenarioOutlineMatch = line.match(/^Scenario Outline:\s*(.+)$/i);
  if (scenarioOutlineMatch) {
    return {
      badge: "场景模板",
      color: "magenta",
      content: scenarioOutlineMatch[1],
      strong: true,
    };
  }

  const examplesMatch = line.match(/^Examples:\s*(.*)$/i);
  if (examplesMatch) {
    return {
      badge: "示例",
      color: "cyan",
      content: examplesMatch[1] || "参数样例",
      strong: true,
    };
  }

  const stepMatch = line.match(/^(Given|When|Then|And|But)\s+(.+)$/i);
  if (stepMatch) {
    const keyword = stepMatch[1].toLowerCase();
    const mapping: Record<string, { label: string; color: string }> = {
      given: { label: "前置", color: "default" },
      when: { label: "操作", color: "processing" },
      then: { label: "断言", color: "success" },
      and: { label: "并且", color: "gold" },
      but: { label: "但是", color: "warning" },
    };
    return {
      badge: mapping[keyword]?.label ?? stepMatch[1],
      color: mapping[keyword]?.color ?? "default",
      content: stepMatch[2],
      strong: keyword === "then",
    };
  }

  const commentMatch = line.match(/^#\s*(.+)$/);
  if (commentMatch) {
    const priorityMatch = commentMatch[1].match(/^priority\s*:\s*(P\d+)/i);
    if (priorityMatch) {
      return {
        content: "",
        priority: priorityMatch[1].toUpperCase(),
        hideMarker: true,
      };
    }
    return {
      badge: "备注",
      color: "default",
      content: commentMatch[1],
      secondary: "注释信息",
    };
  }

  return {
    content: line,
  };
}

function resolveTabKey(value: string | null): TaskDetailTabKey {
  if (value && (TAB_KEYS as readonly string[]).includes(value)) {
    return value as TaskDetailTabKey;
  }
  return "parsed";
}

function deriveExecutionStatus(detail?: ExtendedTaskDetail | null): string {
  if (!detail) return "not_started";
  const executionStatus = normalizeStatus(detail.execution_result?.status);
  if (executionStatus && executionStatus !== "received") {
    return executionStatus;
  }
  const taskStatus = normalizeStatus(detail.task_context?.status);
  if (["running", "passed", "failed", "stopped"].includes(taskStatus)) {
    return taskStatus;
  }
  return "not_started";
}

function isAnalyzingStatus(status: string | undefined): boolean {
  const normalized = normalizeStatus(status);
  return ["received", "parsed", "generated"].includes(normalized);
}

function parseStreamPayload(data: string): Record<string, unknown> | null {
  try {
    const payload = JSON.parse(data);
    return payload && typeof payload === "object" ? (payload as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function toReadableText(input: unknown): string {
  if (typeof input === "string") {
    return input;
  }
  if (input && typeof input === "object") {
    const value = input as Record<string, unknown>;
    const preferred = value.label ?? value.category ?? value.reason ?? value.message;
    if (typeof preferred === "string" && preferred.trim()) {
      return preferred;
    }
    try {
      return JSON.stringify(value);
    } catch {
      return "[object]";
    }
  }
  return String(input ?? "-");
}

export default function TaskDetail() {
  const { taskId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
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
  const [executing, setExecuting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [pollingError, setPollingError] = useState<string | null>(null);
  const [featureExpanded, setFeatureExpanded] = useState(false);
  const [dslExpanded, setDslExpanded] = useState(false);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [preflightResult, setPreflightResult] = useState<PreflightCheckPayload | null>(null);
  const [preflightError, setPreflightError] = useState<string | null>(null);
  const [explanationsLoading, setExplanationsLoading] = useState(false);
  const [executionExplanations, setExecutionExplanations] = useState<ExecutionExplanationPayload | null>(null);
  const [explanationsError, setExplanationsError] = useState<string | null>(null);
  const [regressionLoading, setRegressionLoading] = useState(false);
  const [regressionDiff, setRegressionDiff] = useState<RegressionDiffPayload | null>(null);
  const [regressionError, setRegressionError] = useState<string | null>(null);
  const [streamEvents, setStreamEvents] = useState<Array<{ event: string; data: string; at: string }>>([]);
  const [streamStatus, setStreamStatus] = useState<"idle" | "connected" | "fallback">("idle");
  const [caseKeyword, setCaseKeyword] = useState("");
  const [selectedTestPoint, setSelectedTestPoint] = useState("all");
  const [showTopOverview, setShowTopOverview] = useState(false);
  const fromCreateFlow =
    searchParams.get("from") === "create" ||
    Boolean((location.state as { fromCreate?: boolean } | null)?.fromCreate);
  const executionStatus = deriveExecutionStatus(detail);

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
      setBootLoading(true);
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
            setStageError((error as Error).message || "加载任务基础信息失败");
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
        setDashboardLoadError("单任务看板暂不可用，已回退为基础报告视图。");
      }
    } catch (error) {
      if (isLatest()) {
        message.error((error as Error).message || "加载任务详情失败");
      }
    } finally {
      if (!isLatest()) {
        return;
      }
      if (mode === "initial") {
        setBootLoading(false);
      }
      if (mode === "manual") {
        setRefreshing(false);
        setRefreshStageText("");
      }
    }
  };

  useEffect(() => {
    setFeatureExpanded(false);
    setDslExpanded(false);
    setPreflightResult(null);
    setPreflightError(null);
    setExecutionExplanations(null);
    setExplanationsError(null);
    setRegressionDiff(null);
    setRegressionError(null);
    setStreamEvents([]);
    setStreamStatus("idle");
    setCaseKeyword("");
    setSelectedTestPoint("all");
    setShowTopOverview(false);
    setStageState(DEFAULT_STAGE_STATE);
    setStageError(null);
    setRefreshing(false);
    setRefreshStageText("");
    void load({ mode: "initial" });
  }, [taskId]);

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
      message.success("解析结果已刷新");
    } catch (error) {
      message.error((error as Error).message || "刷新解析结果失败");
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
      message.success("报告已刷新");
    } catch (error) {
      message.error((error as Error).message || "刷新报告失败");
    }
  };

  const runPreflightCheck = async (options?: { silent?: boolean }) => {
    setPreflightLoading(true);
    setPreflightError(null);
    try {
      const result = await fetchPreflightCheck(taskId, {
        environment: detail?.environment || "test",
        checks: ["base_url_reachable", "auth_config_valid", "core_endpoints_reachable", "latency_budget"],
        latency_threshold_ms: 1500,
      });
      setPreflightResult(result);
      if (!options?.silent) {
        message.success("执行前检查完成");
      }
      return result;
    } catch (error) {
      setPreflightResult(null);
      setPreflightError((error as Error).message || "执行前检查暂不可用");
      return null;
    } finally {
      setPreflightLoading(false);
    }
  };

  const loadExecutionExplanations = async () => {
    setExplanationsLoading(true);
    setExplanationsError(null);
    try {
      const payload = await fetchExecutionExplanations(taskId, { top_n: 5 });
      setExecutionExplanations(payload);
    } catch (error) {
      setExecutionExplanations(null);
      const errorMessage = (error as Error).message || "";
      if (errorMessage.includes("HTTP 404")) {
        setExplanationsError(null);
      } else {
        setExplanationsError(errorMessage || "失败说明暂不可用");
      }
    } finally {
      setExplanationsLoading(false);
    }
  };

  const loadRegressionDiff = async () => {
    setRegressionLoading(true);
    setRegressionError(null);
    try {
      const payload = await fetchRegressionDiff(taskId);
      setRegressionDiff(payload);
    } catch (error) {
      setRegressionDiff(null);
      setRegressionError((error as Error).message || "回归对比暂不可用");
    } finally {
      setRegressionLoading(false);
    }
  };

  const runExecution = async () => {
    const targetSystem = detail?.target_system;
    if (!isValidHttpUrl(targetSystem)) {
      message.error("无法启动执行：请先配置合法的 target_system 地址");
      return;
    }

    let effectivePreflight = preflightResult;
    if (!effectivePreflight) {
      effectivePreflight = await runPreflightCheck({ silent: true });
    }
    if (effectivePreflight?.blocking) {
      message.error("执行前检查存在阻断项，请先处理后再启动执行");
      return;
    }

    setExecuting(true);
    try {
      await startExecution(taskId, { execution_mode: "api", environment: "test" });
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              execution_result: prev.execution_result
                ? {
                    ...prev.execution_result,
                    status: "running",
                  }
                : {
                    task_id: prev.task_context.task_id,
                    executor: "api-runner",
                    status: "running",
                    scenario_results: [],
                    metrics: {},
                    logs: [],
                  },
              task_context: { ...prev.task_context, status: "running" },
            }
          : prev,
      );
      setPollingError(null);
      message.success("执行已启动");
    } catch (error) {
      message.error((error as Error).message || "启动执行失败");
    } finally {
      setExecuting(false);
    }
  };

  const stopCurrentExecution = async () => {
    setStopping(true);
    try {
      await stopExecution(taskId);
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              execution_result: prev.execution_result
                ? {
                    ...prev.execution_result,
                    status: "stopped",
                    logs: [
                      ...prev.execution_result.logs,
                      {
                        time: new Date().toISOString(),
                        level: "WARN",
                        message: "用户已手动停止执行",
                      },
                    ],
                  }
                : prev.execution_result,
              task_context: { ...prev.task_context, status: "stopped" },
            }
          : prev,
      );
      message.success("执行已停止");
    } catch (error) {
      message.error((error as Error).message || "停止执行失败");
    } finally {
      setStopping(false);
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
        content: "读取产物失败，请重试",
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

  const onTabChange = (tab: string) => {
    const nextTab = resolveTabKey(tab);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("tab", nextTab);
    setSearchParams(nextParams, { replace: true });
  };

  useEffect(() => {
    if (executionStatus !== "running") {
      return;
    }

    const timer = window.setInterval(async () => {
      try {
        const executionResult = await fetchExecution(taskId);
        if (pollingError) {
          setPollingError(null);
        }
        setDetail((prev) =>
          prev
            ? {
                ...prev,
                execution_result: executionResult,
                task_context: { ...prev.task_context, status: executionResult.status },
              }
            : prev,
        );

        if (executionResult.status !== "running") {
          const [validationReport, analysisReport] = await Promise.all([
            fetchValidationReport(taskId),
            fetchAnalysisReport(taskId),
          ]);
          setDetail((prev) =>
            prev
              ? {
                  ...prev,
                  validation_report: validationReport,
                  analysis_report: analysisReport,
                }
              : prev,
          );
        }
      } catch {
        setPollingError("执行状态轮询失败，请稍后重试或手动刷新。");
      }
    }, 2500);

    return () => window.clearInterval(timer);
  }, [executionStatus, pollingError, taskId]);

  useEffect(() => {
    const hasFailedExecution = executionStatus === "failed";
    const hasPartialFailures = (detail?.execution_result?.scenario_results ?? []).some(
      (item) => item.status === "failed",
    );
    if (hasFailedExecution || hasPartialFailures) {
      void loadExecutionExplanations();
      void loadRegressionDiff();
    }
  }, [executionStatus, detail?.execution_result?.scenario_results, taskId]);

  useEffect(() => {
    if (executionStatus !== "running") {
      return;
    }
    const source = new EventSource(`${API_BASE_URL}/api/tasks/${taskId}/execution/stream`);
    source.onopen = () => setStreamStatus("connected");
    source.onerror = () => {
      setStreamStatus("fallback");
      source.close();
    };
    source.onmessage = (event) => {
      setStreamEvents((prev) => [
        ...prev.slice(-49),
        { event: "message", data: event.data, at: new Date().toISOString() },
      ]);
    };
    source.addEventListener("step_start", (event) => {
      setStreamEvents((prev) => [
        ...prev.slice(-49),
        { event: "step_start", data: (event as MessageEvent).data, at: new Date().toISOString() },
      ]);
    });
    source.addEventListener("step_end", (event) => {
      setStreamEvents((prev) => [
        ...prev.slice(-49),
        { event: "step_end", data: (event as MessageEvent).data, at: new Date().toISOString() },
      ]);
    });
    source.addEventListener("assertion_failed", (event) => {
      setStreamEvents((prev) => [
        ...prev.slice(-49),
        { event: "assertion_failed", data: (event as MessageEvent).data, at: new Date().toISOString() },
      ]);
    });
    source.addEventListener("execution_done", (event) => {
      setStreamEvents((prev) => [
        ...prev.slice(-49),
        { event: "execution_done", data: (event as MessageEvent).data, at: new Date().toISOString() },
      ]);
      source.close();
    });
    return () => source.close();
  }, [executionStatus, taskId]);

  const activeTabKey = resolveTabKey(searchParams.get("tab"));
  const shouldCompareLatest = searchParams.get("compare") === "latest";

  useEffect(() => {
    if (activeTabKey !== "report" || !shouldCompareLatest) {
      return;
    }
    if (!regressionDiff && !regressionLoading) {
      void loadRegressionDiff();
    }
  }, [activeTabKey, shouldCompareLatest, regressionDiff, regressionLoading, taskId]);

  const taskLifecycleStatus = normalizeStatus(detail?.task_context?.status);
  const shouldAutoRefreshCards =
    ["received", "parsed", "generated", "running"].includes(taskLifecycleStatus) ||
    executionStatus === "running";

  useEffect(() => {
    if (!detail || !shouldAutoRefreshCards) {
      return;
    }
    const timer = window.setInterval(() => {
      if (refreshing) {
        return;
      }
      void load({ mode: "silent" });
    }, 2500);
    return () => window.clearInterval(timer);
  }, [detail, shouldAutoRefreshCards, taskId, refreshing]);

  const primaryAnalysisReport = taskDashboard?.analysis_report ?? detail?.analysis_report;

  const qualityColor = useMemo(() => {
    const status = primaryAnalysisReport?.quality_status;
    if (status === "passed") return "success";
    if (status === "failed") return "error";
    return "default";
  }, [primaryAnalysisReport?.quality_status]);

  useEffect(() => {
    if (activeTabKey !== "execution") {
      return;
    }
    if (!isValidHttpUrl(detail?.target_system)) {
      return;
    }
    if (!preflightResult && !preflightLoading) {
      void runPreflightCheck({ silent: true });
    }
  }, [activeTabKey, detail?.target_system, preflightResult, preflightLoading, taskId]);

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
    if (!fromCreateFlow) {
      return <Spin size="large" style={{ display: "block", marginTop: 120 }} />;
    }
    const stageItems = [
      {
        title: STAGE_LABELS.basic,
        description: "任务元信息、状态、解析摘要",
        status: stageState.basic,
      },
      {
        title: STAGE_LABELS.artifacts,
        description: "DSL / Feature / 报告等产物入口",
        status: stageState.artifacts,
      },
      {
        title: STAGE_LABELS.dashboard,
        description: "执行摘要、分析图表、质量指标",
        status: stageState.dashboard,
      },
    ];

    return (
      <Card bordered={false}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Space direction="vertical" size={4}>
            <Title level={4} style={{ margin: 0 }}>
              任务详情加载中
            </Title>
            <Text type="secondary">
              {fromCreateFlow ? "任务已创建，正在准备详情数据。" : "正在加载任务详情，请稍候。"}
            </Text>
          </Space>
          <Steps direction="vertical" size="small" items={stageItems as unknown as Parameters<typeof Steps>[0]["items"]} />
          {stageError ? <Alert type="warning" showIcon message={stageError} /> : null}
          <Spin size="small" />
        </Space>
      </Card>
    );
  }

  if (!detail) {
    return <Empty description="任务不存在或响应为空" />;
  }

  const taskStatus = normalizeStatus(detail.task_context.status);
  const displayTaskStatus = executionStatus === "not_started" ? taskStatus : executionStatus;
  const uiExecutionStatus = executing ? "running" : executionStatus;
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
  const dslCases = detail.test_case_dsl?.scenarios ?? [];
  const streamStepTrackerMap = (() => {
    const tracker = new Map<string, StreamStepTracker>();
    streamEvents.forEach((evt) => {
      const payload = parseStreamPayload(evt.data);
      const scenarioId = typeof payload?.scenario_id === "string" ? payload.scenario_id : "";
      if (!scenarioId) {
        return;
      }
      const existing =
        tracker.get(scenarioId) ??
        ({
          completedStepIds: new Set<string>(),
        } as StreamStepTracker);
      const stepId = typeof payload?.step_id === "string" ? payload.step_id : undefined;
      const message = typeof payload?.message === "string" ? payload.message : undefined;
      const status = typeof payload?.status === "string" ? payload.status : undefined;
      if (evt.event === "step_start") {
        existing.currentStepId = stepId;
        existing.currentStepMessage = message;
      }
      if (evt.event === "step_result" || evt.event === "step_end") {
        if (stepId) {
          existing.completedStepIds.add(stepId);
        }
        if (status) {
          existing.scenarioStatus = status;
        }
        existing.currentStepId = undefined;
      }
      if (evt.event === "scenario_result" && status) {
        existing.scenarioStatus = status;
      }
      tracker.set(scenarioId, existing);
    });
    return tracker;
  })();
  const scenarioResultMap = new Map(
    (detail.execution_result?.scenario_results ?? []).map((item) => [item.scenario_id, item]),
  );
  const scenarioMetaMap = new Map((detail.scenarios ?? []).map((item) => [item.scenario_id, item]));
  const executionCaseRows: ExecutionCaseRow[] = dslCases.map((item) => {
    const result = scenarioResultMap.get(item.scenario_id);
    const meta = scenarioMetaMap.get(item.scenario_id);
    const stepTracker = streamStepTrackerMap.get(item.scenario_id);
    const testPoint = (meta?.goal || item.goal || "默认测试点").trim() || "默认测试点";
    const totalSteps = Array.isArray(item.steps) ? item.steps.length : 0;
    const completedFromTracker = stepTracker?.completedStepIds.size ?? 0;
    const completedFromResult =
      typeof result?.passed_steps === "number" && typeof result?.failed_steps === "number"
        ? result.passed_steps + result.failed_steps
        : Array.isArray((result as { steps?: unknown[] } | undefined)?.steps)
          ? ((result as { steps?: unknown[] }).steps?.length ?? 0)
          : 0;
    const completedSteps = Math.min(totalSteps || completedFromResult || completedFromTracker, Math.max(completedFromTracker, completedFromResult));
    const currentStepId = stepTracker?.currentStepId;
    const currentStep = currentStepId
      ? item.steps.find((step) => step.step_id === currentStepId)?.text || stepTracker?.currentStepMessage || currentStepId
      : stepTracker?.currentStepMessage || "-";
    const status =
      result?.status || stepTracker?.scenarioStatus || (uiExecutionStatus === "running" ? "queued" : "pending");
    const progressPercent = totalSteps > 0 ? Math.min(100, Math.round((completedSteps / totalSteps) * 100)) : status === "passed" ? 100 : 0;
    return {
      key: item.scenario_id,
      id: item.scenario_id,
      name: item.name || item.scenario_id,
      testPoint,
      priority: (item.priority || meta?.priority || "-").toUpperCase(),
      status,
      durationMs: result?.duration_ms ?? 0,
      failedSteps: result?.failed_steps ?? 0,
      stepProgress: progressPercent,
      stepProgressText: totalSteps > 0 ? `${completedSteps}/${totalSteps}` : "-",
      currentStep,
    };
  });
  const testPointGroups = Array.from(new Set(executionCaseRows.map((item) => item.testPoint)));
  const filteredExecutionCaseRows = executionCaseRows.filter((item) => {
    if (selectedTestPoint !== "all" && item.testPoint !== selectedTestPoint) {
      return false;
    }
    if (!caseKeyword.trim()) {
      return true;
    }
    const keyword = caseKeyword.trim().toLowerCase();
    return item.id.toLowerCase().includes(keyword) || item.name.toLowerCase().includes(keyword);
  });

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
          <Text type="secondary">{row.stepProgressText}</Text>
        </Space>
      ),
    },
    { title: "当前步骤", dataIndex: "currentStep", key: "currentStep", ellipsis: true, width: 260 },
    { title: "失败步骤", dataIndex: "failedSteps", key: "failedSteps", width: 110 },
  ];

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      {refreshing ? (
        <Card bordered={false}>
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            <Text strong>{refreshStatusText}</Text>
            <Progress
              percent={refreshProgressPercent}
              showInfo={false}
              size="small"
              status={hasStageError ? "exception" : "active"}
              strokeColor="#722ed1"
            />
            {stageError ? <Text type="danger">{stageError}</Text> : null}
          </Space>
        </Card>
      ) : null}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Title level={4} style={{ margin: 0 }}>
          任务详情
        </Title>
        <Space>
          <Button onClick={() => setShowTopOverview((prev) => !prev)}>
            {showTopOverview ? "收起概览" : "查看概览"}
          </Button>
          <Button loading={refreshing} disabled={refreshing} onClick={() => void load({ mode: "manual" })}>刷新</Button>
          <Button type="primary" loading={executing} onClick={runExecution} disabled={!canExecute || preflightLoading}>
            启动执行
          </Button>
          <Button
            danger
            loading={stopping}
            onClick={stopCurrentExecution}
            disabled={uiExecutionStatus !== "running" || stopping || executing}
          >
            停止执行
          </Button>
        </Space>
      </div>

      <Card bordered={false} bodyStyle={{ paddingTop: 12, paddingBottom: 12 }}>
        <Space wrap size={[12, 8]}>
          <Text type="secondary">当前状态</Text>
          <StatusTag status={uiExecutionStatus === "running" ? "running" : displayTaskStatus} />
          <Text type="secondary">场景数</Text>
          <Tag color="processing">{detail.scenarios?.length ?? 0}</Tag>
          {!isValidHttpUrl(detail.target_system) ? <Tag color="warning">target_system 待配置</Tag> : null}
          {preflightBlocking ? <Tag color="error">执行前检查阻断</Tag> : null}
        </Space>
      </Card>

      {showTopOverview ? (
      <>
      <Card bordered={false}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Steps items={steps as unknown as Parameters<typeof Steps>[0]["items"]} size="small" />
          {!isValidHttpUrl(detail.target_system) ? (
            <Alert
              type="warning"
              showIcon
              message="执行受阻"
              description="target_system 缺失或不合法，请先配置有效的 http(s) 地址"
            />
          ) : null}
          {preflightBlocking ? (
            <Alert
              type="error"
              showIcon
              message="执行已被前置检查阻断"
              description="请先处理阻断项后再启动执行。"
            />
          ) : null}
        </Space>
      </Card>

      <div className="metric-row">
            <MetricCard title="任务状态" value={uiExecutionStatus === "running" ? "running" : displayTaskStatus} color="#722ed1" />
        <MetricCard title="已解析" value={hasParsedResult ? "是" : "否"} color={hasParsedResult ? "#52c41a" : "#d48806"} />
        <MetricCard title="场景数量" value={detail.scenarios?.length ?? 0} color={hasScenarios ? "#52c41a" : "#d48806"} />
            <MetricCard title="执行状态" value={uiExecutionStatus} color={uiExecutionStatus === "failed" ? "#ff4d4f" : "#722ed1"} />
      </div>

      <Card bordered={false}>
        <Descriptions title="基本信息" bordered size="small" column={{ xs: 1, md: 2, lg: 3 }}>
          <Descriptions.Item label="任务名称">{detail.task_context.task_name}</Descriptions.Item>
          <Descriptions.Item label="任务 ID">{detail.task_context.task_id}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <StatusTag status={uiExecutionStatus === "running" ? "running" : displayTaskStatus} />
          </Descriptions.Item>
          <Descriptions.Item label="来源类型">{detail.task_context.source_type}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{new Date(detail.task_context.created_at).toLocaleString()}</Descriptions.Item>
          <Descriptions.Item label="语言">{detail.task_context.language}</Descriptions.Item>
          <Descriptions.Item label="target_system">{detail.target_system || "-"}</Descriptions.Item>
          <Descriptions.Item label="environment">{detail.environment || "-"}</Descriptions.Item>
        </Descriptions>
      </Card>
      </>
      ) : null}

      <Tabs
        activeKey={activeTabKey}
        onChange={onTabChange}
        items={[
          {
            key: "parsed",
            label: "解析",
            children: hasParsedResult ? (
              <Row gutter={[16, 16]}>
                <Col span={24}>
                  <Card bordered={false} title="结构化需求" extra={<Button size="small" onClick={refreshParsedSection}>刷新</Button>}>
                    <Space direction="vertical" size={12} style={{ width: "100%" }}>
                      <div>
                        <Text strong>目标：</Text>
                        <Text style={{ marginLeft: 8 }}>{detail.parsed_requirement?.objective || "-"}</Text>
                      </div>
                      <div>
                        <Text strong>关键动作：</Text>
                        <Text style={{ marginLeft: 8 }}>
                          {detail.parsed_requirement?.actions?.slice(0, 4).join("；") || "-"}
                        </Text>
                      </div>
                      <div>
                        <Text strong>预期结果：</Text>
                        <Text style={{ marginLeft: 8 }}>
                          {detail.parsed_requirement?.expected_results?.slice(0, 4).join("；") || "-"}
                        </Text>
                      </div>
                      <div>
                        <Text strong>歧义点：</Text>
                        <Text style={{ marginLeft: 8 }}>
                          {detail.parsed_requirement?.ambiguities?.length
                            ? detail.parsed_requirement.ambiguities.slice(0, 3).join("；")
                            : "无"}
                        </Text>
                      </div>
                      <Button size="small" onClick={() => openRawData("结构化需求（原始 JSON）", detail.parsed_requirement)}>
                        查看原始数据
                      </Button>
                    </Space>
                  </Card>
                </Col>
                <Col span={24}>
                  <Card bordered={false} title="检索上下文">
                    {detail.retrieved_context?.length ? (
                      <List
                        dataSource={detail.retrieved_context.slice(0, 5)}
                        renderItem={(item) => (
                          <List.Item>
                            <List.Item.Meta
                              title={<Space><Tag>{item.chunk_id}</Tag><Text>{item.section_title}</Text><Text type="secondary">score: {item.score}</Text></Space>}
                              description={<Space direction="vertical" size={2}><Text>{item.content}</Text><Text type="secondary">{item.source_file}</Text></Space>}
                            />
                          </List.Item>
                        )}
                      />
                    ) : (
                      <Empty description="暂无检索上下文" />
                    )}
                    {detail.retrieved_context?.length ? (
                      <Button
                        size="small"
                        onClick={() => openRawData("检索上下文（原始 JSON）", detail.retrieved_context)}
                      >
                        查看原始数据
                      </Button>
                    ) : null}
                  </Card>
                </Col>
              </Row>
            ) : (
              <div className="empty-tab"><Empty description="暂无解析结果" /></div>
            ),
          },
          {
            key: "scenario",
            label: "场景",
            children: detail.scenarios?.length ? (
              <Space direction="vertical" style={{ width: "100%" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <Text type="secondary">共 {detail.scenarios.length} 个场景，默认展示摘要。</Text>
                  <Button size="small" onClick={() => openRawData("场景列表（原始 JSON）", detail.scenarios)}>查看原始数据</Button>
                </div>
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <Button size="small" onClick={refreshScenarioSection}>刷新</Button>
                </div>
                {detail.scenarios.map((scenario) => (
                  <Card key={scenario.scenario_id} className="scenario-card" title={scenario.name} extra={<Tag color="purple">{scenario.priority}</Tag>} bordered={false}>
                    <p><Text strong>目标：</Text>{scenario.goal}</p>
                    <p><Text strong>前置条件：</Text>{scenario.preconditions.join("；") || "-"}</p>
                    <div style={{ marginTop: 8 }}>
                      <Text strong>步骤：</Text>
                      <div style={{ marginTop: 6 }}>
                        {scenario.steps.slice(0, 5).map((step, idx) => (
                          <div key={`${scenario.scenario_id}_${idx}`} className="step-item">
                            <span className="step-keyword">{step.type}</span>
                            <span>{step.text}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </Card>
                ))}
              </Space>
            ) : (
              <div className="empty-tab"><Empty description="暂无场景" /></div>
            ),
          },
          {
            key: "dsl",
            label: "DSL / Feature",
            children: (
              <Space direction="vertical" style={{ width: "100%" }}>
                <Card bordered={false} title="测试用例 DSL" extra={<Button size="small" onClick={refreshScenarioSection}>刷新</Button>}>
                  {detail.test_case_dsl ? (
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      <Text>DSL 版本：{detail.test_case_dsl.dsl_version}</Text>
                      <Text>执行模式：{detail.test_case_dsl.execution_mode}</Text>
                      <Text>场景数量：{detail.test_case_dsl.scenarios?.length ?? 0}</Text>
                      {dslDisplayScenarios.length ? (
                        <List
                          size="small"
                          bordered
                          dataSource={dslDisplayScenarios}
                          renderItem={(scenario) => (
                            <List.Item>
                              <Space direction="vertical" size={2} style={{ width: "100%" }}>
                                <Space>
                                  <Text strong>{scenario.name}</Text>
                                  {scenario.priority ? <Tag color="purple">{scenario.priority}</Tag> : null}
                                </Space>
                                <Text type="secondary">
                                  步骤数：{scenario.steps?.length ?? 0}
                                  {scenario.preconditions?.length ? `，前置条件：${scenario.preconditions.length}` : ""}
                                </Text>
                              </Space>
                            </List.Item>
                          )}
                        />
                      ) : null}
                      <Space>
                        {hasDslOverflow ? (
                          <Button size="small" onClick={() => setDslExpanded((prev) => !prev)}>
                            {dslExpanded ? "收起列表" : "展开列表"}
                          </Button>
                        ) : null}
                        <Button size="small" onClick={() => openRawData("DSL（原始 JSON）", detail.test_case_dsl)}>查看原始数据</Button>
                      </Space>
                      {hasDslOverflow ? (
                        <Text type="secondary">
                          当前为摘要视图（{DSL_PREVIEW_SCENARIOS} 个场景），可展开查看完整列表。
                        </Text>
                      ) : null}
                    </Space>
                  ) : (
                    <Empty description="暂无 DSL" />
                  )}
                </Card>

                <Card bordered={false} title="功能用例（Feature）">
                  {featureText ? (
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      <List
                        size="small"
                        bordered
                        dataSource={featureDisplayLines}
                        renderItem={(line) => {
                          const parsed = parseFeatureLine(line);
                          return (
                            <List.Item className="feature-pretty-item">
                              <Space align="start" size={10} style={{ width: "100%" }}>
                                {parsed.badge ? (
                                  <Tag color={parsed.color} className="feature-pretty-badge">
                                    {parsed.badge}
                                  </Tag>
                                ) : parsed.hideMarker ? null : (
                                  <span className="feature-pretty-dot" />
                                )}
                                <Space direction="vertical" size={2} style={{ width: "100%" }}>
                                  <Space align="start" style={{ width: "100%", justifyContent: "space-between" }}>
                                    {parsed.content ? (
                                      <Text strong={Boolean(parsed.strong)} className="feature-line-text">
                                        {parsed.content}
                                      </Text>
                                    ) : (
                                      <span />
                                    )}
                                    {parsed.priority ? (
                                      <Tag color="purple" className="feature-priority-tag">
                                        {parsed.priority}
                                      </Tag>
                                    ) : null}
                                  </Space>
                                  {parsed.secondary ? (
                                    <Text type="secondary">{parsed.secondary}</Text>
                                  ) : null}
                                </Space>
                              </Space>
                            </List.Item>
                          );
                        }}
                      />
                      <Space>
                        {hasFeatureOverflow ? (
                          <Button size="small" onClick={() => setFeatureExpanded((prev) => !prev)}>
                            {featureExpanded ? "收起文本" : "展开文本"}
                          </Button>
                        ) : null}
                        <Button
                          size="small"
                          onClick={() =>
                            openRawData("Feature 文本（源数据）", {
                              feature_text: featureText,
                            })
                          }
                        >
                          查看源数据
                        </Button>
                      </Space>
                      {hasFeatureOverflow ? (
                        <Text type="secondary">
                          当前为摘要视图（{FEATURE_PREVIEW_LINES} 行），可展开查看完整文本。
                        </Text>
                      ) : null}
                    </Space>
                  ) : (
                    <Empty description="暂无 Feature 文本" />
                  )}
                </Card>
              </Space>
            ),
          },
          {
            key: "execution",
            label: "执行",
            children: (
              <Space direction="vertical" style={{ width: "100%" }}>
                {pollingError ? <Alert type="warning" showIcon message="轮询异常" description={pollingError} /> : null}
                <Card bordered={false} title="执行前检查" extra={<Button size="small" loading={preflightLoading} onClick={() => void runPreflightCheck()}>执行前检查</Button>}>
                  {preflightError ? <Alert type="warning" showIcon message={preflightError} /> : null}
                  {preflightResult ? (
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      <Space>
                        <Text>检查结论：</Text>
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
                          message="建议处理"
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
                    <Text type="secondary">尚未执行检查；若检查接口暂未上线，仍可按当前逻辑执行。</Text>
                  )}
                </Card>
                <Card bordered={false} title="用例执行视图（Meter 风格）">
                  <Space direction="vertical" size={12} style={{ width: "100%" }}>
                    <Input
                      allowClear
                      placeholder="按 ID / 用例名称搜索"
                      value={caseKeyword}
                      onChange={(event) => setCaseKeyword(event.target.value)}
                    />
                    <div className="execution-split-view">
                      <div className="execution-point-sidebar">
                        <div
                          className={`execution-point-item ${selectedTestPoint === "all" ? "active" : ""}`}
                          onClick={() => setSelectedTestPoint("all")}
                        >
                          <span>全部测试点</span>
                          <Tag>{executionCaseRows.length}</Tag>
                        </div>
                        {testPointGroups.map((point) => (
                          <div
                            key={point}
                            className={`execution-point-item ${selectedTestPoint === point ? "active" : ""}`}
                            onClick={() => setSelectedTestPoint(point)}
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
                          locale={{ emptyText: "暂无可展示用例" }}
                        />
                      </div>
                    </div>
                  </Space>
                </Card>
                <Card
                  bordered={false}
                  title="执行结果"
                  extra={
                    <Button size="small" loading={refreshing} disabled={refreshing} onClick={() => void load({ mode: "manual" })}>
                      刷新
                    </Button>
                  }
                >
                  {detail.execution_result ? (
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      <Text>执行器：{detail.execution_result.executor || "-"}</Text>
                      <Text>当前状态：{detail.execution_result.status || "-"}</Text>
                      <Text>场景结果条目：{detail.execution_result.scenario_results?.length ?? 0}</Text>
                      <Button size="small" onClick={() => openRawData("执行结果（原始 JSON）", detail.execution_result)}>查看原始数据</Button>
                    </Space>
                  ) : (
                    <Alert type="info" showIcon message="尚未开始执行" />
                  )}
                </Card>
                <Card
                  bordered={false}
                  title="失败说明"
                  extra={<Button size="small" loading={explanationsLoading} onClick={() => void loadExecutionExplanations()}>刷新</Button>}
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
                              <Text type="secondary">次数：{group.count}</Text>
                            </Space>
                            {group.recommended_actions?.length ? (
                              <Text>{group.recommended_actions.join("；")}</Text>
                            ) : (
                              <Text type="secondary">暂无推荐动作</Text>
                            )}
                          </Space>
                        </List.Item>
                      )}
                    />
                  ) : (
                    <Text type="secondary">暂无失败说明数据。</Text>
                  )}
                </Card>
                <Card bordered={false} title="执行日志">
                  <LogPanel logs={detail.execution_result?.logs ?? []} />
                </Card>
              </Space>
            ),
          },
          {
            key: "report",
            label: "报告",
            children: (
              <Space direction="vertical" style={{ width: "100%" }}>
                {dashboardLoadError ? <Alert type="info" showIcon message={dashboardLoadError} /> : null}
                {taskDashboard ? (
                  <Card bordered={false} title="单任务看板摘要">
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      {taskDashboard.task_summary_text ? (
                        <Text>{taskDashboard.task_summary_text}</Text>
                      ) : (
                        <Text type="secondary">暂无摘要说明</Text>
                      )}
                      {taskDashboard.failure_reasons?.length ? (
                        <Space wrap>
                          {taskDashboard.failure_reasons.slice(0, 6).map((reason, idx) => (
                            <Tag color="volcano" key={`${toReadableText(reason)}_${idx}`}>{toReadableText(reason)}</Tag>
                          ))}
                        </Space>
                      ) : null}
                      <Button size="small" onClick={() => openRawData("单任务看板（原始 JSON）", taskDashboard)}>
                        查看原始数据
                      </Button>
                    </Space>
                  </Card>
                ) : null}
                <Card
                  bordered={false}
                  title="失败解释"
                  extra={<Button size="small" loading={explanationsLoading} onClick={() => void loadExecutionExplanations()}>刷新</Button>}
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
                              <Text type="secondary">次数：{group.count}</Text>
                            </Space>
                            {group.recommended_actions?.length ? (
                              <Text>{group.recommended_actions.join("；")}</Text>
                            ) : (
                              <Text type="secondary">暂无推荐动作</Text>
                            )}
                          </Space>
                        </List.Item>
                      )}
                    />
                  ) : (
                    <Text type="secondary">暂无失败解释数据。</Text>
                  )}
                </Card>
                <Card
                  bordered={false}
                  title="回归对比"
                  extra={<Button size="small" loading={regressionLoading} onClick={() => void loadRegressionDiff()}>对比最近一次</Button>}
                >
                  {shouldCompareLatest ? <Alert type="info" showIcon message="已从历史任务入口自动加载“最近一次回归对比”" /> : null}
                  {regressionError ? <Alert type="info" showIcon message={regressionError} /> : null}
                  {regressionDiff ? (
                    <Space direction="vertical" size={8}>
                      <Space>
                        <Text>结论：</Text>
                        <Tag color={regressionDiff.verdict === "improved" ? "success" : regressionDiff.verdict === "regressed" ? "error" : "default"}>
                          {regressionDiff.verdict || "unknown"}
                        </Tag>
                      </Space>
                      <Button size="small" onClick={() => openRawData("回归对比（原始 JSON）", regressionDiff)}>查看原始数据</Button>
                    </Space>
                  ) : (
                    <Text type="secondary">暂无回归对比数据。</Text>
                  )}
                </Card>
                <Card bordered={false} title="质量状态" extra={<Button size="small" onClick={refreshReportSection}>刷新</Button>}>
                  {primaryAnalysisReport ? (
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      <Space>
                        <Text>当前质量：</Text>
                        <Tag color={qualityColor}>{primaryAnalysisReport.quality_status}</Tag>
                      </Space>
                      <Text>任务：{primaryAnalysisReport.task_name}</Text>
                      <Button size="small" onClick={() => openRawData("分析报告（原始 JSON）", primaryAnalysisReport)}>查看原始数据</Button>
                    </Space>
                  ) : (
                    <Empty description="暂无分析报告" />
                  )}
                </Card>

                <Card bordered={false} title="图表视图（chart_data）">
                  {chartItems.length ? (
                    <Space direction="vertical" size={10} style={{ width: "100%" }}>
                      {chartItems.map((item) => (
                        <div key={item.key}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                            <Text>{item.label}</Text>
                            <Text strong>{item.value}</Text>
                          </div>
                        <Progress percent={Math.round((item.value / chartMax) * 100)} strokeColor="#722ed1" showInfo={false} />
                        </div>
                      ))}
                      <Button size="small" onClick={() => openRawData("chart_data（原始 JSON）", analysisChartData)}>查看原始数据</Button>
                    </Space>
                  ) : (
                    <Empty description="chart_data 暂无可展示数值" />
                  )}
                </Card>
              </Space>
            ),
          },
          {
            key: "artifacts",
            label: "产物",
            children: (
              <List
                grid={{ gutter: 16, xs: 1, md: 2, lg: 3 }}
                dataSource={artifacts}
                renderItem={(item) => (
                  <List.Item>
                    <Card className="artifact-card" bordered={false} title={item.label} onClick={() => void openArtifact(item)}>
                      <Text type="secondary">类型：{item.type}</Text>
                      <br />
                      <Text type="secondary">更新时间：{new Date(item.updated_at).toLocaleString()}</Text>
                    </Card>
                  </List.Item>
                )}
              />
            ),
          },
        ]}
      />

      <Drawer
        title={activeArtifact ? `产物：${activeArtifact.type}` : "产物"}
        open={artifactDrawerOpen}
        onClose={() => setArtifactDrawerOpen(false)}
        width={680}
      >
        {artifactLoading ? (
          <Spin />
        ) : !activeArtifact ? (
          <Empty description="暂无产物内容" />
        ) : typeof activeArtifact.content === "string" ? (
          <pre className="feature-text">{activeArtifact.content}</pre>
        ) : (
          <JsonViewer data={activeArtifact.content} />
        )}
      </Drawer>

      <Drawer
        title={rawDrawerTitle}
        open={rawDrawerOpen}
        onClose={() => setRawDrawerOpen(false)}
        width={760}
      >
        {rawDrawerData == null ? (
          <Empty description="暂无原始数据" />
        ) : typeof rawDrawerData === "string" ? (
          <pre className="feature-text raw-text-viewer">{rawDrawerData}</pre>
        ) : (
          <JsonViewer data={rawDrawerData} />
        )}
      </Drawer>

    </Space>
  );
}
