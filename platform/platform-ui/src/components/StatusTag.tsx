import { Tag } from "antd";
import type { TaskStatus } from "../types";

const statusConfig: Record<string, { color: string; label: string }> = {
  received: { color: "default", label: "已接收" },
  parsed: { color: "blue", label: "已解析" },
  scenario_generated: { color: "cyan", label: "用例已生成" },
  running: { color: "processing", label: "执行中" },
  passed: { color: "success", label: "通过" },
  failed: { color: "error", label: "失败" },
};

export default function StatusTag({ status }: { status: TaskStatus | string }) {
  const cfg = statusConfig[status] ?? { color: "default", label: status };
  return <Tag color={cfg.color}>{cfg.label}</Tag>;
}
