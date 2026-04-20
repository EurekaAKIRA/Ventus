import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Alert, Button, Card, Form, Input, Space, Tabs, Typography, message } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { useAuth } from "../auth/AuthContext";

const { Title, Text } = Typography;

type AuthTabKey = "login" | "register";

function resolveNextPath(location: ReturnType<typeof useLocation>): string {
  const next = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;
  if (next && next !== "/login") {
    return next;
  }
  return "/dashboard";
}

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, register, ready, isAuthenticated } = useAuth();
  const [activeTab, setActiveTab] = useState<AuthTabKey>("login");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (ready && isAuthenticated) {
      navigate(resolveNextPath(location), { replace: true });
    }
  }, [ready, isAuthenticated, location, navigate]);

  const handleLogin = async (values: { username: string; password: string }) => {
    setSubmitting(true);
    try {
      await login(values);
      message.success("登录成功");
      navigate(resolveNextPath(location), { replace: true });
    } catch (error) {
      message.error((error as Error).message || "登录失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRegister = async (values: {
    username: string;
    password: string;
    confirm_password: string;
    display_name?: string;
    email?: string;
  }) => {
    if (values.password !== values.confirm_password) {
      message.error("两次输入的密码不一致");
      return;
    }
    setSubmitting(true);
    try {
      await register({
        username: values.username,
        password: values.password,
        display_name: values.display_name,
        email: values.email,
      });
      message.success("注册并登录成功");
      navigate(resolveNextPath(location), { replace: true });
    } catch (error) {
      message.error((error as Error).message || "注册失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        background:
          "radial-gradient(circle at top left, rgba(114,46,209,0.14), transparent 34%), linear-gradient(135deg, #f7f3ff 0%, #f5f7ff 42%, #ffffff 100%)",
      }}
    >
      <Card bordered={false} style={{ width: "100%", maxWidth: 520, boxShadow: "0 16px 40px rgba(31, 35, 41, 0.08)" }}>
        <Space direction="vertical" size={18} style={{ width: "100%" }}>
          <div>
            <Title level={3} style={{ marginBottom: 8 }}>
              Ventus 平台登录
            </Title>
            <Text type="secondary">登录后即可按项目管理任务、历史与执行结果，前后端会自动复用当前项目上下文。</Text>
          </div>
          <Alert
            type="info"
            showIcon
            message="首次使用可直接注册"
            description="注册成功后，服务端会自动创建默认工作区与默认项目。"
          />
          <Tabs
            activeKey={activeTab}
            onChange={(value) => setActiveTab(value as AuthTabKey)}
            items={[
              {
                key: "login",
                label: "登录",
                children: (
                  <Form layout="vertical" onFinish={handleLogin}>
                    <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入用户名" }]}>
                      <Input prefix={<UserOutlined />} placeholder="请输入用户名" />
                    </Form.Item>
                    <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
                      <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" />
                    </Form.Item>
                    <Button type="primary" htmlType="submit" loading={submitting} block>
                      登录
                    </Button>
                  </Form>
                ),
              },
              {
                key: "register",
                label: "注册",
                children: (
                  <Form layout="vertical" onFinish={handleRegister}>
                    <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入用户名" }]}>
                      <Input prefix={<UserOutlined />} placeholder="请输入用户名" />
                    </Form.Item>
                    <Form.Item name="display_name" label="显示名称">
                      <Input placeholder="可选，用于页面展示" />
                    </Form.Item>
                    <Form.Item name="email" label="邮箱">
                      <Input placeholder="可选，用于通知或找回" />
                    </Form.Item>
                    <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
                      <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" />
                    </Form.Item>
                    <Form.Item
                      name="confirm_password"
                      label="确认密码"
                      rules={[{ required: true, message: "请再次输入密码" }]}
                    >
                      <Input.Password prefix={<LockOutlined />} placeholder="请再次输入密码" />
                    </Form.Item>
                    <Button type="primary" htmlType="submit" loading={submitting} block>
                      注册并登录
                    </Button>
                  </Form>
                ),
              },
            ]}
          />
        </Space>
      </Card>
    </div>
  );
}
