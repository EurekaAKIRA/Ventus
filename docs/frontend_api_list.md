# 前端阶段接口清单

## 1.1 前端参考文档索引（总目录）

说明：本节是给前端同学的统一入口，按“必看/建议看/可选/代码侧”分层。

### 必看
- `docs/frontend_api_list.md`（本文件）：接口总表、页面映射、实施状态。
- `docs/ux_service_api_contract_draft.md`：体验增强接口草案（预检、失败解释、回归对比、SSE）。
- `platform/platform-ui/FRONTEND_DEVELOPMENT_GUIDE.md`：前端开发约束与落地规范。
- `platform/platform-ui/FRONTEND_PAGE_PLAN.md`：页面职责与模块落位。

### 建议看
- `docs/platform_requirements_status.md`：契约冻结、约束、优先级。
- `docs/platform_e2e_requirement.md`：端到端验收口径。
- `docs/platform_quickstart.md`：本地启动与联调路径。

### 可选
- `platform/task-center/loadtest/README.md`：Task Center API 压测（JMeter / k6）；若要把 JMeter HTML 报告嵌进前端，见 `platform/platform-ui/FRONTEND_DEVELOPMENT_GUIDE.md` **§1.3**。
- `docs/dsl_spec.md`：DSL 细节。
- `docs/project_requirements.md`：原始需求背景。
- `docs/requirement_analysis_rag_llm_design.md`：解析链路设计细节。

### 代码侧
- `platform/platform-ui/api-contract.ts`：TS 契约定义。
- `platform/platform-ui/src/api/tasks.ts`：前端 API 封装入口。
- OpenAPI：`http://127.0.0.1:8001/docs`（以后端实际发布为准）。

### 一句话
- 前端查文档从本节开始；体验增强能力优先对照 `docs/ux_service_api_contract_draft.md`。

## 1.2 依据（补充）
- 在原有依据基础上，新增体验草案作为联调依据：`docs/ux_service_api_contract_draft.md`。

## 7. 用户体验增强接口规划（补充说明）
- 本节实施前先回看 **§1.1 前端参考文档索引**。
- 详细字段契约以 `docs/ux_service_api_contract_draft.md` 为准。
- **已落地（第一批）**：`POST /api/tasks/{task_id}/preflight-check`、`GET /api/tasks/{task_id}/execution/explanations`（见该文档 §1.2）；其余条目仍为规划。

---
# 鍓嶇闃舵鎺ュ彛娓呭崟

## 1. 鏂囨。璇存槑

鏈枃妗ｇ敤浜庢暣鐞嗘瘯涓氳璁″钩鍙板湪鍓嶇寮€鍙戦樁娈垫渶鍙兘闇€瑕佺殑鎺ュ彛锛屼究浜庯細

- 鍓嶇椤甸潰璁捐鏃剁粺涓€鏁版嵁鏉ユ簮
- 鍚庣鍚庣画琛ュ厖 REST API 鏃朵綔涓哄弬鑰?
- 鑱旇皟鍓嶅厛瀹屾垚 mock 鏁版嵁涓庨〉闈㈢粨鏋勮璁?

褰撳墠浠撳簱涓殑骞冲彴涓绘祦绋嬩负锛?

`浠诲姟鎺ュ叆 -> 闇€姹傝В鏋?-> 鐢ㄤ緥鐢熸垚 -> 娴嬭瘯鎵ц -> 缁撴灉鍒嗘瀽 -> 鍓嶇灞曠ず`

鎺ュ彛璁捐涓昏渚濇嵁浠ヤ笅鍐呭锛?

- `docs/project_requirements.md`
- `docs/ux_service_api_contract_draft.md`锛堜綋楠屽寮烘帴鍙ｈ崏妗堬紝涓庢湰鏂囨。 搂7 瀵瑰簲锛?
- `platform/platform-ui/README.md`
- `platform/shared/src/platform_shared/models.py`
- `platform/task-center/src/task_center/pipeline.py`

褰撳墠浠ｇ爜閲屽凡缁忔槑纭殑鏍稿績瀵硅薄鍖呮嫭锛?

- `TaskContext`
- `ParsedRequirement`
- `ScenarioModel`
- `TestCaseDSL`
- `ExecutionResult`
- `ValidationReport`
- `AnalysisReport`

### 1.1 鍓嶇鍙傝€冩枃妗ｇ储寮曪紙姹囨€荤粰鍓嶇锛?

浠ヤ笅鎸変紭鍏堢骇鏁寸悊锛屼究浜庤浆浜ゅ墠绔洟闃燂紱璺緞鍧囩浉瀵逛粨搴撴牴鐩綍銆?

#### 蹇呯湅锛堣仈璋冧笌濂戠害锛?

| 鏂囨。 | 璺緞 | 鐢ㄩ€?|
| --- | --- | --- |
| 鍓嶇鎺ュ彛娓呭崟锛堟湰鏂囨。锛?| `docs/frontend_api_list.md` | 鐜版湁 30 鏉?API銆侀〉闈㈡槧灏勩€佹暟鎹祦銆佸疄鐜扮姸鎬佷笌娉ㄦ剰浜嬮」銆?|
| 浣撻獙澧炲己鎺ュ彛濂戠害鑽夋 | `docs/ux_service_api_contract_draft.md` | 棰勬 / 澶辫触瑙ｉ噴 / 鍥炲綊瀵规瘮 / SSE 鐨勮姹傚搷搴旂ず渚嬨€侀敊璇爜涓庡垎闃舵钀藉湴锛?*鍚庣鏈疄鐜板墠涔熷彲鍏堝榻愯璁?*锛夈€?|
| 鍓嶇寮€鍙戞寚鍗?| `platform/platform-ui/FRONTEND_DEVELOPMENT_GUIDE.md` | 璺敱銆佹帴鍙ｅ垎灞傘€佷氦浜掍笌宸ョ▼绾︽潫銆?|
| 鍓嶇椤甸潰瑙勫垝 | `platform/platform-ui/FRONTEND_PAGE_PLAN.md` | 椤甸潰涓?Tab 鍒掑垎锛屾柊鑳藉姏搴旇惤鍦ㄥ摢涓€椤靛榻愮敤銆?|

#### 寤鸿鐪嬶紙绾︽潫涓庨獙鏀讹級

| 鏂囨。 | 璺緞 | 鐢ㄩ€?|
| --- | --- | --- |
| 闇€姹傚畬鎴愬害涓庣害鏉?| `docs/platform_requirements_status.md` | API 鍐荤粨銆佺粺涓€ envelope銆佹墽琛岃秴鏃剁瓑宸ョ▼绾︽潫锛涗綋楠屾湇鍔′紭鍏堢骇銆?|
| 绔埌绔獙鏀堕渶姹?| `docs/platform_e2e_requirement.md` | 涓氬姟楠屾敹鍏虫敞鐐逛笌鎺ュ彛鍩虹嚎鍒嗙粍锛堜笌鏈枃妗ｄ竴鑷达級銆?|
| 骞冲彴蹇€熷紑濮?| `docs/platform_quickstart.md` | 鏈嶅姟鍚姩銆佹ā鍧楀垎宸ャ€佸缓璁紑鍙戦『搴忎笌浣撻獙璺嚎鍥俱€?|

#### 鍙€夛紙娣卞叆锛?

| 鏂囨。 | 璺緞 | 鐢ㄩ€?|
| --- | --- | --- |
| DSL 璇存槑 | `docs/dsl_spec.md` | 鎵ц渚?DSL 缁撴瀯锛屾墽琛岃鎯?璋冭瘯椤靛彲鍙傝€冦€?|
| 骞冲彴鍘熷闇€姹?| `docs/project_requirements.md` | 鑳屾櫙涓庤寖鍥淬€?|
| 瑙ｆ瀽 / RAG / LLM 璁捐 | `docs/requirement_analysis_rag_llm_design.md` | 瑙ｆ瀽涓庡寮鸿兘鍔涜鏄庯紝瑙ｆ瀽缁撴灉椤靛睍绀哄彲鍙傝€冦€?|

#### 浠ｇ爜渚у绾︼紙涓庢枃妗ｅ鐓э級

| 浣嶇疆 | 鐢ㄩ€?|
| --- | --- |
| `platform/platform-ui/api-contract.ts` | TypeScript 绫诲瀷涓庡搷搴斿舰鐘讹紝涓庢湰鏂囨。瀵圭収缁存姢銆?|
| `platform/platform-ui/src/api/tasks.ts` | 璇锋眰灏佽鍏ュ彛锛堣寮€鍙戞寚鍗楋級銆?|
| OpenAPI | 鍚庣鍚姩鍚?`http://127.0.0.1:8001/docs`銆?*浣撻獙澧炲己鍥涚被鎺ュ彛鑻ュ皻鏈嚭鐜板湪 OpenAPI 涓紝浠?`docs/ux_service_api_contract_draft.md` 涓哄噯銆?* |

#### 涓€鍙ヨ瘽

- **鏃ュ父鑱旇皟**锛氫互鏈枃妗ｏ紙`docs/frontend_api_list.md`锛変负涓汇€? 
- **浣撻獙澧炲己**锛堥妫€銆佽В閲娿€佸姣斻€佸疄鏃舵祦锛夛細浠?`docs/ux_service_api_contract_draft.md` 涓轰富锛涜惤鍦板悗鍐嶅悓姝ユ洿鏂版湰鏂囨。 搂7 涓?`api-contract.ts`銆? 
- **鍒俯鍧?*锛歚docs/platform_requirements_status.md` 涓绾﹀喕缁撱€?22銆佹墽琛屽悓姝?瓒呮椂绛夎鏄庛€?

---

## 2. 鍓嶇椤甸潰瀵瑰簲妯″潡

寤鸿鍓嶇绗竴闃舵椤甸潰鍒掑垎濡備笅锛?

- 浠诲姟鍒涘缓椤?
- 浠诲姟鍒楄〃椤?
- 浠诲姟璇︽儏椤?
- 闇€姹傝В鏋愮粨鏋滈〉
- 娴嬭瘯鍦烘櫙/DSL 灞曠ず椤?
- 鎵ц鐩戞帶椤?
- 鍒嗘瀽鎶ュ憡椤?
- 鍘嗗彶浠诲姟椤?

---

## 3. 鎺ュ彛娓呭崟

## 3.1 浠诲姟绠＄悊鎺ュ彛

### 1. 鍒涘缓浠诲姟

- 鏂规硶锛歚POST`
- 璺緞锛歚/api/tasks`
- 鐢ㄩ€旓細鍒涘缓涓€涓柊鐨勬祴璇曚换鍔?

璇锋眰浣撳缓璁細

```json
{
  "task_name": "鐢ㄦ埛鐧诲綍鍔熻兘娴嬭瘯",
  "source_type": "text",
  "requirement_text": "鐢ㄦ埛杈撳叆姝ｇ‘璐﹀彿瀵嗙爜鍚庣櫥褰曟垚鍔熷苟杩涘叆涓汉涓績",
  "target_system": "http://localhost:8080",
  "environment": "test"
}
```

杩斿洖浣撳缓璁細

```json
{
  "task_id": "task_20260329_001",
  "task_context": {
    "task_id": "task_20260329_001",
    "task_name": "鐢ㄦ埛鐧诲綍鍔熻兘娴嬭瘯",
    "source_type": "text",
    "source_path": null,
    "created_at": "2026-03-29T10:00:00Z",
    "language": "zh-CN",
    "status": "received",
    "notes": []
  }
}
```

### 2. 鑾峰彇浠诲姟鍒楄〃

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks`
- 鐢ㄩ€旓細浠诲姟鍒楄〃椤点€佸巻鍙蹭换鍔￠〉

鏌ヨ鍙傛暟寤鸿锛?

- `status`
- `keyword`
- `page`
- `page_size`

### 3. 鑾峰彇浠诲姟璇︽儏

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}`
- 鐢ㄩ€旓細浠诲姟璇︽儏椤靛熀纭€淇℃伅灞曠ず

### 4. 鍒犻櫎鎴栧綊妗ｄ换鍔?

- 鏂规硶锛歚DELETE`
- 璺緞锛歚/api/tasks/{task_id}`
- 鐢ㄩ€旓細褰撳墠瀹炵幇涓洪€昏緫褰掓。锛坄archived=true`锛夛紝涓嶆槸鐗╃悊鍒犻櫎

---

## 3.2 闇€姹傝В鏋愭帴鍙?

### 5A. 鍒嗘瀽妯″潡鐩磋皟瑙ｆ瀽锛堟柊澧烇級

- 鏂规硶锛歚POST`
- 璺緞锛歚/api/analysis/parse`
- 鐢ㄩ€旓細涓嶄緷璧栦换鍔＄敓鍛藉懆鏈燂紝鐩存帴璋冪敤 requirement-analysis 鏈嶅姟灞傝兘鍔?

璇锋眰浣撳缓璁細

```json
{
  "task_name": "闇€姹傚揩閫熻В鏋?,
  "source_type": "text",
  "requirement_text": "鐢ㄦ埛鐧诲綍鍚庡簲杩涘叆涓汉涓績骞剁湅鍒版樀绉?,
  "use_llm": false,
  "rag_enabled": true,
  "retrieval_top_k": 5,
  "rerank_enabled": false
}
```

杩斿洖寤鸿鍖呭惈锛?

- `parsed_requirement`
- `retrieved_context`
- `validation_report`
- `parse_metadata`

### 5. 瑙﹀彂闇€姹傝В鏋?

- 鏂规硶锛歚POST`
- 璺緞锛歚/api/tasks/{task_id}/parse`
- 鐢ㄩ€旓細瀵逛换鍔¤緭鍏ョ殑闇€姹傛枃妗ｆ墽琛岃В鏋?

鍙€夊寮哄弬鏁帮紙璇锋眰鍙傛暟浼樺厛绾ф渶楂橈級锛?

- `use_llm`锛堥粯璁?`false`锛?
- `rag_enabled`锛堥粯璁?`true`锛?
- `retrieval_top_k`锛堥粯璁?`5`锛?
- `rerank_enabled`锛堥粯璁?`false`锛?

### 6. 鑾峰彇缁撴瀯鍖栭渶姹?

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/parsed-requirement`
- 鐢ㄩ€旓細灞曠ず闇€姹傝В鏋愮粨鏋?

杩斿洖瀛楁寤鸿锛?

- `objective`
- `actors`
- `entities`
- `preconditions`
- `actions`
- `expected_results`
- `constraints`
- `ambiguities`
- `source_chunks`

### 7. 鑾峰彇妫€绱笂涓嬫枃

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/retrieved-context`
- 鐢ㄩ€旓細灞曠ず瑙ｆ瀽鍛戒腑鐨勬枃妗ｇ墖娈碉紝渚夸簬璇存槑鈥滀负浠€涔堢敓鎴愯繖浜涙祴璇曠偣鈥?

---

## 3.3 鐢ㄤ緥鐢熸垚鎺ュ彛

### 8. 鐢熸垚娴嬭瘯鍦烘櫙

- 鏂规硶锛歚POST`
- 璺緞锛歚/api/tasks/{task_id}/scenarios/generate`
- 鐢ㄩ€旓細鏍规嵁缁撴瀯鍖栭渶姹傜敓鎴愭祴璇曞満鏅?

### 9. 鑾峰彇娴嬭瘯鍦烘櫙鍒楄〃

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/scenarios`
- 鐢ㄩ€旓細鍦烘櫙鍒楄〃銆佸満鏅鎯呭睍绀?

杩斿洖鍐呭寤鸿鍖呭惈锛?

- `scenario_id`
- `name`
- `goal`
- `priority`
- `preconditions`
- `steps`
- `assertions`
- `source_chunks`

### 10. 鑾峰彇 DSL

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/dsl`
- 鐢ㄩ€旓細鍓嶇鏌ョ湅缁熶竴娴嬭瘯鎻忚堪 `TestCaseDSL`

### 11. 鑾峰彇 Gherkin 鐗规€ф枃浠?

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/feature`
- 鐢ㄩ€旓細灞曠ず `.feature` 鏂囨湰

---

## 3.4 鎵ц绠＄悊鎺ュ彛

### 12. 鍚姩鎵ц

- 鏂规硶锛歚POST`
- 璺緞锛歚/api/tasks/{task_id}/execute`
- 鐢ㄩ€旓細鍚姩娴嬭瘯鎵ц

璇锋眰浣撳缓璁細

```json
{
  "execution_mode": "api",
  "environment": "test"
}
```

妯″潡褰掑睘璇存槑锛?
- `execution_mode=api` -> `execution-engine/api-runner`锛堝綋鍓嶄富鎵ц璺緞锛?
- `execution_mode=cloud-load` -> `execution-engine/cloud-load-runner`锛堝綋鍓嶄负鏈湴骞跺彂鍘嬫祴妯℃嫙锛岄潪绗笁鏂逛簯鍘嬫祴锛?
- `execution_mode=web-ui` -> `execution-engine/lavague-adapter`锛堥€傞厤涓級

### 13. 鑾峰彇鎵ц鐘舵€?

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/execution`
- 鐢ㄩ€旓細鎵ц鐩戞帶椤佃幏鍙栧綋鍓嶆墽琛岃繘搴︿笌缁撴灉

寤鸿杩斿洖鍐呭锛?

- `task_id`
- `executor`
- `status`
- `scenario_results`
- `metrics`
- `logs`

### 14. 鑾峰彇鎵ц鏃ュ織

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/execution/logs`
- 鐢ㄩ€旓細鏃ュ織闈㈡澘瀹炴椂灞曠ず

### 15. 鍋滄鎵ц

- 鏂规硶锛歚POST`
- 璺緞锛歚/api/tasks/{task_id}/execution/stop`
- 鐢ㄩ€旓細涓褰撳墠鎵ц浠诲姟

---

## 3.5 鎶ュ憡涓庡彲瑙嗗寲鎺ュ彛

### 16. 鑾峰彇鏍￠獙鎶ュ憡

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/validation-report`
- 鐢ㄩ€旓細灞曠ず鐢ㄤ緥鏍￠獙缁撴灉

寤鸿杩斿洖鍐呭锛?

- `feature_name`
- `passed`
- `errors`
- `warnings`
- `metrics`

### 17. 鑾峰彇鍒嗘瀽鎶ュ憡

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/analysis-report`
- 鐢ㄩ€旓細灞曠ず鍒嗘瀽鎶ュ憡涓庡浘琛?

寤鸿杩斿洖鍐呭锛?

- `task_id`
- `task_name`
- `quality_status`
- `summary`
- `findings`
- `chart_data`

### 18. 鑾峰彇浠〃鐩樿仛鍚堟暟鎹?

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/dashboard`
- 鐢ㄩ€旓細鎶ュ憡椤典竴娆℃€ц幏鍙栨瑙堛€佸浘琛ㄥ拰鎽樿淇℃伅

---

## 3.6 浜х墿涓庡巻鍙叉帴鍙?

### 19. 鑾峰彇浠诲姟浜х墿鍒楄〃

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/artifacts`
- 鐢ㄩ€旓細鏌ョ湅浠诲姟鐢熸垚鐨勬枃浠跺拰涓棿浜х墿

寤鸿鍖呮嫭锛?

- 鍘熷闇€姹傛枃鏈?
- 瑙ｆ瀽鍏冩暟鎹紙`parse-metadata`锛?
- 娓呮礂鍚庢枃鏈?
- 缁撴瀯鍖栭渶姹?
- 鍦烘櫙鏂囦欢
- DSL 鏂囦欢
- Gherkin 鏂囦欢
- 鏍￠獙鎶ュ憡
- 鍒嗘瀽鎶ュ憡

### 20. 鑾峰彇鍗曚釜浜х墿鍐呭

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/artifacts/{type}`
- 鐢ㄩ€旓細璇诲彇鎸囧畾浜х墿鍐呭

褰撳墠瀹炵幇涓紝`type` 寤鸿浣跨敤杩炲瓧绗﹀懡鍚嶏紙濡?`parsed-requirement`銆乣validation-report`銆乣parse-metadata`锛夈€?

### 21. 鑾峰彇鍘嗗彶浠诲姟

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/history/tasks`
- 鐢ㄩ€旓細鍘嗗彶浠诲姟鏌ヨ銆佺粺璁°€佺瓫閫?

---

## 4. 鍓嶇 MVP 鎺ㄨ崘浼樺厛绾?

濡傛灉褰撳墠鐩爣鏄敖蹇妸鍓嶇椤甸潰鍋氬嚭鏉ワ紝寤鸿浼樺厛浣跨敤浠ヤ笅鎺ュ彛锛?

### 绗竴浼樺厛绾?

- `POST /api/tasks`
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `GET /api/tasks/{task_id}/parsed-requirement`
- `GET /api/tasks/{task_id}/scenarios`
- `GET /api/tasks/{task_id}/dsl`
- `GET /api/tasks/{task_id}/analysis-report`

### 绗簩浼樺厛绾?

- `POST /api/tasks/{task_id}/execute`
- `GET /api/tasks/{task_id}/execution`
- `GET /api/tasks/{task_id}/execution/logs`

### 绗笁浼樺厛绾?

- `GET /api/tasks/{task_id}/feature`
- `GET /api/tasks/{task_id}/validation-report`
- `GET /api/tasks/{task_id}/artifacts`
- `GET /api/history/tasks`

---

## 5. 寤鸿鐨勫墠绔暟鎹祦

椤甸潰鑱旇皟鏃跺缓璁寜涓嬮潰椤哄簭璋冪敤锛?

1. 鍒涘缓浠诲姟锛歚POST /api/tasks`
2. 鑾峰彇浠诲姟璇︽儏锛歚GET /api/tasks/{task_id}`
3. 鑾峰彇缁撴瀯鍖栭渶姹傦細`GET /api/tasks/{task_id}/parsed-requirement`
4. 鑾峰彇娴嬭瘯鍦烘櫙锛歚GET /api/tasks/{task_id}/scenarios`
5. 鑾峰彇 DSL / Feature锛歚GET /api/tasks/{task_id}/dsl`銆乣GET /api/tasks/{task_id}/feature`
6. 鍚姩鎵ц锛歚POST /api/tasks/{task_id}/execute`
7. 杞鎵ц鐘舵€侊細`GET /api/tasks/{task_id}/execution`
8. 鑾峰彇鎶ュ憡锛歚GET /api/tasks/{task_id}/analysis-report`

---

## 6. 瀹炵幇鐘舵€侊紙2026-04-02 鏇存柊锛?

鎴嚦 2026-04-02 鍚庣瀹¤纭锛?

- **鏈枃妗ｆ墍鍒楀叏閮?30 鏉?API 璺敱宸插疄鐜板苟鍙敤**锛屾帴鍙ｈ鐩栧畬鏁淬€?
- 鍓嶇寮€鍙戝凡鍙叏闈㈠垏鎹㈠埌鐪熷疄 API 鑱旇皟锛宮ock 鏁版嵁搴旈檷绾т负鍏滃簳銆?
- 鍚庣 API 濂戠害宸插喕缁擄紝璺緞涓庢牳蹇冨瓧娈典笉鍐嶅彉鏇达紙璇﹁ `docs/platform_requirements_status.md` 绗?8 鑺傦級銆?
- 鎵€鏈夋帴鍙ｇ粺涓€杩斿洖 `{"success", "code", "message", "data", "timestamp"}` 鍝嶅簲 envelope銆?
- OpenAPI 鏂囨。鍙€氳繃 `http://127.0.0.1:8001/docs` 鏌ョ湅銆?

宸茬煡娉ㄦ剰浜嬮」锛?
- 422 鏍￠獙閿欒宸叉敹鏁涘埌缁熶竴 envelope锛坄code=VALIDATION_ERROR`锛夛紝鍓嶇浠嶅缓璁繚鐣欏厹搴曞睍绀洪€昏緫銆?
- `POST /execute` 褰撳墠涓哄悓姝ラ樆濉炶繑鍥烇紝鍚庣画浼氬垏鎹负寮傛鎻愪氦妯″紡銆?
- 鎵ц缁撴灉涓儴鍒嗘柇瑷€鍙兘鍥犵簿搴︿笉瓒宠€屾樉绀?failed锛屽睘浜庢柇瑷€璐ㄩ噺闂锛屼笉褰卞搷鎺ュ彛鍙敤鎬с€?
- `execution_mode=cloud-load` 鐩墠鏄渶灏忓苟鍙戝帇娴嬭兘鍔涳紝鏆備笉鎻愪緵浜戝钩鍙颁换鍔?ID銆佽繙绋嬭繘搴︿笌鍥炶皟绛夎兘鍔涖€?

## 7. 鐢ㄦ埛浣撻獙澧炲己鎺ュ彛瑙勫垝锛堟湭瀹炵幇锛屼緵鍚庣画鍙傝€冿級

璇︾粏濂戠害鑽夋锛歚docs/ux_service_api_contract_draft.md`锛堝畬鏁村瓧娈典笌閿欒鐮佽璇ユ枃妗ｏ紱**鍓嶇姹囨€荤储寮曡鏈枃妗?搂1.1**锛夈€?

浠ヤ笅鎺ュ彛涓哄缓璁柊澧炶兘鍔涳紝閬靛惊鈥滄柊澧炵鐐广€佷笉鐮村潖鐜版湁 30 鏉℃帴鍙ｂ€濈殑鍘熷垯銆?

### 7.1 鐜鍋ュ悍妫€鏌?

- 鏂规硶锛歚POST`
- 璺緞锛歚/api/tasks/{task_id}/preflight-check`
- 鐢ㄩ€旓細鎵ц鍓嶆鏌?base_url銆侀壌鏉冦€佸叧閿帴鍙ｈ繛閫氭€т笌鍩虹鑰楁椂
- 杩斿洖寤鸿锛歚overall_status`銆乣checks[]`銆乣blocking_issues[]`銆乣suggestions[]`

### 7.2 澶辫触瑙ｉ噴

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/execution/explanations`
- 鐢ㄩ€旓細鍩轰簬鎵ц缁撴灉鑷姩杈撳嚭澶辫触鍒嗙被涓庝慨澶嶅缓璁?
- 杩斿洖寤鸿锛歚failure_groups[]`銆乣top_reasons[]`銆乣recommended_actions[]`

### 7.3 鍘嗗彶鍥炲綊瀵规瘮

- 鏂规硶锛歚GET`
- 璺緞锛歚/api/tasks/{task_id}/regression-diff`
- 鐢ㄩ€旓細瀵规瘮鏈€杩戜袱娆℃垨鎸囧畾涓ゆ鎵ц缁撴灉
- 杩斿洖寤鸿锛歚success_rate_diff`銆乣latency_diff`銆乣failure_type_diff`銆乣verdict`

### 7.4 瀹炴椂鎵ц浜嬩欢娴?

- 鏂规硶锛歚GET`锛圫SE锛?
- 璺緞锛歚/api/tasks/{task_id}/execution/stream`
- 鐢ㄩ€旓細瀹炴椂鎺ㄩ€佹楠ょ姸鎬佸彉鍖栵紝鍑忓皯杞鍘嬪姏
- 浜嬩欢寤鸿锛歚step_start`銆乣step_end`銆乣assertion_failed`銆乣execution_done`


## 8. 下一步迭代入口（2026-04-03）

- 状态基线：`docs/platform_requirements_status.md` 见 **§M 下一步迭代更新**。
- 规则落地：`platform/platform-ui/FRONTEND_DEVELOPMENT_GUIDE.md` 见 **§13 迭代规则对齐**。
- 本轮优先级（前端）：
  - P0：历史分页边界收敛（`page_size<=200`）、执行态统一、未上线接口降级。
  - P1：SSE + 轮询双通道稳定性、联调回归自动化。
- 开发时先看本文件 §1.1，再看上述两节执行。
