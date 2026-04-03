import { Button, Card, Empty, List, Space, Tag, Typography } from "antd";
import type { ExtendedTaskDetail } from "../hooks/useTaskDetailData";

const { Text } = Typography;

type ParsedFeatureLine = {
  badge?: string;
  color?: string;
  content: string;
  secondary?: string;
  strong?: boolean;
  priority?: string;
  hideMarker?: boolean;
};

function parseFeatureLine(rawLine: string): ParsedFeatureLine {
  const line = rawLine.trim();
  if (!line) {
    return { content: " " };
  }

  const featureMatch = line.match(/^Feature:\s*(.+)$/i);
  if (featureMatch) {
    return { badge: "功能", color: "blue", content: featureMatch[1], strong: true };
  }
  const backgroundMatch = line.match(/^Background:\s*(.+)$/i);
  if (backgroundMatch) {
    return { badge: "背景", color: "geekblue", content: backgroundMatch[1], strong: true };
  }
  const scenarioMatch = line.match(/^Scenario:\s*(.+)$/i);
  if (scenarioMatch) {
    return { badge: "场景", color: "purple", content: scenarioMatch[1], strong: true };
  }
  const scenarioOutlineMatch = line.match(/^Scenario Outline:\s*(.+)$/i);
  if (scenarioOutlineMatch) {
    return { badge: "场景模板", color: "magenta", content: scenarioOutlineMatch[1], strong: true };
  }
  const examplesMatch = line.match(/^Examples:\s*(.*)$/i);
  if (examplesMatch) {
    return { badge: "示例", color: "cyan", content: examplesMatch[1] || "参数样例", strong: true };
  }

  const stepMatch = line.match(/^(Given|When|Then|And|But)\s+(.+)$/i);
  if (stepMatch) {
    const keyword = stepMatch[1].toLowerCase();
    const mapping: Record<string, { label: string; color: string }> = {
      given: { label: "前置", color: "default" },
      when: { label: "操作", color: "processing" },
      then: { label: "断言", color: "success" },
      and: { label: "并且", color: "gold" },
      but: { label: "但是", color: "warning" },
    };
    return {
      badge: mapping[keyword]?.label ?? stepMatch[1],
      color: mapping[keyword]?.color ?? "default",
      content: stepMatch[2],
      strong: keyword === "then",
    };
  }

  const commentMatch = line.match(/^#\s*(.+)$/);
  if (commentMatch) {
    const priorityMatch = commentMatch[1].match(/^priority\s*:\s*(P\d+)/i);
    if (priorityMatch) {
      return { content: "", priority: priorityMatch[1].toUpperCase(), hideMarker: true };
    }
    return { badge: "备注", color: "default", content: commentMatch[1], secondary: "注释信息" };
  }

  return { content: line };
}

export function TaskDetailDslTab(props: {
  detail: ExtendedTaskDetail;
  dslDisplayScenarios: NonNullable<ExtendedTaskDetail["test_case_dsl"]>["scenarios"];
  hasDslOverflow: boolean;
  dslExpanded: boolean;
  onToggleDslExpanded: () => void;
  onRefreshScenarioSection: () => void;
  onOpenRawData: (title: string, data: unknown) => void;
  featureText: string;
  featureDisplayLines: string[];
  hasFeatureOverflow: boolean;
  featureExpanded: boolean;
  onToggleFeatureExpanded: () => void;
  featurePreviewLines: number;
  dslPreviewScenarios: number;
}) {
  const {
    detail,
    dslDisplayScenarios,
    hasDslOverflow,
    dslExpanded,
    onToggleDslExpanded,
    onRefreshScenarioSection,
    onOpenRawData,
    featureText,
    featureDisplayLines,
    hasFeatureOverflow,
    featureExpanded,
    onToggleFeatureExpanded,
    featurePreviewLines,
    dslPreviewScenarios,
  } = props;

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Card bordered={false} title="测试用例 DSL" extra={<Button size="small" onClick={onRefreshScenarioSection}>刷新</Button>}>
        {detail.test_case_dsl ? (
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            <Text>DSL 版本：{detail.test_case_dsl.dsl_version}</Text>
            <Text>执行模式：{detail.test_case_dsl.execution_mode}</Text>
            <Text>场景数量：{detail.test_case_dsl.scenarios?.length ?? 0}</Text>
            {dslDisplayScenarios.length ? (
              <List
                size="small"
                bordered
                dataSource={dslDisplayScenarios}
                renderItem={(scenario) => (
                  <List.Item>
                    <Space direction="vertical" size={2} style={{ width: "100%" }}>
                      <Space>
                        <Text strong>{scenario.name}</Text>
                        {scenario.priority ? <Tag color="purple">{scenario.priority}</Tag> : null}
                      </Space>
                      <Text type="secondary">
                        步骤数：{scenario.steps?.length ?? 0}
                        {scenario.preconditions?.length ? `，前置条件：${scenario.preconditions.length}` : ""}
                      </Text>
                    </Space>
                  </List.Item>
                )}
              />
            ) : null}
            <Space>
              {hasDslOverflow ? (
                <Button size="small" onClick={onToggleDslExpanded}>
                  {dslExpanded ? "收起列表" : "展开列表"}
                </Button>
              ) : null}
              <Button size="small" onClick={() => onOpenRawData("DSL（原始 JSON）", detail.test_case_dsl)}>查看原始数据</Button>
            </Space>
            {hasDslOverflow ? (
              <Text type="secondary">当前为摘要视图（{dslPreviewScenarios} 个场景），可展开查看完整列表。</Text>
            ) : null}
          </Space>
        ) : (
          <Empty description="暂无 DSL" />
        )}
      </Card>

      <Card bordered={false} title="功能用例（Feature）">
        {featureText ? (
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            <List
              size="small"
              bordered
              dataSource={featureDisplayLines}
              renderItem={(line) => {
                const parsed = parseFeatureLine(line);
                return (
                  <List.Item className="feature-pretty-item">
                    <Space align="start" size={10} style={{ width: "100%" }}>
                      {parsed.badge ? (
                        <Tag color={parsed.color} className="feature-pretty-badge">{parsed.badge}</Tag>
                      ) : parsed.hideMarker ? null : (
                        <span className="feature-pretty-dot" />
                      )}
                      <Space direction="vertical" size={2} style={{ width: "100%" }}>
                        <Space align="start" style={{ width: "100%", justifyContent: "space-between" }}>
                          {parsed.content ? (
                            <Text strong={Boolean(parsed.strong)} className="feature-line-text">{parsed.content}</Text>
                          ) : (
                            <span />
                          )}
                          {parsed.priority ? <Tag color="purple" className="feature-priority-tag">{parsed.priority}</Tag> : null}
                        </Space>
                        {parsed.secondary ? <Text type="secondary">{parsed.secondary}</Text> : null}
                      </Space>
                    </Space>
                  </List.Item>
                );
              }}
            />
            <Space>
              {hasFeatureOverflow ? (
                <Button size="small" onClick={onToggleFeatureExpanded}>
                  {featureExpanded ? "收起文本" : "展开文本"}
                </Button>
              ) : null}
              <Button
                size="small"
                onClick={() => onOpenRawData("Feature 文本（源数据）", { feature_text: featureText })}
              >
                查看源数据
              </Button>
            </Space>
            {hasFeatureOverflow ? (
              <Text type="secondary">当前为摘要视图（{featurePreviewLines} 行），可展开查看完整文本。</Text>
            ) : null}
          </Space>
        ) : (
          <Empty description="暂无 Feature 文本" />
        )}
      </Card>
    </Space>
  );
}

