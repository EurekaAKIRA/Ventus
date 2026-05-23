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

function buildDraftModeIntro() {
  return [
    "当前还没有创建任务。",
    "你可以先告诉我：要测哪个接口、目标系统地址、业务流程和预期结果。",
    "我会先帮你整理成可创建的测试任务草稿，再提醒缺少的环境、鉴权、参数和断言信息。",
  ].join("\n");
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
          { role: "bot", meta: "后端 Agent", text: result.reply || "后端没有返回可展示内容；我不会在前端临时拼模板，请稍后重试或换一个更具体的问题。" },
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
