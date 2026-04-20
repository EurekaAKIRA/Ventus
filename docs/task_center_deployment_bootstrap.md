# Task Center 部署与初始化说明

这份文档面向“第一次把 `task-center` 跑起来”的场景，优先覆盖当前交付最需要的启动、数据库、默认账号和安全配置。

## 1. 必要环境变量

建议至少设置下面四项：

```powershell
$env:TASK_CENTER_PERSISTENCE_BACKEND="db"
$env:TASK_CENTER_DATABASE_URL="sqlite+pysqlite:///platform/task-center/data/task_center.db"
$env:TASK_CENTER_JWT_SECRET="replace-with-a-long-random-secret"
$env:TASK_CENTER_CONFIG_SECRET="replace-with-a-second-long-random-secret"
```

说明：

- `TASK_CENTER_JWT_SECRET`：访问令牌签名密钥
- `TASK_CENTER_CONFIG_SECRET`：环境敏感字段加密密钥
- `TASK_CENTER_CONFIG_SECRET` 未设置时，会回退到 `TASK_CENTER_JWT_SECRET`
- 生产环境请固定这两个密钥，不要频繁更换

快速生成随机密钥：

```powershell
@'
import secrets
print(secrets.token_urlsafe(48))
print(secrets.token_urlsafe(48))
'@ | python -
```

## 2. 初始化数据库

```powershell
cd platform/task-center
alembic upgrade head
```

默认数据库是 SQLite。切 PostgreSQL 时，只需要先设置 `TASK_CENTER_DATABASE_URL` 再执行同一条迁移命令。

## 3. 启动服务

在仓库根目录执行：

```powershell
cd E:\ending\LaVague-main
python run_api_server.py
```

如果前端也要联调，再启动：

```powershell
cd platform/platform-ui
npm install
npm run dev
```

## 4. 默认管理员

默认会自动初始化：

- 用户名：`admin`
- 密码：`123456`

如需关闭默认管理员自动创建：

```powershell
$env:TASK_CENTER_BOOTSTRAP_ADMIN_ENABLED="false"
```

如需自定义：

```powershell
$env:TASK_CENTER_DEFAULT_ADMIN_USERNAME="admin"
$env:TASK_CENTER_DEFAULT_ADMIN_PASSWORD="change-me"
$env:TASK_CENTER_DEFAULT_ADMIN_EMAIL="admin@example.com"
$env:TASK_CENTER_DEFAULT_ADMIN_DISPLAY_NAME="Administrator"
```

## 5. 环境配置安全说明

当前在 DB 模式下：

- `auth`
- `cookies`
- 敏感 `default_headers`（如 `Authorization` / `X-API-Key`）

会走“加密存储、脱敏返回”链路。

接口返回中如果看到：

```json
"token": "***MASKED***"
```

表示服务端仍保留原值，前端若直接保存，不会把 secret 清掉；只有输入新值时才会覆盖。

注意：

- 如果更换 `TASK_CENTER_CONFIG_SECRET`，历史环境 secret 会无法解密
- `json` 持久化后端只建议开发调试使用，不建议承载正式 secret

## 6. Redis 边界

Redis 只覆盖运行期、短生命周期、跨步骤传递的状态，不替代长期数据库。

可选开启：

```powershell
$env:TASK_CENTER_REDIS_URL="redis://127.0.0.1:6379/0"
```

未配置时，系统会自动退化到进程内内存存储。

## 7. 启动后最小验收

建议按下面顺序验收：

1. 登录 `admin / 123456`
2. 创建或确认默认项目存在
3. 新增一个环境并测试连接
4. 创建一条任务并执行
5. 打开审计日志页确认关键操作有留痕
6. 重启服务后确认数据库数据仍在

## 8. 交付前建议

- 固定并备份 `TASK_CENTER_JWT_SECRET`
- 固定并备份 `TASK_CENTER_CONFIG_SECRET`
- 确认 Alembic 已升级到最新
- 明确 `api_artifacts/` 的保留和清理策略
- 决定是否保留默认管理员账号
