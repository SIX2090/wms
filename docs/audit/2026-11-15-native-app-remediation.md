# 原生 Android 审计 A01–A12 修复交付记录

任务：`AI-APP-AUDIT-FIX-20261115-001`；BUG-2026-11-15-009～020；日期：2026-11-15。

**12/12 类的软件修复、回归、提交推送和精确目标CI已验收。真机及生产生效仍待人工验证/另行授权。** 最终代码目标 `dbe403058eec536ab93411906bc0b44de023b871`，Android54/3.9.30、Windows2026.11.76；真实push及远端main一致、可达性已核对。本文收口提交自身CI另行验收，回执在本地证据目录及最终交付登记。

审计基于023ac9e5及当时未提交内容；本轮核对当前实现，以并行更新任务完成后的84fac39015732d22e3e71cc77b0c071a621b7e04作源码基线。始终直接main，不建分支，不覆盖/提交/回退其它任务文件。只处理A01～A12及确认的同根因消费者，不新增R01～R04能力、审批、作废、权限或强制采购来源。

下表K指 `app/android-native-wms/app/src/main/java/com/factory/wms/`；测试位于同工程 `app/src/test/java/com/factory/wms/`。F指用户原审计目录同级的 `native-wms-fix/`，完整目录为 `C:/Users/Administrator/.codex/visualizations/2026/11/15/01a1de80-0f3b-75d1-bcbd-a7f2c7e704aa/native-wms-fix/`。

## 12项验收矩阵

所有行均已完成代码、本地适用验证、实际push及目标CI。最终510项包含各项代表锁；正常对照不要求旧版失败，设备/现网状态统一见文末。

| 项目 | 根因与修复位置 | 最终行为及同根因消费者 | 有效旧业务反证 |
|---|---|---|---|
| A01 / BUG-2026-11-15-009 | `K/ui/viewmodel/scan/ScanViewModel.kt` 的 `materialExists`、`enrichScanLineMaterial`；`K/ui/viewmodel/opening/OpeningStockViewModel.kt` 的 `addLine`。精确失败后曾取模糊首项回填编码。 | 只接受相同编码的精确信息补全，补名称、规格、品牌时不修改已确认编码；非精确查找交候选选择。排查入库、出库、盘点、期初共用消费者，以及网页多候选/单候选分支。 | `Audit.ambiguousManualKeywordNeverChangesMaterialIdentity`：Bolt被换成M001。 |
| A02 / BUG-2026-11-15-010 | `K/ui/viewmodel/report/{StockDailyReportViewModel,InOutDetailReportViewModel,StockLedgerReportViewModel}.kt`、`opening/OpeningStockViewModel.kt`、`scan/ScanViewModel.kt`、`list/OrderListViewModel.kt`、`stocktake/StocktakeRecordViewModel.kt`、`archive/MaterialArchiveViewModel.kt`。异步回调曾缺上下文世代保护。 | 每个查询捕获完整参数、请求版本和账号会话，取消/迟到成功/迟到失败不得更新新查询；跨查询清旧列表，不把旧页追加到新筛选。员工部门联动、盘点单选项、单据状态、记录详情和档案图片同根消费者一并处理。复核再补台账选料搜索：绑定关键字+仓库+账号，选择/清空/改词即取消；库存日报和出入库明细编辑关键词时复位旧加载/分页，不自动发新请求。 | `stockDailyIgnoresOldWarehouseResponse`、`inOutIgnoresOldWarehouseResponse`、`stockLedgerIgnoresOldWarehouseResponse`、`openingIgnoresOldWarehouseResponse` 均期望B却得到A；`departmentEmployeesRejectLatePreviousDepartment` 得1而非2；`checkOrderOptionsRejectLatePreviousWarehouse` 得11而非22；`orderStatusListRejectsOldFailureAfterNewSuccess` 出现旧503错误。 |
| A03 / BUG-2026-11-15-011 | `K/ui/viewmodel/scan/ScanViewModel.kt` 的 `maybeRestoreStocktakeDraft`、仓库/盘点单选择和持久化；`K/data/model/ScanRequests.kt` 的 `StocktakeDraft`。原先只恢复清单，默认仓/仓库异步先后可错挂。 | 原仓、原盘点单、区域、明细、原请求号作为一组恢复；停用或失效时保留内容并阻止改挂。待核实原请求可保留原上下文核实回执。恢复未成功读出原稿时禁止自动空保存；坏JSON不删除，须人工明确清空后才解除保护。 | `stocktakeRestoresOriginalWarehouse`：原B恢复成A；`unavailableOriginalWarehousePreservesStocktakeAndBlocksReplacement` 错选A；`completedOriginalCheckPreservesStocktakeWithoutSubmittingElsewhere` 原B上下文丢失。追加 `unreadableOwnedDraftCannotBeDeletedByAutomaticEmptySave`：原 `{broken-json` 被自动删成null。 |
| A04 / BUG-2026-11-15-012 | `K/data/repository/WmsRepository.kt` 的 `logout`、草稿key；`K/ui/viewmodel/scan/ScanViewModel.kt` 的账号一致性及恢复保护。认证清理曾 `DataStore.clear()` 删除业务草稿。 | 只清认证元数据，保留按服务器/原账号隔离的草稿、待核实请求和原键；其他账号不能恢复/发送原账号记录。原401世代隔离、权限重新核对、离线队列归属保持。旧无归属盘点稿原文保留，仅提示人工核对，不猜账号自动恢复。入/出库坏稿也不能被默认空清单覆盖。 | `logoutPreservesOwnedEditDraft` 真实持久化前后比较旧版丢稿；`legacyUnownedStocktakeStaysPreservedWithoutBeingAssignedToCurrentAccount` 旧无归属稿被自动归当前账号。入/出库补充 `unreadableInboundDraftCannotBeAutomaticallyOverwritten`、`unreadableOutboundDraftCannotBeAutomaticallyOverwritten` 原JSON被自动删成null。 |
| A05 / BUG-2026-11-15-013 | `K/ui/navigation/NavGraph.kt`、`K/ui/screens/{AiScreens,ScanScreens}.kt`、`ScanViewModel` 区域状态。识物和原盘点目的地各建一个 owner-local ViewModel。 | 识物目的地绑定原盘点导航条目的 ViewModelStoreOwner，并以当前 NavBackStackEntry 作 `remember` 键；返回原清单可见识物明细，仓库、盘点单、区域和数量保持。加载/待核实时禁用识物添加。 | `NativeAuditNavigationRegressionTest.recognitionReturnsLineToOriginalStocktakeWithWarehouseCheckAndArea`：实际图、实际添加按钮和返回导航之后，原盘点清单为空，取single触发NoSuchElement。 |
| A06 / BUG-2026-11-15-014 | `K/data/repository/WmsRepository.kt` 的 `getMaterialInfo`；现有 `MaterialEntity/MaterialDao` 消费链。原Room缓存只以物料编码键控。 | 内部缓存key包含规范服务器、稳定用户ID、仓库和编码；离线仅能读取相同来源，返回展示恢复原编码并标注缓存时间。历史无归属行不冒充当前库存，原数据不删。无需Room schema/版本迁移，离线队列的身份、状态、原请求号不改。 | `cacheNeverReturnsAnotherWarehouse`、`legacyUnownedMaterialIsNeverCurrentWarehouseStock` 明确旧缓存串用；增强 `cacheNeverReturnsAnotherServerOrAccount` 在同服务器/仓库仅换账号、同账号/仓库仅换服务器两种维度都执行后汇总失败。 |
| A07 / BUG-2026-11-15-015 | `app/app.py` 的 `material_search_api`、`material_info_api`；复核补 `app/routes/mobile.py` 的物料查询消费者。显式仓库校验错误被忽略后回退全局 `material.stock`。 | 无效、停用、歧义仓库受控拒绝；有效仓仍按仓隔离。未传warehouse的合法元数据协议保持。R6追踪38个脚本/测试/模块路径/通用TARGETS消费者，修正历史002 T7和004 T5的旧“错误回退全局”协议断言；其余10项合法断言AST完全保留。 | `MaterialWarehouseContractTest.test_invalid_info_cannot_return_global_stock`、`test_invalid_search_cannot_return_global_stock`、`test_mobile_lookup_invalid_warehouse_never_returns_global_stock` 旧版400≠200；历史004 T5/002 T7的新断言也对旧产品失败。 |
| A08 / BUG-2026-11-15-016 | `ScanViewModel.persistStocktakeDraftNow`、手工清空/最后一行移除/提交交接分支；`WmsRepository.saveStocktakeDraft`。旧实现不保存空状态，离线成功只清内存。 | 草稿保存串行读取最新状态；手工清空/删空删除对应持久草稿；确认队列可靠接收后清编辑版本，失败保留。恢复未读懂原稿时禁止自动写空；只有人工明确清空才解除。保留服务端同批已盘行保护。 | `emptyStocktakeDeletesPersistedDraft`、`queuedStocktakeClearsCorrespondingDraft` 旧版持久旧稿仍存在；坏稿自动空保存用A03同一明确断言。 |
| A09 / BUG-2026-11-15-017 | `K/data/repository/WmsRepository.kt` 的 `nativeWrite`、`PendingNativeWrite`；`K/ui/components/PendingNativeWriteStatus.kt`；盘点、期初新增/编辑、OCR、语音、AI消费者。旧人工重试在每次调用新建幂等键。复核发现聊天普通重建的随机 scope 仍会绕开记录。 | 发送前持久化原body和requestId，同一意图冻结；结果不明保留，人工核实只用原键/原body，并走服务端当前权限和原子回执；成功由消费方处理后才ack。普通聊天VM重建遇到其它scope未决记录拒发新HTTP并保留输入/附件，同VM原scope重试保持；仅明确清空会话允许新意图，旧请求不回写。 | `stocktakeRetryKeepsOriginalRequestKey`、`openingEditRetryKeepsOriginalRequestKey`、`inboundDraftRetryKeepsOriginalRequestKey` 旧版两次键不同；`lostOpeningEditResponseRetriesSameBodyAndProducesOneEffect` 旧版键/合成效果集合为2。`NativeAssistantRecreationTest.recreatedChatCannotTurnUnresolvedRequestIntoANewBusinessIntent` 旧候选重建后HTTP数1变2。 |
| A10 / BUG-2026-11-15-018 | `ScanViewModel.submitInbound/submitOutbound` 成功及离线入队状态。上一单的evidence未重置，离线交接还可能保留旧打印目标。 | 在线成功或可靠入队后清照片；入队清旧打印目标，失败保留当前报文。仓库、往来单位等用户连续选择不擅自清除。既有打印提示关闭流程继续清理打印目标。 | `nextInboundHasNoPreviousEvidence`、`consecutiveOutboundRequestsDoNotReusePreviousEvidence` 旧版成功后仍残留上一单照片。 |
| A11 / BUG-2026-11-15-019 | `app/routes/native_api.py::native_api_warehouses`；`K/data/model/OpeningStockModels.kt::WarehouseDto`；扫码、期初、首页、报表、OCR和语音ViewModel。接口无明确默认标记，客户端取列表第一条。 | 服务端仅返回启用仓并显式bool `is_default`；客户端仅自动选唯一有效默认项，默认不在第一位也正确。无有效默认时保留未选仓，不发库存查询；已有草稿/人工选择保持原上下文。停用项不得成为新单默认仓。 | `warehousesUseConfiguredDefault` 旧版第二项B默认却选A；`noDefaultWarehouseLeavesNewOpeningUnselected` 旧版无默认仍选A。 |
| A12 / BUG-2026-11-15-020 | `AssistantChatViewModel.clearConversation/send`、`WmsRepository.safeCall`、`VoiceCommandViewModel`。仅清UI，旧响应仍回写会话/附件；仓库层可能吞取消。 | 清空取消作业并递增会话世代；发起/返回/错误处理均检查会话版本及账号generation；清空后立即新问属于新意图，旧成功、旧失败不能恢复消息、附件或conversationId。传播CancellationException，语音消费取消不再落入本地兜底动作。 | `clearConversationRejectsOldResponse` 旧消息回写；`clearChatRejectsOldFailureAndAttachmentRestoration` 旧image恢复。 |

## 回归、编译与相邻验证

- 修改前451项Android基线通过；原审计19探针断言缺陷现状，不计修复新绿。主旧实现回归31项中28个明确业务断言失败、1个等待原上下文超时、2个正常控制；超时和夹具错误不计明确红灯。坏稿、出库、聊天重建、报表候选等追加有效旧红及各项准确测试名见F/final-red-green-evidence.md和原始XML。
- 最终真实Kotlin编译、510 tests / 0 failures / 0 errors / 0 skipped，lint 0 Error / 5 Warning / 3 Information，BUILD SUCCESSFUL 6m34s；F/validated-corrected-native-510/summary.json、corrected-native-full-510-v4.log。40项raw/LF冻结输入逐Git blob相等，无漂移。
- 真实ViewModel、实际Navigation Compose及添加按钮、Retrofit+loopback合成HTTP、Room及PreferenceDataStore；不以addScanLine或源码字符串代替页面运行。67/208/65受限相邻源码套件各自通过（有重叠，不相加）；最终精确源码树复核通过。严格AI映射44代码任务/143完成台账一致，提交规则0违规。
- DataStore原夹具只丢委托缓存，未结束actor；Robolectric清理后可继续访问旧文件。13套真实store消费者显式拥有固定canonical File、独立IO Job；VM取消后泵Main直到Job完成，再cancel/join实际存储scope并仅解绑自身。旧夹具关闭后仍写成功为1项有效旧红，同文件重开保值为对照。相关128项全部通过。首版断链刺激被HTTP自动重试取回回执、旧raw VM未关闭造成的中途挂起均保留原日志/线程dump，不算产品旧红或全量通过。
- A09新增 everyAffectedWriteLostReceiptReplaysExactlyOneOriginalEffect：合成服务端先保存原body及效果再持续丢失首轮回执；六个非队列入口人工用原未决记录恢复，盘点按原可靠Room队列原key/body补传；七入口各effect=1，原键原报文，无额外HTTP。503/账号隔离控制保留。此为真实HTTP与合成服务端效果模型，未操作生产单据；真实服务端原子回执、权限、revision、盘点冲突保护由隔离全站CI对应模块验证。
- A06无Room schema/version=3变更，不需要新迁移；旧无归属缓存保留但不作当前库存。既有PendingQueueRebuildProtectionTest 15项真实合成v1/v2升级、原队列身份/状态/请求号保护继续通过，不能冒充真机旧库现场升级。
- A07本地实际源码函数9/9，精确旧源码4失败+5对照；历史T5/T7当前4/4、旧3失败+1对照，其它10项合法元数据断言AST不变，核查38个接口/H5/模块/TARGETS消费者。原生21个verify消费者208项；47个测试函数和25个明细check原AST保真，不机械翻转业务断言。缺旧文件/初始化/JSON读回错误均排除。

## 精确目标CI和隔离

| 目标 | 工作流 | 结果 |
|---|---|---|
| `dbe403058eec536ab93411906bc0b44de023b871` | [WMS CI #2204](https://github.com/SIX2090/wms/actions/runs/43718443314) | completed/success，全部所选作业及gate通过 |
| 同上 | [WMS AI Verification #2499](https://github.com/SIX2090/wms/actions/runs/43718443243) | completed/success，gate通过 |
| 同上 | [Android APK Build #896](https://github.com/SIX2090/wms/actions/runs/43718443363) | completed/success，Linux510单测、lint、签名APK构建通过，不借旧包 |

全站实际结果：16760 passed、207 skipped（既有跳过）、1653子测试通过、0失败；三个unit分片均先验证只读源码及私有PID/network命名空间，日志绑定同一精确SHA。完整应用只在先证明只读源码、私有PID/network命名空间及独立数据库的目标CI运行。本机不绕过LPAC导入完整Flask app，不登录生产服务；F/native-corrected-acceptance.json及同run原始job日志归档。不能以最新main、其它旧绿或查询异常替代本目标。

## 提交范围、失败纠正及R8

全部代码范围 `84fac39015732d22e3e71cc77b0c071a621b7e04..dbe403058eec536ab93411906bc0b44de023b871`，6个本任务提交、净69文件；后续文档收口不改产品输入。

| 提交 | 实际状态 |
|---|---|
| 829aeaa8f91d63d7902a4c913a34a629099cc378 | 后端首推，CI失败，不计交付 |
| ec036f141d8cf6941589bba177614fcc24ca547f | 按R8整批撤回11文件，完整树回84fac |
| 379ff0ec2aad2ca0ac48ce67cf3b94d5fe4a25a2 | 后端纠正批已push验收，A07及A11服务端 |
| 7262849b3ac3cda7f07d8956694b028612566480 | 原生首推，历史消费者/DataStore夹具CI失败，不计交付 |
| a06ffbfc869c7b2982a9e86b1a5ab8d7378f100e | 按R8完整原生批回退44文件，树等于379ff0ec |
| dbe403058eec536ab93411906bc0b44de023b871 | 原生纠正批62文件已push，完整三工作流已验收 |

后端379的[WMS CI](https://github.com/SIX2090/wms/actions/runs/43710500469)、[AI](https://github.com/SIX2090/wms/actions/runs/43710500481)成功；Android仅此后端批复用[祖先84fac的成功构建](https://github.com/SIX2090/wms/actions/runs/43706012293)，已证明可达、两输入路径无变及223对象齐全，见F/backend-corrected-android-reuse-proof.json。

最终后端16文件和原生62文件分别在隔离纯源码副本实际整批reverse/restore，逐文件哈希等于原树/恢复树；F/backend-corrected-rollback.json、native-corrected-final-rollback.json。原生40冻结输入与Git blob一致，树99b12c608a5bee155c6c894d2852d504c3d2730f。索引构造回退及部分共享文件提交保留其它任务工作内容，未force、stash或回退他人提交。

实际push输出F/backend-corrected-push.log、native-corrected-push.log；推送时目标与远端main一致、非空且可达。后续main推进不改变本次目标。

## 真机待验与生产生效条件

1. 未执行真机相机取证、真实设备系统回收/杀进程恢复、真实网络下连续入出库/离线交接、旧安装库现场升级和覆盖安装，均待人工设备验收；Robolectric不替代这些事实。
2. A07及is_default服务端协议需另行授权，从已验收干净目标部署/重启；不能将混有其它任务未验收改动的C:/wms工作目录直接当绿SHA发布。App需用户安装对应已验收54/3.9.30 APK后现场复验。
3. 本轮未读取/修改生产数据库，未登录生产服务或操作真实单据，未改账号密码、发微信、实际打印、部署、重启或安装APK。旧401、权限复核、队列归属、期初revision、同批已盘行保护和采购来源可选规则保持。
4. 无法证明归属的历史盘点稿/坏JSON保留原文，仅提示人工核对；其它账号不可自动恢复或发送，不猜归属，明确清空才解除坏稿保护。
