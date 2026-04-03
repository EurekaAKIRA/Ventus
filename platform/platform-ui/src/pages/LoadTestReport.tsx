import { Alert, Card, Typography } from "antd";
import { useMemo } from "react";

const { Paragraph, Text } = Typography;

/**
 * JMeter HTML 报告嵌入：默认加载 public/loadtest-report/index.html；
 * 生产可将整包静态资源部署到任意源，并设置 VITE_JMETER_REPORT_URL（完整 URL，含 path 至 index.html 或目录以 / 结尾由网关处理）。
 */
export default function LoadTestReport() {
  const src = useMemo(() => {
    const override = (import.meta.env.VITE_JMETER_REPORT_URL || "").trim();
    if (override) {
      return override.endsWith("/") ? `${override}index.html` : override;
    }
    const base = import.meta.env.BASE_URL || "/";
    const prefix = base.endsWith("/") ? base.slice(0, -1) : base;
    return `${prefix}/loadtest-report/index.html`;
  }, []);

  return (
    <div style={{ padding: "0 8px" }}>
      <Card title="压测报告（JMeter HTML）" bordered={false}>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="说明"
          description={
            <Paragraph style={{ marginBottom: 0 }}>
              下方为内嵌页面。若仍为占位页，请将 JMeter{" "}
              <Text code>-e -o</Text> 生成的<strong>整包文件</strong>复制到{" "}
              <Text code>platform-ui/public/loadtest-report/</Text> 后重新构建或刷新。
              生产环境可配置 <Text code>VITE_JMETER_REPORT_URL</Text> 指向已部署的报告地址。
            </Paragraph>
          }
        />
        <iframe
          title="JMeter HTML Report"
          src={src}
          style={{
            width: "100%",
            height: "min(78vh, 900px)",
            border: "1px solid #f0f0f0",
            borderRadius: 8,
            background: "#fff",
          }}
        />
      </Card>
    </div>
  );
}
