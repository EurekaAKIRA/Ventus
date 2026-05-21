import { FormEvent, useMemo, useState } from "react";
import type { TaskDraftAgentPayload } from "../types";

export type TaskAgentPanelProps = {
  payload: TaskDraftAgentPayload | null;
  loading: boolean;
  stale: boolean;
  activeView: string;
  onAnalyze?: () => void;
  onApply?: () => void;
  onGenerateTests?: (prompt: string) => Promise<string>;
  canApply?: boolean;
};

type ChatMessage = {
  role: "bot" | "user";
  text: string;
  meta?: string;
};

function toneClass(severity?: string) {
  if (severity === "error") return "danger";
  if (severity === "warning") return "warning";
  if (severity === "success") return "success";
  return "default";
}

function confidenceText(level?: string) {
  if (level === "high") return "高";
  if (level === "medium") return "中";
  if (level === "low") return "低";
  return level || "待评估";
}

function buildSuggestionReply(payload: TaskDraftAgentPayload | null, question: string) {
  const lowerQuestion = question.toLowerCase();
  if (!payload) {
    return "先导入接口文档或粘贴需求说明，我会根据识别到的接口、依赖链和质量门禁给出测试建议。";
  }
  if (lowerQuestion.includes("断言") || question.includes("校验")) {
    const gates = payload.quality_gates?.filter((item) => item.status !== "pass").map((item) => item.label) ?? [];
    return gates.length
      ? `建议先补充这些断言：${gates.slice(0, 3).join("、")}。再覆盖状态码、关键字段、上下文变量一致性和错误分支。`
      : "当前质量门禁没有明显阻断项。建议继续补充状态码、业务状态、资源 ID 传递、权限边界和失败重试断言。";
  }
  if (lowerQuestion.includes("场景") || question.includes("用例")) {
    const count = payload.scenario_outlook?.estimated_scenario_count ?? payload.diagnostic_verdict?.estimated_scenario_count ?? 0;
    const gaps = payload.coverage_gaps ?? [];
    return count
      ? `当前预计可生成 ${count} 个测试场景。优先覆盖主链路、创建后查询、修改后验证、删除确认；${gaps.length ? `还要注意：${gaps.slice(0, 2).join("、")}。` : "再补一组异常参数和鉴权失败分支。"}`
      : "建议先按资源生命周期组织用例：创建、查询、修改、删除，再补登录态、无效参数和边界值。";
  }
  if (lowerQuestion.includes("风险") || question.includes("问题")) {
    const risks = [...(payload.risks ?? []), ...(payload.warnings ?? [])].slice(0, 3);
    return risks.length ? `目前最需要关注：${risks.join("；")}。` : "当前没有明显高风险提示。可以继续检查鉴权、跨接口变量、异步回调和幂等重试。";
  }
  if (lowerQuestion.includes("rag") || question.includes("知识")) {
    const hits = payload.knowledge_hits?.length ?? 0;
    const summary = payload.knowledge_summary;
    return hits
      ? `RAG 当前命中 ${hits} 条知识依据。${summary || "建议检查知识来源是否覆盖接口约束、错误码和业务规则。"}`
      : "当前没有知识命中。建议补充接口规范、错误码说明、业务规则文档后重新分析。";
  }
  return payload.next_actions?.length
    ? `可以先做这几步：${payload.next_actions.slice(0, 3).join("；")}。`
    : "建议先确认接口路径、方法、鉴权、请求参数和上下游变量，再生成 DSL 并执行冒烟测试。";
}

function formatAgentError(error: unknown) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  if (typeof error === "string" && error.trim()) {
    return error;
  }
  const maybeValidationError = error as { errorFields?: Array<{ errors?: string[] }>; message?: string };
  const firstValidationMessage = maybeValidationError.errorFields?.[0]?.errors?.[0];
  if (firstValidationMessage) {
    return firstValidationMessage;
  }
  if (maybeValidationError.message) {
    return maybeValidationError.message;
  }
  return "请检查后端服务和当前表单内容。";
}

export default function TaskAgentPanel({
  payload,
  loading,
  stale,
  activeView,
  onAnalyze,
  onApply,
  onGenerateTests,
  canApply,
}: TaskAgentPanelProps) {
  const [draft, setDraft] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "bot",
      meta: "测试建议机器人",
      text: "我会根据当前 Agent 诊断结果，给你整理用例、断言、风险和 RAG 依据方面的测试建议。",
    },
  ]);

  const readiness = useMemo(() => {
    const score = payload?.summary?.ready_score ?? 0;
    const max = payload?.summary?.max_score ?? 0;
    return max > 0 ? Math.round((score / max) * 100) : 0;
  }, [payload?.summary?.max_score, payload?.summary?.ready_score]);

  const openItems = useMemo(() => {
    if (!payload) return [];
    return [
      ...(payload.follow_up_questions ?? []).map((item) => ({ type: "追问", text: item.question, level: item.priority || "medium" })),
      ...(payload.risks ?? []).map((item) => ({ type: "风险", text: item, level: "high" })),
      ...(payload.coverage_gaps ?? []).map((item) => ({ type: "缺口", text: item, level: "medium" })),
    ].slice(0, 4);
  }, [payload]);

  const gateSummary = useMemo(() => {
    const gates = payload?.quality_gates ?? [];
    return {
      pass: gates.filter((item) => item.status === "pass").length,
      warn: gates.filter((item) => item.status === "warn").length,
      block: gates.filter((item) => item.status === "block").length,
    };
  }, [payload?.quality_gates]);

  const quickPrompts = useMemo(
    () => [
      "给我测试场景建议",
      "需要补哪些断言",
      "当前最大风险是什么",
      payload?.knowledge_hits?.length ? "RAG依据够不够" : "如何补充知识依据",
    ],
    [payload?.knowledge_hits?.length],
  );

  const sendMessage = async (text?: string) => {
    const nextText = String(text ?? draft).trim();
    if (!nextText || chatLoading) return;
    setDraft("");
    setMessages((current) => {
      const nextMessages: ChatMessage[] = [...current, { role: "user", text: nextText }];
      return nextMessages.slice(-8);
    });
    setChatLoading(true);
    try {
      const reply = onGenerateTests ? await onGenerateTests(nextText) : buildSuggestionReply(payload, nextText);
      setMessages((current) => {
        const nextMessages: ChatMessage[] = [
          ...current,
          { role: "bot", meta: onGenerateTests ? "生成测试 API" : "建议", text: reply },
        ];
        return nextMessages.slice(-8);
      });
    } catch (error) {
      setMessages((current) => {
        const nextMessages: ChatMessage[] = [
          ...current,
          {
            role: "bot",
            meta: "生成测试 API",
            text: `生成测试失败：${formatAgentError(error)}`,
          },
        ];
        return nextMessages.slice(-8);
      });
    } finally {
      setChatLoading(false);
    }
  };

  const verdict = payload?.diagnostic_verdict;
  const currentTone = toneClass(verdict?.severity);
  const statusText = loading ? "分析中" : stale ? "待刷新" : payload ? "已同步" : "待输入";

  return (
    <div className="vue-agent-dialogue-mount">
      <aside className={`vue-agent-dialogue is-${currentTone}`}>
        <div className="vue-agent-dialogue__head">
          <div>
            <span className="vue-agent-dialogue__eyebrow">Agent Mode</span>
            <h3>测试建议 Agent</h3>
          </div>
          <div className="vue-agent-dialogue__head-actions">
            <span className={`vue-agent-dialogue__state ${loading ? "is-loading" : stale ? "is-stale" : "is-ready"}`}>
              {statusText}
            </span>
          </div>
        </div>

        <div className="vue-agent-dialogue__actions">
          <button type="button" onClick={onAnalyze} disabled={loading || chatLoading}>
            {payload ? "重新分析" : "生成建议"}
          </button>
          <button type="button" className="is-primary" onClick={onApply} disabled={!canApply || stale}>
            一键回填
          </button>
        </div>

        <div className="vue-agent-dialogue__snapshot">
          <div className="vue-agent-dialogue__meter-ring" style={{ "--agent-ready": `${readiness}%` } as React.CSSProperties}>
            <strong>{readiness}</strong>
            <span>ready</span>
          </div>
          <div className="vue-agent-dialogue__metrics">
            <div>
              <span>诊断</span>
              <strong>{verdict?.label || "等待分析"}</strong>
            </div>
            <div>
              <span>可信度</span>
              <strong>{confidenceText(payload?.summary?.confidence_level)}</strong>
            </div>
            <div>
              <span>接口</span>
              <strong>{verdict?.endpoint_count ?? payload?.recognized_endpoints?.length ?? 0}</strong>
            </div>
            <div>
              <span>场景</span>
              <strong>{verdict?.estimated_scenario_count ?? payload?.scenario_outlook?.estimated_scenario_count ?? 0}</strong>
            </div>
          </div>
        </div>

        <p className="vue-agent-dialogue__reply">
          {payload?.reply || "导入接口文档后，我会给出测试场景、断言、风险和知识依据建议。"}
        </p>

        <div className="vue-agent-dialogue__gates">
          <span>
            <strong>{gateSummary.pass}</strong>通过
          </span>
          <span>
            <strong>{gateSummary.warn}</strong>提醒
          </span>
          <span>
            <strong>{gateSummary.block}</strong>阻断
          </span>
        </div>

        <div className="vue-agent-dialogue__thread">
          {messages.map((item, index) => (
            <div key={`${item.role}-${index}-${item.text}`} className={`vue-agent-dialogue__message is-${item.role}`}>
              <span>{item.meta || (item.role === "bot" ? "Bot" : "你")}</span>
              <p>{item.text}</p>
            </div>
          ))}
        </div>

        {openItems.length ? (
          <div className="vue-agent-dialogue__tips">
            {openItems.map((item) => (
              <button
                key={`${item.type}-${item.text}`}
                className={`vue-agent-dialogue__tip is-${item.level}`}
                disabled={chatLoading}
                onClick={() => void sendMessage(item.text)}
                type="button"
              >
                <span>{item.type}</span>
                <strong>{item.text}</strong>
              </button>
            ))}
          </div>
        ) : null}

        <div className="vue-agent-dialogue__quick">
          {quickPrompts.map((item) => (
            <button key={item} disabled={chatLoading} onClick={() => void sendMessage(item)} type="button">
              {item}
            </button>
          ))}
        </div>

        <form
          className="vue-agent-dialogue__composer"
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            void sendMessage();
          }}
        >
          <input
            value={draft}
            placeholder={chatLoading ? "正在调用生成测试 API..." : "问我：生成场景、断言、风险、RAG依据..."}
            disabled={chatLoading}
            onChange={(event) => setDraft(event.target.value)}
          />
          <button type="submit" disabled={chatLoading}>
            {chatLoading ? "生成中" : "发送"}
          </button>
        </form>
      </aside>
    </div>
  );
}
