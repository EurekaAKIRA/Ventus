# API 需求文档模板 v1

> 用途：复制本模板后填写具体功能、接口、资源关系与预期效果，让系统自动生成场景、用例并一键测试。

## 文档定位

- 文档目标：说明本需求文档用于自动生成 API 场景、DSL 与执行报告。
- 业务目标：一句话写清楚要验证的主功能。
- 覆盖范围：列出本次纳入的核心接口或能力链路。

---

## 环境信息

| 项 | 值 |
| --- | --- |
| Base URL | `http://127.0.0.1:8001` |
| `environment` | `test` |
| Content-Type | `application/json` |
| Accept | `application/json` |

如存在统一响应 envelope，可补充：

```json
{
  "success": true,
  "code": "SOME_CODE",
  "message": "ok",
  "data": {}
}
```

---

## 鉴权与全局约束

### 鉴权方式

- 是否需要鉴权：是 / 否
- 鉴权接口：`POST /auth`
- 令牌字段：
- 注入方式：`Authorization: Bearer {{token}}` 或 `Cookie: token={{token}}`

### 全局约束

- 默认请求头：
- 全局 query 参数：
- 全局响应 envelope：
- 特殊状态码规则：
- 轮询或异步规则：

---

## 资源依赖说明

### 资源来源

- `GET /resource/{id}` 的资源来源：
- `PUT /resource/{id}` 的资源来源：
- `PATCH /resource/{id}` 的资源来源：
- `DELETE /resource/{id}` 的资源来源：

资源来源只能是以下三类之一：

- 同链路 `create`
- 同资源 `list / detail` 后保存 id
- 文档显式声明预置资源

### 预置资源

- 若使用预置资源，在此明确：
- 示例：`resource_id=1`

---

## 接口清单

### 接口：在此填写接口名称

- 方法：`POST`
- 路径：`/resource`
- 功能：创建资源
- 鉴权：否
- 请求语义：提交资源创建所需关键字段
- 结果语义：返回新资源标识及创建结果

### 接口：在此填写接口名称

- 方法：`GET`
- 路径：`/resource/{id}`
- 功能：读取资源详情
- 鉴权：否
- 资源前置条件：需要已存在资源
- 结果语义：返回当前资源关键字段

### 接口：在此填写接口名称

- 方法：`PATCH`
- 路径：`/resource/{id}`
- 功能：部分更新资源
- 鉴权：是
- 资源前置条件：需要已存在资源
- 结果语义：仅目标字段变化，未修改字段保持不变

---

### Scenario: 在此填写能力链路名称

一句话说明本场景覆盖的能力链路。

**涉及接口:** `POST /resource`、`GET /resource/{id}`、`PATCH /resource/{id}`、`DELETE /resource/{id}`

**关键依赖:** `GET /resource/{id}`、`PATCH /resource/{id}`、`DELETE /resource/{id}` 依赖已存在资源

**资源来源:** 默认通过 `POST /resource` 创建资源

### Scenario: 在此填写只读能力名称

一句话说明本场景覆盖的只读查询或过滤能力。

**涉及接口:** `GET /resource`、`GET /resource?status=active`

**关键依赖:** 本场景不依赖创建资源，仅验证只读查询能力

**资源来源:** 不适用

---

## 预期效果

- 创建成功后应返回新资源标识
- 详情读取应返回与创建或更新后一致的关键字段
- 全量更新后所有目标字段应按新值覆盖
- 部分更新后未修改字段应保持不变
- 删除后再次读取应返回资源不存在
- 过滤查询应返回合法数组结果

---

## 可选增强信息

以下内容仅在需要提高生成稳定性时补充，不是必填项：

- 请求体样例
- Header 样例
- 特殊字段路径说明
- 显式 `save_context`
- 显式 `uses_context`
- 步骤级 `Request / Expected`

例如：

```md
**save_context:**

- `resource_id` ← `json.id`
```

```md
**uses_context:**

- `resource_id`
- `token`
```

---

## 常见错误提示

避免以下写法：

- 只写“调用创建接口”，不写 `` `POST /resource` ``
- 只写“接口正常工作”，不写可验证预期效果
- 只写 `PATCH /resource/{id}`，不写资源来源
- 不写是否需要鉴权
- 不写功能目标，只堆请求样例

最小自查清单：

- 是否写清了文档目标
- 是否列出了核心接口
- 是否写清了资源来源
- 是否说明了鉴权方式
- 是否给出了可验证的预期效果
