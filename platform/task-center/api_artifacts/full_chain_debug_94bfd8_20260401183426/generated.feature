Feature: full_chain_debug_94bfd8
  Background: 分析结果来自当前需求文档
    Given 已加载当前任务的需求说明

  # priority: P0
  Scenario: 调用 `POST /api/auth/login`，请求体包含 `username` 和 `password` 字段
    Given 用户通过用户名和密码登录平台，登录成功后进入个人中心页面，查看并修改个人信息
    When 调用 `POST /api/auth/login`，请求体包含 `username` 和 `password` 字段
    Then 密码错误三次，账号锁定 10 分钟，`POST /api/auth/login` 返回 403
    And 登录态过期，`GET /api/user/profile` 返回 401，前端自动跳转登录页，提示"会话已过期"

  # priority: P2
  Scenario: 用户跳转至个人中心，调用 `GET /api/user/profile`，携带 Authorization header
    Given 用户通过用户名和密码登录平台，登录成功后进入个人中心页面，查看并修改个人信息
    When 用户跳转至个人中心，调用 `GET /api/user/profile`，携带 Authorization header
    Then 密码错误三次，账号锁定 10 分钟，`POST /api/auth/login` 返回 403
    And 登录态过期，`GET /api/user/profile` 返回 401，前端自动跳转登录页，提示"会话已过期"

  # priority: P2
  Scenario: 用户点击"编辑"，修改昵称后调用 `PUT /api/user/profile`，系统返回 200 并刷新页面
    Given 用户通过用户名和密码登录平台，登录成功后进入个人中心页面，查看并修改个人信息
    When 用户点击"编辑"，修改昵称后调用 `PUT /api/user/profile`，系统返回 200 并刷新页面
    Then 密码错误三次，账号锁定 10 分钟，`POST /api/auth/login` 返回 403
    And 登录态过期，`GET /api/user/profile` 返回 401，前端自动跳转登录页，提示"会话已过期"
