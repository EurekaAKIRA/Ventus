import { ConfigProvider, theme as antdTheme, type ThemeConfig } from "antd";
import zhCN from "antd/locale/zh_CN";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type PlatformThemeMode = "dark" | "light";

type PlatformThemeContextValue = {
  mode: PlatformThemeMode;
  isLightMode: boolean;
  setMode: (mode: PlatformThemeMode) => void;
  toggleMode: () => void;
};

const THEME_STORAGE_KEY = "ventus-ui-theme-mode";

const PlatformThemeContext = createContext<PlatformThemeContextValue | null>(null);

function readInitialMode(): PlatformThemeMode {
  if (typeof window === "undefined") {
    return "dark";
  }

  const savedMode = window.localStorage.getItem(THEME_STORAGE_KEY);
  return savedMode === "light" ? "light" : "dark";
}

const darkTheme: ThemeConfig = {
  algorithm: antdTheme.darkAlgorithm,
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
    boxShadow: "0 24px 80px rgba(3, 8, 18, 0.38), inset 0 1px 0 rgba(255, 255, 255, 0.03)",
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
      boxShadowTertiary: "0 20px 60px rgba(2, 6, 23, 0.32), inset 0 1px 0 rgba(255, 255, 255, 0.02)",
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
};

const lightTheme: ThemeConfig = {
  algorithm: antdTheme.defaultAlgorithm,
  token: {
    colorPrimary: "#5865f2",
    colorPrimaryHover: "#4f5edc",
    colorPrimaryActive: "#3f4dcc",
    colorInfo: "#2563eb",
    colorLink: "#4f5edc",
    colorSuccess: "#238636",
    colorWarning: "#b7791f",
    colorError: "#d92d20",
    colorBgBase: "#f6f8fc",
    colorBgContainer: "#ffffff",
    colorBgElevated: "#ffffff",
    colorBorder: "rgba(43, 55, 78, 0.14)",
    colorSplit: "rgba(43, 55, 78, 0.1)",
    colorTextBase: "#172033",
    colorText: "#172033",
    colorTextSecondary: "#5c6b80",
    colorTextTertiary: "#8794a8",
    borderRadius: 18,
    borderRadiusLG: 22,
    borderRadiusSM: 14,
    boxShadow: "0 18px 52px rgba(31, 45, 72, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.76)",
    fontFamily: '"Avenir Next", "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
  },
  components: {
    Layout: {
      bodyBg: "#f6f8fc",
      siderBg: "rgba(255, 255, 255, 0.92)",
      headerBg: "rgba(255, 255, 255, 0.82)",
      footerBg: "transparent",
      triggerBg: "rgba(88, 101, 242, 0.12)",
      triggerColor: "#46526a",
    },
    Card: {
      colorBgContainer: "rgba(255, 255, 255, 0.88)",
      boxShadowTertiary: "0 18px 52px rgba(31, 45, 72, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.78)",
    },
    Menu: {
      itemBg: "transparent",
      itemSelectedBg: "rgba(88, 101, 242, 0.12)",
      itemHoverBg: "rgba(88, 101, 242, 0.08)",
      itemSelectedColor: "#2f3fc7",
      itemColor: "#536176",
      itemBorderRadius: 14,
    },
    Button: {
      controlHeight: 42,
      borderRadius: 14,
      primaryShadow: "0 12px 24px rgba(88, 101, 242, 0.18)",
    },
    Table: {
      colorBgContainer: "rgba(255, 255, 255, 0.92)",
      headerBg: "#eef2f8",
      rowHoverBg: "rgba(88, 101, 242, 0.06)",
      borderColor: "rgba(43, 55, 78, 0.1)",
    },
    Input: {
      colorBgContainer: "rgba(255, 255, 255, 0.96)",
      hoverBorderColor: "rgba(88, 101, 242, 0.5)",
      activeBorderColor: "#5865f2",
    },
    Select: {
      colorBgContainer: "rgba(255, 255, 255, 0.96)",
      optionSelectedBg: "rgba(88, 101, 242, 0.12)",
    },
    Tabs: {
      itemActiveColor: "#2f3fc7",
      itemSelectedColor: "#2f3fc7",
      itemHoverColor: "#4f5edc",
      inkBarColor: "#5865f2",
    },
    Segmented: {
      trackBg: "#edf1f7",
      itemSelectedBg: "#ffffff",
    },
  },
};

export function PlatformThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<PlatformThemeMode>(() => readInitialMode());

  useEffect(() => {
    document.documentElement.dataset.theme = mode;
    document.documentElement.style.colorScheme = mode;
    window.localStorage.setItem(THEME_STORAGE_KEY, mode);
  }, [mode]);

  const toggleMode = useCallback(() => {
    setMode((current) => (current === "light" ? "dark" : "light"));
  }, []);

  const value = useMemo(
    () => ({
      mode,
      isLightMode: mode === "light",
      setMode,
      toggleMode,
    }),
    [mode, toggleMode],
  );

  return (
    <PlatformThemeContext.Provider value={value}>
      <ConfigProvider locale={zhCN} theme={mode === "light" ? lightTheme : darkTheme}>
        {children}
      </ConfigProvider>
    </PlatformThemeContext.Provider>
  );
}

export function usePlatformTheme() {
  const context = useContext(PlatformThemeContext);
  if (!context) {
    throw new Error("usePlatformTheme must be used within PlatformThemeProvider");
  }
  return context;
}
