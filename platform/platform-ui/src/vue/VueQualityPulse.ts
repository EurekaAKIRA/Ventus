import { computed, defineComponent, h, type App as VueApp, type PropType } from "vue";
import { createApp } from "vue";

export type VueQualityPulseStats = {
  total: number;
  passed: number;
  failed: number;
  running: number;
  pending: number;
  passRate: number;
  failRate: number;
  qualityScore: number;
};

export type VueQualityPulseStatus = {
  status: string;
  label: string;
  count: number;
  percent: number;
  color: string;
};

export type VueQualityPulseProps = {
  stats: VueQualityPulseStats;
  statuses: VueQualityPulseStatus[];
};

const VueQualityPulse = defineComponent({
  name: "VueQualityPulse",
  props: {
    stats: {
      type: Object as PropType<VueQualityPulseStats>,
      required: true,
    },
    statuses: {
      type: Array as PropType<VueQualityPulseStatus[]>,
      required: true,
    },
  },
  setup(props) {
    const dominantStatus = computed(() => {
      return [...props.statuses].sort((a, b) => b.count - a.count)[0];
    });

    const riskLevel = computed(() => {
      if (props.stats.failRate >= 30) return { label: "高风险", className: "danger" };
      if (props.stats.failRate > 0 || props.stats.running > 0) return { label: "需关注", className: "warning" };
      return { label: "稳定", className: "success" };
    });

    const scoreStyle = computed(() => ({
      "--vue-quality-score": `${Math.max(0, Math.min(100, props.stats.qualityScore))}%`,
    }));

    return () =>
      h("section", { class: "vue-quality-pulse" }, [
        h("div", { class: "vue-quality-pulse__head" }, [
          h("div", [
            h("span", { class: "vue-quality-pulse__eyebrow" }, "Vue3 状态洞察"),
            h("h3", "质量脉冲"),
          ]),
          h("span", { class: ["vue-quality-pulse__badge", riskLevel.value.className] }, riskLevel.value.label),
        ]),
        h("div", { class: "vue-quality-pulse__score" }, [
          h("div", { class: "vue-quality-pulse__ring", style: scoreStyle.value }, [
            h("strong", `${props.stats.qualityScore}`),
            h("span", "score"),
          ]),
          h("div", { class: "vue-quality-pulse__summary" }, [
            h("div", [h("span", "通过"), h("strong", `${props.stats.passRate}%`)]),
            h("div", [h("span", "失败"), h("strong", `${props.stats.failRate}%`)]),
            h("div", [h("span", "执行中"), h("strong", `${props.stats.running}`)]),
          ]),
        ]),
        h(
          "div",
          { class: "vue-quality-pulse__bars" },
          props.statuses
            .filter((item) => item.count > 0)
            .map((item) =>
              h("div", { key: item.status, class: "vue-quality-pulse__bar-row" }, [
                h("div", { class: "vue-quality-pulse__bar-meta" }, [
                  h("span", item.label),
                  h("strong", `${item.count}`),
                ]),
                h("div", { class: "vue-quality-pulse__track" }, [
                  h("i", {
                    style: {
                      width: `${Math.max(2, item.percent)}%`,
                      backgroundColor: item.color,
                    },
                  }),
                ]),
              ]),
            ),
        ),
        h("p", { class: "vue-quality-pulse__hint" }, [
          "当前最多状态：",
          h("strong", dominantStatus.value ? `${dominantStatus.value.label} ${dominantStatus.value.count}` : "暂无任务"),
        ]),
      ]);
  },
});

export function mountVueQualityPulse(el: Element, props: VueQualityPulseProps): VueApp {
  return createApp(VueQualityPulse, props);
}
