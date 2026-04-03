# 用户体验增强接口契约草案（Draft）

## 1.1 相关参考文档（与前端总表对应）

本节与 `docs/frontend_api_list.md` 的 **§1.1 前端参考文档索引**一一对应：
- 前端总入口：`docs/frontend_api_list.md §1.1`
- 本文定位：体验增强接口字段级契约（预检/解释/对比/SSE）
- 页面落位：`platform/platform-ui/FRONTEND_PAGE_PLAN.md`
- 工程约束：`platform/platform-ui/FRONTEND_DEVELOPMENT_GUIDE.md`
- 契约冻结与验收口径：`docs/platform_requirements_status.md`、`docs/platform_e2e_requirement.md`

OpenAPI 未上线时约定：
- 若本文接口尚未进入 `http://127.0.0.1:8001/docs`，以前述 Markdown 契约为准。
- 一旦后端发布 OpenAPI，以 OpenAPI 为发布事实；本文与前端契约需同步更新。

### 1.2 已实现端点（第一批，task-center）

| 方法 | 路径 | 成功 `code` | 说明 |
| --- | --- | --- | --- |
| `POST` | `/api/tasks/{task_id}/preflight-check` | `PREFLIGHT_OK` | 可选请求体：`environment`、`checks`、`latency_threshold_ms`；默认探测 `GET {base_url}/health` 并给出鉴权配置提示。 |
| `GET` | `/api/tasks/{task_id}/execution/explanations` | `EXECUTION_EXPLANATIONS_OK` | 查询参数 `top_n`（1–20）；无执行结果时返回 **404**。规则归类，无 LLM。 |

**api-runner（同批，无新 HTTP 路由）**：步骤默认超时 **30s**（DSL 仍可用 `request.timeout` 覆盖）；对 **URLError** 默认重试 **2 次**（可用 `request.retries` 覆盖）；`json.*` 的 **`exists` 断言**与 **`save_context`** 支持在统一 envelope 下回退读取 `data.*`。

---

## 2. 閫氱敤绾﹀畾

### 2.1 缁熶竴鍝嶅簲缁撴瀯

鎴愬姛锛?
```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {},
  "timestamp": "2026-04-02T16:00:00Z"
}
```

澶辫触锛?
```json
{
  "success": false,
  "code": "VALIDATION_ERROR",
  "message": "Field required",
  "data": {
    "detail": []
  },
  "timestamp": "2026-04-02T16:00:00Z"
}
```

### 2.2 閿欒鐮佸缓璁?
- `VALIDATION_ERROR`锛氬弬鏁版牎楠屽け璐ワ紙422锛?- `TASK_NOT_FOUND`锛氫换鍔′笉瀛樺湪锛?04锛?- `PRECHECK_FAILED`锛氶妫€澶辫触锛?00锛?- `REGRESSION_DIFF_NOT_READY`锛氭棤鍙姣斿巻鍙诧紙409锛?- `INTERNAL_ERROR`锛氭湇鍔″紓甯革紙500锛?
---

## 3. 鐜鍋ュ悍妫€鏌?
## 3.1 鎵ц鍓嶉妫€

- 鏂规硶锛歚POST`
- 璺緞锛歚/api/tasks/{task_id}/preflight-check`
- 鐢ㄩ€旓細鎵ц鍓嶆帰娴?base_url銆侀壌鏉冮厤缃€佸叧閿帴鍙ｈ繛閫氭€э紝鎻愬墠闃绘柇鏃犳晥鎵ц

璇锋眰浣擄細

```json
{
  "environment": "test",
  "checks": [
    "base_url_reachable",
    "auth_config_valid",
    "core_endpoints_reachable",
    "latency_budget"
  ],
  "latency_threshold_ms": 1500
}
```

杩斿洖浣?`data`锛?
```json
{
  "task_id": "task_20260402_001",
  "overall_status": "passed",
  "blocking": false,
  "checks": [
    {
      "name": "base_url_reachable",
      "status": "passed",
      "elapsed_ms": 42,
      "message": "base_url reachable"
    },
    {
      "name": "auth_config_valid",
      "status": "warning",
      "elapsed_ms": 2,
      "message": "no explicit auth configured"
    }
  ],
  "blocking_issues": [],
  "suggestions": [
    "寤鸿鍦ㄧ幆澧冧腑閰嶇疆榛樿 Authorization 澶?
  ]
}
```

鐘舵€佽涔夛細

- `overall_status`: `passed | warning | failed`
- `blocking=true` 鏃跺墠绔簲闃绘瑙﹀彂 `POST /execute`

---

## 4. 澶辫触瑙ｉ噴鏈嶅姟

## 4.1 鑾峰彇鎵ц澶辫触瑙ｉ噴

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/execution/explanations`
- 鐢ㄩ€旓細瀵规渶杩戜竴娆℃墽琛屽け璐ヨ繘琛岃嚜鍔ㄥ綊绫伙紝缁欏嚭淇寤鸿

鏌ヨ鍙傛暟锛?
- `execution_id`锛堝彲閫夛紱涓嶄紶鍒欓粯璁ゆ渶杩戜竴娆★級
- `top_n`锛堝彲閫夛紝榛樿 `5`锛?
杩斿洖浣?`data`锛?
```json
{
  "task_id": "task_20260402_001",
  "execution_id": "exec_20260402_001",
  "summary": {
    "failed_scenarios": 2,
    "failed_steps": 3
  },
  "failure_groups": [
    {
      "category": "field_mapping",
      "count": 1,
      "examples": [
        "json.id not found, expected json.data.task_id"
      ],
      "recommended_actions": [
        "璋冩暣 save_context 瀛楁璺緞鏄犲皠",
        "浼樺厛浣跨敤鎺ュ彛鐧藉悕鍗曡姹備綋妯℃澘"
      ]
    },
    {
      "category": "status_code_mismatch",
      "count": 1,
      "examples": [
        "expected 201, actual 200"
      ],
      "recommended_actions": [
        "灏嗘帶鍒剁被鎺ュ彛鏂█闄嶄负 200"
      ]
    }
  ],
  "top_reasons": [
    "field_mapping",
    "status_code_mismatch"
  ]
}
```

鍒嗙被寤鸿锛?
- `field_mapping`
- `status_code_mismatch`
- `auth_failure`
- `network_timeout`
- `context_missing`

---

## 5. 鍘嗗彶鍥炲綊瀵规瘮

## 5.1 鑾峰彇浠诲姟鍥炲綊宸紓

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/regression-diff`
- 鐢ㄩ€旓細瀵规瘮涓ゆ鎵ц缁撴灉锛岃緭鍑衡€滄敼鍠?閫€鍖?鎸佸钩鈥?
鏌ヨ鍙傛暟锛?
- `base_execution_id`锛堝彲閫夛級
- `target_execution_id`锛堝彲閫夛級
- 涓虹┖鏃堕粯璁も€滄渶杩戜袱娆℃墽琛屸€?
杩斿洖浣?`data`锛?
```json
{
  "task_id": "task_20260402_001",
  "base_execution_id": "exec_20260401_001",
  "target_execution_id": "exec_20260402_001",
  "metrics_diff": {
    "success_rate": {
      "base": 0.75,
      "target": 0.875,
      "delta": 0.125
    },
    "avg_elapsed_ms": {
      "base": 824.2,
      "target": 701.6,
      "delta": -122.6
    }
  },
  "failure_type_diff": [
    {
      "category": "field_mapping",
      "base": 2,
      "target": 0,
      "delta": -2
    }
  ],
  "verdict": "improved"
}
```

`verdict` 鍙栧€硷細

- `improved`
- `regressed`
- `unchanged`

---

## 6. 瀹炴椂鎵ц浜嬩欢娴?
## 6.1 璁㈤槄鎵ц浜嬩欢锛圫SE锛?
- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/execution/stream`
- 鐢ㄩ€旓細瀹炴椂鎺ㄩ€佹墽琛岃繘搴︼紝鍑忓皯杞
- 鍝嶅簲绫诲瀷锛歚text/event-stream`

浜嬩欢绀轰緥锛?
```text
event: step_start
data: {"task_id":"task_001","step_id":"scenario_001_step_02","at":"2026-04-02T16:10:00Z"}

event: step_end
data: {"task_id":"task_001","step_id":"scenario_001_step_02","status":"passed","elapsed_ms":123}

event: assertion_failed
data: {"task_id":"task_001","step_id":"scenario_001_step_03","reason":"json.data.task_id missing"}

event: execution_done
data: {"task_id":"task_001","status":"passed","scenario_passed":8,"scenario_total":8}
```

鍓嶇鍥為€€绛栫暐锛?
- SSE 鏂紑鍚庤嚜鍔ㄩ噸杩烇紙鎸囨暟閫€閬匡級
- 瓒呰繃闃堝€煎悗鍥為€€鍒?`GET /api/tasks/{task_id}/execution` 杞

---

## 7. 鍒嗛樁娈佃惤鍦板缓璁?
### 绗?1 闃舵锛? 鍛級

- `POST /preflight-check`
- `GET /execution/explanations`

### 绗?2 闃舵锛?-2 鍛級

- `GET /regression-diff`
- 鍓嶇鎶ュ憡椤垫柊澧炩€滃姣斿崱鐗団€?
### 绗?3 闃舵锛? 鍛級

- `GET /execution/stream`锛圫SE锛?- 鍓嶇鎵ц鐩戞帶椤靛垏鎹㈠疄鏃舵祦

---

## 8. 涓庣幇鏈夋帴鍙ｅ吋瀹圭害鏉?
- 涓嶄慨鏀瑰凡鏈?30 鏉℃帴鍙ｈ矾寰勫拰鏍稿績瀛楁
- 鎵€鏈夊寮鸿兘鍔涗互鏂板绔偣鎵胯浇
- 鏂板瀛楁浠呰拷鍔狅紝涓嶅垹闄ゆ棫瀛楁
- 閿欒杩斿洖蹇呴』鍖呭惈鍙 `message`


