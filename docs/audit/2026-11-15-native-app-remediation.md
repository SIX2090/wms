# 原生 Android 审计 A01–A12 修复交付记录（待最终收口稿）

任务：`AI-APP-AUDIT-FIX-20261115-001`。整理日期：2026-11-15。**本稿只汇总已实施变更及已归档证据；待补结果不可据此登记完成。**

审计报告使用 `023ac9e5` 及当时未提交内容。本轮对照实际实现、工作区和冻结清单推进；并行更新任务前移到 `84fac39015732d22e3e71cc77b0c071a621b7e04` 后，核对本轮产品文件无交叉覆盖。原审计19项探针断言缺陷现状，不计为修复通过。未纳入 R01–R04 独立开发，不新增审批、作废、账号权限、强制采购来源、更新安装或网络策略。

下文 `K/` 指 `app/android-native-wms/app/src/main/java/com/factory/wms/`，`T/` 指同工程 `app/src/test/java/com/factory/wms/`。原始证据根目录为用户本次审计目录同级 `native-wms-fix/`（下文 `F/`）。

## 逐项矩阵

| 项目 / BUG | 根因与修复位置 | 最终行为及同根因消费点 | 已有业务验证与当前状态 |
|---|---|---|---|
| A01 / BUG-2026-11-15-009 | `K/ui/viewmodel/scan/ScanViewModel.kt` 的 `materialExists`、`enrichScanLineMaterial`；`K/ui/viewmodel/opening/OpeningStockViewModel.kt` 的 `addLine`。精确失败后曾取模糊首项回填编码。 | 只接受相同编码的精确信息补全，补名称、规格、品牌时不修改已确认编码；非精确查找交候选选择。排查入库、出库、盘点、期初共用消费者，以及网页多候选/单候选分支。 | `ambiguousManualKeywordNeverChangesMaterialIdentity` 旧版明确把 Bolt 改成 M001，修复冻结版通过；`exactMaterialEnrichmentPreservesConfirmedIdentity` 为正常精确补全对照。冻结484项全量已过；最新追加边界的最终全量/目标CI待补。 |
| A02 / BUG-2026-11-15-010 | `K/ui/viewmodel/report/{StockDailyReportViewModel,InOutDetailReportViewModel,StockLedgerReportViewModel}.kt`、`opening/OpeningStockViewModel.kt`、`scan/ScanViewModel.kt`、`list/OrderListViewModel.kt`、`stocktake/StocktakeRecordViewModel.kt`、`archive/MaterialArchiveViewModel.kt`。异步回调曾缺上下文世代保护。 | 每个查询捕获完整参数、请求版本和账号会话，取消/迟到成功/迟到失败不得更新新查询；跨查询清旧列表，不把旧页追加到新筛选。员工部门联动、盘点单选项、单据状态、记录详情和档案图片同根消费者一并处理。复核再补台账选料搜索：绑定关键字+仓库+账号，选择/清空/改词即取消；库存日报和出入库明细编辑关键词时复位旧加载/分页，不自动发新请求。 | 四个页面切仓回归、员工联动、盘点选项和旧状态失败隔离均有旧版明确业务断言失败，冻结版通过。追加 `NativeReportSearchContextTest` 一组旧红证据已归档 `followup-before-results.json`；最新修复版运行/最终全量/CI待补。 |
| A03 / BUG-2026-11-15-011 | `K/ui/viewmodel/scan/ScanViewModel.kt` 的 `maybeRestoreStocktakeDraft`、仓库/盘点单选择和持久化；`K/data/model/ScanRequests.kt` 的 `StocktakeDraft`。原先只恢复清单，默认仓/仓库异步先后可错挂。 | 原仓、原盘点单、区域、明细、原请求号作为一组恢复；停用或失效时保留内容并阻止改挂。待核实原请求可保留原上下文核实回执。恢复未成功读出原稿时禁止自动空保存；坏JSON不删除，须人工明确清空后才解除保护。 | 原仓恢复、停用原仓拒改挂、完成盘点单不误投等旧版断言失败，冻结版通过。一个“等不到原上下文”旧版超时不计明确红灯。追加坏稿保护用例旧版出现原始 `{broken-json` 被删成 null 的明确断言失败；修复版与入出库同根补测结果待补。 |
| A04 / BUG-2026-11-15-012 | `K/data/repository/WmsRepository.kt` 的 `logout`、草稿key；`K/ui/viewmodel/scan/ScanViewModel.kt` 的账号一致性及恢复保护。认证清理曾 `DataStore.clear()` 删除业务草稿。 | 只清认证元数据，保留按服务器/原账号隔离的草稿、待核实请求和原键；其他账号不能恢复/发送原账号记录。原401世代隔离、权限重新核对、离线队列归属保持。旧无归属盘点稿原文保留，仅提示人工核对，不猜账号自动恢复。入/出库坏稿也不能被默认空清单覆盖。 | `logoutPreservesOwnedEditDraft` 按真实持久化前后比较，旧版明确丢稿，冻结版通过；`NativePendingWriteRecoveryTest` 验证注销/换账号/原账号重新进入只列记录，不自动发送，核实时仍原键原报文。旧401与队列归属原回归保留。历史无归属盘点新增用例旧版明确失败；最新坏稿/清空及目标CI待补。 |
| A05 / BUG-2026-11-15-013 | `K/ui/navigation/NavGraph.kt`、`K/ui/screens/{AiScreens,ScanScreens}.kt`、`ScanViewModel` 区域状态。识物和原盘点目的地各建一个 owner-local ViewModel。 | 识物目的地绑定原盘点导航条目的 ViewModelStoreOwner，并以当前 NavBackStackEntry 作 `remember` 键；返回原清单可见识物明细，仓库、盘点单、区域和数量保持。加载/待核实时禁用识物添加。 | `T/NativeAuditNavigationRegressionTest.kt` 使用实际 `AppNavGraph`、Navigation Compose、实际“添加到盘点清单”按钮和返回导航，旧版返回后原清单为空，冻结修复版通过。不是只调 `addScanLine`。导航lint键问题已修，冻结版 lint 0 Error。设备相机仍待验。 |
| A06 / BUG-2026-11-15-014 | `K/data/repository/WmsRepository.kt` 的 `getMaterialInfo`；现有 `MaterialEntity/MaterialDao` 消费链。原Room缓存只以物料编码键控。 | 内部缓存key包含规范服务器、稳定用户ID、仓库和编码；离线仅能读取相同来源，返回展示恢复原编码并标注缓存时间。历史无归属行不冒充当前库存，原数据不删。无需Room schema/版本迁移，离线队列的身份、状态、原请求号不改。 | 跨仓、跨服务器/账号、旧无归属缓存回归在旧版明确串用，冻结版通过；同来源离线缓存正常返回为正向对照。整套 Room/队列原模块回归保留。未声称真机历史安装升级已经实测。 |
| A07 / BUG-2026-11-15-015 | `app/app.py` 的 `material_search_api`、`material_info_api`；复核补 `app/routes/mobile.py` 的物料查询消费者。显式仓库校验错误被忽略后回退全局 `material.stock`。 | 无效、停用、歧义仓库受控拒绝；有效仓仍按仓隔离。未传warehouse的合法元数据协议保持。R6追踪38个脚本/测试/模块路径/通用TARGETS消费者，修正历史002 T7和004 T5的旧“错误回退全局”协议断言；其余10项合法断言AST完全保留。 | 纠正后实际源码函数契约9/9通过；精确84fac旧源码4个业务断言失败+5个对照通过，0夹具初始化错误。历史T5/T7当前4/4通过、旧3失败+1既有受控拒绝对照。真实 Flask 多仓/无效/停用/歧义矩阵仅交已验证隔离目标CI；本机不绕过LPAC导入完整app。后端纠正批379ff0ec已push，完整CI已验收；详见后端批回执。 |
| A08 / BUG-2026-11-15-016 | `ScanViewModel.persistStocktakeDraftNow`、手工清空/最后一行移除/提交交接分支；`WmsRepository.saveStocktakeDraft`。旧实现不保存空状态，离线成功只清内存。 | 草稿保存串行读取最新状态；手工清空/删空删除对应持久草稿；确认队列可靠接收后清编辑版本，失败保留。恢复未读懂原稿时禁止自动写空；只有人工明确清空才解除。保留服务端同批已盘行保护。 | `emptyStocktakeDeletesPersistedDraft`、`queuedStocktakeClearsCorrespondingDraft` 旧版保留旧稿的明确断言失败，冻结版通过；等待真实存储完成后断言，早期夹具时序超时不计产品证据。507项执行中已确认坏稿自动保存、显式清空/取消、同账号key保护及同根入/出库坏稿均通过；完整lint及最终目标CI仍待收口。 |
| A09 / BUG-2026-11-15-017 | `K/data/repository/WmsRepository.kt` 的 `nativeWrite`、`PendingNativeWrite`；`K/ui/components/PendingNativeWriteStatus.kt`；盘点、期初新增/编辑、OCR、语音、AI消费者。旧人工重试在每次调用新建幂等键。复核发现聊天普通重建的随机 scope 仍会绕开记录。 | 发送前持久化原body和requestId，同一意图冻结；结果不明保留，人工核实只用原键/原body，并走服务端当前权限和原子回执；成功由消费方处理后才ack。普通聊天VM重建遇到其它scope未决记录拒发新HTTP并保留输入/附件，同VM原scope重试保持；仅明确清空会话允许新意图，旧请求不回写。 | 盘点、期初编辑、OCR旧版请求键不相同，修复冻结版通过；断开已处理响应后的期初重试为同键同报文、一次合成效果。`NativePendingWriteRecoveryTest` 七入口原body/原键、注销归属和人工核实通过冻结运行。`NativeAssistantRecreationTest` 4项：旧候选“重建发第二次HTTP”明确失败，其余3项控制通过；最新修复版与总量/目标CI待补。 |
| A10 / BUG-2026-11-15-018 | `ScanViewModel.submitInbound/submitOutbound` 成功及离线入队状态。上一单的evidence未重置，离线交接还可能保留旧打印目标。 | 在线成功或可靠入队后清照片；入队清旧打印目标，失败保留当前报文。仓库、往来单位等用户连续选择不擅自清除。既有打印提示关闭流程继续清理打印目标。 | 连续入库两次实际请求体验证第一单带照片、第二单不带，旧版失败、冻结版通过。连续出库新增两次真实preflight/submit请求体回归，旧版明确复用照片断言失败；新版已在507项中通过，最终目标CI仍待收口。离线/失败原回归和实物打印未执行须分别表述。 |
| A11 / BUG-2026-11-15-019 | `app/routes/native_api.py::native_api_warehouses`；`K/data/model/OpeningStockModels.kt::WarehouseDto`；扫码、期初、首页、报表、OCR和语音ViewModel。接口无明确默认标记，客户端取列表第一条。 | 服务端仅返回启用仓并显式bool `is_default`；客户端仅自动选唯一有效默认项，默认不在第一位也正确。无有效默认时保留未选仓，不发库存查询；已有草稿/人工选择保持原上下文。停用项不得成为新单默认仓。 | 默认在第二项、无默认不选仓回归旧版失败、冻结版通过。首页/每日报表旧测试夹具显式声明默认仓，并把无仓回退全局改为“不查询”的业务约束；原界面/数量断言保留。服务端协议已随纠正后端批push；Android客户端尚待后批目标CI，不能把A11整类写已交付。 |
| A12 / BUG-2026-11-15-020 | `AssistantChatViewModel.clearConversation/send`、`WmsRepository.safeCall`、`VoiceCommandViewModel`。仅清UI，旧响应仍回写会话/附件；仓库层可能吞取消。 | 清空取消作业并递增会话世代；发起/返回/错误处理均检查会话版本及账号generation；清空后立即新问属于新意图，旧成功、旧失败不能恢复消息、附件或conversationId。传播CancellationException，语音消费取消不再落入本地兜底动作。 | `clearConversationRejectsOldResponse`、`clearChatRejectsOldFailureAndAttachmentRestoration` 旧版明确失败、冻结版通过；重建追加套件的显式clear/附件/账号控制旧候选已通过，最新修复版及最终全量待补。 |

## 已归档验证账本

| 层级 | 实际已执行结果 | 原始证据 / 限制 |
|---|---|---|
| 修改前基线 | 原生451 tests，0 failures/errors/skips。 | `F/baseline-results.json`、`baseline-results/`；此数字不是最终候选总数。 |
| 原生整批旧版回归 | 31例：28个明确业务断言失败、1个原上下文未出现的等待超时、2个正向控制通过。 | `F/whole-batch-old-results.json`、`whole-batch-old-results/`；不把该等待超时或最初队列单例/异步等待夹具问题计为明确红灯。 |
| 冻结候选全量 | 484项单测全部通过，真实Kotlin编译成功；lint 0 Error / 5 Warning / 3 Info。 | `F/final-frozen-native.log` 以 BUILD SUCCESSFUL 结束；该冻结尚未含最后追加的所有聊天/查询/坏稿边界，不得冒充最新完整候选验收。 |
| 追加历史稿/出库红灯 | 历史无归属盘点不能分配当前账号、连续出库不能复用照片两项在旧实现明确失败。 | `F/legacy-outbound-old-results.json`；最新新版执行结果待补。 |
| 追加交叉复核红灯 | 聊天重建发第二HTTP；坏盘点原文被自动空保存删除；台账选料旧候选覆盖新候选/跨仓/旧会话；关键词编辑后分页/加载态等，已留旧版结果。 | `F/followup-before-results.json`；只引用其中明确业务断言失败，不能把反序列化异常/初始化失败算业务红灯。最新修复版运行由android_validation汇总。 |
| 后端实际函数契约 | 当前9/9；精确旧源码4失败/5对照；历史消费者当前4/4、旧3失败/1对照。 | `backend-independent-corrected-current.log`、`backend-independent-corrected-old-valid.log`、`backend-historical-corrected-current.log`、`backend-historical-corrected-old-valid.log`；完整应用仅在已证明隔离的CI跑。 |
| 历史消费者保真 | 合法多仓/无仓/全局元数据的10项原断言AST保持相同；38个调用/模块/通用测试消费者核查。 | `F/backend-r6-corrected-evidence.json`。不是把所有旧断言翻转。 |
| 整批可逆性 | 私有副本对43个本任务文件实际反向应用、恢复、再次反向，逐文件内容哈希精确核对；共享目录未回退其它任务。 | `F/whole-batch-rollback.json`。最新追加文件/修正的最终整批哈希、提交范围仍待最后冻结后补齐。 |
| 后端纠正批R8 | 第一批失败后按R8整批撤回11文件，树回到84fac；纠正后另有独立回退/恢复哈希。 | `F/backend-batch-rollback.json`、`backend-corrected-rollback.json`；失败首批不算交付。 |
| 规则/台账/静态邻域 | 已运行版本规则0违规、严格AI映射一致、67项受限源契约通过。 | `F/rules.log`、`ai-ledger.log`、`source-contracts-2.log`；本机源契约阻止完整app导入、文件数据库及真实外部I/O，不能代替Android运行或完整Flask应用测试。最新最终索引和台账仍待检查。 |
| 最新候选全量 | 最新冻结507项真实Android单测已核实0失败/0错误/0跳过，Kotlin编译成功；同轮lint 0 Error / 5 Warning / 3 Information，BUILD SUCCESSFUL。其后仅增强同一缓存用例的独立账号/服务器维度，精准1项也已通过；所有产品哈希与507冻结版完全相同，原测试版本单独保留。 | 聊天重建/报告选料/坏稿保护及关联回归正在验证。 |

## 提交、推送与目标CI

1. `829aeaa8f91d63d7902a4c913a34a629099cc378` 为首批后端推送，目标 [WMS CI 43709268235](https://github.com/SIX2090/wms/actions/runs/43709268235) 失败，不能登记交付。
2. `ec036f141d8cf6941589bba177614fcc24ca547f` 按R8整批回退11文件；完整Git树精确回到 `84fac39015732d22e3e71cc77b0c071a621b7e04`。不误撤其他任务。
3. 纠正后端批 `379ff0ec2aad2ca0ac48ce67cf3b94d5fe4a25a2` **已实际push**；证据 `F/backend-corrected-push.log`。本批是 A07 与 A11 的服务端协议部分，不能当Android客户端已交付。

| 精确目标 | 工作流 | 当前记录 | 链接/证明 |
|---|---|---|---|
| `379ff0ec2aad2ca0ac48ce67cf3b94d5fe4a25a2` | WMS CI | **运行中/待最终核实** | [43710500469](https://github.com/SIX2090/wms/actions/runs/43710500469) |
| 同上 | WMS AI Verification | **运行中/待最终核实** | [43710500481](https://github.com/SIX2090/wms/actions/runs/43710500481) |
| 同上 | Android APK Build | 目标因路径过滤无运行；只复用已证明成功祖先 | [祖先运行43706012293](https://github.com/SIX2090/wms/actions/runs/43706012293)，祖先 `84fac39015732d22e3e71cc77b0c071a621b7e04`；Android工程与workflow差异为空，祖先可达，223个Git对象齐全，见 `F/backend-corrected-android-reuse-proof.json`。目标有失败/进行中记录时不得借旧绿。 |
| **Android后批完整SHA待补** | WMS CI | 待推送/待验收 | **待补实际run链接** |
| 同上 | WMS AI Verification | 待推送/待验收 | **待补实际run链接** |
| 同上 | Android APK Build | 工程有改动，须该目标真实构建证据 | **待补实际run链接，不能复用后端批旧包** |

最后收口必须补：Android批自洽提交范围、实际push输出、完整40位SHA、远端main可达证明、上述三工作流同一精确SHA的最近运行结论。后续main推进不改变本批目标，不能拿最新main或别的旧绿替代。

## 真机与生产边界

- 未读取或修改生产数据库，未登录生产服务，未操作真实单据、账号密码、微信、实际打印、部署、服务重启或APK安装。
- 本地Android使用普通Application、真实ViewModel/Navigation/Retrofit/Room/DataStore及loopback合成HTTP；完整Flask应用须先证明运行环境及数据库隔离，不绕过LPAC/数据库保护。
- **未执行且仍待人工设备验收**：真实相机拍摄/取证、系统回收/杀进程后的真实设备恢复、真实网络下连续入出库和离线交接、历史安装环境升级、覆盖安装及界面可达性。不能用Robolectric或源码检查替代这些事实。
- 服务端A07及`is_default`协议需另行授权部署到已验收的干净目标后才对现网生效；部署前确认将加载文件与目标一致，不能将混有未验收工作区当绿SHA发布。App需用户安装对应已验收APK；本次不从代码修复授权推导安装/重启授权。
- 不能安全确认归属的历史无账号盘点稿保留原文，只提示人工核对；不猜账号、不冒充恢复成功。损坏草稿原文不自动覆写，明确清空才允许重新录入。

## 主代理最终替换清单

- [ ] Android最新完整源树、版本、提交范围及完整目标SHA。
- [ ] 最新全量测试/邻域/编译/lint的实际结果，含新增边界的旧红新绿，异常或夹具问题单列。
- [ ] 最新批完整反向应用/恢复哈希及失败后的整批纠正记录。
- [ ] 后端纠正批已实际push379ff0ec并验收；Android批的完整SHA、CI及远端可达性仍待补。
- [ ] 12类最终状态逐项更新：有代码/本地通过/已push/精确CI通过/设备生效分别登记；任何尚未通过或未核实的项仍标未完成。

## 后端纠正批已验收（2026-11-15）

完整SHA `379ff0ec2aad2ca0ac48ce67cf3b94d5fe4a25a2` 已实际推送并从远端main确认。[WMS CI #2202](https://github.com/SIX2090/wms/actions/runs/43710500469) 与 [WMS AI Verification #2497](https://github.com/SIX2090/wms/actions/runs/43710500481) 的最新运行均completed/success，已逐作业/gate及Actions同SHA页面核对。全站隔离单测合计16760 passed、207 skipped、1653子测试通过、0失败；日志证明只读源码及私有PID/network命名空间后才运行应用测试。Android复用[成功祖先构建#894](https://github.com/SIX2090/wms/actions/runs/43706012293)，输入两路径无变化、祖先可达及223对象齐全证明已存档。此旧APK只验收本次未改Android的后端批，后续Android修复必须新目标真实构建。

后端详细失败→R8→纠正过程见[第一批回执](2026-11-15-native-api-remediation-batch1.md)。A07软件代码已交付、A11服务端协议已交付；生产未部署。Android全部缺陷修复仍等待本批最终验证、提交推送和精确CI，不得据此宣称12类全部交付。

## Android后批本地验收冻结（2026-11-15）

- 原生工程33个本任务文件，包含23个产品文件、9个测试/夹具和发行元数据；排除其他任务未提交的视觉checkpoint注释及视觉文件。
- `final-native-507.log`：真实Kotlin编译、507项完整Android单测0失败/0错误/0跳过、lint 0 Error / 5 Warning / 3 Information，BUILD SUCCESSFUL（10m5s）。`validated-native-507/summary.json`及原始XML/lint保留，冻结输入哈希无漂移。
- 随后仅增强已有缓存用例，把“换账号”和“换服务器”拆成同仓库两个独立断言，精准复验1项0失败/0错误/0跳过。该增强不冒充已在前一507执行；所有产品字节哈希相同，最终目标CI仍完整运行507项。
- 独立纯源码/内存相邻契约67项通过，不能替代Android运行或完整应用隔离证据。入/出库及盘点坏JSON原文保留、人工确认清空/取消、当前账号key保护，真实Navigation识物回传，聊天重建和9项报表上下文回归均已在507中通过。
- Android版本53/3.9.29，Windows发行输入2026.11.75；后批完整提交、实际push及目标CI仍待记录。未取得精确目标CI前不算12类整体交付。


## Android首次目标失败与R8纠正（2026-11-15）

`7262849b3ac3cda7f07d8956694b028612566480` 已实际push（`F/native-push.log`），但不是验收通过目标：[WMS CI #2203](https://github.com/SIX2090/wms/actions/runs/43712755555) 失败；[Android #895](https://github.com/SIX2090/wms/actions/runs/43712755550) 编译和lint成功、507项单测中1项临时DataStore文件生命周期异常；[AI #2498](https://github.com/SIX2090/wms/actions/runs/43712755539) 成功。WMS隔离应用单测只有期初接口的一个历史源码调用形状断言失败，其余业务单测通过；另10个verify消费者仍绑定旧调用/默认仓/清空协议，不能把失败解释为通过。

按R8形成完整原生批回退提交 `a06ffbfc869c7b2982a9e86b1a5ab8d7378f100e`，树精确等于已验收后端 `379ff0ec2aad2ca0ac48ce67cf3b94d5fe4a25a2`；通过索引构建回退，不覆盖共享工作区任何候选或其他任务文件。重新评估并行修正既有源码消费者和测试自有DataStore作用域，不吞异常、不削弱业务断言。纠正后版本54/3.9.30与2026.11.76；完整回归、整批可逆性、新push及新目标CI尚待补证，当前仍仅A07完成软件交付。


## 纠正批当前冻结与专项（2026-11-15）

Android 54/3.9.30、Windows 2026.11.76。冻结40个本任务Android输入（23产品、16测试/夹具、1发行文件），本批精确范围62文件；其他任务视觉改动不纳入。`F/corrected-android-owned-manifest.json`及LF清单标识实际构建输入。

新增专项 `F/validated-corrected-focused/summary.json` 为6 tests、0 failure/error/skip。原CI失败盘点清空通过；真实PreferenceDataStore生命周期2项通过；七入口503/账号隔离、服务端先记效果后断链均通过。`everyAffectedWriteLostReceiptReplaysExactlyOneOriginalEffect` 对六个非队列入口用原未决记录恢复，盘点按现有可靠Room交接后以原key/body补传，每个合成效果计数1；保留真实OkHttp自动重试，不把其自动取得回执误当人工未决测试。首版专项中该场景夹具未持续丢回执的失败不计产品红灯，原始失败日志保留。

测试资源同根因修正覆盖5个新增套件和7个既有reset消费者：独立IO作用域、固定canonical File、VM/Compose结束后cancel/join实际DataStore，再仅解绑自身。业务产品代码不因该夹具问题改动。旧夹具关闭后仍能写的明确反证见 `F/datastore-lifecycle-before-results.json`；重开同文件保值为正向对照。

精确私有源码快照的受限契约67/208/65项各自通过（套件有重叠，不相加冒充独立数量），严格AI映射44代码任务/143完成台账一致。首次62文件整批实际reverse/restore哈希通过；断链夹具最后一处漂移后的最终整批证据在提交前重做。完整510单测及lint正在运行，实际最终结果/纠正目标SHA/新CI仍待补。


## 纠正批最终本地验收（2026-11-15）

`F/corrected-native-full-510-v4.log` 实际以 BUILD SUCCESSFUL 结束（6m34s）；JUnit XML合计 **510 tests / 0 failures / 0 errors / 0 skipped**。同一Gradle真实Kotlin编译及lint完成，lint **0 Error / 5 Warning / 3 Information**。最终40项raw/LF输入清单与已执行版本一致，交入Git前逐blob核对。

中途旧测试创建的raw ViewModel未关闭，导致DataStore退出等待Main回调的全量挂起，原日志和 `F/corrected-full-thread-dump.txt` 留存，不能计通过。修正7个既有测试和新增标准TestMain消费者的显式资源归属，取消后泵Main直到Job.isCompleted，10秒仍未结束明确失败；不以超时跳过或吞IO异常。之后7套消费者及focused专项 **128项全部通过**，归档 `F/validated-corrected-consumers-v3/summary.json`。最终v4才是510全量/编译/lint的交付输入。

最终本批62文件按精确索引树在私有副本执行整批reverse/restore及逐文件hash，证据 `F/native-corrected-final-rollback.json`；必须执行成功才提交。相邻受限67/208/65套件与严格AI对账在该精确源码快照复核；早先缺完整AI源码的私有夹具错误已单独排除，补齐所有Git源文件后44/143映射通过。未在主机导入完整Flask app，不绕过LPAC/数据库保护。

当前仅本地验收完成；纠正目标完整SHA、真实push输出、远端可达性及三工作流结果仍须追加，不能据此报告12类全部交付。
