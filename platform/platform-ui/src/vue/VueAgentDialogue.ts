import { computed, defineComponent, h, type App as VueApp, type PropType } from "vue";
import { createApp } from "vue";
import type { TaskDraftAgentPayload } from "../types";

export type VueAgentDialogueProps = {
  payload: TaskDraftAgentPayload | null;
  loading: boolean;
  stale: boolean;
  activeView: string;
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
  },
  setup(props) {
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
        ...(payload.warnings ?? []).map((item) => ({ type: "提示", text: item, level: "medium" })),
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

    return () => {
      const payload = props.payload;
      const verdict = payload?.diagnostic_verdict;
      const currentTone = toneClass(verdict?.severity);
      return h("section", { class: ["vue-agent-dialogue", `is-${currentTone}`] }, [
        h("div", { class: "vue-agent-dialogue__head" }, [
          h("div", [
            h("span", { class: "vue-agent-dialogue__eyebrow" }, "Vue3 Agent Dialogue"),
            h("h3", verdict?.label || (props.loading ? "Agent 正在分析" : "等待诊断输入")),
          ]),
          h("span", { class: ["vue-agent-dialogue__state", props.loading ? "is-loading" : props.stale ? "is-stale" : "is-ready"] }, props.loading ? "分析中" : props.stale ? "待刷新" : "同步"),
        ]),
        h("p", { class: "vue-agent-dialogue__reply" }, payload?.reply || "导入接口文档后，后端 Agent 会返回任务草案、质量门禁、追问和知识依据。"),
        h("div", { class: "vue-agent-dialogue__meter" }, [
          h("div", { class: "vue-agent-dialogue__meter-ring", style: { "--agent-ready": `${readiness.value}%` } }, [
            h("strong", `${readiness.value}`),
            h("span", "ready"),
          ]),
          h("div", { class: "vue-agent-dialogue__metrics" }, [
            h("div", [h("span", "可信度"), h("strong", confidenceText(payload?.summary?.confidence_level))]),
            h("div", [h("span", "接口"), h("strong", `${verdict?.endpoint_count ?? payload?.recognized_endpoints?.length ?? 0}`)]),
            h("div", [h("span", "场景"), h("strong", `${verdict?.estimated_scenario_count ?? payload?.scenario_outlook?.estimated_scenario_count ?? 0}`)]),
            h("div", [h("span", "知识"), h("strong", `${payload?.knowledge_hits?.length ?? 0}`)]),
          ]),
        ]),
        h("div", { class: "vue-agent-dialogue__gates" }, [
          h("span", [h("strong", `${gateSummary.value.pass}`), "通过"]),
          h("span", [h("strong", `${gateSummary.value.warn}`), "提醒"]),
          h("span", [h("strong", `${gateSummary.value.block}`), "阻断"]),
        ]),
        openItems.value.length
          ? h(
              "div",
              { class: "vue-agent-dialogue__thread" },
              openItems.value.map((item) =>
                h("div", { key: `${item.type}-${item.text}`, class: [`vue-agent-dialogue__message`, `is-${item.level}`] }, [
                  h("span", item.type),
                  h("p", item.text),
                ]),
              ),
            )
          : h("div", { class: "vue-agent-dialogue__empty" }, props.activeView === "overview" ? "暂无待处理追问" : "切换视图后继续查看对应建议"),
      ]);
    };
  },
});

export function mountVueAgentDialogue(el: Element, props: VueAgentDialogueProps): VueApp {
  return createApp(VueAgentDialogue, props);
}
