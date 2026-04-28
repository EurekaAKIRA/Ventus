import type { ReactNode } from "react";
import { Space } from "antd";
import MetricCard from "./MetricCard";

type PageHeroProps = {
  eyebrow?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
};

type MetricItem = {
  title: string;
  value: number | string;
  color?: string;
  suffix?: string;
};

export function PageStack({ children }: { children: ReactNode }) {
  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      {children}
    </Space>
  );
}

export function PageHero({ eyebrow, title, subtitle, actions, meta }: PageHeroProps) {
  return (
    <div className="page-hero">
      <div className="page-hero__copy">
        {eyebrow ? <div className="page-hero__eyebrow">{eyebrow}</div> : null}
        <h1 className="page-hero__heading">{title}</h1>
        {subtitle ? <div className="page-hero__subtitle">{subtitle}</div> : null}
      </div>
      {actions ? <div className="page-hero__actions">{actions}</div> : null}
      {meta ? <div className="page-hero__meta">{meta}</div> : null}
    </div>
  );
}

export function MetricGrid({ items }: { items: MetricItem[] }) {
  return (
    <div className="metric-row">
      {items.map((item) => (
        <MetricCard key={item.title} title={item.title} value={item.value} color={item.color} suffix={item.suffix} />
      ))}
    </div>
  );
}
