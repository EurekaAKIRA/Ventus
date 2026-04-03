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
