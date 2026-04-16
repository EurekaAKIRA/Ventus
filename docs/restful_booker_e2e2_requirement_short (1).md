# Restful Booker E2E2 

## 固定环境

| 项 | 值 |
| --- | --- |
| Base URL | `https://restful-booker.herokuapp.com` |
| Content-Type | `application/json` |
| Accept | `application/json` |

统一目标：验证从鉴权、创建 booking、读取 booking 到删除 booking 的最小闭环。

---

## Feature: Booking 主链路烟测

### Scenario: 创建并清理 booking

#### Step 1 — 获取鉴权 token

**Request:** `POST /auth`

**Body:**

```json
{
  "username": "admin",
  "password": "password123"
}
```

**Expected:**

- HTTP `200`
- `token` 存在且非空

**save_context:**

- `token` ← `json.token`

#### Step 2 — 创建 booking

**Request:** `POST /booking`

**Body:**

```json
{
  "firstname": "Jim",
  "lastname": "Brown",
  "totalprice": 111,
  "depositpaid": true,
  "bookingdates": {
    "checkin": "2026-04-10",
    "checkout": "2026-04-12"
  },
  "additionalneeds": "Breakfast"
}
```

**Expected:**

- HTTP `200` 或 `201`
- `bookingid` 存在
- `booking.firstname` = `Jim`
- `booking.lastname` = `Brown`

**save_context:**

- `booking_id` ← `json.bookingid`

#### Step 3 — 读取 booking 详情

**Request:** `GET /booking/{{booking_id}}`

**Expected:**

- HTTP `200`
- `firstname` = `Jim`
- `lastname` = `Brown`
- `bookingdates.checkin` = `2026-04-10`
- `bookingdates.checkout` = `2026-04-12`

#### Step 4 — 删除 booking

**Request:** `DELETE /booking/{{booking_id}}`

**Headers:**

```json
{
  "Cookie": "token={{token}}"
}
```

**Expected:**

- HTTP `201`

---

## 断言摘要

| 检查点 | 规则 |
| --- | --- |
| 鉴权 | 成功拿到 `token` 并保存 |
| 创建 | 成功返回 `bookingid`，保存 `booking_id` |
| 查询 | 读取结果与创建时关键字段一致 |
| 删除 | 携带 `Cookie: token={{token}}` 后删除成功 |
