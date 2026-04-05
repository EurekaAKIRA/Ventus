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

/** 执行已终态：分析报告与看板数据已稳定，无需再静默轮询详情。 */
function isExecutionTerminal(detail: ExtendedTaskDetail | null): boolean {
  if (!detail) return false;
  const exec = deriveExecutionStatus(detail);
  return exec === "passed" || exec === "failed" || exec === "stopped";
}

/**
 * 流水线已产出场景且尚未启动执行：解析/生成阶段结束，无需再为等 DSL 轮询。
 * （用户若之后点执行，由执行轮询负责。）
 */
function isPipelineIdleWithScenarios(detail: ExtendedTaskDetail | null): boolean {
  if (!detail) return false;
  if (deriveExecutionStatus(detail) !== "not_started") return false;
  const life = normalizeStatus(detail.task_context?.status);
  return life === "generated" && (detail.scenarios?.length ?? 0) > 0;
}

/** 详情页静默轮询是否应停止（分析/生成阶段已结束或执行已终态）。 */
export function isTaskDetailPollingSettled(detail: ExtendedTaskDetail | null): boolean {
  return isExecutionTerminal(detail) || isPipelineIdleWithScenarios(detail);
}

/** 用于 summary 轮询：仅当这些字段变化时才值得拉 full / 产物。 */
export function fingerprintFromSummaryPayload(summary: ExtendedTaskDetail): string {
  const life = normalizeStatus(summary.task_context?.status);
  const exec = normalizeStatus(summary.execution_result?.status || "");
  const pm = String(summary.parse_metadata?.parse_mode ?? "");
  const rm = String(summary.parse_metadata?.retrieval_mode ?? "");
  const fr = String(summary.parse_metadata?.fallback_reason ?? "");
  return `${life}|${exec}|${pm}|${rm}|${fr}`;
}

/** 大字段内容指纹：相同时跳过 setState，避免重复渲染相同 DSL/场景。 */
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

/**
 * summary 接口会把大字段置 null；合并时保留上一份 full 中的实体，避免轮询闪空再补全。
 */
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
