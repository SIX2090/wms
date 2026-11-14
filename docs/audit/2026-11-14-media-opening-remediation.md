# 2026-11-14 第二批：媒体权限与期初归属整改

当前状态：首次代码目标 d2264350c885c317d630e461b4bbeed899474f7f 的 WMS CI 未通过，已按 R8 整批本地回退到 4bd8f06e8c4f2a7ea1a7e558a5e00ba7a0c6f2a2（树等同原 e854cc76），纠正版本 2026.11.59 尚待最终统一回归、推送及精确新目标 CI。此前局部通过仅作历史证据，不代表交付成功。生产未操作，生效确认：待人工确认。

## 基线与范围

共享 C:/wms 的 main 基线 e854cc76667017bbedfbb4fb5bf2753a91d9699b；已核实远端同 SHA、索引为空，保留 2 个既有删除与 2 个未跟踪文件。改动先在本次新建的私有 source 中验证，未把历史 nonce/回执当作新隔离证明。

本批覆盖 C1、D1、D2；指定 Windows 2026.11.57 制品来源/哈希核验；其他方言支持范围核查。新 BUG 编号 0，旧根因续修 2 组（媒体授权、期初归属），ASR 为已批准的政策变化，不把原所有登录可用自动定为历史漏洞。测试夹具、文档与验收缺口另列，不以测试数等同 BUG 数。

## 已明确的业务规则

- 独立识物、ASR：管理员、仓管、采购、销售、生产；服从 AI 总开关、既有灰度及主体限流。拒绝不调用提供方。
- OCR 两入口：保留既有管理员、仓管、采购，更窄的业务角色装饰器继续生效。
- 无单据号期初：唯一行保留原单据归属，多行提示明确单据；新行及 NULL 行兼容归入 QSLEGACY。跨单同物料合法，不能合并/猜测/转移归属。

## 全系统同根消费点矩阵

| 根因/检索 | 消费点 | 现有保护/处理 | 验证 |
|---|---|---|---|
| _ai_call_llm_vision / recognize_material | H5、Android 共用 mobile_recognize_material | 补实际主体能力/总开关/灰度；保留候选人工确认、配置检查及 5/60s 限流 | 五允许角色、两拒绝角色、会话/Bearer/双身份、CSRF、灰度名单、配置变化、异常/重试 |
| sentence_recognition / _asr_call_tokenhub | mobile_asr 的腾讯与 TokenHub 分支；语音导航客户端 | 批准的同五角色及总开关/灰度，保留原调用频率；只返回文字 | 两提供方模拟、非法/空上传、失败重试、403/429、实际主体审计、零库存动作 |
| _ai_call_llm_vision / call_with_evidence | api_document_ocr、ai_excel.api_document_ocr_excel | 原角色保留，补共享能力/开关/灰度；每次尝试和回退检查 | 关闭全局/灰度、会话/Bearer；首次失败后关开关禁止再次提供方调用 |
| AI chat/stream、文档重试 | chat/stream 原有 AI 角色/运行上下文；job_retry 原登录+归属后直调 LLM | chat/stream 保留原保护；job_retry 补 document_retry 五个既有 AI 角色/总开关/灰度和逐次调用审计，保留任务归属/人工确认 | 真实会话/CSRF、七角色、灰度/开关、本人/他人任务；既有 AI 契约及目标 AI Verification |
| (material_id,warehouse_id).first / doc_id assignment | native_api_opening_stock_submit、batch_save 旧分支 | 共享解析，SQLite 先取真实写栅栏；最多两行判断歧义，懒建兼容单；原事务/幂等保留 | 唯一/多行/NULL、两仓、库位开关、请求回放、失败回滚、独立连接竞争 |
| _apply_opening_stock_balance | 直接编辑、明确 doc_id 保存/导入、原生行编辑 | 中央拒绝已有非 NULL 归属转移；显式单据调用方已按 doc_id 定位 | 原有库存/库位/流水、导入/删除/回冲及历史金额相邻回归 |
| opening_stock/add | 历史单行新增 | 已存在即拒绝，不会取首行更新或移属，保留既定兼容行为 | 既有新增/库位回归 |
| 网页/Android/脚本、打印/报表 | 识物/语音请求、期初归属与合计消费 | 没有新增第二套接口、库存余额或自动提交动作；打印报表依赖真实归属，跨单按 SUM 汇总不改 | 后端专项与相邻回归；真机未执行，不冒充验证 |

## 本机隔离及测试证据

运行者为本次 fresh LPAC，不在宿主 C:/wms 导入/测试应用。解释器私有副本，源码只读，写入仅本次 profile；证明先于应用导入，内存库固定。文件/ALL APPLICATION PACKAGES 合成哨兵、WFP IPv4/IPv6 阻断、Job 子进程、父状态不可写均通过；每轮结束核实零存活子进程、移除本轮 WFP 和 profile。合成文件库只在已验证 profile 下独占新建并更换测试 engine，结束恢复内存 engine；不读取生产或历史文件库。

主证据目录（本机，不提交临时日志）：C:/Users/Administrator/Documents/Codex/2026-11-09/new-chat/audit_phase2_20261114。完整非空 manifest、冻结哈希和 parent-only completion receipts 在该目录及其记录的本次 supervisor state；实际 run_id 与最终结果在下方收口。初始 14 个资源/夹具失败已分开处理：补齐确切 Git 跟踪 Kotlin 资产、清理旧识物全局函数污染，不能把它们算成产品复现。

旧业务基线 20 文件 363 passed、2 subtests；新回归旧业务 72 failed/8 passed，涵盖未授权/开关关闭仍调用、审计缺失、归属转移、多行选择及 helper 未拒绝。候选曾发现新审计来源枚举错误（改回既有 api），日期对象兼容与旧 ASR 限流夹具污染均已修正，不弱化原断言。最终清单及回退以实际收口为准，不累加重叠轮次。

## Windows 2026.11.57 指定制品

- Release: https://github.com/SIX2090/wms/releases/tag/windows-v2026.11.57 ，Release ID 445215880；source_sha 6736c335266e80d20c4c33d7426738e461e372b6，已核对当前发布元数据及构建 [43585589915](https://github.com/SIX2090/wms/actions/runs/43585589915) 为同 SHA completed/success。
- ZIP 97,298,622 字节，SHA256 ed443a52c5c08080fa2d00ce3fe6daf6d438d9ad999380d863cb221a78d00fcc。
- release.json 533 字节，SHA256 0936e1d9d63ae4678dcfe75464c235c768d8e527b19bf8cd6f1a8a1ddb352ba9；runtime.json 374 字节，SHA256 a816101a3adf02dd4025ef42289f317e9ed983957170775bcb9bd050198f7578；zip.sha256 98 字节，SHA256 28dada09f8e5e6a2b134149cfbb61005fadff058440513d8d7d7ab8c17274d02。四附件实际下载大小与摘要全部匹配；HTTPS、目标域和每次重定向先核验，不使用凭据。
- 归档 11,541 项，总展开 272,600,786 字节；无绝对/穿越/链接成员，无 .db/.sqlite/事务旁文件或 .env；仅静态读取代码/清单，未安装或执行。
- 发布 runtime receipt 的 artifact_id=41a1bc4816e7d1a2a99c93f585fc9bb67353764a47db438832780250c26eeb7a 与 release.json 绑定一致，原 CI 记 dependencies/manifest/imports/fresh_initialization/existing_database_preserved/guarded_startup/chinese_login/footer_css 成功。此为发行 CI 的既有证据，不是本批新 LPAC 运行验收。
- **本批包运行未执行**：当前能力绑定的是私有解释器、source 与导入前内存目标；发行初始化器/嵌入式解释器/文件库不能继承该证明。既有 check_portable_runtime 直接启动进程并继承宽环境、端口先释放后绑定、HTTP 缺少本批 PID/nonce 校验，不能在本任务边界下直接使用。不放宽 LPAC/WFP/文件证明来运行；首启、健康、关键查询、草稿保存/读取、关闭重开一致性与异常退出均待独立合规 package runner 验收。

## 其他数据库方言

README 明确默认 SQLite；app/config.py 接受 SQLAlchemy DATABASE_URL，app/requirements.txt 存在 PyMySQL；环境兼容说明提供 MySQL 配置示例，旧迁移也有 MySQL/PG 分支。因此仅能确认“有配置/部分代码路径”，未发现本批 CI 提供全方言业务并发验收；不能把驱动或 SQL 编译当实际支持证明，也未读取生产连接串猜部署类型。

本批隔离器仅支持合成内存 SQLite 和 profile 内新建 SQLite 文件，不支持启动/授权新合成 MySQL/PostgreSQL 服务。该两平台**未验收**，不擅自禁用，不宣称所有方言并发安全。需独立合成实例后验证：共享来源跨销售退货单竞争、完成/编辑/反提交、同键/不同键竞争、幂等响应丢失、失败回滚；期初多单/单仓竞争与 NULL/新行/明确单据同时写；断言来源总量、行归属、三账和回执。只锁当前退货单不足以证明共享来源安全。

## 回退、交付及生产

整批逆序回退仅在本任务私有 source 进行：撤回全部产品/规则/版本/文档/夹具改动至准确基线，保留相同新回归锁，证明旧行为失败；再恢复候选并校验逐文件哈希，最后统一回归。未在共享目录做破坏性回退，也不涉及任何数据库恢复。

提交/推送和精确目标 CI：待本批最终验收后补录实际 SHA、push 输出与运行链接；不把当前候选测试当交付完成。生产未部署、未重启、未迁移；没有真实模型、语音、设备或生产操作验收，生效确认：待人工确认。Windows .57 制品运行及其他方言验收缺口保留，不用一次 CI 宣称整个 WMS 已无 BUG。

## 冻结前验证补充

58 文件统一预检为 920 passed、21 failed、8 subtests；21 项均属于 test_opening_stock_global_import_runtime.py 的 Windows WinError 206（命令行携带大段源码/夹具超长），不是业务断言失败。测试入口改从标准输入传 JSON，不删任何 JS 断言，不绕过 Node、LPAC 或 Job。随后 5 文件包含该 21 项、新媒体/期初/并发/注册契约合计 136 passed（run wms.synthetic.a9ac3d788eb44257a17393b90ae0e4bf）。候选由 25 扩至 26 文件，将重新冻结并执行整批逆序回退和最终统一回归，不把此前 920 项直接冒充最终通过。

独立权限矩阵已补三个能力的真实期望（五角色媒体、三角色 OCR），保留未知能力拒绝及全部旧能力断言；注册合规为 30 项工具。探索性调用完整 verify_wms_bugs 子进程链时，prelaunch 子进程因没有绑定自己 PID 的独立能力而阻断，未借用父证明；直接 prelaunch 在 Windows LPAC 的 BACKUP-READY 断言亦未通过，未修改其断言/生产备份逻辑。本批不把该探索结果记作通过；完整链以精确目标 CI 为准，独立媒体/期初实际路由及所列相邻测试继续验证。

指定 .57 制品内嵌 wms-release.json 的 source_sha/artifact_id 与 Release sidecar/CI 一致，列出的 7,385 个文件大小和 SHA256 全部匹配；版本、配置、run_server 和初始化器与 6736c335 的对应 Git blob 字节相同，离线启动 bat 经构建脚本明示的 CRLF 归一化后相同。这仍是静态核验，没有执行包内程序。

最终统一测试文件清单（显式 65 项；执行参数由本机隔离器固定，不使用 --noconftest）：

```json
[
  "tests/verify_mobile_recognize_material_api.py",
  "tests/verify_mobile_asr_route.py",
  "tests/verify_tencent_asr_helper.py",
  "tests/verify_mobile_opening_stock_api.py",
  "tests/test_f3_14_vision_throttle.py",
  "tests/test_feature_2026_10_08_asr_tokenhub_fallback.py",
  "tests/test_bug_2026_09_07_002_voice_asr_domain_correction.py",
  "tests/test_bug_2026_08_16_013_ai_role_gate.py",
  "tests/test_opening_stock_multi_doc.py",
  "tests/test_opening_line_revision.py",
  "tests/test_opening_reference_ownership_runtime_20261113.py",
  "tests/test_opening_recorded_quantity_runtime_20261113.py",
  "tests/test_opening_money_routes_20261109.py",
  "tests/test_opening_preserve_historical_amount_20261109.py",
  "tests/test_opening_rebuild_transaction_20261109.py",
  "tests/test_opening_stock_mobile_list_edit.py",
  "tests/test_opening_stock_import.py",
  "tests/test_opening_stock_batch_delete_lines.py",
  "tests/test_opening_stock_progress.py",
  "tests/test_p1_7_opening_stock_balance_converged.py",
  "tests/test_mobile_ai_media_policy_20261114.py",
  "tests/test_opening_legacy_ownership_20261114.py",
  "tests/test_native_request_atomicity.py",
  "tests/test_native_atomic_receipts_20261109.py",
  "tests/test_ai_tool_input_issue6.py",
  "tests/test_ai_tool_call_p2_001.py",
  "tests/test_ai_llm_gate_removal.py",
  "tests/test_bug_2026_08_16_002_opening_stock_location_inventory.py",
  "tests/test_p1_7_material_opening_converged.py",
  "tests/test_opening_amount_synthetic_memory_20261109.py",
  "tests/test_opening_fixture_ledger_source_20261113.py",
  "tests/test_opening_historical_display_20261109.py",
  "tests/test_opening_import_numbers_20261109.py",
  "tests/test_opening_legacy_concurrent_20261114.py",
  "tests/test_opening_money_alignment_20261109.py",
  "tests/test_opening_recorded_quantity_source_20261113.py",
  "tests/test_opening_reference_ownership_source_20261113.py",
  "tests/test_opening_stock_delete_all.py",
  "tests/test_opening_stock_delete_row_persist.py",
  "tests/test_opening_stock_doc_list.py",
  "tests/test_opening_stock_doc_navigation.py",
  "tests/test_opening_stock_doc_no.py",
  "tests/test_opening_stock_doc_number_migration_20261109.py",
  "tests/test_opening_stock_entry_draft.py",
  "tests/test_opening_stock_export_csv.py",
  "tests/test_opening_stock_global_import_runtime.py",
  "tests/test_opening_stock_import_dry_run.py",
  "tests/test_opening_stock_location_column.py",
  "tests/test_opening_stock_material_lookup_runtime.py",
  "tests/test_opening_stock_material_search.py",
  "tests/test_opening_stock_migration.py",
  "tests/test_opening_stock_navigation_runtime.py",
  "tests/test_phase2_media_contracts_20261114.py",
  "tests/test_native_request_concurrent.py",
  "tests/test_inventory_truth_line_refs.py",
  "tests/test_f4_4_ledger_split.py",
  "tests/test_ai_replay_permissions.py",
  "tests/test_native_ai_replay_permissions.py",
  "tests/test_audit_20261020_remaining.py",
  "tests/test_bug_2026_08_27_005_stock_txn_warehouse_id.py",
  "tests/test_p1_7_convergence_guards.py",
  "tests/verify_app_py_split_batch_import.py",
  "tests/test_browser_audit_35_ocr_contract.py",
  "tests/test_browser_audit_36_ocr_numeric.py",
  "tests/test_browser_audit_37_ocr_mixed_packaging.py"
]
```

## 最后消费点收敛与追加验证

26 文件冻结候选经完整逆序回退（2,598 个基线文件逐个哈希一致）、同锁旧版 100 failed/15 passed、候选逐文件恢复后，58 文件统一回归 941 passed、8 subtests，run wms.synthetic.833d8dbe456945819c84ba97a2e9e000。随后最终扫描发现文档任务重试的付费调用遗漏，按既有 AI_USE_ROLES 规则纳入同一子修复，注册总数变为 31，未扩大 OCR 两接口原角色范围。追加后媒体/注册/库存文档锚点 3 文件 136 passed（run wms.synthetic.9c62e44eca464980b7a6bdef760f191b），含七角色、总开关/灰度和任务归属、原 vision 关闭 400。

扫描底层期初 helper 的全部测试消费者后，再纳入 4 个既有相邻文件，最终统一清单为 62 项。因本批范围追加，将再次冻结完整候选、整批逆序回退/恢复，并做最终统一回归，先前 941 不冒充追加后的验收。

预检 BACKUP-READY 在准确旧基线（run wms.synthetic.d2ea79c9871b47c19e515de991510673）与候选均相同断言失败，证明不是本批新增；未改断言或放宽隔离，Windows LPAC 的该独立预检不计通过。其完整工作流仍须验收本批精确目标 CI。

## 首轮本地证据（对应失败目标 d2264350，不代表交付）

最终业务候选 27 文件已整批逆序撤回并验证 2,598 原文件一致；同一新锁在旧版 111 failed/25 passed（run wms.synthetic.032ff976b5f74de6ab480083eb34a2c1），候选 27 文件恢复逐个哈希一致。62 个明确文件统一回归 **1,055 passed、8 subtests passed、57 warnings，505.94 秒**，run wms.synthetic.5f50858a150f469e8fe8d305692d55b1。

收口补齐 verify_ai_tool_schemas 的四项新能力有效样本（均为无自主 JSON handler 的空对象 schema），保留全旧样本、必填/空明细/未知字段等全部旧断言；追加在 tests/test_phase2_media_contracts_20261114.py 直接执行原 main 的覆盖锁，防止只检查角色注册而遗漏输入样本。变更仅该脚本、对应测试及本记录，所有 app/ 业务代码逐文件与上述 1,055 项冻结源完全一致。按实际失效范围重跑注册/输入/调用/角色 4 文件 **121 passed，24.90 秒**，run wms.synthetic.290f4f58805c44389f86b31332e29a4d；不与 1,055 相加，因文件有交集。最后再次冻结整批 28 文件，逆序回退/恢复及恢复后受影响锁另记实际回执；既有库存/期初全模块结果按未变业务哈希保留，精确目标 CI 仍完整验收全站。

## R8：首次 CI 失败及整批纠正

首次普通提交/推送 d2264350c885c317d630e461b4bbeed899474f7f，版本.58，28文件。实际push为 e854cc76..d2264350 main -> main，本地/远端一致。AI43601430083与静态、verify四片、smoke、browser及性能成功；[WMS CI43601430098](https://github.com/SIX2090/wms/actions/runs/43601430098)的3个unit失败：15/20/12，共47失败、16623通过、203跳过、1636子测试通过。失败集中在原有QA35/36/37 OCR数值/混合包装/事务契约。不能把局部绿或本机1055项当整批成功。

根因是本批共享门禁在提供方前新增 OperationLog 并 commit()，会把调用方已暂存的 OCR 任务一并提交；失败后rollback无法撤回，另有额外operation_log行违反原受控OCR契约。已在fresh LPAC准确复现47 failed/23 passed（wms.synthetic.90981bf71c434ae69aa03d498c807073）。

按R8在共享main用普通git revert完整撤回本批28文件，生成4bd8f06e8c4f2a7ea1a7e558a5e00ba7a0c6f2a2；git diff e854cc76 HEAD为空，原2删除/2未跟踪保留。未强推或覆盖别人的内容，回退提交不单独推送旧发行号，待验证纠正后一起普通推送。

纠正：调用尝试只通过现有运行日志写user_id/role/capability及结构化同名字段，不写业务数据库、不commit调用方；拒绝先rollback待办业务，再单独写AIRolloutAudit，防止晚期权限/开关变化时提交半成品。失败仍不调用提供方。原有tests/test_browser_audit_35_ocr_contract.py、36_ocr_numeric.py、37_ocr_mixed_packaging.py完整保留，没有放宽快照、允许额外表或删除回滚断言。修正本批自行新增的审计用例，使其验证实际主体运行日志及业务库无额外行；这是纠正错误的审计存储假设，权限和实际主体断言保留。

纠正首轮7文件208 passed（wms.synthetic.daa59502e8904ca992e87ef8d0e3aee1），包含原70项OCR用例及本批新锁。继续加入真实拒绝请求清理已暂存任务的回归。最后清单扩大到65文件；28文件候选将重新冻结、逆序回退、恢复并统一验收。版本递增.59以满足对远端.58基线的普通发行门禁，不沿用任何历史一次性跳钩授权。代码CI与生产生效分别待验，生产未部署/重启/迁移。

纠正后补真实拒绝请求清理暂存业务的用例，连同原三个完整OCR模块共4文件183 passed，35.31秒，run wms.synthetic.e7cc520530ab4ec58fcea6d8b977d735；原业务快照/不允许额外表/失败无部分任务均保留。后续以.59冻结候选的统一65文件和精确新SHA CI为准。

授权范围复核：用户对独立ASR明确选择的是五个既有AI角色、总开关和灰度，未决定新增操作额度；因此撤回首轮附加的ASR 5次/分钟限制，保留原调用频率。相应三个语音旧测试文件恢复准确基线，不为额外限额改夹具；本批新测试同时验证识物原429与语音原可连续调用，全部旧断言保留。冻结文件范围相应减少，后续以实际候选清单为准。

最终授权范围收敛后，原三模块OCR及媒体门禁、三个原语音模块共7文件208 passed（44.19秒，wms.synthetic.b56b5c6d3a5e44ac994660648e70fe67）。语音原文件逐字节未改；所有提供方仅模拟。接下来以25文件.59候选的整批回退/恢复及65文件统一回归为最终本地证据。
