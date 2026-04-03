import { Card, List, Typography } from "antd";
import type { TaskArtifactItem } from "../../types";

const { Text } = Typography;

type TaskDetailArtifactsTabProps = {
  artifacts: TaskArtifactItem[];
  onOpenArtifact: (item: TaskArtifactItem) => void | Promise<void>;
};

export function TaskDetailArtifactsTab(props: TaskDetailArtifactsTabProps) {
  const { artifacts, onOpenArtifact } = props;

  return (
    <List
      grid={{ gutter: 16, xs: 1, md: 2, lg: 3 }}
      dataSource={artifacts}
      renderItem={(item) => (
        <List.Item>
          <Card className="artifact-card" bordered={false} title={item.label} onClick={() => void onOpenArtifact(item)}>
            <Text type="secondary">类型：{item.type}</Text>
            <br />
            <Text type="secondary">更新时间：{new Date(item.updated_at).toLocaleString()}</Text>
          </Card>
        </List.Item>
      )}
    />
  );
}
