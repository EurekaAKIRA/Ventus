# 前端开发指南（platform-ui）

## 1.1 参考文档索引（前端入口）
- 权威总表：`docs/frontend_api_list.md` 的 **§1.1 前端参考文档索引**。
- 本文用于工程与交互约束；接口与协作文档请从总表 §1.1 进入。
- JMeter 压测脚本与 HTML 报告生成：`platform/task-center/loadtest/README.md`；若要把报告嵌进前端，见本文 **§1.3**。

## 1.2 体验增强接口落位（2026-04-03）
- 详情页 `执行` Tab：
  - `POST /api/tasks/{task_id}/preflight-check`：执行前检查卡片（支持阻断提示）。
  - `GET /api/tasks/{task_id}/execution/stream`：实时流区域，若接口未上线则回退轮询并提示。
- 详情页 `报告` Tab：
  - `GET /api/tasks/{task_id}/execution/explanations`：失败解释卡片。
  - `GET /api/tasks/{task_id}/regression-diff`：回归对比卡片（若接口未上线显示“暂不可用”）。
- 历史任务页 `/tasks/history`：
  - 新增“回归对比”快捷入口，跳转 `?tab=report&compare=latest`，在详情页自动触发“对比最近一次”。
- 兼容策略：
  - 新接口按“可用即展示，不可用即降级”接入，不阻塞现有任务主流程。

## 1.3 JMeter 压测 HTML 报告（可选嵌入前端）

压测脚本与生成方式见 `platform/task-center/loadtest/README.md`（`jmeter -n -t ... -l ... -e -o <目录>`）。若产品需要在平台内以**图形化页面**查看该报告，前端可做如下之一（**非强制**，按排期选做）：

1. **静态资源嵌入（开发/简单部署）**  
   - 将 JMeter `-e -o` 生成的**整包**（含 `index.html`、`content/` 等）复制到 `platform-ui/public/` 下某一子目录（例如 `public/loadtest-report/`）。  
   - 构建后通过站点根路径访问，例如 `/loadtest-report/index.html`。  
   - 新增路由页用 **`<iframe src="...">`** 嵌入上述 URL 即可；注意 iframe 与站点**同源**时 JMeter 自带脚本一般可正常运行。

2. **独立部署 + 环境变量**  
   - 将 HTML 包部署到 CDN / 对象存储 / 网关静态目录，得到完整 HTTPS URL。  
   - 前端通过 `import.meta.env.VITE_JMETER_REPORT_URL`（或你们统一的运行时配置）指向该 URL，iframe `src` 读配置。  
   - **跨域**：若报告域与前端域不同，需确认 JMeter 报表是否依赖 `file://` 或受限 API；多数静态资源同包内相对路径即可，一般无问题。

3. **不要做的事**  
   - 不必把 JMeter 生成的上百个静态文件**提交进 Git**（体积大、无意义 diff）；CI 可在压测 job 里产出 artifact，再部署到静态托管。  
   - 不必为“嵌入报告”新增后端业务 API，除非后续要做「按任务 ID 关联某次压测 run」——那时再约定由后端存路径或签名 URL。

4. **与任务详情的关系**  
   - 当前 JMeter 报告是**独立压测产物**，与 `GET /api/tasks/{id}/...` 无自动绑定；若产品要「某任务下挂最后一次压测报告」，需要另行设计存储与接口，本文不展开。

---
# 鍓嶇寮€鍙戞寚鍗楋紙platform-ui锛?
> 鏂囦欢鏇村悕璇存槑锛氭湰鏂囦欢鍘熷悕 `FRONTEND_PREP.md`锛岀幇缁熶竴涓?`FRONTEND_DEVELOPMENT_GUIDE.md`銆?
## 1. 鐩爣
鏈枃浠剁敤浜庢寚瀵?`platform-ui` 鎸佺画杩唬锛岀‘淇濋〉闈㈢粨鏋勩€佹帴鍙ｄ娇鐢ㄣ€佷氦浜掍綋楠屼笌宸ョ▼瑙勮寖涓€鑷淬€?
鎺ㄨ崘涓绘祦绋嬶細
`浠诲姟鍒涘缓 -> 闇€姹傝В鏋?-> 鍦烘櫙/DSL -> 鎵ц鐩戞帶 -> 鍒嗘瀽鎶ュ憡 -> 浜х墿鏌ョ湅`

## 1.1 鍙傝€冩枃妗ｇ储寮曪紙浠撳簱鍐咃紝缁欏墠绔眹鎬伙級

瀹屾暣鍒嗙骇鍒楄〃锛堝繀鐪?/ 寤鸿鐪?/ 鍙€?/ 浠ｇ爜渚у绾︼級瑙?**`docs/frontend_api_list.md` 搂1.1**銆傛湰鑺備负蹇€熻烦杞細

| 鐢ㄩ€?| 璺緞 |
| --- | --- |
| 30 鏉′富鎺ュ彛涓庢暟鎹祦 | `docs/frontend_api_list.md` |
| 浣撻獙澧炲己 API 鑽夋锛堥妫€銆佽В閲娿€佸姣斻€丼SE锛?| `docs/ux_service_api_contract_draft.md` |
| 椤甸潰瑙勫垝锛堜笌鏈粨搴撹矾鐢变竴鑷达級 | `platform/platform-ui/FRONTEND_PAGE_PLAN.md`锛堟湰鏂囨。鍚岀洰褰曪級 |
| 濂戠害鍐荤粨銆?22銆佽秴鏃剁瓑绾︽潫 | `docs/platform_requirements_status.md` |
| 绔埌绔獙鏀朵笌鎺ュ彛鍩虹嚎 | `docs/platform_e2e_requirement.md` |
| 鍚庣鍚姩涓庢ā鍧楀垎宸?| `docs/platform_quickstart.md` |
| TS 绫诲瀷涓?OpenAPI 瀵圭収 | `api-contract.ts`锛汷penAPI锛歚http://127.0.0.1:8001/docs`锛堟柊浣撻獙鎺ュ彛鏈笂绾垮墠浠ヨ崏妗堜负鍑嗭級 |

## 2. 椤甸潰涓庤矾鐢?鏍稿績璺敱锛?- `/dashboard`锛氫华琛ㄧ洏
- `/tasks`锛氫换鍔″垪琛?- `/tasks/create`锛氬垱寤轰换鍔?- `/tasks/:taskId`锛氫换鍔¤鎯咃紙澶?Tab锛?- `/tasks/history`锛氬巻鍙蹭换鍔?
椤甸潰鍒嗗伐锛堝己绾︽潫锛夛細
1. 浠〃鐩橈紙鍐崇瓥灞傦級锛氬彧鍋氭眹鎬汇€佽秼鍔裤€侀璀︿笌瀵艰埅锛屼笉鎵胯浇閲嶆搷浣溿€?2. 浠诲姟鍒楄〃锛堟墽琛屽眰锛夛細鍙鐞嗚繘琛屼腑浠诲姟锛堟帴鏀?瑙ｆ瀽/鐢熸垚/鎵ц涓?澶辫触/鍋滄锛夛紝鎵胯浇澶勭悊鍔ㄤ綔銆?3. 鍘嗗彶浠诲姟锛堝璁″眰锛夛細鍙仛宸插畬鎴愪笌褰掓。浠诲姟鍥炴函锛屾壙杞界瓫閫夈€佸鐩樸€佹姤鍛婃煡鐪嬶紝涓嶆壙杞芥墽琛屾帶鍒躲€?
浠诲姟璇︽儏椤?Tab锛?- 瑙ｆ瀽
- 鍦烘櫙
- DSL / Feature
- 鎵ц
- 鎶ュ憡
- 浜х墿

## 3. 鎺ュ彛鍒嗗眰寤鸿
浼樺厛绾?P0锛?- `POST /api/tasks`
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `GET /api/tasks/{task_id}/parsed-requirement`
- `GET /api/tasks/{task_id}/scenarios`
- `GET /api/tasks/{task_id}/dsl`
- `GET /api/tasks/{task_id}/analysis-report`

浼樺厛绾?P1锛?- `POST /api/tasks/{task_id}/execute`
- `GET /api/tasks/{task_id}/execution`
- `GET /api/tasks/{task_id}/execution/logs`
- `POST /api/tasks/{task_id}/execution/stop`

浼樺厛绾?P2锛?- `GET /api/tasks/{task_id}/feature`
- `GET /api/tasks/{task_id}/validation-report`
- `GET /api/tasks/{task_id}/artifacts`
- `GET /api/history/tasks`

## 4. 浜や簰瑙勮寖
1. 榛樿灞曠ず鎽樿锛屼笉鐩存帴鍫嗘弧 JSON銆?2. 寮傛璇锋眰蹇呴』鏈夊姞杞芥€併€佹垚鍔熸彁绀恒€佸け璐ユ彁绀恒€侀噸璇曞叆鍙ｃ€?3. 鎵ц鍓嶅繀椤绘牎楠?`target_system`锛岄伩鍏?`base_url` 绫婚敊璇€?4. 鎵ц涓殑杞闂撮殧寤鸿 `2~3s`锛岀寮€椤甸潰鑷姩鍋滄銆?5. 澶辫触鎻愮ず蹇呴』鍙鍔紙鍛婅瘔鐢ㄦ埛涓嬩竴姝ヨ鍋氫粈涔堬級銆?
## 5. 鎵ц閾捐矾锛堝凡瀹炵幇锛?1. 鐐瑰嚮鈥滃惎鍔ㄦ墽琛屸€濄€?2. 鏍￠獙 `target_system` 涓哄悎娉?URL銆?3. 璋冪敤 `POST /api/tasks/{task_id}/execute`銆?4. 骞惰鎷夊彇 `execution + validation-report + analysis-report`銆?5. 鑻?`execution.status=running`锛屾瘡 `2.5s` 杞 `execution`锛岀粨鏉熷悗鍐嶆媺鍙栨姤鍛娿€?6. 鏀寔鈥滃仠姝㈡墽琛屸€濆苟鍥炲啓鍓嶇鐘舵€併€?
## 6. 鏂囨涓庤瑷€绾︽潫
- 褰撳墠闃舵椤甸潰缁熶竴涓枃鏂囨銆?- 绂佹涓嫳娣锋潅鎸夐挳涓庢彁绀猴紙渚嬪鍚岄〉鍑虹幇 `Start Execution` 涓?`鍚姩鎵ц`锛夈€?- 鏂板椤甸潰鎴栫粍浠跺繀椤诲湪 PR 鑷涓‘璁ゆ枃妗堣瑷€涓€鑷淬€?
## 7. 宸ョ▼绾︽潫
- API 璋冪敤缁熶竴鏀舵暃鍒?`src/api/tasks.ts`銆?- 绫诲瀷浠?`src/types` 涓?`api-contract.ts` 涓哄噯锛岄伩鍏嶉〉闈㈠唴瀹氫箟涓存椂缁撴瀯銆?- 鍏叡灞曠ず缁勪欢娌夋穩鍒?`src/components`锛岄〉闈㈠彧鍋氱紪鎺掋€?
## 8. platform-ui 鎵ц淇敼璁″垝锛堝悓姝ョ増锛?宸插畬鎴愶紙褰撳墠浠ｇ爜宸茶惤鍦帮級锛?1. 鎵ц鍏ュ彛鍓嶇疆鏍￠獙锛歚target_system` 蹇呴』涓哄悎娉?`http(s)` URL銆?2. 鍚姩鎵ц閾捐矾锛歚POST /execute` 鍚庡苟琛屾媺鍙?`execution + validation-report + analysis-report`銆?3. 鎵ц鎬佽疆璇細`execution.status=running` 鏃舵瘡 `2.5s` 杞锛岀粨鏉熷悗鍥炴媺鎶ュ憡銆?4. 浜哄伐鍋滄鎵ц锛氭敮鎸?`POST /execution/stop`锛屽苟绔嬪嵆鍥炲啓鍓嶇鐘舵€佷笌鏃ュ織銆?5. 鎵ц鍙楅樆鍙鍖栵細鏃犳晥 `target_system` 鏄剧ず鍛婅骞剁鐢ㄢ€滃惎鍔ㄦ墽琛屸€濄€?
涓嬩竴姝ワ紙鎸変紭鍏堢骇鎺ㄨ繘锛夛細
1. P1锛氫换鍔″垪琛ㄨˉ鍏呭け璐ュ師鍥犵瓫閫変笌鐘舵€佺粺璁°€?2. P1锛氭姤鍛婇〉澧炲姞 `chart_data` 鍥捐〃瑙嗗浘銆?3. P2锛氫骇鐗╄鍥惧鍔犲垎缁勩€佹绱笌蹇€熼瑙堛€?4. P2锛氭墽琛屾€佸紓甯告彁绀轰粠鈥滈潤榛樺け璐モ€濆崌绾т负鈥滃彲瑙佷絾涓嶆墦鏂€濄€?
## 9. 寤舵湡浜嬮」锛堝凡纭锛?1. 璇︽儏椤垫枃鏈唴瀹圭粺涓€鍙岃鍥撅細`闃呰瑙嗗浘` + `婧愮爜瑙嗗浘`銆?2. 娑夊強 `***`銆丮arkdown銆丏SL銆丗eature銆丣SON 鐨勫唴瀹癸紝鍦ㄦ簮鐮佽鍥句腑缁熶竴鎸変唬鐮佸潡椋庢牸娓叉煋锛坄pre/code`锛夛紝閬垮厤琚綋鏅€氭枃鏈墦鏁ｃ€?3. 閫傜敤鑼冨洿锛氳В鏋愩€佸満鏅€丏SL / Feature銆佹绱笂涓嬫枃銆佹姤鍛婂師濮嬫暟鎹瓑璇︽儏椤靛唴瀹瑰潡銆?4. 褰撳墠缁撹锛氬厛淇濈暀鐜版湁瀹炵幇锛屽悗缁崟鐙帓鏈熷鐞嗭紝涓嶅奖鍝嶅綋鍓嶈凯浠ｄ氦浠樸€?
## 10. 浠〃鐩樻帴鍙ｈ瘎浼帮紙2026-04-02锛?缁撹锛氬綋鍓嶅悗绔帴鍙ｅ彲鏀拺鈥淢eterSphere 椋庢牸鈥濅华琛ㄧ洏鏀归€狅紝鏃犻渶鏂板鎺ュ彛鍗冲彲鍒嗛樁娈佃惤鍦般€?
宸叉牳鏌ュ彲鐢ㄦ帴鍙ｏ細
1. `GET /api/tasks`锛氬叏灞€浠诲姟鍒楄〃銆佺姸鎬佸垎甯冦€佸緟澶勭悊娓呭崟銆佹渶杩戜换鍔°€?2. `GET /api/history/tasks`锛氭寜鏃堕棿/鐘舵€?鍏抽敭瀛楃瓫閫変换鍔″巻鍙诧紝鍙仛鏃堕棿绐楀彛缁熻銆?3. `GET /api/history/executions`锛氭墽琛屽巻鍙诧紙鍚?`executed_at/status/environment/analysis_summary`锛夛紝鍙仛瓒嬪娍涓庨闄╃湅鏉裤€?4. `GET /api/tasks/{task_id}/analysis-report`锛氬崟浠诲姟娣卞害鎸囨爣涓?`chart_data`銆?5. `GET /api/tasks/{task_id}/dashboard`锛氬崟浠诲姟鑱氬悎瑙嗗浘锛堟姤鍛婃憳瑕併€佸け璐ュ垎绫汇€佸浘琛ㄦ暟鎹級銆?
寤鸿鎺ュ叆椤哄簭锛?1. Phase 1锛堝凡鍙惤鍦帮級锛氫粎鍩轰簬 `GET /api/tasks` 瀹屾垚 KPI銆佺姸鎬佸垎甯冦€佸緟澶勭悊娓呭崟銆佸け璐ュ揩閫熷叆鍙ｃ€?2. Phase 2锛堝凡钀藉湴锛夛細鎺ュ叆 `GET /api/history/executions`锛屽凡瀹炵幇杩?7/30 澶╄秼鍔裤€佸け璐ュ師鍥?Top銆佺幆澧冪ǔ瀹氭€ц瀵熴€?3. Phase 3锛堝凡钀藉湴锛夛細鍦ㄤ换鍔¤鎯呴〉涓庝华琛ㄧ洏鑱斿姩涓娇鐢?`analysis-report/dashboard` 鍋氬崟浠诲姟閽诲彇銆?
娉ㄦ剰浜嬮」锛?1. `POST /execute` 褰撳墠涓哄悓姝ラ樆濉烇紝浠〃鐩樿疆璇笌瀹炴椂鎬т互鍘嗗彶鎺ュ彛鍒锋柊鑺傚涓哄噯銆?2. 鍘嗗彶绫绘帴鍙ｆ暟鎹潵鑷湰鍦?JSON 鎸佷箙鍖栵紙`api_artifacts`锛夛紝鐢熶骇鍖栧墠闇€鍏虫敞鏁版嵁閲忓闀夸笅鐨勬煡璇㈡€ц兘銆?
## 11. 鍚庣画澧炲己娓呭崟锛堜粎鍩轰簬鐜版湁鍚庣鎺ュ彛锛?鐩爣锛氱户缁悜 MeterSphere 椋庢牸闈犳嫝锛屼絾涓嶅鍔犲悗绔柊鎺ュ彛锛屼紭鍏堝仛鍓嶇缂栨帓涓庝氦浜掍紭鍖栥€?
P1锛堝缓璁紭鍏堬級锛?1. 鎴戠殑寰呭姙瑙嗗浘锛?- 鑳藉姏锛氬け璐ヤ换鍔°€佹墽琛屼腑浠诲姟銆佸緟鎺ㄨ繘浠诲姟鍒嗙粍灞曠ず锛屽苟缁欏嚭鈥滃缓璁姩浣溾€濄€?- 鎺ュ彛锛歚GET /api/tasks`銆?- 璇存槑锛氬綋鍓嶆棤鈥滃綋鍓嶇敤鎴封€濆瓧娈碉紝鍏堜互鈥滅姸鎬?鏃堕棿鈥濅綔涓哄緟鍔炴帓搴忎緷鎹€?- 褰撳墠杩涘睍锛氬凡钀藉湴寰呭姙鍒嗙粍鍒囨崲锛堝叏閮?澶辫触浼樺厛/鎵ц涓?寰呮帹杩涳級銆?
2. 鏃堕棿绐楀彛缁熶竴绛涢€夛紙杩?7/30 澶┿€佽嚜瀹氫箟鑼冨洿锛夛細
- 鑳藉姏锛氫华琛ㄧ洏鎵€鏈夌粺璁″崱鐗囦笌瓒嬪娍鍥剧粺涓€浣跨敤鍚屼竴鏃堕棿杩囨护銆?- 鎺ュ彛锛歚GET /api/history/tasks`銆乣GET /api/history/executions`锛坄start_time/end_time`锛夈€?- 璇存槑锛氬噺灏戔€滃崱鐗囦笌鍥捐〃鍙ｅ緞涓嶄竴鑷粹€濈殑鐞嗚В鎴愭湰銆?- 褰撳墠杩涘睍锛氬凡钀藉湴椤堕儴缁熶竴鏃堕棿绛涢€夛紝骞剁粺涓€ KPI/瓒嬪娍/椋庨櫓/鍔ㄦ€佸彛寰勩€?
3. 澶辫触浠诲姟蹇€熸帓鏌ュ叆鍙ｏ細
- 鑳藉姏锛氬け璐ュ師鍥?Top銆佺幆澧冪ǔ瀹氭€с€佽秼鍔挎潯鍧囧彲涓€閿烦杞换鍔¤鎯呮姤鍛婇〉銆?- 鎺ュ彛锛歚GET /api/history/executions` + `GET /api/tasks/{task_id}/dashboard`銆?- 璇存槑锛氬凡鍏峰鍩虹鑱斿姩锛屽悗缁ˉ鍏呴珮浜潵婧愪笌鍥炶烦璺緞銆?
P2锛堝彲骞惰鎺ㄨ繘锛夛細
1. 鎴戝垱寤虹殑浠诲姟瑙嗗浘锛堣繎浼肩増锛夛細
- 鑳藉姏锛氭彁渚涒€滄垜鍒涘缓鐨勨€濆叆鍙ｄ笌绛涢€夐潰鏉裤€?- 鎺ュ彛锛歚GET /api/history/tasks`銆乣GET /api/tasks`锛坄keyword/status/environment/time`锛夈€?- 璇存槑锛氬悗绔殏鏃?owner 瀛楁锛屽厛鐢ㄢ€滃悕绉扮害瀹?鍏抽敭瀛楄鍒欌€濅綔涓轰复鏃剁瓥鐣ワ紱鍚庣画鑻ュ悗绔ˉ owner 鍐嶅垏鎹㈢簿纭繃婊ゃ€?
2. 鍗曚换鍔℃姤鍛婃憳瑕佸寮猴細
- 鑳藉姏锛氳鎯呴〉鎶ュ憡鍖哄睍绀?`task_summary_text/failure_reasons/findings` 鐨勭粨鏋勫寲鍗＄墖锛屼笉鍙樉绀哄師濮?JSON銆?- 鎺ュ彛锛歚GET /api/tasks/{task_id}/dashboard`銆?- 璇存槑锛氭彁楂樷€滄姤鍛婂彲璇绘€р€濓紝闄嶄綆鏌ョ湅鍘熷鏁版嵁棰戠巼銆?
3. 鍘嗗彶鎵ц鍋ュ悍鐪嬫澘锛?- 鑳藉姏锛氭寜鐜銆佺姸鎬併€佸け璐ユ瘮渚嬭緭鍑衡€滃仴搴峰垎灞傗€濓紙绋冲畾/棰勮/楂橀闄╋級銆?- 鎺ュ彛锛歚GET /api/history/executions`銆?- 璇存槑锛氫粎鍋氬墠绔仛鍚堣绠楋紝涓嶆敼鍚庣鏁版嵁缁撴瀯銆?
P3锛堝悗缁級
1. 缂洪櫡闂幆鐪嬫澘锛堝墠绔崰浣嶇増锛夛細
- 鑳藉姏锛氬湪澶辫触浠诲姟鍗＄墖涓鐣欌€滄彁浜ょ己闄?鏌ョ湅缂洪櫡鈥濆叆鍙ｅ尯鍩熴€?- 鎺ュ彛锛氬綋鍓嶄粎鍙敤浠诲姟/鎵ц鍘嗗彶鎺ュ彛鍋氬崰浣嶇粺璁°€?- 璇存槑锛氱湡瀹炵己闄锋祦杞渶瑕佸悗绔己闄峰煙鎺ュ彛锛岀幇闃舵浠呭仛 UI 鐣欏彛涓庝氦浜掑崰浣嶃€?


## 12. 基于后端现状的前端实现建议（2026-04-03）

### 12.1 接口能力边界（必须遵守）
- 历史接口分页上限：`/api/history/tasks` 与 `/api/history/executions` 的 `page_size` 最大为 `200`。
  - 建议统一常量：`HISTORY_PAGE_SIZE_MAX = 200`。
  - 默认建议：任务历史 `100`，执行历史 `100~200`，避免 422。
- 回归对比接口：`/api/tasks/{task_id}/regression-diff` 当前后端未上线。
  - 前端策略：保留入口但默认显示“暂不可用（接口未上线）”，避免连续重试刷日志。
- 实时执行流：`/api/tasks/{task_id}/execution/stream` 可用，但应保留轮询降级。
  - SSE 失败时回退至 `execution` 轮询（2~3s）。

### 12.2 执行态 UI 建议（与当前后端模型对齐）
- 启动执行后立即进入 optimistic `running`，直到 `execution` 拉取到最终状态。
- “停止执行”按钮仅在 `running` 可点击，其他状态置灰并给出原因提示。
- 详情页所有执行相关卡片使用同一状态源，避免“状态卡保留上一次值”的错位。
- 解析与执行阶段开启静默自动刷新（标签页内容联动更新），避免依赖手动刷新。

### 12.3 Dashboard / TaskList / History 分工建议
- Dashboard：看趋势与风险（时间窗统一、失败 Top、环境稳定性、待办分组）。
- TaskList：看当前与操作（筛选、快速跳转、运行中优先）。
- TaskHistory：看复盘与检索（时间范围、环境、状态、关键词）。
- 三页统一：筛选参数 URL 同步、统一状态字典、统一时间口径。

### 12.4 前后端联调清单（建议纳入回归）
- 历史接口：`page_size` 边界（200/201）与时间格式校验。
- 任务详情：`preflight-check`、`execution/explanations`、`execution/stream`、`execution/stop`。
- 回归对比：接口未上线时的空态与提示一致性。
- 失败链路：404/422/500 文案统一与操作建议一致。

### 12.5 后续开发建议（按投入产出）
- P0：先做“体验稳定”而非“功能扩张”
  - 消除 422/404 噪音请求。
  - 收敛状态源，避免执行态显示不一致。
  - 完善空态、降级态、错误态。
- P1：增强可视化深度
  - 在现有接口基础上增加趋势图、漏斗图、环境健康分层。
  - 强化 Dashboard 到详情页的钻取与回跳。
- P2：等待后端补齐后再接入
  - 回归对比详情、执行队列视图、任务级实时进度分段。
