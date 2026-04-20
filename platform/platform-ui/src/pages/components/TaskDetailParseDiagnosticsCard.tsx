import { Button, Card, Descriptions, Empty, List, Space, Tag, Typography } from "antd";
import type { ExtendedTaskDetail } from "../hooks/useTaskDetailData";

const { Text } = Typography;

function formatPercent(value: number | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  return `${(value * 100).toFixed(1)}%`;
}

export function TaskDetailParseDiagnosticsCard(props: {
  detail: ExtendedTaskDetail;
  onOpenRawData: (title: string, data: unknown) => void;
}) {
  const { detail, onOpenRawData } = props;
  const meta = detail.parse_metadata;

  if (!meta) {
    return (
      <Card bordered={false} title="解析诊断">
        <Empty description="暂无解析诊断信息" />
      </Card>
    );
  }

  const retrievalMetrics = meta.retrieval_metrics;
  const phaseTimings = Object.entries(meta.performance?.phase_timings_ms ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);

  return (
    <Card
      bordered={false}
      title="解析诊断"
      extra={
        <Space>
          <Button size="small" onClick={() => onOpenRawData("解析元数据（原始 JSON）", meta)}>
            查看原始元数据
          </Button>
          {detail.retrieved_context?.length ? (
            <Button size="small" onClick={() => onOpenRawData("检索上下文（原始 JSON）", detail.retrieved_context)}>
              查看检索上下文
            </Button>
          ) : null}
        </Space>
      }
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Space wrap>
          <Tag color="blue">{meta.parse_mode || "rules"}</Tag>
          <Tag color={meta.llm_used ? "success" : meta.llm_attempted ? "warning" : "default"}>
            {meta.llm_used ? "LLM 已生效" : meta.llm_attempted ? "LLM 尝试失败" : "规则解析"}
          </Tag>
          <Tag color={meta.rag_enabled ? "processing" : "default"}>
            {meta.rag_enabled ? "RAG 开启" : "RAG 关闭"}
          </Tag>
          <Tag color={meta.rerank_enabled ? "purple" : "default"}>
            {meta.retrieval_mode || "keyword"}
          </Tag>
        </Space>

        <Descriptions size="small" column={2} bordered>
          <Descriptions.Item label="LLM 提供者">{meta.llm_provider_profile || "-"}</Descriptions.Item>
          <Descriptions.Item label="模型配置">{meta.model_profile || "-"}</Descriptions.Item>
          <Descriptions.Item label="Retrieval Top-K">{meta.retrieval_top_k ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="文档分块数">{meta.chunk_count ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="原始字符数">{meta.document_char_count ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="清洗后字符数">{meta.cleaned_char_count ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="Embedding 覆盖率">{formatPercent(retrievalMetrics?.embedding_coverage)}</Descriptions.Item>
          <Descriptions.Item label="估算 Embedding 调用">{meta.estimated_embedding_calls ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="检索返回片段">{retrievalMetrics?.returned_count ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="重复率">{formatPercent(retrievalMetrics?.duplicate_ratio)}</Descriptions.Item>
          <Descriptions.Item label="覆盖率">{formatPercent(retrievalMetrics?.coverage_ratio)}</Descriptions.Item>
          <Descriptions.Item label="平均得分">
            {typeof retrievalMetrics?.score_avg === "number" ? retrievalMetrics.score_avg.toFixed(3) : "-"}
          </Descriptions.Item>
          <Descriptions.Item label="处理层级">{meta.processing_tier || "-"}</Descriptions.Item>
          <Descriptions.Item label="检测到的 Base URL">{meta.detected_base_url || "-"}</Descriptions.Item>
        </Descriptions>

        {meta.fallback_reason || meta.rag_fallback_reason || meta.llm_error_type || retrievalMetrics?.embedding_error ? (
          <Space direction="vertical" size={4} style={{ width: "100%" }}>
            <Text strong>降级与异常提示</Text>
            {meta.fallback_reason ? <Text type="warning">fallback_reason: {meta.fallback_reason}</Text> : null}
            {meta.rag_fallback_reason ? <Text type="warning">rag_fallback_reason: {meta.rag_fallback_reason}</Text> : null}
            {meta.llm_error_type ? <Text type="danger">llm_error_type: {meta.llm_error_type}</Text> : null}
            {retrievalMetrics?.embedding_error ? <Text type="danger">embedding_error: {retrievalMetrics.embedding_error}</Text> : null}
          </Space>
        ) : null}

        {phaseTimings.length ? (
          <div>
            <Text strong style={{ display: "block", marginBottom: 8 }}>阶段耗时 Top</Text>
            <List
              size="small"
              dataSource={phaseTimings}
              renderItem={([key, value]) => (
                <List.Item>
                  <Space style={{ width: "100%", justifyContent: "space-between" }}>
                    <Text>{key}</Text>
                    <Text type="secondary">{value.toFixed(1)} ms</Text>
                  </Space>
                </List.Item>
              )}
            />
          </div>
        ) : null}
      </Space>
    </Card>
  );
}
