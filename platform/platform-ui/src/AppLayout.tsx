import { useMemo, useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Avatar, Button, Dropdown, Layout, Menu, Select, Space, Typography, message } from "antd";
import {
  DashboardOutlined,
  UnorderedListOutlined,
  PlusCircleOutlined,
  ExperimentOutlined,
  HistoryOutlined,
  DeploymentUnitOutlined,
  BugOutlined,
  LoginOutlined,
  LogoutOutlined,
  PlusOutlined,
  DatabaseOutlined,
  UserOutlined,
  ApiOutlined,
  FileDoneOutlined,
  ScheduleOutlined,
} from "@ant-design/icons";
import { useAuth } from "./auth/AuthContext";

const { Sider, Content, Footer, Header } = Layout;
const { Text, Title } = Typography;

const menuItems = [
  { key: "/dashboard", icon: <DashboardOutlined />, label: "仪表盘" },
  { key: "/tasks", icon: <UnorderedListOutlined />, label: "任务列表" },
  { key: "/tasks/history", icon: <HistoryOutlined />, label: "历史任务" },
  { key: "/interfaces", icon: <ApiOutlined />, label: "接口资产" },
  { key: "/test-cases", icon: <FileDoneOutlined />, label: "用例资产" },
  { key: "/test-suites", icon: <ScheduleOutlined />, label: "用例套件" },
  { key: "/defects", icon: <BugOutlined />, label: "缺陷管理" },
  { key: "/tasks/create", icon: <PlusCircleOutlined />, label: "创建任务" },
  { key: "/environments", icon: <DeploymentUnitOutlined />, label: "环境管理" },
  { key: "/audit", icon: <DatabaseOutlined />, label: "审计日志", adminOnly: true },
  { key: "/users/me", icon: <UserOutlined />, label: "用户中心" },
];

const pageMeta: Record<string, { title: string }> = {
  "/dashboard": { title: "测试运营总览" },
  "/tasks": { title: "任务与执行工作台" },
  "/tasks/history": { title: "历史与回归追踪" },
  "/interfaces": { title: "接口资产中心" },
  "/test-cases": { title: "用例资产中心" },
  "/test-suites": { title: "用例套件与回归计划" },
  "/defects": { title: "缺陷与修复协同" },
  "/agent": { title: "文档诊断 Agent" },
  "/tasks/create": { title: "新建测试任务" },
  "/environments": { title: "环境与鉴权配置" },
  "/audit": { title: "平台审计视图" },
  "/users/me": { title: "用户与项目协作" },
};

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { ready, isAuthenticated, user, projects, currentProjectId, setCurrentProjectId, logout, createProject } = useAuth();
  const visibleMenuItems = useMemo(
    () => menuItems.filter((item) => !item.adminOnly || Boolean(user?.is_platform_admin)),
    [user?.is_platform_admin],
  );

  const selectedKey =
    visibleMenuItems
      .filter((m) => location.pathname.startsWith(m.key))
      .sort((a, b) => b.key.length - a.key.length)[0]?.key ?? "/dashboard";
  const currentPageMeta = pageMeta[selectedKey] ?? pageMeta["/dashboard"];

  const projectOptions = useMemo(
    () =>
      projects.map((project) => ({
        value: project.id,
        label: project.is_default ? `${project.name}（默认）` : project.name,
      })),
    [projects],
  );

  const handleCreateProject = async () => {
    const name = window.prompt("请输入新项目名称");
    if (!name?.trim()) {
      return;
    }
    try {
      await createProject({ name: name.trim() });
      message.success("项目已创建并切换");
    } catch (error) {
      message.error((error as Error).message || "创建项目失败");
    }
  };

  const userMenuItems = isAuthenticated
    ? [
        {
          key: "logout",
          icon: <LogoutOutlined />,
          label: "退出登录",
          onClick: async () => {
            await logout();
            navigate("/login", { replace: true });
          },
        },
      ]
    : [
        {
          key: "login",
          icon: <LoginOutlined />,
          label: "登录 / 注册",
          onClick: () => navigate("/login"),
        },
      ];

  return (
    <Layout className="app-shell">
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        width={220}
        className="app-shell__sider"
      >
        <div className={`app-shell__brand${collapsed ? " is-collapsed" : ""}`} onClick={() => navigate("/dashboard")}>
          <div className="app-shell__brand-mark">
            <ExperimentOutlined />
          </div>
          {!collapsed ? (
            <div className="app-shell__brand-copy">
              <span className="app-shell__brand-title">Ventus QA</span>
            </div>
          ) : null}
        </div>
        <Menu
          className="app-shell__menu"
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={visibleMenuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout className="app-shell__main">
        <Header className="app-shell__header">
          <div className="app-shell__header-copy">
            <Title level={3} className="app-shell__header-title">
              {currentPageMeta.title}
            </Title>
          </div>
          <Space size={12} wrap className="app-shell__toolbar">
            <div className="app-shell__project-switch">
              <Text className="app-shell__project-label">当前项目</Text>
            <Select
              value={currentProjectId || undefined}
              className="app-shell__project-select"
              style={{ minWidth: 240 }}
              placeholder={ready ? "未选择项目" : "加载中..."}
              options={projectOptions}
              disabled={!ready || !isAuthenticated || !projectOptions.length}
              onChange={(value) => setCurrentProjectId(String(value))}
            />
            </div>
            <Button className="app-shell__ghost-button" icon={<PlusOutlined />} onClick={() => void handleCreateProject()} disabled={!isAuthenticated}>
              新建项目
            </Button>
          </Space>
          <Dropdown menu={{ items: userMenuItems }} trigger={["click"]}>
            <Button type="text" className="app-shell__user-button">
              <Space size={8}>
                <Avatar size="small" icon={<UserOutlined />} />
                <span>{isAuthenticated ? user?.display_name || user?.username || "当前用户" : "未登录"}</span>
              </Space>
            </Button>
          </Dropdown>
        </Header>
        <Content className="page-container">
          <Outlet />
        </Content>
        <Footer className="app-shell__footer">
          Ventus QA Platform © {new Date().getFullYear()}
        </Footer>
      </Layout>
    </Layout>
  );
}
