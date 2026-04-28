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
  CrownOutlined,
  MailOutlined,
  ProjectOutlined,
  SafetyCertificateOutlined,
  UserAddOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useAuth } from "../auth/AuthContext";
import { addProjectMember, fetchProject, searchUsers, updateMyProfile } from "../api/auth";
import type { ProjectMemberPayload, UserProfile } from "../types";
import MetricCard from "../components/MetricCard";

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
  const ownerCount = useMemo(() => members.filter((member) => member.role === "owner").length, [members]);
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
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <div className="user-center-hero">
        <div className="user-center-hero__identity">
          <Avatar size={72} src={user?.avatar_url || undefined} icon={<UserOutlined />} className="user-center-hero__avatar" />
          <div className="user-center-hero__copy">
            <Text className="page-hero__eyebrow">Account Center</Text>
            <Title level={3} className="page-hero__title">用户中心</Title>
            <Text className="user-center-hero__subtitle">管理个人资料、项目成员和当前账号的协作权限。</Text>
          </div>
        </div>
        <div className="page-hero__meta">
          <div className="page-meta-chip">
            <span className="page-meta-chip__label">当前用户</span>
            <span className="page-meta-chip__value">{user?.display_name || user?.username || "-"}</span>
          </div>
          <div className="page-meta-chip">
            <span className="page-meta-chip__label">当前项目</span>
            <span className="page-meta-chip__value">{currentProject?.name || "未选择"}</span>
          </div>
          <div className="page-meta-chip">
            <span className="page-meta-chip__label">平台角色</span>
            <span className="page-meta-chip__value">{user?.is_platform_admin ? "管理员" : "普通用户"}</span>
          </div>
        </div>
      </div>

      <div className="metric-row">
        <MetricCard title="可访问项目" value={projects.length} />
        <MetricCard title="当前项目成员" value={members.length} color="#4f8cff" />
        <MetricCard title="Owner 数量" value={ownerCount} color="#f5b94c" />
        <MetricCard title="当前项目角色" value={currentMembership?.role || "-"} color="#3ecf8e" />
      </div>

      <Row gutter={16}>
        <Col xs={24} xl={9}>
          <Card bordered={false} className="panel-card panel-card--form" title="个人资料" extra={<UserOutlined />}>
            <div className="profile-spotlight">
              <Avatar size={56} src={user?.avatar_url || undefined} icon={<UserOutlined />} className="profile-spotlight__avatar" />
              <div className="profile-spotlight__meta">
                <Text strong className="profile-spotlight__name">
                  {user?.display_name || user?.username || "当前用户"}
                </Text>
                <Text type="secondary">@{user?.username || "-"}</Text>
                <div className="profile-spotlight__chips">
                  <span className={`surface-chip ${user?.is_platform_admin ? "surface-chip--gold" : ""}`}>
                    {user?.is_platform_admin ? <CrownOutlined /> : <SafetyCertificateOutlined />}{" "}
                    <strong>{user?.is_platform_admin ? "平台管理员" : "普通用户"}</strong>
                  </span>
                  <span className="surface-chip">
                    <MailOutlined /> <strong>{user?.email || "未填写邮箱"}</strong>
                  </span>
                </div>
              </div>
            </div>
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

        <Col xs={24} xl={15}>
          <Card className="panel-card" bordered={false} title="当前项目" extra={<ProjectOutlined />}>
            {currentProject ? (
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <div className="project-focus-card">
                  <div>
                    <Text className="project-focus-card__label">当前协作空间</Text>
                    <Title level={4} className="project-focus-card__title">
                      {currentProject.name}
                    </Title>
                    <Text className="project-focus-card__desc">{currentProject.description || "当前项目暂无描述"}</Text>
                  </div>
                  <div className="project-focus-card__badges">
                    <Tag color={currentMembership?.role === "owner" ? "gold" : "processing"}>{currentMembership?.role || "member"}</Tag>
                    {currentProject.is_default ? <Tag color="green">默认项目</Tag> : null}
                  </div>
                </div>
                <div className="project-pill-grid">
                  {projects.map((project) => (
                    <div key={project.id} className={`project-pill${project.id === currentProjectId ? " is-active" : ""}`}>
                      <span className="project-pill__name">{project.name}</span>
                      <span className="project-pill__meta">{project.is_default ? "默认" : "项目"}</span>
                    </div>
                  ))}
                </div>
              </Space>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前没有可用项目" />
            )}
          </Card>
        </Col>
      </Row>

      <Card
        bordered={false}
        className="panel-card"
        title="项目成员"
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
          <div className="member-inline-editor">
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
          className="member-list"
          loading={loadingMembers}
          locale={{ emptyText: "当前项目暂无成员数据" }}
          dataSource={members}
          renderItem={(item) => (
            <List.Item>
              <div className="member-row">
                <div className="member-row__identity">
                  <Avatar size={36} icon={<UserOutlined />} />
                  <Space direction="vertical" size={2}>
                    <Text strong className="member-row__name">
                      {item.display_name || item.username || item.user_id}
                    </Text>
                    <Text type="secondary">{item.username}</Text>
                  </Space>
                </div>
                <Space className="member-row__actions">
                  <Tag color={item.role === "owner" ? "gold" : item.role === "editor" ? "processing" : "default"}>{item.role}</Tag>
                </Space>
              </div>
            </List.Item>
          )}
        />
      </Card>
    </Space>
  );
}
