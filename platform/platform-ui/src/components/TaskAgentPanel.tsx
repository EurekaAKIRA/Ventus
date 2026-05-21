import { FormEvent, useState } from "react";
import type { TaskDraftAgentPayload } from "../types";

export type TaskAgentPanelProps = {
  payload: TaskDraftAgentPayload | null;
};

type ChatMessage = {
  role: "bot" | "user";
  text: string;
  meta?: string;
};

function buildSuggestionReply(payload: TaskDraftAgentPayload | null, question: string) {
  const lowerQuestion = question.toLowerCase();
  if (!payload) {
    return "你可以先在左侧填写需求或导入接口文档。我会按你写的内容，帮你整理测试场景、断言和风险。";
  }
  if (lowerQuestion.includes("断言") || question.includes("校验")) {
    const gates = payload.quality_gates?.filter((item) => item.status !== "pass").map((item) => item.label) ?? [];
    return gates.length
      ? `建议先补这些断言：${gates.slice(0, 3).join("、")}。再覆盖状态码、关键字段、上下文变量一致性和错误分支。`
      : "当前质量门禁没有明显阻断项。可以继续补状态码、业务状态、资源 ID 传递、权限边界和失败重试断言。";
  }
  if (lowerQuestion.includes("场景") || question.includes("用例")) {
    const count = payload.scenario_outlook?.estimated_scenario_count ?? payload.diagnostic_verdict?.estimated_scenario_count ?? 0;
    const gaps = payload.coverage_gaps ?? [];
    return count
      ? `当前预计可设计 ${count} 个测试场景。优先覆盖主链路、创建后查询、修改后验证、删除确认；${gaps.length ? `还要注意：${gaps.slice(0, 2).join("、")}。` : "再补异常参数和鉴权失败分支。"}`
      : "建议按资源生命周期组织用例：创建、查询、修改、删除，再补登录态、无效参数和边界值。";
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

export default function TaskAgentPanel({ payload }: TaskAgentPanelProps) {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "bot",
      meta: "Agent",
      text: "你好，我是测试建议聊天助手。你可以直接问我测试场景、断言、风险或 RAG 依据。",
    },
  ]);

  const sendMessage = (text?: string) => {
    const nextText = String(text ?? draft).trim();
    if (!nextText) return;
    setDraft("");
    setMessages((current) => {
      const nextMessages: ChatMessage[] = [
        ...current,
        { role: "user", text: nextText },
        { role: "bot", meta: "建议", text: buildSuggestionReply(payload, nextText) },
      ];
      return nextMessages.slice(-10);
    });
  };

  return (
    <div className="vue-agent-dialogue-mount">
      <aside className="vue-agent-dialogue is-default">
        <div className="vue-agent-dialogue__head">
          <div>
            <span className="vue-agent-dialogue__eyebrow">Agent</span>
            <h3>聊天助手</h3>
          </div>
        </div>

        <div className="vue-agent-dialogue__thread">
          {messages.map((item, index) => (
            <div key={`${item.role}-${index}-${item.text}`} className={`vue-agent-dialogue__message is-${item.role}`}>
              <span>{item.meta || (item.role === "bot" ? "Agent" : "你")}</span>
              <p>{item.text}</p>
            </div>
          ))}
        </div>

        <form
          className="vue-agent-dialogue__composer"
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            sendMessage();
          }}
        >
          <input
            value={draft}
            placeholder="问我：场景、断言、风险、RAG依据..."
            onChange={(event) => setDraft(event.target.value)}
          />
          <button type="submit">发送</button>
        </form>
      </aside>
    </div>
  );
}
