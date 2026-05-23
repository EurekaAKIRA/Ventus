import { FormEvent, useEffect, useRef, useState } from "react";
import type { TaskDraftAgentPayload } from "../types";

export type TaskAgentPanelSendContext = {
  intent: string;
  task_id?: string;
  conversation_history: Array<{ role: "bot" | "user"; text: string }>;
};

export type TaskAgentPanelProps = {
  payload: TaskDraftAgentPayload | null;
  onSendMessage: (message: string, context?: TaskAgentPanelSendContext) => Promise<{ reply: string; payload?: TaskDraftAgentPayload | null }>;
  initialMessage?: string;
  taskId?: string;
  currentStage?: string;
  quickActions?: Array<{
    label: string;
    message: string;
    disabled?: boolean;
  }>;
};

type ChatMessage = {
  role: "bot" | "user";
  text: string;
  meta?: string;
};

type TaskAgentIntent =
  | "status_query"
  | "failure_diagnosis"
  | "assertion_quality"
  | "llm_usage"
  | "task_import"
  | "next_action"
  | "general_question";

function includesAny(text: string, keywords: string[]) {
  return keywords.some((keyword) => text.includes(keyword));
}

function isContinuationMessage(text: string) {
  return includesAny(text, ["继续", "这个", "刚才", "上面", "前面", "然后", "那", "接着", "再看"]);
}

function isContextualQualityQuestion(text: string, hasTaskContext = false) {
  const lower = text.toLowerCase();
  if (!includesAny(lower, ["质量", "quality"])) return false;
  if (includesAny(lower, ["测试", "断言", "用例", "执行", "任务", "脚本", "生成", "报告", "case", "test", "assert"])) return true;
  const compact = lower.replace(/[\s?？。！!，,；;：:]+/g, "");
  return hasTaskContext && ["质量如何", "质量怎样", "质量怎么样", "质量好不好", "质量行不行", "质量靠谱不", "quality"].includes(compact);
}

function inferAgentIntent(text: string, history: ChatMessage[] = [], hasTaskContext = false): TaskAgentIntent {
  const lower = text.toLowerCase();
  if (includesAny(lower, ["llm", "大模型", "模型", "增强", "候选", "过滤", "fallback"])) return "llm_usage";
  if (includesAny(lower, ["断言", "assertion", "校验", "误杀", "测试质量", "用例质量", "执行质量", "质量评估"])) return "assertion_quality";
  if (isContextualQualityQuestion(lower, hasTaskContext)) return "assertion_quality";
  if (includesAny(lower, ["失败", "报错", "为什么", "原因", "定位", "不通过", "挂了"])) return "failure_diagnosis";
  if (includesAny(lower, ["导入", "资产", "baseurl", "base url"])) return "task_import";
  if (includesAny(lower, ["下一步", "怎么修", "怎么办", "建议", "修复"])) return "next_action";
  if (includesAny(lower, ["状态", "进度", "现在", "当前", "结果", "跑完"])) return "status_query";
  if (isContinuationMessage(lower)) {
    const recent = [...history].reverse();
    for (const item of recent.filter((entry) => entry.role === "user")) {
      const previousIntent: TaskAgentIntent = inferAgentIntent(item.text, [], hasTaskContext);
      if (previousIntent !== "general_question") return previousIntent;
    }
    for (const item of recent) {
      const previousIntent: TaskAgentIntent = inferAgentIntent(item.text, [], hasTaskContext);
      if (previousIntent !== "general_question") return previousIntent;
    }
  }
  return "general_question";
}

function intentLabel(intent: TaskAgentIntent) {
  if (intent === "failure_diagnosis") return "失败诊断";
  if (intent === "assertion_quality") return "质量评估";
  if (intent === "llm_usage") return "LLM 监督";
  if (intent === "task_import") return "资产导入";
  if (intent === "next_action") return "下一步";
  if (intent === "status_query") return "任务状态";
  return "上下文分析";
}

function compactTaskId(taskId?: string) {
  const value = String(taskId || "").trim();
  if (!value) return "任务未绑定";
  if (value.length <= 34) return value;
  return `${value.slice(0, 18)}...${value.slice(-10)}`;
}

function buildLoadingLabel(intent: string) {
  if (intent === "failure_diagnosis") return "正在读取执行结果和失败断言...";
  if (intent === "assertion_quality") return "正在评估测试与断言质量...";
  if (intent === "llm_usage") return "正在检查 LLM 候选和质量门...";
  if (intent === "task_import") return "正在核对资产和环境信息...";
  if (intent === "status_query") return "正在同步当前任务状态...";
  return "正在结合任务上下文分析...";
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

function renderAgentMessage(text: string) {
  const blocks = String(text || "").split(/(```[\s\S]*?```)/g).filter(Boolean);
  return blocks.map((block, blockIndex) => {
    if (block.startsWith("```")) {
      return (
        <pre key={`code-${blockIndex}`} className="vue-agent-dialogue__pre">
          {block.replace(/^```\w*\n?/, "").replace(/```$/, "")}
        </pre>
      );
    }
    const lines = block.split(/\n+/).filter((line) => line.trim());
    return lines.map((line, lineIndex) => {
      const trimmed = line.trim();
      if (trimmed.includes("|") && trimmed.split("|").length >= 3) {
        return (
          <pre key={`table-${blockIndex}-${lineIndex}`} className="vue-agent-dialogue__pre vue-agent-dialogue__pre--table">
            {trimmed}
          </pre>
        );
      }
      return <p key={`p-${blockIndex}-${lineIndex}`}>{trimmed}</p>;
    });
  });
}

export default function TaskAgentPanel({ payload, onSendMessage, initialMessage, taskId, currentStage, quickActions = [] }: TaskAgentPanelProps) {
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState("正在结合任务上下文分析...");
  const [lastIntent, setLastIntent] = useState<TaskAgentIntent>("general_question");
  const threadRef = useRef<HTMLDivElement | null>(null);
  const normalizedInitialMessage = String(initialMessage || buildDraftModeIntro()).trim();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "bot",
      meta: "Agent",
      text: normalizedInitialMessage,
    },
  ]);

  useEffect(() => {
    setMessages((current) => {
      if (current.length !== 1 || current[0]?.role !== "bot") {
        return current;
      }
      if (current[0].text === normalizedInitialMessage) {
        return current;
      }
      return [{ ...current[0], text: normalizedInitialMessage }];
    });
  }, [normalizedInitialMessage]);

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
    const recentHistory = messages.slice(-8);
    const intent = inferAgentIntent(nextText, recentHistory, Boolean(taskId));
    setLastIntent(intent);
    setLoadingLabel(buildLoadingLabel(intent));
    try {
      const result = await onSendMessage(nextText, {
        intent,
        task_id: taskId,
        conversation_history: recentHistory.map((item) => ({ role: item.role, text: item.text })),
      });
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
            {taskId || currentStage ? (
              <small className="vue-agent-dialogue__context">
                {taskId ? `任务 ${taskId}` : "任务未绑定"}
                {currentStage ? ` · ${currentStage}` : ""}
              </small>
            ) : null}
          </div>
        </div>
        <div className="vue-agent-dialogue__focus" title={taskId || "任务未绑定"}>
          <span>跟踪</span>
          <strong>{compactTaskId(taskId)}</strong>
          {currentStage ? <em>{currentStage}</em> : null}
          <b>{intentLabel(lastIntent)}</b>
        </div>

        <div className="vue-agent-dialogue__thread" ref={threadRef}>
          {messages.map((item, index) => (
            <div key={`${item.role}-${index}-${item.text}`} className={`vue-agent-dialogue__message is-${item.role}`}>
              <span>{item.meta || (item.role === "bot" ? "Agent" : "你")}</span>
              <div className="vue-agent-dialogue__markdown">{renderAgentMessage(item.text)}</div>
            </div>
          ))}
          {sending ? (
            <div className="vue-agent-dialogue__message is-bot is-loading">
              <span>Agent</span>
              <div className="vue-agent-dialogue__markdown">
                <p>{loadingLabel}</p>
              </div>
            </div>
          ) : null}
        </div>

        {quickActions.length ? (
          <div className="vue-agent-dialogue__quick">
            {quickActions.map((item) => (
              <button key={item.label} type="button" disabled={item.disabled || sending} onClick={() => void sendMessage(item.message)}>
                {item.label}
              </button>
            ))}
          </div>
        ) : null}

        <form
          className="vue-agent-dialogue__composer"
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            void sendMessage();
          }}
        >
          <input
            value={draft}
            placeholder={sending ? loadingLabel : "问我：失败原因、断言质量、下一步怎么修..."}
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
