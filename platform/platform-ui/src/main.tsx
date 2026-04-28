import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import "./App.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: "#5865f2",
          colorPrimaryHover: "#6f7dfb",
          colorPrimaryActive: "#3f4dcc",
          colorInfo: "#2f81f7",
          colorLink: "#9aa8ff",
          colorSuccess: "#3fb950",
          colorWarning: "#f5b94c",
          colorError: "#ff6b6b",
          colorBgBase: "#091018",
          colorBgContainer: "#111925",
          colorBgElevated: "#162130",
          colorBorder: "rgba(148, 163, 184, 0.16)",
          colorSplit: "rgba(148, 163, 184, 0.12)",
          colorTextBase: "#e5edf5",
          colorText: "#e5edf5",
          colorTextSecondary: "#8da2b8",
          colorTextTertiary: "#61758a",
          borderRadius: 18,
          borderRadiusLG: 22,
          borderRadiusSM: 14,
          boxShadow:
            "0 24px 80px rgba(3, 8, 18, 0.38), inset 0 1px 0 rgba(255, 255, 255, 0.03)",
          fontFamily: '"Avenir Next", "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
        },
        components: {
          Layout: {
            bodyBg: "#091018",
            siderBg: "rgba(9, 16, 24, 0.92)",
            headerBg: "rgba(9, 16, 24, 0.72)",
            footerBg: "transparent",
            triggerBg: "rgba(88, 101, 242, 0.18)",
            triggerColor: "#dce7f1",
          },
          Card: {
            colorBgContainer: "rgba(17, 25, 37, 0.78)",
            boxShadowTertiary:
              "0 20px 60px rgba(2, 6, 23, 0.32), inset 0 1px 0 rgba(255, 255, 255, 0.02)",
          },
          Menu: {
            darkItemBg: "transparent",
            darkSubMenuItemBg: "transparent",
            darkItemSelectedBg: "rgba(88, 101, 242, 0.18)",
            darkItemHoverBg: "rgba(141, 162, 184, 0.08)",
            darkItemSelectedColor: "#eef2ff",
            itemBorderRadius: 14,
          },
          Button: {
            controlHeight: 42,
            borderRadius: 14,
            primaryShadow: "0 12px 28px rgba(88, 101, 242, 0.28)",
          },
          Table: {
            colorBgContainer: "rgba(14, 22, 33, 0.9)",
            headerBg: "rgba(20, 31, 45, 0.95)",
            rowHoverBg: "rgba(88, 101, 242, 0.08)",
            borderColor: "rgba(148, 163, 184, 0.12)",
          },
          Input: {
            colorBgContainer: "rgba(10, 18, 29, 0.88)",
            hoverBorderColor: "rgba(88, 101, 242, 0.68)",
            activeBorderColor: "#5865f2",
          },
          Select: {
            colorBgContainer: "rgba(10, 18, 29, 0.88)",
            optionSelectedBg: "rgba(88, 101, 242, 0.18)",
          },
          Tabs: {
            itemActiveColor: "#eef2ff",
            itemSelectedColor: "#eef2ff",
            itemHoverColor: "#b7c2ff",
            inkBarColor: "#5865f2",
          },
          Segmented: {
            trackBg: "rgba(10, 18, 29, 0.88)",
            itemSelectedBg: "rgba(88, 101, 242, 0.18)",
          },
        },
      }}
    >
      <AuthProvider>
        <App />
      </AuthProvider>
    </ConfigProvider>
  </React.StrictMode>,
);
