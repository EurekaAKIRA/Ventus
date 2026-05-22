import { FormEvent, useEffect, useRef, useState } from "react";
import type { TaskDraftAgentPayload } from "../types";

export type TaskAgentPanelProps = {
  payload: TaskDraftAgentPayload | null;
  onSendMessage: (message: string) => Promise<{ reply: string; payload?: TaskDraftAgentPayload | null }>;
};

type ChatMessage = {
  role: "bot" | "user";
  text: string;
  meta?: string;
};

function includesAny(text: string, keywords: string[]) {
  return keywords.some((keyword) => text.includes(keyword));
}

function buildGeneralHelp() {
  return [
    "我可以帮你做这些事：",
    "1. 把需求拆成正向、异常、边界和权限类测试场景。",
    "2. 给接口补状态码、字段、业务状态和上下文变量断言。",
    "3. 提醒文档里缺失的路径、方法、鉴权、参数和依赖关系。",
    "4. 根据 RAG 命中情况判断知识依据是否够用。",
  ].join("\n");
}

function buildDraftModeIntro() {
  return [
    "当前还没有创建任务。",
    "你可以先告诉我：要测哪个接口、目标系统地址、业务流程和预期结果。",
    "我会先帮你整理成可创建的测试任务草稿，再提醒缺少的环境、鉴权、参数和断言信息。",
  ].join("\n");
}

function buildFallbackReply(question: string) {
  if (includesAny(question, ["你好", "您好", "hello", "hi", "在吗"])) {
    return "你好，我在。你可以把接口需求、文档片段或想测的功能发给我，我会帮你拆测试场景和断言。";
  }
  if (includesAny(question, ["你会", "能做", "功能", "帮助", "怎么用"])) {
    return buildGeneralHelp();
  }
  if (includesAny(question, ["登录", "注册", "订单", "支付", "用户", "查询", "创建", "删除", "修改"])) {
    return "可以按业务流程来拆：先测主流程成功，再测参数缺失、参数非法、未登录、权限不足、重复提交、资源不存在和状态流转异常。多步骤接口还要检查前一步返回的 Token、ID 或订单号能否被后续步骤正确使用。";
  }
  return "可以。你把具体接口、业务流程或文档片段发我，我会继续帮你拆成测试场景、断言点和风险点。";
}

function buildSuggestionReply(payload: TaskDraftAgentPayload | null, question: string) {
  const lowerQuestion = question.toLowerCase();
  if (includesAny(lowerQuestion, ["你好", "您好", "hello", "hi", "在吗", "你会", "能做", "功能", "帮助", "怎么用"])) {
    return buildFallbackReply(lowerQuestion);
  }
  if (!payload) {
    if (includesAny(lowerQuestion, ["你好", "您好", "hello", "hi", "在吗", "帮助", "怎么用", "你会", "能做"])) {
      return buildDraftModeIntro();
    }
    return `${buildDraftModeIntro()}\n\n针对你刚才的问题：${buildFallbackReply(lowerQuestion)}`;
  }
  if (lowerQuestion.includes("断言") || question.includes("校验")) {
    const firstSuggestion = payload.assertion_suggestions?.[0];
    if (firstSuggestion?.assertions?.length) {
      return `建议优先补“${firstSuggestion.title}”：${firstSuggestion.assertions.slice(0, 3).join("；")}。${firstSuggestion.reason || ""}`.trim();
    }
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
    const prioritized = payload.risk_priorities?.slice(0, 3).map((item) => `${item.title}: ${item.impact}`) ?? [];
    if (prioritized.length) {
      return `目前最需要关注：${prioritized.join("；")}。`;
    }
    const risks = [...(payload.risks ?? []), ...(payload.warnings ?? [])].slice(0, 3);
    return risks.length ? `目前最需要关注：${risks.join("；")}。` : "当前没有明显高风险提示。可以继续检查鉴权、跨接口变量、异步回调和幂等重试。";
  }
  if (lowerQuestion.includes("执行") || lowerQuestion.includes("运行") || lowerQuestion.includes("冒烟") || lowerQuestion.includes("重跑")) {
    const strategy = payload.execution_strategy;
    return strategy?.phases?.length
      ? `建议先跑“${strategy.smoke_path}”。执行顺序：${strategy.phases.slice(0, 4).map((item) => item.title).join("、")}。${strategy.rerun_policy}`
      : "建议先做环境预检，再执行主链路冒烟；失败后按环境、鉴权、依赖、请求、断言的顺序排查。";
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

function formatChatError(error: unknown) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Agent 后端暂时不可用，请检查后端服务。";
}

export default function TaskAgentPanel({ payload, onSendMessage }: TaskAgentPanelProps) {
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const threadRef = useRef<HTMLDivElement | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "bot",
      meta: "Agent",
      text: buildDraftModeIntro(),
    },
  ]);

  useEffect(() => {
    const thread = threadRef.current;
    if (!thread) return;
    thread.scrollTo({ top: thread.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text?: string) => {
    const nextText = String(text ?? draft).trim();
    if (!nextText || sending) return;
    setDraft("");
    setMessages((current) => {
      const nextMessages: ChatMessage[] = [
        ...current,
        { role: "user", text: nextText },
      ];
      return nextMessages.slice(-10);
    });
    setSending(true);
    try {
      const result = await onSendMessage(nextText);
      setMessages((current) => {
        const nextMessages: ChatMessage[] = [
          ...current,
          { role: "bot", meta: "后端 Agent", text: result.reply || buildSuggestionReply(result.payload ?? payload, nextText) },
        ];
        return nextMessages.slice(-10);
      });
    } catch (error) {
      setMessages((current) => {
        const nextMessages: ChatMessage[] = [
          ...current,
          { role: "bot", meta: "后端 Agent", text: formatChatError(error) },
        ];
        return nextMessages.slice(-10);
      });
    } finally {
      setSending(false);
    }
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

        <div className="vue-agent-dialogue__thread" ref={threadRef}>
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
            void sendMessage();
          }}
        >
          <input
            value={draft}
            placeholder={sending ? "正在请求后端 Agent..." : "问我：场景、断言、风险、RAG依据..."}
            disabled={sending}
            onChange={(event) => setDraft(event.target.value)}
          />
          <button type="submit" disabled={sending}>
            {sending ? "等待" : "发送"}
          </button>
        </form>
      </aside>
    </div>
  );
}
