# 用户登录与个人中心功能需求

## 1. 功能目标

用户通过用户名和密码登录平台，登录成功后进入个人中心页面，查看并修改个人信息。

## 2. 接口清单

| 接口 | 方法 | 路径 |
|------|------|------|
| 用户登录 | POST | /api/auth/login |
| 获取个人中心 | GET | /api/user/profile |
| 修改昵称 | PUT | /api/user/profile |

## 3. 主流程

1. 用户在登录页输入用户名和密码，点击"登录"按钮。
2. 调用 `POST /api/auth/login`，请求体包含 `username` 和 `password` 字段。
3. 系统校验凭据，返回 200 及 `token` 字段。
4. 用户跳转至个人中心，调用 `GET /api/user/profile`，携带 Authorization header。
5. 页面展示 `nickname`、`avatar` 和 `email` 字段。
6. 用户点击"编辑"，修改昵称后调用 `PUT /api/user/profile`，系统返回 200 并刷新页面。

## 4. 异常流程

- 密码错误三次，账号锁定 10 分钟，`POST /api/auth/login` 返回 403。
- 登录态过期，`GET /api/user/profile` 返回 401，前端自动跳转登录页，提示"会话已过期"。

## 5. 约束

- 所有接口必须在 500ms 内响应。
- 用户名长度为 4–20 字符，密码须包含数字和字母。
- 所有需鉴权接口需携带 `Authorization: Bearer <token>` header。
