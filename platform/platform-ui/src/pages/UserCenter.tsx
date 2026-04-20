import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  AutoComplete,
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  List,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { TeamOutlined, UserOutlined } from "@ant-design/icons";
import { useAuth } from "../auth/AuthContext";
import { addProjectMember, fetchProject, searchUsers, updateMyProfile } from "../api/auth";
import type { ProjectMemberPayload, UserProfile } from "../types";

const { Title, Text } = Typography;

export default function UserCenter() {
  const { user, projects, currentProjectId, reloadProfile } = useAuth();
  const [profileForm] = Form.useForm();
  const [memberForm] = Form.useForm();
  const [savingProfile, setSavingProfile] = useState(false);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [addingMember, setAddingMember] = useState(false);
  const [members, setMembers] = useState<ProjectMemberPayload[]>([]);
  const [userOptions, setUserOptions] = useState<Array<{ value: string; label: string }>>([]);

  useEffect(() => {
    profileForm.setFieldsValue({
      username: user?.username ?? "",
      display_name: user?.display_name ?? "",
      email: user?.email ?? "",
      avatar_url: user?.avatar_url ?? "",
    });
  }, [user, profileForm]);

  const loadMembers = async () => {
    if (!currentProjectId) {
      setMembers([]);
      return;
    }
    setLoadingMembers(true);
    try {
      const payload = await fetchProject(currentProjectId);
      setMembers(payload.members ?? []);
    } catch (error) {
      message.error((error as Error).message || "加载项目成员失败");
      setMembers([]);
    } finally {
      setLoadingMembers(false);
    }
  };

  useEffect(() => {
    void loadMembers();
  }, [currentProjectId]);

  const currentProject = useMemo(
    () => projects.find((item) => item.id === currentProjectId) ?? null,
    [projects, currentProjectId],
  );

  const handleSaveProfile = async (values: { display_name?: string; email?: string; avatar_url?: string }) => {
    setSavingProfile(true);
    try {
      await updateMyProfile(values);
      await reloadProfile();
      message.success("个人资料已更新");
    } catch (error) {
      message.error((error as Error).message || "更新个人资料失败");
    } finally {
      setSavingProfile(false);
    }
  };

  const handleUserSearch = async (keyword: string) => {
    const q = String(keyword || "").trim();
    if (!q) {
      setUserOptions([]);
      return;
    }
    try {
      const users = await searchUsers({ keyword: q, limit: 10 });
      setUserOptions(
        users.map((item: UserProfile) => ({
          value: item.username,
          label: `${item.display_name || item.username}${item.email ? ` (${item.email})` : ""}`,
        })),
      );
    } catch {
      setUserOptions([]);
    }
  };

  const handleAddMember = async (values: { username: string; role: string }) => {
    if (!currentProjectId) {
      message.warning("请先选择项目");
      return;
    }
    setAddingMember(true);
    try {
      await addProjectMember(currentProjectId, values);
      memberForm.resetFields();
      await loadMembers();
      message.success("项目成员已保存");
    } catch (error) {
      message.error((error as Error).message || "添加项目成员失败");
    } finally {
      setAddingMember(false);
    }
  };

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <div>
        <Title level={4} style={{ marginBottom: 4 }}>
          用户中心
        </Title>
        <Text type="secondary">这里补齐了真正可操作的用户模块入口：个人资料、当前项目、项目成员管理。</Text>
      </div>

      <Row gutter={16}>
        <Col xs={24} xl={10}>
          <Card bordered={false} title="个人资料" extra={<UserOutlined />}>
            <Form form={profileForm} layout="vertical" onFinish={handleSaveProfile}>
              <Form.Item name="username" label="用户名">
                <Input disabled />
              </Form.Item>
              <Form.Item name="display_name" label="显示名称">
                <Input placeholder="请输入显示名称" />
              </Form.Item>
              <Form.Item name="email" label="邮箱">
                <Input placeholder="请输入邮箱" />
              </Form.Item>
              <Form.Item name="avatar_url" label="头像地址">
                <Input placeholder="可选" />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={savingProfile}>
                保存资料
              </Button>
            </Form>
          </Card>
        </Col>

        <Col xs={24} xl={14}>
          <Card
            bordered={false}
            title="当前项目"
            extra={<TeamOutlined />}
          >
            {currentProject ? (
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <Alert
                  type="info"
                  showIcon
                  message={currentProject.name}
                  description={currentProject.description || "当前项目暂无描述"}
                />
                <div>
                  <Text type="secondary">你可访问的项目</Text>
                  <div style={{ marginTop: 10 }}>
                    <Space wrap>
                      {projects.map((project) => (
                        <Tag key={project.id} color={project.id === currentProjectId ? "processing" : "default"}>
                          {project.name}
                        </Tag>
                      ))}
                    </Space>
                  </div>
                </div>
              </Space>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前没有可用项目" />
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} xl={9}>
          <Card bordered={false} title="添加项目成员">
            <Form form={memberForm} layout="vertical" onFinish={handleAddMember}>
              <Form.Item
                name="username"
                label="用户名"
                rules={[{ required: true, message: "请输入或选择用户名" }]}
              >
                <AutoComplete
                  options={userOptions}
                  onSearch={handleUserSearch}
                  placeholder="输入用户名进行搜索"
                  filterOption={false}
                />
              </Form.Item>
              <Form.Item
                name="role"
                label="项目角色"
                initialValue="viewer"
                rules={[{ required: true, message: "请选择角色" }]}
              >
                <Select
                  options={[
                    { value: "owner", label: "owner" },
                    { value: "editor", label: "editor" },
                    { value: "runner", label: "runner" },
                    { value: "viewer", label: "viewer" },
                  ]}
                />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={addingMember} disabled={!currentProjectId}>
                保存成员
              </Button>
            </Form>
          </Card>
        </Col>

        <Col xs={24} xl={15}>
          <Card bordered={false} title="项目成员">
            <List
              loading={loadingMembers}
              locale={{ emptyText: "当前项目暂无成员数据" }}
              dataSource={members}
              renderItem={(item) => (
                <List.Item>
                  <Space style={{ width: "100%", justifyContent: "space-between" }}>
                    <Space direction="vertical" size={2}>
                      <Text strong>{item.display_name || item.username || item.user_id}</Text>
                      <Text type="secondary">{item.username}</Text>
                    </Space>
                    <Space>
                      <Tag color={item.role === "owner" ? "gold" : item.role === "editor" ? "processing" : "default"}>
                        {item.role}
                      </Tag>
                    </Space>
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
