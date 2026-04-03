import { Button, Card, Col, Empty, List, Row, Space, Tag, Typography } from "antd";
import type { ExtendedTaskDetail } from "../hooks/useTaskDetailData";

const { Text } = Typography;

export function TaskDetailParsedTab(props: {
  detail: ExtendedTaskDetail;
  hasParsedResult: boolean;
  onRefreshParsedSection: () => void;
  onOpenRawData: (title: string, data: unknown) => void;
}) {
  const { detail, hasParsedResult, onRefreshParsedSection, onOpenRawData } = props;

  if (!hasParsedResult) {
    return (
      <div className="empty-tab">
        <Empty description="暂无解析结果" />
      </div>
    );
  }

  return (
    <Row gutter={[16, 16]}>
      <Col span={24}>
        <Card
          bordered={false}
          title="结构化需求"
          extra={
            <Button size="small" onClick={onRefreshParsedSection}>
              刷新
            </Button>
          }
        >
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <div>
              <Text strong>目标：</Text>
              <Text style={{ marginLeft: 8 }}>{detail.parsed_requirement?.objective || "-"}</Text>
            </div>
            <div>
              <Text strong>关键动作：</Text>
              <Text style={{ marginLeft: 8 }}>{detail.parsed_requirement?.actions?.slice(0, 4).join("；") || "-"}</Text>
            </div>
            <div>
              <Text strong>预期结果：</Text>
              <Text style={{ marginLeft: 8 }}>
                {detail.parsed_requirement?.expected_results?.slice(0, 4).join("；") || "-"}
              </Text>
            </div>
            <div>
              <Text strong>歧义点：</Text>
              <Text style={{ marginLeft: 8 }}>
                {detail.parsed_requirement?.ambiguities?.length ? detail.parsed_requirement.ambiguities.slice(0, 3).join("；") : "无"}
              </Text>
            </div>
            <Button size="small" onClick={() => onOpenRawData("结构化需求（原始 JSON）", detail.parsed_requirement)}>
              查看原始数据
            </Button>
          </Space>
        </Card>
      </Col>
      <Col span={24}>
        <Card bordered={false} title="检索上下文">
          {detail.retrieved_context?.length ? (
            <List
              dataSource={detail.retrieved_context.slice(0, 5)}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    title={
                      <Space>
                        <Tag>{item.chunk_id}</Tag>
                        <Text>{item.section_title}</Text>
                        <Text type="secondary">score: {item.score}</Text>
                      </Space>
                    }
                    description={
                      <Space direction="vertical" size={2}>
                        <Text>{item.content}</Text>
                        <Text type="secondary">{item.source_file}</Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          ) : (
            <Empty description="暂无检索上下文" />
          )}
          {detail.retrieved_context?.length ? (
            <Button size="small" onClick={() => onOpenRawData("检索上下文（原始 JSON）", detail.retrieved_context)}>
              查看原始数据
            </Button>
          ) : null}
        </Card>
      </Col>
    </Row>
  );
}

