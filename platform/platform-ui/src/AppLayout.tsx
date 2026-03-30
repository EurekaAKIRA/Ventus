import { useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu } from "antd";
import {
  DashboardOutlined,
  UnorderedListOutlined,
  PlusCircleOutlined,
  ExperimentOutlined,
} from "@ant-design/icons";

const { Sider, Content, Footer } = Layout;

const menuItems = [
  { key: "/dashboard", icon: <DashboardOutlined />, label: "仪表盘" },
  { key: "/tasks", icon: <UnorderedListOutlined />, label: "任务列表" },
  { key: "/tasks/create", icon: <PlusCircleOutlined />, label: "创建任务" },
];

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const selectedKey =
    menuItems.find((m) => location.pathname.startsWith(m.key))?.key ??
    "/dashboard";

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        width={220}
      >
        <div
          className="logo"
          style={{ height: 64, lineHeight: "64px", cursor: "pointer" }}
          onClick={() => navigate("/dashboard")}
        >
          <ExperimentOutlined style={{ fontSize: 22 }} />
          {!collapsed && <span>LaVague 测试平台</span>}
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
        <Content className="page-container">
          <Outlet />
        </Content>
        <Footer style={{ textAlign: "center", color: "#999", fontSize: 13 }}>
          LaVague QA Platform &copy; {new Date().getFullYear()}
        </Footer>
      </Layout>
    </Layout>
  );
}
