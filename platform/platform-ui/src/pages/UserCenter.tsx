import { useEffect, useMemo, useState } from "react";
import {
  Avatar,
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
import {
  UserAddOutlined,
  UserOutlined,
} from "@ant-design/icons";
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
  const [memberEditorOpen, setMemberEditorOpen] = useState(false);
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
  const currentMembership = useMemo(
    () => members.find((member) => member.user_id === user?.id || member.username === user?.username) ?? null,
    [members, user?.id, user?.username],
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
      setMemberEditorOpen(false);
      await loadMembers();
      message.success("项目成员已保存");
    } catch (error) {
      message.error((error as Error).message || "添加项目成员失败");
    } finally {
      setAddingMember(false);
    }
  };

  return (
    <div className="github-settings">
      <aside className="github-settings__sidebar">
        <div className="github-profile-card">
          <Avatar size={64} src={user?.avatar_url || undefined} icon={<UserOutlined />} />
          <div className="github-profile-card__name">{user?.display_name || user?.username || "当前用户"}</div>
          <div className="github-profile-card__handle">@{user?.username || "-"}</div>
          <Tag className="github-profile-card__tag">{user?.is_platform_admin ? "Platform admin" : "User"}</Tag>
        </div>
        <nav className="github-settings-nav" aria-label="用户设置">
          <a className="github-settings-nav__item is-active">Public profile</a>
          <a className="github-settings-nav__item">Projects</a>
          <a className="github-settings-nav__item">Members</a>
        </nav>
      </aside>

      <main className="github-settings__main">
        <div className="github-settings__heading">
          <div>
            <Title level={3} className="github-settings__title">用户中心</Title>
            <Text type="secondary">管理个人资料、项目权限和成员协作。</Text>
          </div>
        </div>

        <Card bordered={false} className="github-settings-card" title="Public profile">
          <Row gutter={24}>
            <Col xs={24} lg={16}>
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
            </Col>
            <Col xs={24} lg={8}>
              <div className="github-profile-preview">
                <Avatar size={96} src={user?.avatar_url || undefined} icon={<UserOutlined />} />
                <Text type="secondary">头像地址可选；未填写时显示默认头像。</Text>
              </div>
            </Col>
          </Row>
        </Card>

        <Card className="github-settings-card" bordered={false} title="Projects">
          {currentProject ? (
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <div className="github-project-current">
                <div>
                  <Text strong>{currentProject.name}</Text>
                  <div className="github-project-current__desc">{currentProject.description || "当前项目暂无描述"}</div>
                </div>
                <Space>
                  <Tag>{currentMembership?.role || "member"}</Tag>
                  {currentProject.is_default ? <Tag color="green">default</Tag> : null}
                </Space>
              </div>
              <div className="github-project-list">
                {projects.map((project) => (
                  <div key={project.id} className={`github-project-row${project.id === currentProjectId ? " is-active" : ""}`}>
                    <span>{project.name}</span>
                    <Text type="secondary">{project.is_default ? "default" : "project"}</Text>
                  </div>
                ))}
              </div>
            </Space>
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前没有可用项目" />
          )}
        </Card>

        <Card
          bordered={false}
          className="github-settings-card"
          title="Members"
          extra={
            <Space>
              <Button onClick={() => void loadMembers()} loading={loadingMembers}>
                刷新
              </Button>
              <Button
                type={memberEditorOpen ? "default" : "primary"}
                icon={<UserAddOutlined />}
                disabled={!currentProjectId}
                onClick={() => setMemberEditorOpen((value) => !value)}
              >
                {memberEditorOpen ? "收起添加" : "添加成员"}
              </Button>
            </Space>
          }
        >
          {memberEditorOpen ? (
            <div className="github-inline-editor">
              <Form form={memberForm} layout="vertical" onFinish={handleAddMember}>
                <Row gutter={16} align="bottom">
                  <Col xs={24} lg={12}>
                    <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入或选择用户名" }]}>
                      <AutoComplete options={userOptions} onSearch={handleUserSearch} placeholder="输入用户名进行搜索" filterOption={false} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} lg={8}>
                    <Form.Item name="role" label="项目角色" initialValue="viewer" rules={[{ required: true, message: "请选择角色" }]}>
                      <Select
                        options={[
                          { value: "owner", label: "owner · 项目管理" },
                          { value: "editor", label: "editor · 编辑协作" },
                          { value: "runner", label: "runner · 执行任务" },
                          { value: "viewer", label: "viewer · 只读查看" },
                        ]}
                      />
                    </Form.Item>
                  </Col>
                  <Col xs={24} lg={4}>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={addingMember} block>
                        保存成员
                      </Button>
                    </Form.Item>
                  </Col>
                </Row>
              </Form>
            </div>
          ) : null}
          <List
            className="github-member-list"
            loading={loadingMembers}
            locale={{ emptyText: "当前项目暂无成员数据" }}
            dataSource={members}
            renderItem={(item) => (
              <List.Item>
                <div className="github-member-row">
                  <div className="github-member-row__identity">
                    <Avatar size={32} src={item.avatar_url || undefined} icon={<UserOutlined />} />
                    <Space direction="vertical" size={0}>
                      <Text strong>{item.display_name || item.username || item.user_id}</Text>
                      <Text type="secondary">{item.username}</Text>
                    </Space>
                  </div>
                  <Tag color={item.role === "owner" ? "gold" : item.role === "editor" ? "processing" : "default"}>{item.role}</Tag>
                </div>
              </List.Item>
            )}
          />
        </Card>
      </main>
    </div>
  );
}
