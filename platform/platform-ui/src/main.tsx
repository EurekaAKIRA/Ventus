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
          colorPrimary: "#3ecf8e",
          colorPrimaryHover: "#5dd39e",
          colorPrimaryActive: "#2aa871",
          colorInfo: "#3ecf8e",
          colorLink: "#8bf0bc",
          colorSuccess: "#3ecf8e",
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
            triggerBg: "rgba(62, 207, 142, 0.18)",
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
            darkItemSelectedBg: "rgba(62, 207, 142, 0.14)",
            darkItemHoverBg: "rgba(141, 162, 184, 0.08)",
            darkItemSelectedColor: "#ecfff6",
            itemBorderRadius: 14,
          },
          Button: {
            controlHeight: 42,
            borderRadius: 14,
            primaryShadow: "0 12px 28px rgba(62, 207, 142, 0.24)",
          },
          Table: {
            colorBgContainer: "rgba(14, 22, 33, 0.9)",
            headerBg: "rgba(20, 31, 45, 0.95)",
            rowHoverBg: "rgba(62, 207, 142, 0.06)",
            borderColor: "rgba(148, 163, 184, 0.12)",
          },
          Input: {
            colorBgContainer: "rgba(10, 18, 29, 0.88)",
            hoverBorderColor: "rgba(62, 207, 142, 0.6)",
            activeBorderColor: "#3ecf8e",
          },
          Select: {
            colorBgContainer: "rgba(10, 18, 29, 0.88)",
            optionSelectedBg: "rgba(62, 207, 142, 0.14)",
          },
          Tabs: {
            itemActiveColor: "#ecfff6",
            itemSelectedColor: "#ecfff6",
            itemHoverColor: "#a9f5cf",
            inkBarColor: "#3ecf8e",
          },
          Segmented: {
            trackBg: "rgba(10, 18, 29, 0.88)",
            itemSelectedBg: "rgba(62, 207, 142, 0.18)",
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
