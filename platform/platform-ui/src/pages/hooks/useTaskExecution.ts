import { message } from "antd";
import { useEffect, useState } from "react";
import {
  fetchAnalysisReport,
  fetchExecution,
  fetchExecutionExplanations,
  fetchPreflightCheck,
  fetchRegressionDiff,
  fetchValidationReport,
  startExecution,
  stopExecution,
} from "../../api/tasks";
import type {
  ExecutionExplanationPayload,
  PreflightCheckPayload,
  RegressionDiffPayload,
} from "../../types";
import type { ExtendedTaskDetail } from "./useTaskDetailData";

const API_BASE_URL = (import.meta.env.VITE_PLATFORM_API_BASE as string | undefined)?.trim() || "http://127.0.0.1:8001";

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

export function useTaskExecution(params: {
  taskId: string;
  detail: ExtendedTaskDetail | null;
  setDetail: React.Dispatch<React.SetStateAction<ExtendedTaskDetail | null>>;
  executionStatus: string;
  activeTabKey: string;
  shouldCompareLatest: boolean;
}) {
  const { taskId, detail, setDetail, executionStatus, activeTabKey, shouldCompareLatest } = params;

  const [executing, setExecuting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [pollingError, setPollingError] = useState<string | null>(null);
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
        message.success("前置检查已完成");
      }
      return result;
    } catch (error) {
      setPreflightResult(null);
      setPreflightError((error as Error).message || "前置检查请求失败");
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
        setExplanationsError(errorMessage || "失败归因加载失败");
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
      setRegressionError((error as Error).message || "回归对比加载失败");
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
      message.success("执行任务已启动");
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
                        message: "执行已被用户手动停止",
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

  useEffect(() => {
    setPreflightResult(null);
    setPreflightError(null);
    setExecutionExplanations(null);
    setExplanationsError(null);
    setRegressionDiff(null);
    setRegressionError(null);
    setStreamEvents([]);
    setStreamStatus("idle");
    setPollingError(null);
    setExecuting(false);
    setStopping(false);
  }, [taskId]);

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
        setPollingError("执行状态轮询失败，正在等待下一次自动重试");
      }
    }, 2500);

    return () => window.clearInterval(timer);
  }, [executionStatus, pollingError, taskId, setDetail]);

  useEffect(() => {
    const hasFailedExecution = executionStatus === "failed";
    const hasPartialFailures = (detail?.execution_result?.scenario_results ?? []).some(
      (item) => item.status === "failed",
    );
    if (hasFailedExecution || hasPartialFailures) {
      void loadExecutionExplanations();
      if (activeTabKey === "report") {
        void loadRegressionDiff();
      }
    }
  }, [executionStatus, detail?.execution_result?.scenario_results, taskId, activeTabKey]);

  useEffect(() => {
    if (executionStatus !== "running" || activeTabKey !== "execution") {
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
  }, [executionStatus, taskId, activeTabKey]);

  useEffect(() => {
    if (activeTabKey !== "report" || !shouldCompareLatest) {
      return;
    }
    if (!regressionDiff && !regressionLoading) {
      void loadRegressionDiff();
    }
  }, [activeTabKey, shouldCompareLatest, regressionDiff, regressionLoading, taskId]);

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

  return {
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
  };
}
