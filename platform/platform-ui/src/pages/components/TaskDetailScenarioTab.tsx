import { Button, Card, Empty, Space, Tag, Typography } from "antd";
import type { ExtendedTaskDetail } from "../hooks/useTaskDetailData";

const { Text } = Typography;

export function TaskDetailScenarioTab(props: {
  detail: ExtendedTaskDetail;
  onRefreshScenarioSection: () => void;
  onOpenRawData: (title: string, data: unknown) => void;
}) {
  const { detail, onRefreshScenarioSection, onOpenRawData } = props;

  if (!detail.scenarios?.length) {
    return (
      <div className="empty-tab">
        <Empty description="暂无场景" />
      </div>
    );
  }

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <Text type="secondary">共 {detail.scenarios.length} 个场景，默认展示摘要。</Text>
        <Button size="small" onClick={() => onOpenRawData("场景列表（原始 JSON）", detail.scenarios)}>
          查看原始数据
        </Button>
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <Button size="small" onClick={onRefreshScenarioSection}>
          刷新
        </Button>
      </div>
      {detail.scenarios.map((scenario) => (
        <Card
          key={scenario.scenario_id}
          className="scenario-card"
          title={scenario.name}
          extra={<Tag color="purple">{scenario.priority}</Tag>}
          bordered={false}
        >
          <p>
            <Text strong>目标：</Text>
            {scenario.goal}
          </p>
          <p>
            <Text strong>前置条件：</Text>
            {scenario.preconditions.join("；") || "-"}
          </p>
          <div style={{ marginTop: 8 }}>
            <Text strong>步骤：</Text>
            <div style={{ marginTop: 6 }}>
              {scenario.steps.slice(0, 5).map((step, idx) => (
                <div key={`${scenario.scenario_id}_${idx}`} className="step-item">
                  <span className="step-keyword">{step.type}</span>
                  <span>{step.text}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      ))}
    </Space>
  );
}

