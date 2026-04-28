import type { ExtendedTaskDetail } from "./hooks/useTaskDetailData";

export const TAB_KEYS = ["parsed", "scenario", "dsl", "execution", "report", "artifacts"] as const;
export type TaskDetailTabKey = (typeof TAB_KEYS)[number];

export type ChartDatum = {
  key: string;
  label: string;
  value: number;
};

export function isValidHttpUrl(value: string | undefined | null): boolean {
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

export function normalizeStatus(status: string | undefined): string {
  if (!status) {
    return "received";
  }
  return status === "scenario_generated" ? "generated" : status;
}

export function flattenNumericEntries(input: unknown, prefix = ""): ChartDatum[] {
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

export function resolveTabKey(value: string | null): TaskDetailTabKey {
  if (value && (TAB_KEYS as readonly string[]).includes(value)) {
    return value as TaskDetailTabKey;
  }
  return "parsed";
}

export function deriveExecutionStatus(detail?: ExtendedTaskDetail | null): string {
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

function isExecutionTerminal(detail: ExtendedTaskDetail | null): boolean {
  if (!detail) return false;
  const exec = deriveExecutionStatus(detail);
  return exec === "passed" || exec === "failed" || exec === "stopped";
}

function isPipelineIdleWithScenarios(detail: ExtendedTaskDetail | null): boolean {
  if (!detail) return false;
  if (deriveExecutionStatus(detail) !== "not_started") return false;
  const life = normalizeStatus(detail.status || detail.task_context?.status);
  return life === "generated" && (detail.scenarios?.length ?? 0) > 0;
}

export function isTaskDetailPollingSettled(detail: ExtendedTaskDetail | null): boolean {
  return isExecutionTerminal(detail) || isPipelineIdleWithScenarios(detail);
}

export function fingerprintFromSummaryPayload(summary: ExtendedTaskDetail): string {
  const life = normalizeStatus(summary.task_context?.status);
  const exec = normalizeStatus(summary.execution_result?.status || "");
  const pm = String(summary.parse_metadata?.parse_mode ?? "");
  const rm = String(summary.parse_metadata?.retrieval_mode ?? "");
  const fr = String(summary.parse_metadata?.fallback_reason ?? "");
  return `${life}|${exec}|${pm}|${rm}|${fr}`;
}

export function heavyContentSnapshot(d: ExtendedTaskDetail): string {
  const sc = d.scenarios?.length ?? 0;
  const dsl = d.test_case_dsl?.scenarios?.length ?? 0;
  const feat = typeof d.feature_text === "string" ? d.feature_text.length : 0;
  const pr = d.parsed_requirement ? 1 : 0;
  const vr = d.validation_report ? 1 : 0;
  const ar = d.analysis_report ? 1 : 0;
  return `${sc}|${dsl}|${feat}|${pr}|${vr}|${ar}`;
}

export function shallowVisibleTaskDetailEqual(a: ExtendedTaskDetail, b: ExtendedTaskDetail): boolean {
  return (
    normalizeStatus(a.task_context?.status) === normalizeStatus(b.task_context?.status) &&
    deriveExecutionStatus(a) === deriveExecutionStatus(b) &&
    String(a.parse_metadata?.parse_mode ?? "") === String(b.parse_metadata?.parse_mode ?? "") &&
    String(a.parse_metadata?.retrieval_mode ?? "") === String(b.parse_metadata?.retrieval_mode ?? "")
  );
}

export function mergeTaskDetailFromSummaryPreserveHeavy(
  prev: ExtendedTaskDetail | null,
  summary: ExtendedTaskDetail,
): ExtendedTaskDetail {
  if (!prev) {
    return summary;
  }
  const heavyKeys = [
    "parsed_requirement",
    "retrieved_context",
    "scenarios",
    "test_case_dsl",
    "validation_report",
    "analysis_report",
    "feature_text",
  ] as const;
  const out: ExtendedTaskDetail = { ...prev, ...summary };
  for (const key of heavyKeys) {
    const incoming = summary[key];
    if ((incoming === null || incoming === undefined) && prev[key] != null) {
      Object.assign(out, { [key]: prev[key] });
    }
  }
  out.task_context = summary.task_context;
  if (summary.parse_metadata !== undefined && summary.parse_metadata !== null) {
    out.parse_metadata = summary.parse_metadata;
  }
  const sEr = summary.execution_result;
  const pEr = prev.execution_result;
  if (sEr && pEr) {
    const nextLogs = sEr.logs && sEr.logs.length > 0 ? sEr.logs : (pEr.logs ?? []);
    out.execution_result = { ...pEr, ...sEr, logs: nextLogs };
  } else {
    out.execution_result = sEr ?? pEr;
  }
  if (summary.target_system !== undefined) out.target_system = summary.target_system;
  if (summary.environment !== undefined) out.environment = summary.environment;
  return out;
}

export function isAnalyzingStatus(status: string | undefined): boolean {
  const normalized = normalizeStatus(status);
  return ["received", "parsed", "generated"].includes(normalized);
}

export function toReadableText(input: unknown): string {
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
