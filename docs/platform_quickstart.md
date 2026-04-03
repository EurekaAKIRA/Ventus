# Platform Quick Start

## 主线文档列表（补充）
- `docs/frontend_api_list.md`（前端总入口见 §1.1）
- `docs/ux_service_api_contract_draft.md`（体验增强契约草案）
- `docs/platform_requirements_status.md`
- `docs/platform_e2e_requirement.md`

## 前端协作文档入口
- 统一入口：`docs/frontend_api_list.md` 的 **§1.1 前端参考文档索引**。
- 给前端同步时，先发 §1.1；其余文档从该处按链接进入即可。

---
# Platform Quick Start

## 褰撳墠榛樿涓荤嚎

褰撳墠椤圭洰宸茬粡鍒囨崲鍒版柊鐨?`platform/` 鏋舵瀯锛屽缓璁紭鍏堝叧娉ㄤ互涓嬬洰褰曪細

- `platform/task-center`
- `platform/requirement-analysis`
- `platform/case-generation`
- `platform/execution-engine`
- `platform/result-analysis`
- `platform/shared`
- `docs/dsl_spec.md`
- `docs/platform_requirements_status.md`锛堥渶姹傚畬鎴愬害涓庝笅涓€姝ュ缓璁級
- `docs/frontend_api_list.md`锛堝墠绔仈璋冩帴鍙ｅ熀绾匡紱**鍓嶇鏂囨。姹囨€荤储寮曡璇ユ枃妗?搂1.1**锛?
- `docs/ux_service_api_contract_draft.md`锛堜綋楠屽寮烘帴鍙ｅ绾﹁崏妗堬級

鍘嗗彶鐩綍涓昏鐢ㄤ簬杩佺Щ鍙傝€冨拰鍏煎渚濊禆锛屽叾涓ぇ閮ㄥ垎宸茬粡褰掓。鍒帮細

- `legacy/`

## 鍓嶇鍗忎綔鏂囨。鍏ュ彛

- **缁欏墠绔殑鏂囨。鎬昏〃**锛歚docs/frontend_api_list.md` 鈫?**搂1.1 鍓嶇鍙傝€冩枃妗ｇ储寮?*銆? 
- **浣撻獙澧炲己 API 瀛楁绾х害瀹?*锛歚docs/ux_service_api_contract_draft.md`銆? 
- **椤甸潰涓庡伐绋嬭鑼?*锛歚platform/platform-ui/FRONTEND_DEVELOPMENT_GUIDE.md`銆乣platform/platform-ui/FRONTEND_PAGE_PLAN.md`銆?

## 蹇€熻繍琛?

### 杩愯鏂扮殑浠诲姟鍒嗘瀽涓婚摼璺?

```powershell
python run_platform.py pipeline --task-name demo --requirement-text "鐢ㄦ埛鎵撳紑棣栭〉鍚庡簲鐪嬪埌鏍囬鍜屾悳绱㈡"
```

### 杩愯鏂扮殑浠诲姟閾捐矾 smoke test

```powershell
python run_platform.py smoke-test
```

### 杩愯鎺ュ彛鎵ц鍣?smoke test

```powershell
python run_platform.py api-smoke-test
```

### 杩愯鍚庣 API 鏈嶅姟

```powershell
python run_platform.py serve-api
```

榛樿鍦板潃锛?

- `http://127.0.0.1:8001`
- OpenAPI 鏂囨。锛歚http://127.0.0.1:8001/docs`

### 闇€姹傝В鏋愬寮烘ā寮忥紙鍙€夛級

榛樿瑙ｆ瀽绛栫暐閰嶇疆浣嶄簬锛?

- `platform/shared/config/runtime_config.json`

濡傛灉瑕佸惎鐢ㄦā鍨嬪寮猴紝鍙渶閰嶇疆妯″瀷 API 鐜鍙橀噺锛?

```powershell
$env:HUNYUAN_API_KEY="your_api_key"
$env:HUNYUAN_BASE_URL="https://api.hunyuan.cloud.tencent.com/v1"
$env:HUNYUAN_LLM_MODEL="hunyuan-turbos-latest"
$env:HUNYUAN_EMBEDDING_MODEL="hunyuan-embedding"
```

`use_llm`銆乣rag_enabled`銆乣retrieval_top_k`銆乣rerank_enabled` 浠ュ強妫€绱㈡潈閲嶇粺涓€鐢?
`platform/shared/config/runtime_config.json` 绠＄悊锛屼篃鍙湪 API 璇锋眰鍙傛暟涓寜浠诲姟瑕嗙洊銆?

濡傞渶鎸変换鍔￠€夋嫨妯″瀷绛栫暐锛屽彲鍦ㄨВ鏋?API 璇锋眰涓紶鍏?`model_profile`锛堜緥濡?`default`銆乣high_quality`銆乣low_cost`锛夈€?

澧炲己鎺ュ彛锛坱ask-center 浠ｇ悊锛夛細

- `POST /api/analysis/parse`
- `POST /api/tasks/{task_id}/parse`

### 杩愯 API 鏈嶅姟 smoke test

```powershell
python run_platform.py server-smoke-test
```

### 杩愯鍚庣鏍囧噯娴嬭瘯鐢ㄤ緥锛堣繛鐪熷疄鍚庣锛?

鍏堝惎鍔ㄥ悗绔細

```powershell
python run_platform.py serve-api
```

鍐嶆墽琛屾爣鍑嗙敤渚嬶細

```powershell
python platform/task-center/tests/backend_standard_case.py --api-base http://127.0.0.1:8001
```

浼犻渶姹傛枃妗ｈ繍琛岋紙浣跨敤绮剧畝鏍锋湰鏂囨。锛岄伩鍏嶅ぇ鏂囨。 LLM 瓒呮椂锛夛細

```powershell
python platform/task-center/tests/backend_standard_case.py --api-base http://127.0.0.1:8001 --source-type markdown --source-path docs/sample_requirement.md
```

濡傞渶楠岃瘉 LLM 澧炲己閾捐矾锛?

```powershell
python platform/task-center/tests/backend_standard_case.py --api-base http://127.0.0.1:8001 --use-llm --model-profile default --source-type markdown --source-path docs/sample_requirement.md
```

### 杩愯鍓嶇 API 鑱旇皟 smoke test锛堝彲閫夛級

鍏堢‘淇濆悗绔?API 宸插惎鍔紙榛樿 `http://127.0.0.1:8001`锛夛細

```powershell
python run_platform.py serve-api
```

鍐嶆墽琛岋細

```powershell
cd platform/platform-ui
npm run smoke-api
```

濡傚悗绔湴鍧€涓嶅悓锛屽彲璁剧疆锛?

```powershell
$env:PLATFORM_API_BASE="http://127.0.0.1:8001"
npm run smoke-api
```

### 鏌ョ湅鎵ц寮曟搸鍏叡灞傚府鍔?

```powershell
python run_platform.py execution-help
```

## 褰撳墠鏋舵瀯瀹氫綅

- `task-center`锛氱粺涓€浠诲姟鍏ュ彛鍜岀紪鎺掞紙30 鏉?API 璺敱锛?2 涓祴璇曟枃浠讹級
- `requirement-analysis`锛氶渶姹傝В鏋愬拰妫€绱㈠寮猴紙瑙勫垯 + RAG + LLM + fallback锛? 涓祴璇曟枃浠讹級
- `case-generation`锛氭祴璇曞満鏅€丟herkin 鍜?TestCaseDSL 鐢熸垚锛? 涓祴璇曟枃浠?/ 9 cases锛?
- `execution-engine/core`锛氭墽琛屽叕鍏卞眰鍜?DSL 杩愯鏃?
- `execution-engine/api-runner`锛氱湡瀹炴帴鍙ｈ嚜鍔ㄥ寲鎵ц鍣紙HTTP + 鍙橀噺鏇挎崲 + 涓婁笅鏂囦紶閫掞紝3 涓祴璇曟枃浠讹級
- `execution-engine/lavague-adapter`锛歀aVague Web/UI 鎵ц閫傞厤鍣?
- `execution-engine/cloud-load-runner`锛氬帇娴嬫墽琛屽櫒锛堝綋鍓嶄负鏈湴骞跺彂鍘嬫祴妯℃嫙鍣紝宸叉帴鍏?`execution_mode=cloud-load`锛屾湭瀹屾垚绗笁鏂逛簯鍘嬫祴骞冲彴瀵规帴锛?
- `result-analysis`锛氬垎鏋愭姤鍛婁笌璐ㄩ噺璇勪及锛堝鐗堟湰鎶ュ憡鏋勫缓锛? 涓祴璇曟枃浠讹級
- `shared`锛氭牳蹇冩ā鍨嬨€乵odel_gateway銆乺untime_config 鍏变韩灞?

鍚庣鍚堣 23 涓祴璇曟枃浠讹紝涓婚摼璺叏閮ㄥ彲鐢ㄣ€傝缁嗗畬鎴愬害瑙?`docs/platform_requirements_status.md`銆?

## 寤鸿寮€鍙戦『搴?

1. 浼樺厛鍦?`platform/` 涓嬬户缁紑鍙?
2. 浼樺厛浠?`task-center` 涓婚摼璺帴鍏ユ柊鍔熻兘
3. 鍏堟妸鎺ュ彛鑷姩鍖栧仛鎵庡疄锛屽啀鑰冭檻 UI 鑷姩鍖栨墿灞?
4. 涓嶅啀鎶?`lavague-qa` 褰撲綔骞冲彴涓績
5. **API 濂戠害宸插喕缁?*锛?0 鏉¤矾鐢变笉鍐嶄慨鏀硅矾寰勫拰鏍稿績瀛楁锛堣瑙?`docs/platform_requirements_status.md` 绗?8 鑺傦級
6. 褰撳墠閲嶇偣锛氭柇瑷€璐ㄩ噺鎻愬崌銆侀敊璇爜缁熶竴銆佹墽琛岃秴鏃朵繚鎶ゃ€佸墠鍚庣鑱旇皟闂幆
7. 鍘嬫祴妯″潡鎸夆€滃厛绋冲畾鍗忚銆佸啀寮傛鍖栥€佸悗浜戝钩鍙版帴鍏モ€濇帹杩涳紝閬垮厤鍦?`cloud-load` 涓婂弽澶嶆敼鎺ュ彛璇箟
8. 鐢ㄦ埛浣撻獙鏈嶅姟浼樺厛绾э細鍏堝仛鈥滅幆澧冨仴搴锋鏌?+ 澶辫触瑙ｉ噴 + 鍘嗗彶鍥炲綊瀵规瘮鈥濓紝鍐嶅仛瀹炴椂浜嬩欢娴佷笌閫氱煡璁㈤槄

## 鐢ㄦ埛浣撻獙鏈嶅姟寤鸿锛堝悗缁弬鑰冿級

闈㈠悜褰撳墠涓婚摼璺紙鍒涘缓 -> 瑙ｆ瀽 -> 鎵ц -> 鎶ュ憡锛夛紝寤鸿鎸夐樁娈靛寮虹敤鎴蜂綋楠岋細

### 绗竴闃舵锛堟湰鏈堬級

- 鐜鍋ュ悍妫€鏌ワ細鎵ц鍓嶆帰娴?base_url銆侀壌鏉冦€佸叧閿帴鍙ｈ繛閫氭€э紝鎻愬墠鎷︽埅鏃犳晥浠诲姟
- 澶辫触瑙ｉ噴鏈嶅姟锛氬 failed step 鑷姩鍒嗙被骞剁粰淇寤鸿锛岄檷浣庢帓闅滄垚鏈?
- 鍘嗗彶鍥炲綊瀵规瘮锛氬悓浠诲姟澶氭鎵ц鑷姩缁欏嚭閫氳繃鐜?鑰楁椂 diff 涓庣粨璁?

### 绗簩闃舵锛堜笅鏈堬級

- 瀹炴椂鎵ц浜嬩欢娴侊紙SSE/WebSocket锛夛細鏇挎崲楂橀杞锛屾彁鍗囨墽琛岀洃鎺т綋楠?
- 浠诲姟鍚戝锛氬垱寤轰换鍔℃椂鎻愪緵鈥滃彲鎵ц鎬ц瘎鍒嗏€濆拰閰嶇疆琛ュ叏寤鸿

### 绗笁闃舵锛堟寜闇€锛?

- 閫氱煡璁㈤槄锛氭墽琛屽畬鎴愬悗鎺ㄩ€佸埌 IM/閭欢
- 鎶ュ憡鍙俊搴﹁瘎鍒嗭細涓虹粨璁哄鍔犵疆淇″垎涓庨闄╂彁绀?

