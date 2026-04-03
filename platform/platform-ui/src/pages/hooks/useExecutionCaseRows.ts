import { useMemo } from "react";
import type { ExecutionScenarioResult, ScenarioModel, TestCaseDslScenario } from "../../types";
import type { ExtendedTaskDetail } from "./useTaskDetailData";

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
};

type StreamStepTracker = {
  completedStepIds: Set<string>;
  currentStepId?: string;
  currentStepMessage?: string;
  scenarioStatus?: string;
};

function parseStreamPayload(data: string): Record<string, unknown> | null {
  try {
    const payload = JSON.parse(data);
    return payload && typeof payload === "object" ? (payload as Record<string, unknown>) : null;
  } catch {
    return null;
  }
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
        const msg = typeof payload?.message === "string" ? payload.message : undefined;
        const status = typeof payload?.status === "string" ? payload.status : undefined;
        if (evt.event === "step_start") {
          existing.currentStepId = stepId;
          existing.currentStepMessage = msg;
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

    const scenarioResultMap = new Map(scenarioResults.map((item) => [item.scenario_id, item]));
    const scenarioMetaMap = new Map(scenarioMetas.map((item) => [item.scenario_id, item]));

    const executionCaseRows: ExecutionCaseRow[] = dslCases.map((item) => {
      const result = scenarioResultMap.get(item.scenario_id);
      const meta = scenarioMetaMap.get(item.scenario_id);
      const stepTracker = streamStepTrackerMap.get(item.scenario_id);
      const testPoint = (meta?.goal || item.goal || "未分类测试点").trim() || "未分类测试点";
      const totalSteps = Array.isArray(item.steps) ? item.steps.length : 0;
      const completedFromTracker = stepTracker?.completedStepIds.size ?? 0;
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
      const status = result?.status || stepTracker?.scenarioStatus || (uiExecutionStatus === "running" ? "queued" : "pending");
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

    return {
      executionCaseRows,
      testPointGroups,
      filteredExecutionCaseRows,
    };
  }, [detail, streamEvents, uiExecutionStatus, selectedTestPoint, caseKeyword]);
}
