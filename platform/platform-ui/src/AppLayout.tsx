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
  LoginOutlined,
  LogoutOutlined,
  PlusOutlined,
  DatabaseOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useAuth } from "./auth/AuthContext";

const { Sider, Content, Footer, Header } = Layout;
const { Text } = Typography;

const menuItems = [
  { key: "/dashboard", icon: <DashboardOutlined />, label: "仪表盘" },
  { key: "/tasks", icon: <UnorderedListOutlined />, label: "任务列表" },
  { key: "/tasks/history", icon: <HistoryOutlined />, label: "历史任务" },
  { key: "/tasks/create", icon: <PlusCircleOutlined />, label: "创建任务" },
  { key: "/environments", icon: <DeploymentUnitOutlined />, label: "环境管理" },
  { key: "/audit", icon: <DatabaseOutlined />, label: "审计日志" },
  { key: "/users/me", icon: <UserOutlined />, label: "用户中心" },
];

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { ready, isAuthenticated, user, projects, currentProjectId, setCurrentProjectId, logout, createProject } = useAuth();

  // Prefer the most specific match so `/tasks/create` doesn't get overridden by `/tasks`.
  const selectedKey =
    menuItems
      .filter((m) => location.pathname.startsWith(m.key))
      .sort((a, b) => b.key.length - a.key.length)[0]?.key ?? "/dashboard";

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
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        width={220}
        style={{
          position: "sticky",
          top: 0,
          height: "100vh",
          overflow: "auto",
        }}
      >
        <div
          className="logo"
          style={{ height: 64, lineHeight: "64px", cursor: "pointer" }}
          onClick={() => navigate("/dashboard")}
        >
          <ExperimentOutlined style={{ fontSize: 22 }} />
          {!collapsed && <span>Ventus 测试平台</span>}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: "0 24px",
            background: "#fff",
            borderBottom: "1px solid rgba(5, 5, 5, 0.06)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 16,
          }}
        >
          <Space size={12} wrap>
            <Text type="secondary">当前项目</Text>
            <Select
              value={currentProjectId || undefined}
              style={{ minWidth: 220 }}
              placeholder={ready ? "未选择项目" : "加载中..."}
              options={projectOptions}
              disabled={!ready || !isAuthenticated || !projectOptions.length}
              onChange={(value) => setCurrentProjectId(String(value))}
            />
            <Button icon={<PlusOutlined />} onClick={() => void handleCreateProject()} disabled={!isAuthenticated}>
              新建项目
            </Button>
          </Space>
          <Dropdown menu={{ items: userMenuItems }} trigger={["click"]}>
            <Button type="text">
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
        <Footer style={{ textAlign: "center", color: "#999", fontSize: 13 }}>
          Ventus QA Platform &copy; {new Date().getFullYear()}
        </Footer>
      </Layout>
    </Layout>
  );
}
