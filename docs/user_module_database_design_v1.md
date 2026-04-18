# 用户模块与数据库设计 v1

## 1. 目标

本设计面向当前平台即将引入的用户模块，目标不是一次性把全部持久化体系推倒重来，而是在**保持现有 `task-center` 可用**的前提下，补齐后续用户体系、权限体系、项目隔离和任务归属所需的数据库基础。

本设计优先解决以下问题：

- 当前 `task-center` 主要依赖 `api_artifacts/tasks.json`、`executions.json` 等 JSON 文件持久化，适合单机调试，不适合用户体系扩展。
- 后续一旦引入登录、注册、组织/项目空间、任务归属、权限控制，JSON 文件会很难保证并发一致性、查询效率和数据约束。
- 用户模块不仅需要“用户表”，还需要围绕用户展开的会话、角色、项目、环境、任务归属模型。

本设计的原则是：

- 先引入关系型数据库作为**系统元数据主存储**。
- 任务执行产物、DSL、报告、原始需求文档等大文件仍保留在现有 artifact 文件目录。
- 数据库先管“索引与归属”，文件系统继续管“大对象产物”。

## 2. 当前现状

结合当前仓库实现，现状如下：

- 服务入口是 FastAPI，见 [api.py](/E:/ending/LaVague-main/platform/task-center/src/task_center/api.py)。
- 任务注册当前由 `TaskRegistry` 管理，见 [registry.py](/E:/ending/LaVague-main/platform/task-center/src/task_center/registry.py)。
- 当前持久化形式是 JSON repository：
  - `tasks.json`
  - `executions.json`
  - `execution_history.json`
  - `environments.json`
- artifact 目录承担了任务原始输入、解析结果、场景、DSL、执行结果和报告的文件持久化。

这说明当前系统已经天然分成两层：

- 元数据层：任务、环境、执行状态、索引
- 产物层：原始文档、解析结果、DSL、执行报告

因此最合理的数据库化路径不是“把所有 JSON 一次性塞进数据库”，而是：

- 先把**元数据层**数据库化
- 再逐步把必要的结构化结果入库
- 文件型 artifact 保持目录存储

## 3. 选型建议

### 3.1 第一阶段数据库

建议首选：

- 开发环境：SQLite
- 生产/多人协作环境：PostgreSQL

原因：

- 你当前项目是单机开发推进中，SQLite 接入成本最低，方便先把 ORM、表结构、迁移机制和用户模块跑起来。
- SQLite 可以很好承担早期用户、项目、任务索引、环境配置这些元数据表。
- 一旦后续进入多人并发、部署上线、论文展示 demo 服务等阶段，PostgreSQL 更适合用户认证、会话、权限、分页查询和统计分析。

建议架构上直接按“**数据库抽象对 SQLite/PostgreSQL 兼容**”设计，不要写死 SQLite 语义。

### 3.2 ORM 与迁移

建议：

- ORM：SQLAlchemy 2.x
- 迁移：Alembic

原因：

- 关系建模清晰，适合后续用户、项目、任务、执行历史等复杂关联。
- 迁移机制成熟，便于后续迭代表结构。
- 与 FastAPI 生态兼容度高。

## 4. 分层设计

数据库设计建议按 5 个逻辑域划分。

### 4.1 身份域

负责用户身份、认证、授权基础能力。

核心对象：

- 用户 `users`
- 用户凭证 `user_credentials`
- 登录会话 / refresh token `user_sessions`
- 角色 `roles`
- 用户角色绑定 `user_role_bindings`

### 4.2 资源空间域

负责项目、工作空间、任务归属隔离。

核心对象：

- 工作空间/租户 `workspaces`
- 项目 `projects`
- 项目成员 `project_members`

### 4.3 任务域

负责替代当前 JSON 的任务主索引与任务执行索引。

核心对象：

- 任务 `tasks`
- 任务输入快照 `task_inputs`
- 任务执行记录 `task_runs`
- 任务状态变更历史 `task_status_events`

### 4.4 配置域

负责环境、默认 headers、执行目标配置等。

核心对象：

- 环境配置 `environments`
- 用户级环境授权或共享关系 `environment_bindings`

### 4.5 审计与安全域

负责登录审计、敏感操作留痕、封禁和异常追踪。

核心对象：

- 审计日志 `audit_logs`
- 安全事件 `security_events`

## 5. 核心表设计

下面是建议的第一期核心表。

### 5.1 users

用途：

- 用户主表

关键字段：

- `id`：UUID / bigint 主键
- `username`：唯一
- `email`：唯一，可为空但建议唯一
- `display_name`
- `status`：`active` / `disabled` / `pending`
- `created_at`
- `updated_at`
- `last_login_at`

约束：

- `username` 唯一索引
- `email` 唯一索引

说明：

- 不建议把密码 hash 直接和用户扩展字段混在一张大表里，单拆凭证表更干净。

### 5.2 user_credentials

用途：

- 用户认证凭证

关键字段：

- `id`
- `user_id`
- `password_hash`
- `password_algo`
- `password_updated_at`
- `must_change_password`

说明：

- 后续如果支持第三方登录，可继续扩 `auth_provider` / `provider_user_id`。

### 5.3 user_sessions

用途：

- 登录会话、refresh token、设备端会话管理

关键字段：

- `id`
- `user_id`
- `refresh_token_hash`
- `client_type`
- `user_agent`
- `ip_address`
- `expires_at`
- `revoked_at`
- `created_at`

说明：

- Access token 可保持无状态 JWT
- Refresh token 建议入库可撤销

### 5.4 roles

用途：

- 角色定义

建议初始角色：

- `super_admin`
- `admin`
- `member`
- `viewer`

### 5.5 user_role_bindings

用途：

- 用户与全局角色绑定

字段：

- `id`
- `user_id`
- `role_id`
- `created_at`

### 5.6 workspaces

用途：

- 后续多用户、多团队隔离根节点

字段：

- `id`
- `name`
- `slug`
- `owner_user_id`
- `status`
- `created_at`

说明：

- 如果你暂时不做多租户，也建议把这层先设计出来，哪怕先只保留默认 workspace。

### 5.7 projects

用途：

- 任务、环境、文档的业务归属空间

字段：

- `id`
- `workspace_id`
- `name`
- `description`
- `created_by`
- `created_at`
- `updated_at`

### 5.8 project_members

用途：

- 项目成员与项目级角色

字段：

- `id`
- `project_id`
- `user_id`
- `role`
- `joined_at`

建议项目级角色：

- `owner`
- `editor`
- `runner`
- `viewer`

### 5.9 tasks

用途：

- 替代当前 `tasks.json` 的任务主表

字段：

- `id`
- `task_uid`
- `project_id`
- `created_by`
- `task_name`
- `source_type`
- `source_path`
- `target_system`
- `environment_name`
- `status`
- `artifact_dir`
- `current_run_id`
- `archived`
- `created_at`
- `updated_at`

说明：

- `task_uid` 对应当前系统中的 `task_id`
- `artifact_dir` 保留与现有文件产物目录的对应关系
- `status` 对应当前 API 的任务状态枚举

### 5.10 task_inputs

用途：

- 存放任务输入快照

字段：

- `id`
- `task_id`
- `requirement_text`
- `analysis_options_json`
- `execution_options_json`
- `created_at`

说明：

- 可先保留文本输入
- 后续可以扩展 `source_file_sha256`、`input_size_bytes`

### 5.11 task_runs

用途：

- 一次任务可以多次执行，替代 `executions.json` 和部分历史记录

字段：

- `id`
- `task_id`
- `run_no`
- `triggered_by`
- `execution_mode`
- `status`
- `parse_mode`
- `llm_used`
- `rag_enabled`
- `rag_used`
- `started_at`
- `finished_at`
- `duration_ms`
- `summary_json`
- `analysis_report_path`
- `execution_result_path`

说明：

- 一个 task 对应多个 run
- 便于重跑、回归、论文统计

### 5.12 task_status_events

用途：

- 记录状态变迁审计

字段：

- `id`
- `task_id`
- `run_id`
- `from_status`
- `to_status`
- `reason`
- `created_at`
- `operator_user_id`

### 5.13 environments

用途：

- 替代当前 `environments.json`

字段：

- `id`
- `project_id`
- `name`
- `base_url`
- `default_headers_json`
- `auth_json`
- `cookies_json`
- `description`
- `created_by`
- `created_at`
- `updated_at`

说明：

- 环境最好做成项目级资源，而不是纯全局资源

### 5.14 audit_logs

用途：

- 留痕关键系统行为

字段：

- `id`
- `user_id`
- `action`
- `resource_type`
- `resource_id`
- `detail_json`
- `ip_address`
- `created_at`

适合记录：

- 登录
- 登出
- 创建任务
- 执行任务
- 删除环境
- 变更角色

## 6. 推荐索引

建议的第一批索引：

- `users(username)` 唯一
- `users(email)` 唯一
- `tasks(task_uid)` 唯一
- `tasks(project_id, created_at desc)`
- `tasks(created_by, created_at desc)`
- `tasks(status, created_at desc)`
- `task_runs(task_id, run_no desc)`
- `task_runs(triggered_by, started_at desc)`
- `environments(project_id, name)` 唯一
- `project_members(project_id, user_id)` 唯一

## 7. 与现有系统的映射关系

### 7.1 当前 JSON -> 新数据库

现有文件与建议表映射如下：

- `tasks.json` -> `tasks` + `task_inputs`
- `executions.json` -> `task_runs`
- `execution_history.json` -> `task_runs` + `task_status_events`
- `environments.json` -> `environments`

### 7.2 当前 artifact 目录

建议继续保留文件系统存储：

- `raw/requirement.txt`
- `parsed/parsed_requirement.json`
- `parsed/parse_metadata.json`
- `scenarios/scenario_bundle.json`
- `scenarios/test_case_dsl.json`
- `execution/execution_result.json`
- `validation/analysis_report.json`

数据库只保存：

- 路径
- 索引
- 状态
- 统计摘要

这样改造风险最低。

## 8. 用户模块接入设计

用户模块接入后，建议 API 分三层。

### 8.1 认证接口

建议新增：

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`

### 8.2 用户与项目接口

建议新增：

- `GET /api/users/me`
- `PATCH /api/users/me`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{project_id}`
- `POST /api/projects/{project_id}/members`

### 8.3 任务接口改造

现有任务接口建议增加：

- 当前用户上下文
- 项目归属
- 权限校验

例如：

- 创建任务时写入 `created_by`
- 列表任务时按用户/project 过滤
- 执行任务前校验当前用户是否有 `runner/editor` 权限

## 9. 鉴权方案建议

建议方案：

- 登录成功返回：
  - `access_token`
  - `refresh_token`
- `access_token`：短期 JWT
- `refresh_token`：数据库可撤销

建议 JWT claims：

- `sub`：用户 ID
- `username`
- `workspace_id`
- `roles`
- `exp`

这样 FastAPI 里比较容易做依赖注入鉴权。

## 10. 权限模型建议

建议采用“两层权限”：

- 全局角色
- 项目角色

### 10.1 全局角色

控制系统级能力：

- 系统配置
- 用户管理
- 全局审计查看

### 10.2 项目角色

控制业务操作：

- 看任务
- 创建任务
- 执行任务
- 管理环境

推荐权限粒度：

- `task.read`
- `task.create`
- `task.execute`
- `task.archive`
- `env.read`
- `env.write`
- `member.manage`

## 11. 分阶段落地建议

### 阶段 1：数据库底座

目标：

- 引入 SQLAlchemy + Alembic
- 建立 `users`、`tasks`、`task_runs`、`environments` 基础表
- 不改 artifact 文件结构

### 阶段 2：用户认证

目标：

- 实现注册/登录/me
- 任务创建写入 `created_by`
- 任务列表按用户过滤

### 阶段 3：项目与权限

目标：

- 引入 `projects`、`project_members`
- 环境配置转为项目级
- 任务改为项目归属

### 阶段 4：替换 JSON repository

目标：

- `TaskRegistry` 从 JSON repository 切换到 DB repository
- JSON 文件只作为 artifact，不再作为主元数据源

## 12. 风险与注意事项

### 12.1 不建议第一版就把所有解析/执行细节入库

原因：

- 这会让 schema 膨胀很快
- 当前产物天然更适合文件存储
- 对现有系统侵入太大

### 12.2 不建议把用户模块和任务重构同时一次性做完

建议顺序：

1. 先引入数据库
2. 再做用户认证
3. 再做任务归属

### 12.3 需要提前确定主键风格

建议：

- 外部接口标识保留字符串风格 `task_uid`
- 数据库内部主键使用 UUID 或 bigint

这样兼顾外部兼容性和内部关系建模。

## 13. 建议的第一版最小表集

如果只做一个“够支撑用户模块起步”的最小集合，建议先上这 8 张表：

- `users`
- `user_credentials`
- `user_sessions`
- `projects`
- `project_members`
- `tasks`
- `task_runs`
- `environments`

这已经足够支撑：

- 用户注册登录
- 项目隔离
- 任务归属
- 任务执行记录
- 环境配置归属

## 14. 一句话结论

最适合当前项目的路线不是“立刻把所有 JSON 全迁数据库”，而是：

- **数据库接管用户、项目、任务索引、执行索引、环境配置**
- **artifact 文件继续存解析结果和执行产物**
- **先做 SQLite/PostgreSQL 兼容的元数据层，再把用户模块接进来**
