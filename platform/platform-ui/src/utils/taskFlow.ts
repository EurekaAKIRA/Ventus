export type FlowStatus =
  | "received"
  | "parsed"
  | "generated"
  | "running"
  | "passed"
  | "failed"
  | "stopped"
  | "archived"
  | "not_started"
  | string;

export function normalizeTaskStatus(status: string | undefined | null): FlowStatus {
  if (!status) return "received";
  if (status === "scenario_generated") return "generated";
  return status;
}

export function isPendingStatus(status: string | undefined | null): boolean {
  const s = normalizeTaskStatus(status);
  return s === "received" || s === "parsed" || s === "generated" || s === "stopped";
}

export function isRunningStatus(status: string | undefined | null): boolean {
  return normalizeTaskStatus(status) === "running";
}

export function isFailedStatus(status: string | undefined | null): boolean {
  return normalizeTaskStatus(status) === "failed";
}

export function isTerminalStatus(status: string | undefined | null): boolean {
  const s = normalizeTaskStatus(status);
  return s === "passed" || s === "failed" || s === "stopped" || s === "archived";
}

export function progressByTaskStatus(status: string | undefined | null): number {
  const s = normalizeTaskStatus(status);
  if (s === "received") return 10;
  if (s === "parsed") return 35;
  if (s === "generated") return 60;
  if (s === "running") return 80;
  if (s === "passed") return 100;
  if (s === "failed") return 100;
  if (s === "stopped") return 75;
  return 0;
}

export function nextActionByTaskStatus(status: string | undefined | null): string {
  const s = normalizeTaskStatus(status);
  if (s === "received") return "建议优先执行解析";
  if (s === "parsed") return "建议生成场景并检查 DSL";
  if (s === "generated") return "建议启动执行";
  if (s === "running") return "建议查看执行日志";
  if (s === "failed") return "建议进入详情定位失败原因";
  if (s === "stopped") return "确认停止原因后决定是否重跑";
  if (s === "passed") return "可转入历史任务查看报告";
  return "可查看详情";
}
