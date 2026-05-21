import { computed, defineComponent, h, ref, type App as VueApp, type PropType } from "vue";
import { createApp } from "vue";
import type { TaskDraftAgentPayload } from "../types";

export type VueAgentDialogueProps = {
  payload: TaskDraftAgentPayload | null;
  loading: boolean;
  stale: boolean;
  activeView: string;
  onAnalyze?: () => void;
  onApply?: () => void;
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

const VueAgentDialogue = defineComponent({
  name: "VueAgentDialogue",
  props: {
    payload: {
      type: Object as PropType<TaskDraftAgentPayload | null>,
      default: null,
    },
    loading: {
      type: Boolean,
      default: false,
    },
    stale: {
      type: Boolean,
      default: false,
    },
    activeView: {
      type: String,
      default: "overview",
    },
    onAnalyze: {
      type: Function as PropType<() => void>,
      default: undefined,
    },
    onApply: {
      type: Function as PropType<() => void>,
      default: undefined,
    },
    canApply: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const draft = ref("");
    const messages = ref<ChatMessage[]>([
      {
        role: "bot",
        meta: "测试建议机器人",
        text: "我会根据当前 Agent 诊断结果，给你整理用例、断言、风险和 RAG 依据方面的测试建议。",
      },
    ]);

    const readiness = computed(() => {
      const score = props.payload?.summary?.ready_score ?? 0;
      const max = props.payload?.summary?.max_score ?? 0;
      return max > 0 ? Math.round((score / max) * 100) : 0;
    });

    const openItems = computed(() => {
      const payload = props.payload;
      if (!payload) return [];
      return [
        ...(payload.follow_up_questions ?? []).map((item) => ({ type: "追问", text: item.question, level: item.priority || "medium" })),
        ...(payload.risks ?? []).map((item) => ({ type: "风险", text: item, level: "high" })),
        ...(payload.coverage_gaps ?? []).map((item) => ({ type: "缺口", text: item, level: "medium" })),
      ].slice(0, 4);
    });

    const gateSummary = computed(() => {
      const gates = props.payload?.quality_gates ?? [];
      return {
        pass: gates.filter((item) => item.status === "pass").length,
        warn: gates.filter((item) => item.status === "warn").length,
        block: gates.filter((item) => item.status === "block").length,
      };
    });

    const quickPrompts = computed(() => [
      "给我测试场景建议",
      "需要补哪些断言",
      "当前最大风险是什么",
      props.payload?.knowledge_hits?.length ? "RAG依据够不够" : "如何补充知识依据",
    ]);

    const sendMessage = (text?: string) => {
      const nextText = String(text ?? draft.value).trim();
      if (!nextText) return;
      const nextMessages: ChatMessage[] = [
        ...messages.value,
        { role: "user", text: nextText },
        { role: "bot", meta: "建议", text: buildSuggestionReply(props.payload, nextText) },
      ];
      messages.value = nextMessages.slice(-8);
      draft.value = "";
    };

    return () => {
      const payload = props.payload;
      const verdict = payload?.diagnostic_verdict;
      const currentTone = toneClass(verdict?.severity);
      const statusText = props.loading ? "分析中" : props.stale ? "待刷新" : payload ? "已同步" : "待输入";

      return h("aside", { class: ["vue-agent-dialogue", `is-${currentTone}`] }, [
        h("div", { class: "vue-agent-dialogue__head" }, [
          h("div", [
            h("span", { class: "vue-agent-dialogue__eyebrow" }, "Agent Mode"),
            h("h3", "测试建议 Agent"),
          ]),
          h("div", { class: "vue-agent-dialogue__head-actions" }, [
            h("span", { class: ["vue-agent-dialogue__state", props.loading ? "is-loading" : props.stale ? "is-stale" : "is-ready"] }, statusText),
          ]),
        ]),
        h("div", { class: "vue-agent-dialogue__actions" }, [
          h("button", { type: "button", onClick: () => props.onAnalyze?.(), disabled: props.loading }, props.payload ? "重新分析" : "生成建议"),
          h("button", { type: "button", class: "is-primary", onClick: () => props.onApply?.(), disabled: !props.canApply || props.stale }, "一键回填"),
        ]),
        h("div", { class: "vue-agent-dialogue__snapshot" }, [
          h("div", { class: "vue-agent-dialogue__meter-ring", style: { "--agent-ready": `${readiness.value}%` } }, [
            h("strong", `${readiness.value}`),
            h("span", "ready"),
          ]),
          h("div", { class: "vue-agent-dialogue__metrics" }, [
            h("div", [h("span", "诊断"), h("strong", verdict?.label || "等待分析")]),
            h("div", [h("span", "可信度"), h("strong", confidenceText(payload?.summary?.confidence_level))]),
            h("div", [h("span", "接口"), h("strong", `${verdict?.endpoint_count ?? payload?.recognized_endpoints?.length ?? 0}`)]),
            h("div", [h("span", "场景"), h("strong", `${verdict?.estimated_scenario_count ?? payload?.scenario_outlook?.estimated_scenario_count ?? 0}`)]),
          ]),
        ]),
        h("p", { class: "vue-agent-dialogue__reply" }, payload?.reply || "导入接口文档后，我会给出测试场景、断言、风险和知识依据建议。"),
        h("div", { class: "vue-agent-dialogue__gates" }, [
          h("span", [h("strong", `${gateSummary.value.pass}`), "通过"]),
          h("span", [h("strong", `${gateSummary.value.warn}`), "提醒"]),
          h("span", [h("strong", `${gateSummary.value.block}`), "阻断"]),
        ]),
        h(
          "div",
          { class: "vue-agent-dialogue__thread" },
          messages.value.map((item, index) =>
            h("div", { key: `${item.role}-${index}-${item.text}`, class: ["vue-agent-dialogue__message", `is-${item.role}`] }, [
              h("span", item.meta || (item.role === "bot" ? "Bot" : "你")),
              h("p", item.text),
            ]),
          ),
        ),
        openItems.value.length
          ? h(
              "div",
              { class: "vue-agent-dialogue__tips" },
              openItems.value.map((item) =>
                h("button", { key: `${item.type}-${item.text}`, class: [`vue-agent-dialogue__tip`, `is-${item.level}`], onClick: () => sendMessage(item.text) }, [
                  h("span", item.type),
                  h("strong", item.text),
                ]),
              ),
            )
          : null,
        h(
          "div",
          { class: "vue-agent-dialogue__quick" },
          quickPrompts.value.map((item) =>
            h("button", { key: item, onClick: () => sendMessage(item) }, item),
          ),
        ),
        h("form", { class: "vue-agent-dialogue__composer", onSubmit: (event: Event) => { event.preventDefault(); sendMessage(); } }, [
          h("input", {
            value: draft.value,
            placeholder: "问我：场景、断言、风险、RAG依据...",
            onInput: (event: Event) => {
              draft.value = (event.target as HTMLInputElement).value;
            },
          }),
          h("button", { type: "submit" }, "发送"),
        ]),
      ]);
    };
  },
});

export function mountVueAgentDialogue(el: Element, props: VueAgentDialogueProps): VueApp {
  return createApp(VueAgentDialogue, props);
}
