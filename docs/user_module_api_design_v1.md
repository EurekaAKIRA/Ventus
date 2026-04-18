# 用户模块接口设计 v1

## 1. 目标

本文定义平台后续用户模块与项目权限模块的第一版接口设计，服务对象包括：

- 前端页面联调
- FastAPI 路由设计
- 权限依赖注入
- 用户/项目/任务归属体系接入

本设计与现有 `task-center` API 并行规划，目标是：

- 不破坏当前任务接口主链路
- 给注册、登录、`/me`、项目成员管理和任务归属控制提供统一契约

## 2. 设计原则

- 继续沿用当前统一响应 envelope 风格
- 鉴权优先采用 `Bearer access_token`
- 刷新令牌走单独接口
- 用户模块与任务模块解耦，但在任务创建/列表/执行时注入当前用户上下文
- 项目是权限控制的主要作用域

## 3. 统一响应格式

成功：

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {},
  "timestamp": "2026-04-17T12:00:00Z"
}
```

失败：

```json
{
  "success": false,
  "code": "UNAUTHORIZED",
  "message": "invalid token",
  "data": {
    "detail": {}
  },
  "timestamp": "2026-04-17T12:00:00Z"
}
```

## 4. 鉴权模型

### 4.1 Token 策略

建议：

- `access_token`：JWT，短时有效
- `refresh_token`：数据库可撤销

### 4.2 建议 Header

```http
Authorization: Bearer <access_token>
```

### 4.3 JWT 建议 claims

- `sub`：用户 ID
- `username`
- `workspace_id`
- `roles`
- `exp`

## 5. 用户认证接口

---

## 5.1 注册

- 方法：`POST`
- 路径：`/api/auth/register`
- 用途：创建本地账号

请求体：

```json
{
  "username": "demo_user",
  "email": "demo@example.com",
  "password": "StrongPassword123",
  "display_name": "Demo User"
}
```

返回体 `data`：

```json
{
  "user": {
    "id": "uuid",
    "username": "demo_user",
    "email": "demo@example.com",
    "display_name": "Demo User",
    "status": "active"
  }
}
```

建议错误码：

- `VALIDATION_ERROR`
- `USERNAME_ALREADY_EXISTS`
- `EMAIL_ALREADY_EXISTS`

---

## 5.2 登录

- 方法：`POST`
- 路径：`/api/auth/login`
- 用途：账号密码登录

请求体：

```json
{
  "username": "demo_user",
  "password": "StrongPassword123"
}
```

返回体 `data`：

```json
{
  "access_token": "jwt-access-token",
  "refresh_token": "refresh-token",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "username": "demo_user",
    "display_name": "Demo User",
    "roles": ["member"]
  }
}
```

建议错误码：

- `INVALID_CREDENTIALS`
- `ACCOUNT_DISABLED`

---

## 5.3 刷新令牌

- 方法：`POST`
- 路径：`/api/auth/refresh`
- 用途：刷新 access token

请求体：

```json
{
  "refresh_token": "refresh-token"
}
```

返回体 `data`：

```json
{
  "access_token": "new-jwt-access-token",
  "token_type": "bearer",
  "expires_in": 3600
}
```

建议错误码：

- `INVALID_REFRESH_TOKEN`
- `REFRESH_TOKEN_EXPIRED`

---

## 5.4 登出

- 方法：`POST`
- 路径：`/api/auth/logout`
- 用途：撤销 refresh token / 当前会话

请求体：

```json
{
  "refresh_token": "refresh-token"
}
```

返回体 `data`：

```json
{
  "logged_out": true
}
```

---

## 5.5 当前用户信息

- 方法：`GET`
- 路径：`/api/auth/me`
- 用途：获取当前登录用户

返回体 `data`：

```json
{
  "id": "uuid",
  "username": "demo_user",
  "email": "demo@example.com",
  "display_name": "Demo User",
  "roles": ["member"],
  "workspace_id": "default-workspace"
}
```

## 6. 用户资料接口

---

## 6.1 获取我的资料

- 方法：`GET`
- 路径：`/api/users/me`

返回体 `data`：

```json
{
  "id": "uuid",
  "username": "demo_user",
  "email": "demo@example.com",
  "display_name": "Demo User",
  "avatar_url": null,
  "status": "active",
  "created_at": "2026-04-17T12:00:00Z"
}
```

---

## 6.2 更新我的资料

- 方法：`PATCH`
- 路径：`/api/users/me`

请求体：

```json
{
  "display_name": "New Name",
  "avatar_url": "https://example.com/avatar.png"
}
```

返回体 `data`：

```json
{
  "updated": true,
  "user": {
    "id": "uuid",
    "display_name": "New Name",
    "avatar_url": "https://example.com/avatar.png"
  }
}
```

## 7. 项目接口

---

## 7.1 创建项目

- 方法：`POST`
- 路径：`/api/projects`

请求体：

```json
{
  "name": "API Challenges Project",
  "description": "Project for API auto-testing"
}
```

返回体 `data`：

```json
{
  "project": {
    "id": "uuid",
    "name": "API Challenges Project",
    "description": "Project for API auto-testing",
    "role": "owner"
  }
}
```

---

## 7.2 获取项目列表

- 方法：`GET`
- 路径：`/api/projects`

查询参数：

- `keyword`
- `page`
- `page_size`

返回体 `data`：

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "API Challenges Project",
      "description": "Project for API auto-testing",
      "role": "owner",
      "created_at": "2026-04-17T12:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

---

## 7.3 获取项目详情

- 方法：`GET`
- 路径：`/api/projects/{project_id}`

返回体 `data`：

```json
{
  "id": "uuid",
  "name": "API Challenges Project",
  "description": "Project for API auto-testing",
  "role": "owner",
  "created_at": "2026-04-17T12:00:00Z"
}
```

---

## 7.4 更新项目

- 方法：`PATCH`
- 路径：`/api/projects/{project_id}`

请求体：

```json
{
  "name": "Updated Project Name",
  "description": "Updated description"
}
```

---

## 7.5 项目成员列表

- 方法：`GET`
- 路径：`/api/projects/{project_id}/members`

返回体 `data`：

```json
{
  "items": [
    {
      "user_id": "uuid",
      "username": "demo_user",
      "display_name": "Demo User",
      "role": "owner"
    }
  ]
}
```

---

## 7.6 添加项目成员

- 方法：`POST`
- 路径：`/api/projects/{project_id}/members`

请求体：

```json
{
  "username": "runner_user",
  "role": "runner"
}
```

返回体 `data`：

```json
{
  "added": true,
  "member": {
    "username": "runner_user",
    "role": "runner"
  }
}
```

---

## 7.7 修改项目成员角色

- 方法：`PATCH`
- 路径：`/api/projects/{project_id}/members/{user_id}`

请求体：

```json
{
  "role": "editor"
}
```

---

## 7.8 移除项目成员

- 方法：`DELETE`
- 路径：`/api/projects/{project_id}/members/{user_id}`

## 8. 环境配置接口

环境接口建议从全局环境逐步收敛为项目级环境。

---

## 8.1 创建环境

- 方法：`POST`
- 路径：`/api/projects/{project_id}/environments`

请求体：

```json
{
  "name": "test",
  "base_url": "https://apichallenges.eviltester.com",
  "default_headers": {
    "Accept": "application/json"
  },
  "auth": {},
  "cookies": {},
  "description": "Integration test env"
}
```

---

## 8.2 环境列表

- 方法：`GET`
- 路径：`/api/projects/{project_id}/environments`

---

## 8.3 更新环境

- 方法：`PATCH`
- 路径：`/api/projects/{project_id}/environments/{environment_id}`

---

## 8.4 删除环境

- 方法：`DELETE`
- 路径：`/api/projects/{project_id}/environments/{environment_id}`

## 9. 任务接口改造建议

这一部分不是新建独立任务系统，而是在现有 `task-center` API 基础上注入用户与项目维度。

### 9.1 创建任务

现有：

- `POST /api/tasks`

建议新增请求字段：

```json
{
  "task_name": "API Challenges task",
  "project_id": "uuid",
  "source_type": "text",
  "requirement_text": "...",
  "target_system": "https://apichallenges.eviltester.com",
  "environment": "test",
  "rag_enabled": true
}
```

后端行为建议：

- 从 token 中拿当前用户
- 写入 `created_by`
- 校验用户是否拥有项目内 `editor/runner/owner` 权限

### 9.2 查询任务列表

现有：

- `GET /api/tasks`

建议新增查询参数：

- `project_id`
- `mine_only`
- `status`
- `keyword`
- `page`
- `page_size`

返回建议增加：

- `created_by`
- `project_id`
- `last_run_status`

### 9.3 任务详情

现有：

- `GET /api/tasks/{task_id}`

建议新增：

- 返回项目归属
- 返回创建人摘要
- 返回最近运行摘要

### 9.4 执行任务

现有：

- `POST /api/tasks/{task_id}/execute`

建议逻辑：

- 校验当前用户是否具备项目内 `runner/editor/owner`
- 执行记录写入 `task_runs`
- 返回 `run_id`

### 9.5 归档任务

现有：

- `DELETE /api/tasks/{task_id}`

建议保持“逻辑归档”语义，但增加权限校验：

- `owner/editor` 可归档
- `runner/viewer` 不可归档

## 10. 错误码建议

建议新增以下用户模块相关错误码：

- `UNAUTHORIZED`
- `INVALID_CREDENTIALS`
- `TOKEN_EXPIRED`
- `INVALID_REFRESH_TOKEN`
- `FORBIDDEN`
- `PROJECT_NOT_FOUND`
- `PROJECT_ACCESS_DENIED`
- `USER_ALREADY_EXISTS`
- `EMAIL_ALREADY_EXISTS`
- `MEMBER_ALREADY_EXISTS`
- `ENVIRONMENT_NOT_FOUND`

## 11. 权限建议

### 11.1 项目内权限矩阵

| 能力 | owner | editor | runner | viewer |
| --- | --- | --- | --- | --- |
| 查看项目 | Y | Y | Y | Y |
| 修改项目 | Y | Y | N | N |
| 管理成员 | Y | N | N | N |
| 创建任务 | Y | Y | Y | N |
| 执行任务 | Y | Y | Y | N |
| 归档任务 | Y | Y | N | N |
| 管理环境 | Y | Y | N | N |

## 12. 分阶段实施建议

### 阶段 1

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/projects`
- `GET /api/projects`

### 阶段 2

- 项目成员管理
- 项目级环境管理
- 任务接口增加 `project_id` / `created_by`

### 阶段 3

- refresh/logout
- 审计日志接口
- 管理员接口

## 13. 最小前后端联调集

如果你想最短路径支撑“用户模块 + 任务归属”闭环，建议第一版先做这 7 个：

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/projects`
- `GET /api/projects`
- `POST /api/tasks`
- `GET /api/tasks`

这已经足够让系统从“匿名单机任务工具”升级成“带用户身份和项目归属的任务平台”。 
