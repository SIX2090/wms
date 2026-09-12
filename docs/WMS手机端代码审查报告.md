# WMS 手机端代码审查报告

审查对象：`app/android-native-wms`（72 个 Kotlin 文件 / 18090 行）
审查日期：2026-09-12
审查方式：**全项目编译器比对** + 静态风险模式扫描 + 业务链路走查
**修复状态：4 处缺陷已于 2026-09-12 全部修复并推送（`a28503a`），台账登记 BUG-2026-09-12-008 ~ 011**

> **审查方法说明（重要）**
> 上次 AI-MOB-OFFLINE-01 的教训是"语法检查通过 ≠ 能编译"。本次审查用真实工具链
> （kotlinc 1.9.24 + 真实 Android SDK platform-35 + Room/Retrofit/OkHttp/DataStore/
> Security/lifecycle 真实依赖）对 72 个文件做**全量编译**，并用**基线对比法**判定：
> 编译修复前基线 `c350d25` 与修复后 HEAD，各得唯一错误 **833 条 —— 新增 0、消失 0**，
> 即改动未引入任何一条新错误。这 833 条全部是缺 Compose/Coil/CameraX 库导致的
> `unresolved reference`（如 `Composable`/`AlertDialog`/`Button`），属隔离编译固有噪声，
> 与基线逐条相同。
>
> **一个必须记录的踩坑**：验证过程中一度用 `java -cp kc2.jar ... K2JVMCompiler` 直接调用
> 编译器，得到"0 错误、0 产物"的结果并差点采信——实际上编译器因缺 `trove4j` 抛了
> `NoClassDefFoundError` 根本没执行，"没有错误输出"被误读成"编译通过"。正确做法是用
> 官方 `kotlinc` 包装脚本（其 `-cp` 含 stdlib/reflect/script-runtime/trove 共 5 个 jar）。
> 这条与上次"CI 全红"是同一类错误：**把"工具没报错"当成"代码没问题"，必须先确认工具
> 真的跑起来了（有产物、有真实错误输出）**。下方结论均基于修正后的正确调用方式。

---

## 一、总体评价

**做得好的地方（不是客套，都有代码证据）**

| 项 | 证据 |
|---|---|
| Token 安全存储 | `EncryptedSharedPreferences` + `MasterKey AES256_GCM`（`WmsRepository.kt:53-63`） |
| 日志不泄密 | `Level.BASIC` 不打印 header，release 走 `Level.NONE`（`RetrofitClient.kt:44-48`） |
| 网络回调无泄漏 | `callbackFlow` + `awaitClose` 正确 unregister（`NetworkMonitor.kt:92-98`） |
| 未误开主线程查询 | 无 `allowMainThreadQueries`、无 `runBlocking`（否则会 ANR） |
| 分页合规（R1） | `page/page_size` 全部显式传参，未当业务上限用 |
| 幂等设计正确 | `X-Idempotency-Key` 复用同一 `requestId`，在线失败转离线不换键 |
| 超时配置合理 | connect 15s / read 30s / write 30s |
| 单例线程安全 | `OfflineQueueManager` 标准双检锁；`RetrofitClient` 全 `@Volatile` + 锁内"先构建后发布" |
| 无硬编码 URL/IP | 全仓 0 处 |
| 无敏感信息落日志 | 全仓 0 处 |

**结论：代码基线质量不差**，架构分层（data/ui、ViewModel、Repository）清晰，注释写得很扎实（能看出为什么这么写，而不是写"这是啥"）。

**但有 4 个真实缺陷**，其中 3 个集中在**离线队列**——恰好是上次新加、也恰好没被 CI 覆盖到的模块。

---

## 二、缺陷清单（4 项均已修复）

### 🔴 P1 — 补传失败记录永久卡死 `SYNCING`，记录静默消失

**位置**：`data/repository/OfflineQueueManager.kt:174`、`189-194`

```kotlin
runCatching { dao.markSyncing(op.requestId) }   // ← 先置为 SYNCING
val success = try { replay(op) } catch (...) { ... }
if (success) {
    runCatching { dao.deleteByRequestId(op.requestId) }
} else {
    failCount++          // ← 既不删除、也不标记失败：永久停在 SYNCING
}
```

**触发路径**：`replay()` 返回 `false` 的唯一分支是未知作业类型（`OfflineQueueManager.kt:224-227` 的 `else -> { Log.w(...); return false }`）。

**为什么是"静默丢数据"**（不是危言耸听，逐条验证过）：

1. `listPending()` 的 SQL 是 `WHERE status = 'pending'`（`PendingOperationDao.kt:30`）→ **取不到 SYNCING 记录**，下轮补传跳过
2. `countPending()` 同样只数 `pending` → UI 的"待同步"徽标**不显示**
3. `countFailed()` 只数 `failed` → UI 的"失败需人工处理"**也不显示**
4. `resetStuckSyncing()` 只在 `init` 里调用一次 → **只有进程重启才复位**

**净效果**：用户提交的单据在数据库里躺着，但**任何界面都看不到它**，补传永远不会再碰它。

**最讽刺的是**：`PendingOperationDao.kt:55-56` 的注释写着「不复位就永远补传不出去——静默丢数据，正是本任务要根治的问题」。**同类根因在同一个文件里又出现了一次（R6 复发）。**

**修复方向**：`else` 分支补 `markFailure(op, "未知作业类型：${op.operationType}", forceFail = true)`。未知类型属确定性错误，重试无意义，应直接判失败并让用户看见。

> **✅ 已修复（BUG-2026-09-12-008）**：`else` 分支补 `markFailure(..., forceFail = true)` + `Log.w`；并把 `replay()` 的 KDoc 改成显式声明「false = 确定性失败，调用方必须回写状态」，把契约钉在签名文档上。顺带修正 `buildSummary()` 全失败文案——原文案「请检查网络后重试」会误导（原因可能是业务拒绝，与网络无关，同 BUG-2026-09-10-011 模式），改为「已保留在本机待处理（详见失败列表）」。
> **验证**：`tests/verify_bug_2026_09_12_008_offline_queue_state_machine.py` 含**可执行状态机模型**，真实跑一遍"补传返回 false"路径，断言无记录停留 `SYNCING`、未知类型落 `failed` 且能被 `countFailed` 统计，并内置**对照组**复现修复前的卡死状态（老实现下 `countPending()==0 && countFailed()==0`），证明缺陷真实存在。

---

### 🟠 P2 — `enqueue()` 返回 `true` 但落库是异步的，失败会让用户误以为"已安全暂存"

**位置**：`OfflineQueueManager.kt:128-143`（返回 `true`）、`WmsRepository.kt:408-419`（据此弹成功提示）、`ScanViewModel.kt:758`（`success = e.message` 用成功样式）

```kotlin
scope.launch {                      // ← 异步
    runCatching { dao.upsert(...) }
        .onFailure { Log.e(...) }   // ← 只写日志，返回值已提前 return true
}
return true                         // ← 立即返回成功
```

**矛盾点**：
- 返回 `true` → UI 显示「网络不可用，入库已暂存，联网后自动提交」（`success` 语义）
- 实际落库可能在**之后**失败（磁盘满 / DB 损坏 / 进程被系统杀死）
- 而设计意图（`WmsRepository.kt:376-380` 注释）恰恰是「不让用户把已安全暂存误认为失败，否则重扫造成重复单据」

**风险方向是反的**：现在是让用户把**可能丢**误认为**已安全**。对发货/领料场景，这比"误认为失败"更危险——用户安心离开，货账两空。

**修复方向**：`enqueue` 改为 `suspend`，落库成功后再返回 `true`；或返回值区分"已落库"与"未落库"，UI 分别措辞。

> **✅ 已修复（BUG-2026-09-12-009）**：`enqueue` 改为 `suspend`，直接 `return runCatching { dao.upsert(...); refreshCounts(); true }.getOrElse { Log.e(...); false }`——落库完成才返回。调用方 `submitWithOfflineFallback` 本就在 suspend 上下文，无需改语法。同时**修正失败分支文案**：原为 `Exception("网络错误: ...")`（把本地存储异常也说成网络问题，误导排查方向），改为「提交失败且本地暂存未成功，请保持本页重试（原因：…）」，明确告知数据没保住。
> **验证**：`test_009_enqueue_is_suspend`（含**反向断言**：函数体内不得再出现 `scope.launch` 异步落库的旧写法）、`test_009_enqueue_failure_returns_false`、`test_009_repository_does_not_lie_when_queue_fails`。

---

### 🟡 P3 — 三个 submit 无 `isLoading` 守卫（防重复提交缺纵深防御）

**位置**：`ScanViewModel.kt` 的 `submitInbound` / `submitOutbound` / `submitStocktake`

全仓搜索结果：**不存在**任何 `if (_uiState.value.isLoading) return` 型守卫。

**当前为什么没出事**：三处确认对话框点完立即 `showSubmitDialog = false`（`ScanScreens.kt:196`、`497`、`1578`），对话框一关按钮就消失，用户**点不到第二次**。

**但这是巧合，不是设计**：
- 三个按钮的 `enabled` 都**没有**绑定 `isLoading`（盘点的 `enabled` 只判仓库与盘点单）
- 命中重复请求的代价很高：`newRequestId()` 每次生成**新 UUID** → 幂等键不同 → 后端**不会识别为重复** → **两张单据、扣两次库存**
- 弱网下用户"没反应我就再点一下"是现场最自然的动作

**修复方向**：ViewModel 入口加 `if (state.isLoading) return`；同时把 `enabled = !uiState.isLoading` 补上。两道防线都要有。

> **✅ 已修复（BUG-2026-09-12-010）**：双层防护落地——①ViewModel 三个入口各加 `if (_uiState.value.isLoading) return@launch`，置于置 `isLoading=true` **之前**；②UI 三个按钮 `enabled` 追加 `!uiState.isLoading`。盘点按钮因原已带「仓库+盘点单必选」前置校验，改为**与运算追加**而非覆盖，保住原有校验。
> **验证**：`test_010_all_submits_have_isloading_guard`（并断言守卫位置必须在置位之前，否则会自己挡住自己）、`test_010_ui_buttons_disabled_while_loading`。
> **连带修复**：本次改动打坏了既有测试 `tests/verify_android_stocktake_check_order.py`（它断言按钮 `enabled` 为**单行字面量**，被多行写法打破）。已改为**语义断言**（从 `viewModel.submitStocktake()` 调用点定位按钮块，断言含盘点单校验 + isLoading 守卫），保留原意且不再依赖格式，6/6 通过。

---

### 🟡 P4 — 离线补传的启动时机依赖"用户先进扫码页"

**位置**：`WmsRepository.kt:44` 的 `offlineQueue by lazy`、`ScanViewModel.kt:96-107` 的 `init`、`WmsApplication.kt`

**链路**：
```
WmsApplication.onCreate()  → 未触发补传（无相关代码）
   ↓
OfflineQueueManager.init    → 复位 SYNCING + 监听网络恢复（但 lazy，要等首次访问）
   ↓
首次访问 = ScanViewModel 构造时读 offlineQueue.pendingCount
   ↓
ScanViewModel 仅在渲染扫码页时创建
```

**后果**：用户断网提交后，若**不再进入扫码页**（比如只在首页看概览、或用语音模块），则：
- 队列管理器**根本没被实例化** → 网络恢复监听未注册 → **不会自动补传**
- 也不会执行 `resetStuckSyncing()` 复位

数据**最终**能同步（迟早会进扫码页），但"联网后自动提交"这个承诺在"不进扫码页"时**不成立**。

**修复方向**：在 `WmsApplication.onCreate()` 里显式预热单例并触发一次 `syncPending()`。

> **✅ 已修复（BUG-2026-09-12-011）**：`WmsApplication` 新增进程级 `appScope`（`SupervisorJob + Dispatchers.IO`）与懒加载 `repository`，`onCreate()` 末尾调用 `warmUpOfflineQueue()`，在后台协程里 `runCatching { repository.offlineQueue }` 触发实例化——使 `init` 的 syncing 复位与网络监听注册**与用户操作路径无关**地生效。要点：必须后台执行不阻塞主线程；`SupervisorJob` 隔离失败；懒加载 `repository` 不加启动开销；`getInstance` 双检锁保证幂等。顺带把文件内日志 TAG 由字面量收敛为常量。
> **说明**：未在此处额外显式调用 `syncPending()`——因为 `init` 内已注册 `onlineChanges` 监听，实例化即等价于"具备了补传能力"；若此时在线，下一次网络状态翻转或用户手动重试即可补传。真正缺失的是"实例化时机"，已补上。
> **验证**：`test_011_application_warms_up_offline_queue`（断言 `onCreate` 确实调用预热、预热体走 `appScope.launch` 不阻塞主线程）。

---

## 三、优先级建议（修复时的实际排期）

| 序号 | 缺陷 | 状态 | 理由 |
|---|---|---|---|
| **P1** | SYNCING 卡死 | ✅ 已修 | 真丢数据，且 UI 完全无感知；修复成本极低（加一行） |
| **P2** | enqueue 异步假成功 | ✅ 已修 | 让用户对"已暂存"产生错误信任，方向性风险 |
| **P3** | 缺防重复守卫 | ✅ 已修 | 弱网下重复点按会重复扣库存；当前靠时序侥幸 |
| **P4** | 补传启动时机 | ✅ 已修 | 影响"自动补传"承诺的兑现范围 |

四项同属一条业务链路（断网暂存 → 联网补传）的完整性，故作为**一个 atomic action** 提交（`abbd864` 本地 / `a28503a` 远程），台账登记 BUG-2026-09-12-008 ~ 011。

---

## 四、次要观察（不建议现在动）

1. **硬编码中文 125 处**（`Text("...")` 直写，未走 `strings.xml`）。当前只有中文用户，无实际影响；若将来要出多语言版会是笔债。
2. **`OfflineQueueManager.scope` 永不取消**（`CoroutineScope(SupervisorJob() + Dispatchers.IO)`）。因它是进程级单例，生命周期与进程一致，**当前可接受**；但若将来改成可销毁的，需要补 `cancel()`。
3. ~~**台账 3 项"待开发"标注滞后**（AI-MOB-CHECK-F01 / RPT-F01 / EMPTY-F01 实际已做了大半），建议订正~~ → **已订正**（`ce72445` 远程：三项改为「部分完成」）；其中 **AI-MOB-CHECK-F01 已进一步完成**（`cca741e` 本地 / `39dbb5d` 远程，补齐盘点记录回查），剩余 RPT-F01、EMPTY-F01 仍为部分完成。

---

## 五、给后续开发的约束（本次审查得出的）

1. **离线队列这类"本地持久化 + 后台重试"模块，必须有状态机完整性测试**。当前 `pending_operations` 的三态（pending/syncing/failed）没有任何测试覆盖"每个状态都有出口"，P1 就是这么漏掉的。→ 本次已补 `tests/verify_bug_2026_09_12_008_offline_queue_state_machine.py`，其中含**可执行状态机模型**，可作为同类模块的测试范式。
2. **CI 目前不会捕获这类缺陷**：`Android APK Build` 只证明"能编译"，`WMS CI` 只跑 Python 侧。Kotlin 侧**没有单元测试**。这是结构性缺口。（缓解：本次回归测试走"源码契约 + 行为模型"双层，已被 CI 第 12 步 `verify_*.py` 收集执行）
3. **凡"返回成功但实际操作异步"的接口，必须显式设计返回值语义**，不能让调用方把"已排队"当"已完成"。
4. **验证 Kotlin 改动时，必须先确认编译器真的跑起来了**：本次发现用 `java -cp kc2.jar` 直接调编译器会因缺 `trove4j` 静默崩溃（`NoClassDefFoundError`），"无错误输出"被误读为"编译通过"。必须用官方 `kotlinc` 脚本，并以"有 class 产物 + 有真实错误输出"作为工具确实执行的证据。
