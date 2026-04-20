import { useEffect, useMemo, useState } from "react";
import dayjs, { type Dayjs } from "dayjs";
import { Button, Card, DatePicker, Input, Select, Space, Table, Tag, Typography, message } from "antd";
import type { AuditLogPayload } from "../types";
import { fetchAuditLogs } from "../api/system";

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

function toCsv(rows: AuditLogPayload[]): string {
  const headers = ["created_at", "action", "resource_type", "resource_id", "username", "display_name", "user_id", "ip_address", "detail_json"];
  const escapeCell = (value: unknown) => `"${String(value ?? "").replace(/"/g, '""')}"`;
  const lines = rows.map((item) =>
    [
      item.created_at,
      item.action,
      item.resource_type,
      item.resource_id,
      item.username,
      item.display_name,
      item.user_id,
      item.ip_address,
      item.detail_json ? JSON.stringify(item.detail_json) : "",
    ]
      .map(escapeCell)
      .join(","),
  );
  return [headers.join(","), ...lines].join("\n");
}

export default function AuditCenter() {
  const [items, setItems] = useState<AuditLogPayload[]>([]);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [actor, setActor] = useState("");
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null] | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);

  const queryParams = useMemo(
    () => ({
      keyword: keyword || undefined,
      resource_type: resourceType || undefined,
      actor: actor || undefined,
      start_time: range?.[0]?.startOf("day").toISOString(),
      end_time: range?.[1]?.endOf("day").toISOString(),
      page,
      page_size: pageSize,
    }),
    [actor, keyword, page, pageSize, range, resourceType],
  );

  const load = async () => {
    setLoading(true);
    try {
      const payload = await fetchAuditLogs(queryParams);
      setItems(payload.items);
      setTotal(payload.total);
    } catch (error) {
      message.error((error as Error).message || "加载审计日志失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 180);
    return () => window.clearTimeout(timer);
  }, [queryParams]);

  const exportCurrentRows = () => {
    try {
      const blob = new Blob([toCsv(items)], { type: "text/csv;charset=utf-8;" });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `audit_logs_${dayjs().format("YYYYMMDD_HHmmss")}.csv`;
      anchor.click();
      window.URL.revokeObjectURL(url);
      message.success("当前筛选结果已导出");
    } catch (error) {
      message.error((error as Error).message || "导出失败");
    }
  };

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <div>
        <Title level={4} style={{ marginBottom: 4 }}>审计日志</Title>
        <Text type="secondary">这里展示数据库里的关键操作留痕。现在可以按资源、操作人和时间范围筛选，也可以导出当前结果。</Text>
      </div>
      <Card bordered={false}>
        <Space style={{ marginBottom: 16 }} wrap>
          <Input
            allowClear
            placeholder="搜索 action / resource / detail"
            value={keyword}
            onChange={(e) => {
              setPage(1);
              setKeyword(e.target.value);
            }}
            style={{ width: 260 }}
          />
          <Input
            allowClear
            placeholder="操作人（用户名 / 显示名）"
            value={actor}
            onChange={(e) => {
              setPage(1);
              setActor(e.target.value);
            }}
            style={{ width: 220 }}
          />
          <Select
            allowClear
            placeholder="资源类型"
            value={resourceType || undefined}
            onChange={(value) => {
              setPage(1);
              setResourceType(String(value || ""));
            }}
            style={{ width: 180 }}
            options={[
              { value: "task", label: "task" },
              { value: "task_run", label: "task_run" },
              { value: "project", label: "project" },
              { value: "project_member", label: "project_member" },
              { value: "environment", label: "environment" },
              { value: "user", label: "user" },
              { value: "session", label: "session" },
            ]}
          />
          <RangePicker
            value={range}
            onChange={(value) => {
              setPage(1);
              setRange(value);
            }}
          />
          <Button onClick={exportCurrentRows} disabled={!items.length}>
            导出当前页 CSV
          </Button>
        </Space>
        <Table
          rowKey="id"
          loading={loading}
          dataSource={items}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (value) => `共 ${value} 条`,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPage);
              setPageSize(nextPageSize);
            },
          }}
          columns={[
            {
              title: "时间",
              dataIndex: "created_at",
              key: "created_at",
              width: 190,
              render: (v?: string) => (v ? new Date(v).toLocaleString() : "-"),
            },
            { title: "动作", dataIndex: "action", key: "action", width: 220 },
            {
              title: "操作人",
              key: "actor",
              width: 200,
              render: (_, record: AuditLogPayload) => (
                <Space direction="vertical" size={0}>
                  <Text>{record.display_name || record.username || "-"}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {record.username || record.user_id || "system"}
                  </Text>
                </Space>
              ),
            },
            {
              title: "资源类型",
              dataIndex: "resource_type",
              key: "resource_type",
              width: 140,
              render: (value: string) => <Tag>{value}</Tag>,
            },
            { title: "资源标识", dataIndex: "resource_id", key: "resource_id", ellipsis: true, width: 220 },
            {
              title: "详情",
              dataIndex: "detail_json",
              key: "detail_json",
              render: (value: unknown) => (
                <span style={{ fontFamily: "Consolas, monospace", fontSize: 12 }}>
                  {value ? JSON.stringify(value) : "-"}
                </span>
              ),
            },
          ]}
        />
      </Card>
    </Space>
  );
}
