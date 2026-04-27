import { useMemo } from "react";
import type { ExecutionScenarioResult, ScenarioModel, TestCaseDslScenario, TestCaseStep } from "../../types";
import type { ExtendedTaskDetail } from "./useTaskDetailData";

export type ExecutionCaseStepRow = {
  key: string;
  stepId: string;
  text: string;
  status: string;
  message: string;
  requestText: string;
  responseText: string;
};

export type ExecutionCaseRow = {
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
  steps: ExecutionCaseStepRow[];
};

type StreamStepTracker = {
  completedStepIds: Set<string>;
  failedStepIds: Set<string>;
  stepStatusById: Map<string, string>;
  stepMessageById: Map<string, string>;
  currentStepId?: string;
  currentStepMessage?: string;
  scenarioStatus?: string;
};

const LIVE_FINAL_STATUSES = new Set(["passed", "failed", "stopped"]);
const STEP_PHASE_LABEL: Record<string, string> = {
  step_start: "准备执行",
  request_prepared: "请求已发出",
  response_received: "已收到响应",
  context_saved: "上下文已保存",
  assertions_evaluated: "断言已评估",
};

function parseStreamPayload(data: string): Record<string, unknown> | null {
  try {
    const payload = JSON.parse(data);
    return payload && typeof payload === "object" ? (payload as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function stringifySummary(input: unknown) {
  if (!input || typeof input !== "object") {
    return "-";
  }
  const record = input as Record<string, unknown>;
  const method = typeof record.method === "string" ? record.method : "";
  const url = typeof record.url === "string" ? record.url : "";
  const statusCode = typeof record.status_code === "number" || typeof record.status_code === "string" ? String(record.status_code) : "";
  const rootType = typeof record.root_type === "string" ? record.root_type : "";
  const pieces = [method, url, statusCode ? `HTTP ${statusCode}` : "", rootType ? `body=${rootType}` : ""].filter(Boolean);
  if (pieces.length) {
    return pieces.join(" ");
  }
  try {
    return JSON.stringify(input);
  } catch {
    return String(input);
  }
}

function buildStepRows(
  scenario: TestCaseDslScenario,
  result: ExecutionScenarioResult | undefined,
  tracker: StreamStepTracker | undefined,
  isLive: boolean,
): ExecutionCaseStepRow[] {
  const resultSteps = Array.isArray(result?.steps) ? result.steps : [];
  const resultStepMap = new Map(resultSteps.map((item) => [String(item.step_id || ""), item]));
  const dslSteps: TestCaseStep[] = Array.isArray(scenario.steps) ? scenario.steps : [];
  return dslSteps.map((step, index) => {
    const stepId = step.step_id || `step_${index + 1}`;
    const resultStep = resultStepMap.get(stepId);
    const liveStatus = tracker?.stepStatusById.get(stepId);
    const fallbackStatus = isLive ? (tracker?.currentStepId === stepId ? "running" : "queued") : "pending";
    const status = String(resultStep?.status || liveStatus || fallbackStatus);
    const message = String(resultStep?.message || tracker?.stepMessageById.get(stepId) || "");
    return {
      key: `${scenario.scenario_id}::${stepId}`,
      stepId,
      text: step.text || stepId,
      status,
      message: message || "-",
      requestText: stringifySummary(resultStep?.request_summary || resultStep?.request || step.request),
      responseText: stringifySummary(resultStep?.response_summary || resultStep?.response),
    };
  });
}

function eventFromExecutionLog(log: unknown): { event: string; data: string; at: string } | null {
  if (!log || typeof log !== "object") {
    return null;
  }
  const payload = log as Record<string, unknown>;
  const event = typeof payload.event === "string" && payload.event.trim() ? payload.event : "";
  if (!event) {
    return null;
  }
  return {
    event,
    data: JSON.stringify(payload),
    at: typeof payload.time === "string" ? payload.time : new Date().toISOString(),
  };
}

export function useExecutionCaseRows(params: {
  detail: ExtendedTaskDetail | null;
  streamEvents: Array<{ event: string; data: string; at: string }>;
  uiExecutionStatus: string;
  selectedTestPoint: string;
  caseKeyword: string;
}) {
  const { detail, streamEvents, uiExecutionStatus, selectedTestPoint, caseKeyword } = params;

  return useMemo(() => {
    const dslCases: TestCaseDslScenario[] = detail?.test_case_dsl?.scenarios ?? [];
    const scenarioResults: ExecutionScenarioResult[] = detail?.execution_result?.scenario_results ?? [];
    const scenarioMetas: ScenarioModel[] = detail?.scenarios ?? [];
    const logEvents =
      uiExecutionStatus === "running"
        ? (detail?.execution_result?.logs ?? []).map(eventFromExecutionLog).filter((item): item is { event: string; data: string; at: string } => Boolean(item))
        : [];
    const activeStreamEvents = uiExecutionStatus === "running" ? [...logEvents, ...streamEvents] : [];

    const streamStepTrackerMap = (() => {
      const tracker = new Map<string, StreamStepTracker>();
      activeStreamEvents.forEach((evt) => {
        const payload = parseStreamPayload(evt.data);
        const scenarioId = typeof payload?.scenario_id === "string" ? payload.scenario_id : "";
        if (!scenarioId) {
          return;
        }
        const existing =
          tracker.get(scenarioId) ??
          ({
            completedStepIds: new Set<string>(),
            failedStepIds: new Set<string>(),
            stepStatusById: new Map<string, string>(),
            stepMessageById: new Map<string, string>(),
          } as StreamStepTracker);
        const stepId = typeof payload?.step_id === "string" ? payload.step_id : undefined;
        const msg = typeof payload?.message === "string" ? payload.message : undefined;
        const status = typeof payload?.status === "string" ? payload.status : undefined;
        if (["step_start", "request_prepared", "response_received", "context_saved", "assertions_evaluated"].includes(evt.event)) {
          existing.currentStepId = stepId;
          existing.currentStepMessage = [STEP_PHASE_LABEL[evt.event], msg].filter(Boolean).join("：");
          existing.scenarioStatus = "running";
          if (stepId) {
            existing.stepStatusById.set(stepId, evt.event === "request_prepared" ? "requesting" : evt.event === "response_received" ? "response_received" : evt.event === "assertions_evaluated" ? "asserting" : "running");
            if (existing.currentStepMessage) {
              existing.stepMessageById.set(stepId, existing.currentStepMessage);
            }
          }
        }
        if (evt.event === "step_result" || evt.event === "step_end") {
          if (stepId) {
            existing.completedStepIds.add(stepId);
            existing.stepStatusById.set(stepId, status || "done");
            if (msg) {
              existing.stepMessageById.set(stepId, msg);
            }
            if (status === "failed") {
              existing.failedStepIds.add(stepId);
            }
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

    const scenarioResultMap = new Map(scenarioResults.map((item) => [item.scenario_id, item]));
    const scenarioMetaMap = new Map(scenarioMetas.map((item) => [item.scenario_id, item]));

    const executionCaseRows: ExecutionCaseRow[] = dslCases.map((item) => {
      const result = scenarioResultMap.get(item.scenario_id);
      const meta = scenarioMetaMap.get(item.scenario_id);
      const stepTracker = streamStepTrackerMap.get(item.scenario_id);
      const testPoint = (meta?.goal || item.goal || "未分类测试点").trim() || "未分类测试点";
      const totalSteps = Array.isArray(item.steps) ? item.steps.length : 0;
      const completedFromTracker = stepTracker?.completedStepIds.size ?? 0;
      const failedFromTracker = stepTracker?.failedStepIds.size ?? 0;
      const completedFromResult =
        typeof result?.passed_steps === "number" && typeof result?.failed_steps === "number"
          ? result.passed_steps + result.failed_steps
          : Array.isArray((result as { steps?: unknown[] } | undefined)?.steps)
            ? ((result as { steps?: unknown[] }).steps?.length ?? 0)
            : 0;
      const completedSteps = Math.min(
        totalSteps || completedFromResult || completedFromTracker,
        Math.max(completedFromTracker, completedFromResult),
      );
      const currentStepId = stepTracker?.currentStepId;
      const currentStep = currentStepId
        ? item.steps.find((step) => step.step_id === currentStepId)?.text || stepTracker?.currentStepMessage || currentStepId
        : stepTracker?.currentStepMessage || "-";
      const liveScenarioStatus = stepTracker?.scenarioStatus || result?.status || "";
      const status =
        uiExecutionStatus === "running"
          ? LIVE_FINAL_STATUSES.has(liveScenarioStatus)
            ? liveScenarioStatus
            : stepTracker?.currentStepId || completedSteps > 0
              ? "running"
              : "queued"
          : result?.status || "pending";
      const progressPercent = totalSteps > 0 ? Math.min(100, Math.round((completedSteps / totalSteps) * 100)) : status === "passed" ? 100 : 0;
      const steps = buildStepRows(item, result, stepTracker, uiExecutionStatus === "running");
      return {
        key: item.scenario_id,
        id: item.scenario_id,
        name: item.name || item.scenario_id,
        testPoint,
        priority: (item.priority || meta?.priority || "-").toUpperCase(),
        status,
        durationMs: result?.duration_ms ?? 0,
        failedSteps: Math.max(result?.failed_steps ?? 0, failedFromTracker),
        stepProgress: progressPercent,
        stepProgressText: totalSteps > 0 ? `${completedSteps}/${totalSteps}` : "-",
        currentStep,
        steps,
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

    return {
      executionCaseRows,
      testPointGroups,
      filteredExecutionCaseRows,
    };
  }, [detail, streamEvents, uiExecutionStatus, selectedTestPoint, caseKeyword]);
}
