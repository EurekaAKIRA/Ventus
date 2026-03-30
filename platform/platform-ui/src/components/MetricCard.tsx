import { Card, Statistic } from "antd";
import type { ReactNode } from "react";

interface MetricCardProps {
  title: string;
  value: number | string;
  prefix?: ReactNode;
  suffix?: string;
  color?: string;
}

export default function MetricCard({
  title,
  value,
  prefix,
  suffix,
  color,
}: MetricCardProps) {
  return (
    <Card bordered={false} hoverable>
      <Statistic
        title={title}
        value={value}
        prefix={prefix}
        suffix={suffix}
        valueStyle={color ? { color } : undefined}
      />
    </Card>
  );
}
