# 开发计划：安卓 App 离线优先作业队列（AI-MOB-OFFLINE-01）

> 依据：`AGENTS.md`（业务铁律 / 第三节任务粒度 / A1–A11 / R1–R6）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`
> 基准提交：`1692882` ｜ 编制日期：2026-09-12
> 目标模块：`app/android-native-wms`（Kotlin / Jetpack Compose / Room / Retrofit）

---

## 一、问题陈述（为什么要做）

当前安卓 App 的"离线"只有**提示**，没有**降级**：

1. `AppDatabase` 仅两张表（`materials` / `operation_logs`），`version = 1`；
2. 全模块 `grep ConnectivityManager|NetworkCallback|isOnline` **零命中**——无网络状态监听；
3. `OperationLogEntity` 是**成功后的审计日志**，不是待提交队列——断网提交失败后**不会补传**，数据永久丢失。

**现场后果**：仓库货架深处/地下室信号弱，作业员扫码入库到一半点提交 → 失败 → 整单已扫明细作废，必须回到有信号处重扫。

**本任务目标**：让"人工已确认的提交动作"在网络不可用时**本地暂存**，网络恢复后**自动补传**，且**不产生重复单据**。

---

## 二、范围与边界（硬约束）

### 2.1 必须做

| 项 | 内容 |
|---|---|
| Room 扩表 | 新增 `PendingOperationEntity` + DAO，`AppDatabase` version 1→2，迁移登记进 `DatabaseMigrations.ALL` |
| 网络监听 | `ConnectivityManager.registerDefaultNetworkCallback`，状态翻转驱动队列刷新 |
| 提交改造 | `WmsRepository` 三个提交方法在**网络类失败**时落本地队列而非直接抛错 |
| 自动补传 | 恢复网络后按 `created_at` 顺序重放，复用后端 `mobile_api_idempotent`（`X-Idempotency-Key`）保证幂等 |
| 队列可视化 | 扫描页显示待同步条数；支持人工触发重试；失败超次数显式告警 |

### 2.2 明确不做（防止越界）

- ❌ **不允许 AI 草稿进队列**：队列只承载"用户已点击提交"的动作。AI 识别/语音生成的草稿仍走原流程，必须人工确认后才可能入队（AGENTS.md §一 / R5）。
- ❌ **不新增后端接口**：完全复用 `/api/inbound`、`/api/outbound`、`/api/stocktake` 及其既有幂等装饰器。
- ❌ **不做自动完成/审核**：补传只调用原提交接口，单据状态流转仍由后端与人工控制。
- ❌ **不清空既有数据**：`fallbackToDestructiveMigration` 保持禁用，必须写显式迁移。
- ❌ **失败不静默**：补传失败达上限必须显式告警，禁止像 `operation_logs` 那样 `onFailure = { }` 吞掉。

### 2.3 仓库必填规则（AGENTS.md 第二节）

入队前**必须校验仓库**（及启用库位管理时的库位）已在请求中；缺失则拒绝入队并提示"请选择仓库"。**断网时不得回退到"全部仓库"口径**——离线暂存的是用户当时选定的仓库，不允许替换。

---

## 三、技术设计

### 3.1 数据模型

```kotlin
@Entity(tableName = "pending_operations")
data class PendingOperationEntity(
    @PrimaryKey val requestId: String,        // = X-Idempotency-Key，天然去重
    val operationType: String,                // inbound / outbound / stocktake
    val payloadJson: String,                  // 请求体 JSON（Gson）
    val warehouseCode: String?,               // 便于列表展示与校验
    val summary: String,                      // "入库 3 项 / A仓"
    val status: String,                       // pending / syncing / failed / done
    val attemptCount: Int = 0,
    val lastError: String? = null,
    val createdAt: Long,
    val updatedAt: Long
)
```

**关键设计**：主键用 `requestId`（UUID）。重放时携带同一个 `X-Idempotency-Key`，后端 `mobile_api_idempotent` 命中历史成功响应直接回放，**从根本上杜绝重复入库**。

### 3.2 状态机

```
        submit 失败(网络类)
   ─────────────────────────→ pending ──网络恢复──→ syncing
                                  ↑                    │
                                  └────失败(<上限)─────┘
                                                       │
                                                 达上限 ↓
                                                    failed(显式告警)
                                  syncing ──成功──→ done(删除记录)
```

### 3.3 失败分类（关键）

只有**网络类异常**才入队。业务类异常（422/400，如"请选择仓库""库存不足"）**必须立即返回给用户**——这类错误重试一万次也不会成功，入队反而掩盖真实问题、让用户以为提交成功了。

复用既有 `WmsRepository.BusinessException` 做区分（该类已存在，见 `BUG-2026-09-10-011`）。

### 3.4 幂等与并发

- 同一 `requestId` 唯一主键 → 重复入队自动覆盖，不会重复提交。
- 补传加进程内互斥（`Mutex`），避免网络频繁抖动导致并发重放。
- 重放成功即删除记录（保持队列精简）。

---

## 四、执行拆分（atomic actions）

严格按 AGENTS.md 第三节：**每个 atomic action 独立 commit + push 到 `main`**，各自可独立 revert。

| # | atomic action | 产出 | 验证 |
|---|---|---|---|
| **A1** | 离线队列数据层 | `PendingOperationEntity` / `PendingOperationDao` / `AppDatabase` v2 / `DatabaseMigrations.MIGRATION_1_2` | 编译通过；迁移 SQL 语法正确 |
| **A2** | 网络状态监听器 | `util/NetworkMonitor.kt` | 编译通过 |
| **A3** | 仓库层：入队 + 补传 | `WmsRepository` 三提交方法改造 + `OfflineQueueManager` | 编译通过；BusinessException 不入队 |
| **A4** | UI 接入 | `ScanViewModel` 队列状态；扫描页待同步提示条 + 手动重试 | 编译通过 |
| **A5** | 台账登记 | `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 新增 AI-MOB-OFFLINE-01 | 台账一致性检查 |

### 验证手段（受沙箱限制的说明）

本沙箱**无 Android SDK / Gradle 依赖缓存**，无法本地 `assembleDebug`（台账 `AI-APP-UI-001` 曾自建工具链，属额外成本）。因此：

1. **静态正确性**：新增 Kotlin 文件逐个做**结构自检**（括号配平、import 完整、类型一致）；
2. **迁移 SQL**：用 Python `sqlite3` 建库执行等价 DDL，证明 schema 可创建、约束成立；
3. **JSON 契约**：用 Python 复现 `payloadJson` 序列化/反序列化与后端请求体字段一致性；
4. **CI 兜底**：仓库既有 GitHub Actions 会跑 `assembleRelease`，最终以 CI 结果为准（台账惯例）。

> 说明：不谎报"编译通过"。凡未经真实编译器验证的，均标注为"静态自检 + CI 待验"。

---

## 五、风险与对策

| 风险 | 对策 |
|---|---|
| 迁移写错导致升级崩溃 | 显式 `MIGRATION_1_2`，禁用破坏性迁移；本地用 sqlite3 验证 DDL |
| 补传造成重复单据 | 复用 `X-Idempotency-Key` + 后端 `mobile_api_idempotent` 回放机制 |
| 断网时仓库被替换 | 入队即固化 `warehouse_code`，重放原样使用，不回退默认仓 |
| 队列无限膨胀 | `done` 即删；`failed` 显式告警由人工处理，不自动清空 |
| 业务错误被误判为网络错误入队 | 复用 `BusinessException` 分类，业务类异常立即返回用户 |
| Token 过期导致补传全失败 | 补传前 `ensureSession()`；401 不重试，标记 failed 提示重新登录 |

---

## 六、完成标准

- [ ] 三个提交方法均具备"断网入队 / 联网补传"能力
- [ ] 迁移可在既有 v1 库上无损升级到 v2
- [ ] 队列状态在 UI 可见，失败可人工重试
- [ ] AI 草稿无法进入队列（边界守住）
- [ ] 每个 atomic action 已 commit + push 到 `main`，`git log -1` 与 `origin/main` 一致
- [ ] 台账登记完成（任务 ID / 提交哈希 / 验证命令 / 结果 / 遗留子项）
