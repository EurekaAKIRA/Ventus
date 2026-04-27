import { Tag } from "antd";
import type { TaskStatus } from "../types";

const statusConfig: Record<string, { tone: string; label: string }> = {
  received: { tone: "neutral", label: "已接收" },
  parsed: { tone: "info", label: "已解析" },
  generated: { tone: "accent", label: "用例已生成" },
  scenario_generated: { tone: "accent", label: "用例已生成" },
  running: { tone: "running", label: "执行中" },
  passed: { tone: "success", label: "通过" },
  failed: { tone: "danger", label: "失败" },
  stopped: { tone: "warning", label: "已停止" },
  archived: { tone: "neutral", label: "已归档" },
};

export default function StatusTag({ status }: { status: TaskStatus | string }) {
  const cfg = statusConfig[status] ?? { tone: "neutral", label: status };
  return (
    <Tag bordered={false} className={`status-pill status-pill--${cfg.tone}`}>
      {cfg.label}
    </Tag>
  );
}
