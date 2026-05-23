# Manual Validation Order API

## 文档定位

- 文档目标：验证平台从创建任务到执行接口测试的完整链路，包括 LLM 解析、RAG 检索、断言增强、上下文传递、失败归因、缺陷摘要与缺陷导出。
- 目标系统：本地 mock Order API。
- Base URL: `http://127.0.0.1:18080`

## 环境信息

| 项 | 值 |
| --- | --- |
| Base URL | `http://127.0.0.1:18080` |
| Content-Type | `application/json` |
| Accept | `application/json` |

## 鉴权与全局约束

- 登录接口：`POST /login`
- 登录成功后返回 `token`
- 后续受保护接口使用 `Authorization: Bearer {{token}}`
- 请求体均使用 JSON

## 资源依赖说明

- 订单资源通过 `POST /orders` 创建。
- 创建订单后必须保存 `order_id`，后续 `GET /orders/{id}` 和 `DELETE /orders/{id}` 使用该 id。
- `GET /profile` 依赖 `POST /login` 返回的 token。

## 场景清单

### Scenario: 登录并访问受保护资料

一句话说明：验证登录 token 可被后续受保护接口复用。

**涉及接口:** `POST /login`、`GET /profile`
**关键依赖:** `/profile` 依赖登录返回的 `token`
**资源来源:** `token` 来自 `POST /login`

#### Step 1

**Request:** `POST /login`

```json
{
  "username": "demo",
  "password": "secret"
}
```

**Expected:** 返回 `200`，响应 JSON 中存在字符串字段 `token`，且 `user` 为 `demo-admin`。
**save_context:** `token ← json.token`

#### Step 2

**uses_context:** `token`
**Request:** `GET /profile`
**Expected:** 返回 `200`，响应 JSON 中 `role` 应为 `admin`。

### Scenario: 创建订单并校验订单详情

一句话说明：验证订单创建、保存 id、详情查询和业务状态断言。

**涉及接口:** `POST /orders`、`GET /orders/{id}`
**关键依赖:** 详情查询依赖创建订单返回的 `order_id`
**资源来源:** `order_id` 来自同场景 `POST /orders`

#### Step 1

**uses_context:** `token`
**Request:** `POST /orders`

```json
{
  "item": "book",
  "quantity": 1
}
```

**Expected:** 返回 `201`，响应 JSON 中 `id` 应为字符串，`status` 应为 `confirmed`。
**save_context:** `order_id ← json.id`

#### Step 2

**uses_context:** `token`, `order_id`
**Request:** `GET /orders/{id}`
**Expected:** 返回 `200`，响应 JSON 中 `id` 等于 `order_id`，`status` 应为 `confirmed`。

### Scenario: 删除订单

一句话说明：验证已有订单可删除。

**涉及接口:** `DELETE /orders/{id}`
**关键依赖:** 删除依赖已存在的 `order_id`
**资源来源:** 使用同一测试链路创建得到的 `order_id`

#### Step 1

**uses_context:** `token`, `order_id`
**Request:** `DELETE /orders/{id}`
**Expected:** 返回 `204`，且不应出现运行时错误。

## 预期效果

- 在 healthy mock API 下，核心场景应全部通过。
- 在 buggy mock API 下，应至少发现以下问题：登录响应缺少 token、受保护接口鉴权失败、订单 id 类型错误、订单状态错误、删除接口返回 500。
- 执行失败后，应能在任务详情页看到失败归因、智能诊断、缺陷摘要建议，并可导出缺陷。
