# task-center

## 模块定位

平台统一入口模块。

## 核心职责

- 创建和管理测试任务
- 维护项目、环境、目标系统等基础配置
- 生成统一 `TaskContext`
- 负责主流程编排入口

## 输入

- 任务名称
- 需求文档或需求文本
- 目标地址或接口配置
- 环境参数

## 输出

- `TaskContext`
- 标准化任务配置

## 后续来源

- 可吸收 `analysis-module` 中与任务输入、产物目录相关的部分能力

## 当前状态

第一批入口编排代码已迁移到：

- `src/task_center/input_handler.py`
- `src/task_center/artifact_manager.py`
- `src/task_center/pipeline.py`
- `src/task_center/cli.py`
- `run_task_center.py`

当前已经可以通过新架构主链路串起：

- `task-center`
- `requirement-analysis`
- `case-generation`

## API 服务

当前已经基于 `docs/frontend_api_list.md` 落地 FastAPI 服务：

- `src/task_center/api.py`
- `src/task_center/api_models.py`
- `src/task_center/registry.py`
- `run_api_server.py`

可直接启动：

```powershell
python run_platform.py serve-api
```

并可通过以下命令做接口回归：

```powershell
python run_platform.py server-smoke-test
```

## 数据库迁移

`task-center` 已补充首版 SQLAlchemy ORM 与 Alembic 迁移骨架，默认使用：

- SQLite 文件：`platform/task-center/data/task_center.db`
- 环境变量覆盖：`TASK_CENTER_DATABASE_URL`
- 默认持久化后端：`TASK_CENTER_PERSISTENCE_BACKEND=db`

初始化或升级数据库：

```powershell
cd platform/task-center
alembic upgrade head
```

如果后续切到 PostgreSQL，只需要先设置：

```powershell
$env:TASK_CENTER_DATABASE_URL="postgresql+psycopg://user:password@host:5432/task_center"
alembic upgrade head
```

当前服务还支持：

- `TASK_CENTER_PERSISTENCE_BACKEND=json`
  仅使用历史 JSON 持久化，便于临时回退
- `TASK_CENTER_JSON_MIRROR_ENABLED=true`
  在 DB 模式下继续同步写 `tasks.json / executions.json / execution_history.json / environments.json`
- `TASK_CENTER_REDIS_URL=redis://host:6379/0`
  打开运行态上下文与进度缓存；未配置时自动降级为进程内内存存储
- `TASK_CENTER_JWT_SECRET=...`
  配置访问令牌签名密钥，生产环境务必替换默认值
- `TASK_CENTER_CONFIG_SECRET=...`
  配置环境敏感字段加密密钥；未设置时会回退到 `TASK_CENTER_JWT_SECRET`
- `TASK_CENTER_ARTIFACTS_ROOT=...`
  覆盖 artifact 根目录，便于测试与多环境隔离

说明：

- 当前默认策略是“数据库为主、JSON 镜像兼容”
- 在 `TASK_CENTER_PERSISTENCE_BACKEND=db` 下，JSON 镜像默认不再持续写入，只保留导入/兼容开关
- 任务详情、执行结果、分析报告仍继续落在 artifact 目录
- 执行中的进度与上下文会写入 runtime store，并同步快照到 `execution/` 目录
- 环境中的 `auth / cookies / sensitive headers` 在 DB 模式下会加密存储，接口仅返回脱敏值
- 若更换 `TASK_CENTER_CONFIG_SECRET`，历史环境 secret 将无法解密；生产环境请固定并妥善保管

## 用户与项目接口

当前服务已经补齐最小用户模块：

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/users/me`
- `PATCH /api/users/me`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{project_id}`
- `POST /api/projects/{project_id}/members`

环境接口现在支持两种模式：

- 不带 `project_id`：访问全局兼容环境
- 带 `project_id` 且已登录：访问项目级环境，并自动对当前项目做权限校验

行为说明：

- 注册后会自动创建默认 workspace 和默认 project
- 服务启动时默认会初始化一个管理员账号：`admin / 123456`
- 已登录用户创建任务时，若未显式传 `project_id`，会自动挂到默认 project
- 任务列表、任务详情、执行历史会按当前用户可见项目做过滤
- 任务执行中的 runtime context / progress 会同步到 runtime store 与 artifact 快照

如需覆盖默认管理员，可设置：

- `TASK_CENTER_DEFAULT_ADMIN_USERNAME`
- `TASK_CENTER_DEFAULT_ADMIN_PASSWORD`
- `TASK_CENTER_DEFAULT_ADMIN_EMAIL`
- `TASK_CENTER_DEFAULT_ADMIN_DISPLAY_NAME`
- `TASK_CENTER_BOOTSTRAP_ADMIN_ENABLED=false`
  关闭默认管理员自动初始化

## 最小部署步骤

建议最低按下面顺序执行：

1. 配置关键环境变量

```powershell
$env:TASK_CENTER_PERSISTENCE_BACKEND="db"
$env:TASK_CENTER_DATABASE_URL="sqlite+pysqlite:///platform/task-center/data/task_center.db"
$env:TASK_CENTER_JWT_SECRET="replace-with-a-long-random-secret"
$env:TASK_CENTER_CONFIG_SECRET="replace-with-a-second-long-random-secret"
```

如需快速生成随机密钥：

```powershell
@'
import secrets
print(secrets.token_urlsafe(48))
print(secrets.token_urlsafe(48))
'@ | python -
```

2. 初始化数据库

```powershell
cd platform/task-center
alembic upgrade head
```

3. 启动 API 服务

```powershell
cd E:\ending\LaVague-main
python run_api_server.py
```

4. 登录默认管理员并立即改成你的正式配置

- 默认账号：`admin`
- 默认密码：`123456`

如果不想生成默认管理员，请提前设置：

```powershell
$env:TASK_CENTER_BOOTSTRAP_ADMIN_ENABLED="false"
```

## 交付前检查

- 确认 `TASK_CENTER_JWT_SECRET` 已替换
- 确认 `TASK_CENTER_CONFIG_SECRET` 已固定
- 确认数据库迁移已执行到最新版本
- 确认 Redis 未配置时，运行态退化到内存是否符合预期
- 确认默认管理员是否需要保留
- 确认 `api_artifacts/` 是否纳入清理或保留策略

更完整的落地说明见：

- [../../docs/task_center_deployment_bootstrap.md](../../docs/task_center_deployment_bootstrap.md)
