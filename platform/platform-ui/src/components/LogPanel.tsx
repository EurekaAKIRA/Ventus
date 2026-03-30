import type { ExecutionLog } from "../types";

interface LogPanelProps {
  logs: ExecutionLog[];
}

export default function LogPanel({ logs }: LogPanelProps) {
  if (!logs.length) {
    return <div className="log-panel" style={{ color: "#666" }}>暂无日志</div>;
  }

  return (
    <div className="log-panel">
      {logs.map((log, i) => (
        <div key={i} className="log-line">
          <span className="log-time">
            {new Date(log.time).toLocaleTimeString()}
          </span>
          <span className={`log-level ${log.level}`}>[{log.level}]</span>
          <span>{log.message}</span>
        </div>
      ))}
    </div>
  );
}
