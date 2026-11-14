package com.factory.wms.data.repository

import android.util.Log
import com.factory.wms.data.api.WmsApiService
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.local.PendingOperationDao
import com.factory.wms.data.local.PendingOperationEntity
import com.factory.wms.data.model.ApiEnvelope
import com.factory.wms.data.model.InboundRequest
import com.factory.wms.data.model.OutboundRequest
import com.factory.wms.data.model.StocktakeRequest
import com.factory.wms.data.model.SubmitResult
import com.factory.wms.data.repository.WmsRepository.Companion.BusinessException
import com.factory.wms.util.NetworkMonitor
import com.google.gson.Gson
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import retrofit2.Response
import java.io.IOException
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/**
 * AI-MOB-OFFLINE-01：离线待提交作业队列管理器（入队 + 自动补传）。
 *
 * ## 职责边界（AGENTS.md §一 / R5，务必守住）
 *
 * 本类**只处理"用户已点击提交"的动作**。AI 识别 / 语音生成的草稿走各自原流程，
 * 必须经人工确认后才可能被提交——绝不允许 AI 结果绕过人工确认落进本队列直接生效。
 *
 * ## 只入队网络类失败（关键设计）
 *
 * 业务类失败（400/422，如"请选择仓库""库存不足""该盘点单已结束"）**必须立即返回用户**，
 * 绝不入队。理由：这类错误重试一万次也不会成功，入队只是把**确定的失败**伪装成
 * "已暂存待同步"，用户以为提交成功了、实际永远不会成功——那是比丢数据更坏的结果。
 *
 * 区分方式：`WmsRepository.BusinessException` 代表服务端已给出明确业务原因
 * （该类型由 BUG-2026-09-10-011 引入，语义稳定），其余异常（IO/超时/连接失败）
 * 视为网络类，入队。
 *
 * ## 幂等（不产生重复单据）
 *
 * 队列主键 = `requestId`，补传时原样作为 `X-Idempotency-Key` 发出。后端
 * `mobile_api_idempotent`（app/app.py）对同 key 的成功请求直接回放历史响应，
 * 因此弱网反复点击、补传与手动提交并发，都只会在服务端生效一次。
 *
 * ## 失败不静默
 *
 * 与既有 `submitXxx` 中 `onFailure = { }` 吞掉日志的做法不同：补传失败会累计次数、
 * 记录中文原因；达 [PendingOperationEntity.MAX_ATTEMPTS] 转 `failed` 并通过
 * [failedCount] 暴露给 UI 显式告警，交人工处理，绝不自动丢弃。
 */
class OfflineQueueManager internal constructor(
    private val dao: PendingOperationDao,
    private val apiProvider: (RetrofitClient.SessionSnapshot) -> WmsApiService,
    private val currentlyOnline: () -> Boolean,
    onlineChanges: Flow<Boolean>,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
) {

    private val gson = Gson()

    // BUG-2026-09-14-029：构造期不得解析 API，未配置服务器时也可安全创建队列。
    // 每条补传按核验过的会话快照取得新客户端，禁止跨登录缓存首次取得的 API。

    /** 补传互斥：网络抖动会频繁触发 onlineChanges，不加锁会并发重放同一批记录。 */
    private val syncMutex = Mutex()
    private var retryWakeup: Job? = null
    private var updateWakeup: Job? = null

    private val _pendingCount = MutableStateFlow(0)

    /** 待补传条数（UI 展示"待同步 N 条"）。 */
    val pendingCount: StateFlow<Int> = _pendingCount.asStateFlow()

    private val _failedCount = MutableStateFlow(0)

    /** 失败条数（重试耗尽，UI 必须显式告警）。 */
    val failedCount: StateFlow<Int> = _failedCount.asStateFlow()

    private val _canRetry = MutableStateFlow(false)
    val canRetry: StateFlow<Boolean> = _canRetry.asStateFlow()

    private val _lastSyncMessage = MutableStateFlow<String?>(null)

    /** 最近一次补传结果的中文摘要（UI 提示条用）。 */
    val lastSyncMessage: StateFlow<String?> = _lastSyncMessage.asStateFlow()

    init {
        // 启动即复位进程被杀残留的 syncing，否则这些记录永远补传不出去（静默丢数据）
        scope.launch {
            try { syncMutex.withLock { dao.resetStuckSyncing() } } catch (e: Exception) {
                if (e is CancellationException) throw e
                _lastSyncMessage.value = "本地队列读取失败，记录已保留，请核对后重试"
                Log.e(TAG, "队列初始化失败", e)
                return@launch
            }
            syncMutex.withLock { refreshCounts() }
            onlineChanges.collect { online ->
                if (online) syncPending()
            }
        }
    }

    // ───────────────────────── 入队 ─────────────────────────

    /**
     * 入队一条已由人工确认的提交动作。
     *
     * **suspend 且落库完成才返回**（BUG-2026-09-12-009）：本方法此前是非 suspend 的
     * "fire-and-forget"，内部 `scope.launch { dao.upsert(...) }` 后立即 `return true`。
     * 调用方拿到 true 就告诉用户"已暂存，联网后自动提交"，但此刻写库可能还没发生、
     * 甚至可能失败（磁盘满 / DB 损坏）——**用户被引导相信数据是安全的，而它并不在**。
     * 断网暂存这条链路的价值完全建立在"暂存一定成功"上，返回值必须反映真实结果。
     *
     * @param requestId 与请求头 `X-Idempotency-Key` 一致（同一次提交必须复用同值）
     * @param warehouseCode 仓库编码；为空时**拒绝入队**——仓库必填（AGENTS.md 第二节），
     *        断网时更不得回退默认仓，否则补传会落到错误仓库。
     * @return true 已确认写入本地队列；false 参数不合法或写库失败（**均不得当作已暂存**）
     */
    internal suspend fun enqueue(
        requestId: String,
        operationType: String,
        payload: Any,
        warehouseCode: String?,
        summary: String,
        session: RetrofitClient.SessionSnapshot
    ): Boolean {
        // 仓库必填规则：入队前硬校验，缺失直接拒绝（不静默替换）
        if (warehouseCode.isNullOrBlank()) {
            Log.w(TAG, "拒绝入队：缺少仓库编码（AGENTS.md 第二节仓库必填）")
            return false
        }
        if (requestId.isBlank()) {
            Log.w(TAG, "拒绝入队：requestId 为空")
            return false
        }
        if (session.ownerServer == null || session.userId == null || session.token.isNullOrBlank()) {
            _lastSyncMessage.value = "无法核实提交账号，请保留本页并重新登录后重试"
            return false
        }

        return runCatching {
            val operation = PendingOperationEntity(
                    requestId = requestId,
                    operationType = operationType,
                    payloadJson = gson.toJson(payload),
                    warehouseCode = warehouseCode,
                    summary = summary,
                    status = PendingOperationEntity.STATUS_PENDING,
                    ownerServer = session.ownerServer,
                    ownerUserId = session.userId,
                    needsReview = false
            )
            if (dao.upsert(operation) == -1L) {
                val existing = dao.getByRequestId(requestId)
                if (existing == null || existing.needsReview ||
                    existing.ownerServer != operation.ownerServer || existing.ownerUserId != operation.ownerUserId ||
                    existing.payloadJson != operation.payloadJson || existing.operationType != operation.operationType ||
                    existing.warehouseCode != operation.warehouseCode) return@runCatching false
                if (existing.status != PendingOperationEntity.STATUS_PENDING &&
                    existing.status != PendingOperationEntity.STATUS_SYNCING) {
                    _lastSyncMessage.value = "原记录需人工处理，已保留原状态和失败原因，未重新入队"
                    return@runCatching false
                }
            }
            syncMutex.withLock { refreshCounts() }
            true.also { if (currentlyOnline()) syncPending() }
        }.getOrElse { e ->
            if (e is CancellationException) throw e
            // 写库失败必须让调用方知道：不能返回 true 让 UI 谎称"已暂存"
            Log.e(TAG, "入队失败（数据未暂存，必须告知用户）: ${e.message}", e)
            false
        }
    }

    // ───────────────────────── 补传 ─────────────────────────

    /** 手动触发补传（UI"立即重试"按钮与 App 启动时调用）。 */
    fun syncPending() {
        scope.launch {
            try { doSync() } catch (e: CancellationException) { throw e } catch (e: Exception) {
                Log.e(TAG, "本地同步未完成，原记录及幂等键已保留", e)
                _lastSyncMessage.value = "本地同步未完成，记录已保留，请核对后重试"
            }
        }
    }

    internal suspend fun doSync() {
        // 先确认确实在线：网络回调有系统延迟，避免空发
        if (!currentlyOnline()) {
            _lastSyncMessage.value = "当前离线，${_pendingCount.value} 条已暂存待同步"
            return
        }

        val updateGate = com.factory.wms.update.businessUpdateGate
        if (!updateGate.enterBusiness()) {
            synchronized(updateGate) {
                if (updateWakeup?.isActive != true) updateWakeup = scope.launch {
                    kotlinx.coroutines.delay(1000)
                    synchronized(updateGate) { updateWakeup = null }
                    syncPending()
                }
            }
            return
        }
        try {
        syncMutex.withLock {
            val pending = dao.listPending()
            if (pending.isEmpty()) {
                refreshCounts()
                return@withLock
            }

            var okCount = 0
            var failCount = 0
            var blockedCount = 0
            var lastFailure: String? = null
            var lastFailureOwner: PendingOperationEntity? = null

            for (op in pending) {
                // 每条补传前重新确认在线：中途断网应立即停止，剩余保持 pending
                if (!currentlyOnline()) break
                val session = RetrofitClient.sessionSnapshot()
                if (!belongsTo(op, session)) {
                    blockedCount++
                    continue
                }

                if (dao.markSyncing(op.requestId) != 1) continue

                val success = try {
                    replay(op, session)
                } catch (e: CancellationException) {
                    // 留 syncing 由下次启动安全复位，不把取消当成业务拒绝或另一次提交。
                    throw e
                } catch (e: AuthenticationRequired) {
                    lastFailureOwner = op
                    lastFailure = "请使用原账号重新登录或核对权限后重试：${e.message}"
                    check(dao.markFailed(op.requestId, PendingOperationEntity.STATUS_AUTH_REQUIRED,
                        op.attemptCount, lastFailure) == 1)
                    failCount++
                    continue
                } catch (e: RetryLater) {
                    lastFailureOwner = op
                    lastFailure = "服务端暂时限流，稍后重试：${e.message}"
                    markFailure(op, lastFailure, nextRetryAt = e.nextRetryAt)
                    failCount++
                    continue
                } catch (e: BusinessException) {
                    lastFailureOwner = op
                    lastFailure = e.message
                    // 业务类失败：重试无意义，直接判失败并保留服务端给出的中文原因
                    markFailure(op, e.message ?: "服务端拒绝该请求", forceFail = true)
                    failCount++
                    continue
                } catch (e: Exception) {
                    lastFailureOwner = op
                    lastFailure = e.message
                    markFailure(op, e.message ?: "网络不可用")
                    failCount++
                    continue
                }

                if (success) {
                    if (dao.deleteByRequestId(op.requestId) != 1) {
                        throw IOException("已收到成功响应但本地记录未清除，请核对后重试；原幂等键已保留")
                    }
                    okCount++
                } else {
                    // BUG-2026-09-12-008：replay 返回 false 表示"重放无意义"的确定性失败
                    // （当前唯一来源：operation_type 不在已知三类之内）。
                    // 此处**必须**回写状态：上面的 markSyncing 已把该行置为 syncing，
                    // 而 listPending / countPending / countFailed 全部按状态过滤，
                    // syncing 行在三处都取不到 —— 不回写就等于把这条作业从队列中
                    // 抹掉且无人知晓，正是 PendingOperationDao.resetStuckSyncing
                    // 注释所斥的"静默丢数据"（R6：同类消费点已排查）。
                    val error = "未知作业类型 `${op.operationType}`，无法补传"
                    Log.w(TAG, "$error（requestId=${op.requestId}），转 failed 交人工处理")
                    markFailure(op, error, forceFail = true)
                    failCount++
                }
            }

            val reviewCount = refreshCounts()
            val current = RetrofitClient.sessionSnapshot()
            _lastSyncMessage.value = buildSummary(okCount, failCount, pending.size - blockedCount) +
                (if (blockedCount > 0) "；$blockedCount 条归属与当前登录不符，已保留待原账号处理" else "") +
                (if (reviewCount > 0) "；$reviewCount 条历史记录待人工核对归属，禁止自动补传" else "") +
                (lastFailure?.takeIf { lastFailureOwner?.let { belongsTo(it, current) } == true }
                    ?.let { "；$it" } ?: "")
        }
        } finally { updateGate.leaveBusiness() }
    }

    /**
     * 重放单条记录。
     *
     * @return true 表示服务端已确认成功（含幂等回放）；
     *         **false 表示"确定性失败"**，调用方必须回写状态（见 [doSync] 的 else 分支，
     *         BUG-2026-09-12-008）——绝不可直接丢弃返回值。
     * @throws WmsRepository.BusinessException 服务端明确业务拒绝
     */
    private suspend fun replay(op: PendingOperationEntity, session: RetrofitClient.SessionSnapshot): Boolean {
        check(belongsTo(op, session)) { "账号或服务器与原提交不符，已保留记录" }
        val api = apiProvider(session)
        val response: Response<ApiEnvelope<SubmitResult>> = when (op.operationType) {
            PendingOperationEntity.TYPE_INBOUND -> {
                val body = gson.fromJson(op.payloadJson, InboundRequest::class.java)
                api.submitInbound(op.requestId, body)
            }

            PendingOperationEntity.TYPE_OUTBOUND -> {
                val body = gson.fromJson(op.payloadJson, OutboundRequest::class.java)
                api.submitOutbound(op.requestId, body)
            }

            PendingOperationEntity.TYPE_STOCKTAKE -> {
                val body = gson.fromJson(op.payloadJson, StocktakeRequest::class.java)
                api.submitStocktake(op.requestId, body)
            }

            else -> {
                Log.w(TAG, "未知作业类型 ${op.operationType}，按失败处理")
                return false
            }
        }

        if (response.isSuccessful && response.body()?.isOk() == true) return true

        // 区分业务拒绝与临时故障：
        // 4xx 视为业务拒绝（重试无意义），5xx / 网络异常视为临时故障（可重试）
        val code = response.code()
        val msg = runCatching {
            response.body()?.displayMessage() ?: response.errorBody()?.string()?.let {
                gson.fromJson(it, ApiEnvelope::class.java)?.displayMessage()
            }
        }.getOrNull() ?: "服务端返回 $code"

        if (code == 429) {
            val now = System.currentTimeMillis()
            val header = response.headers()["Retry-After"]
            val deadline = header?.toLongOrNull()?.coerceIn(1, (Long.MAX_VALUE - now) / 1000)
                ?.let { now + it * 1000 } ?: header?.let {
                    runCatching { ZonedDateTime.parse(it, DateTimeFormatter.RFC_1123_DATE_TIME)
                        .toInstant().toEpochMilli() }.getOrNull()
                } ?: (now + (30_000L shl op.attemptCount.coerceIn(0, 5)))
            throw RetryLater(msg, maxOf(now + 1000, deadline))
        }
        if (code == 401 || code == 403) throw AuthenticationRequired(msg)
        if (code in 400..499 || response.isSuccessful) {
            throw BusinessException(msg)
        }
        throw Exception(msg)
    }

    private fun belongsTo(op: PendingOperationEntity, session: RetrofitClient.SessionSnapshot): Boolean =
        !op.needsReview && !session.token.isNullOrBlank() && session.userId != null &&
            op.ownerServer != null && op.ownerServer == session.ownerServer && op.ownerUserId == session.userId

    private class AuthenticationRequired(message: String) : Exception(message)
    private class RetryLater(message: String, val nextRetryAt: Long) : Exception(message)

    /** 记录一次失败：累计次数，未达上限回 pending 等下次，达上限转 failed 显式告警。 */
    private suspend fun markFailure(
        op: PendingOperationEntity,
        error: String,
        forceFail: Boolean = false,
        nextRetryAt: Long = 0
    ) {
        val attempts = op.attemptCount + 1
        val exhausted = forceFail || attempts >= PendingOperationEntity.MAX_ATTEMPTS
        val nextStatus =
            if (exhausted) PendingOperationEntity.STATUS_FAILED
            else PendingOperationEntity.STATUS_PENDING
        val retryAt = if (nextRetryAt > 0) nextRetryAt else System.currentTimeMillis() + (30_000L shl op.attemptCount.coerceIn(0, 5))
        check(dao.markFailed(
                requestId = op.requestId,
                nextStatus = nextStatus,
                attemptCount = attempts,
                error = error,
                nextRetryAt = if (exhausted) 0 else retryAt
            ) == 1) { "失败状态未写入，原记录已保留" }

        if (exhausted) {
            Log.w(TAG, "补传放弃（已试 $attempts 次）: ${op.summary} / $error")
        }
    }

    /**
     * 补传结果摘要。
     *
     * 全失败时**不写"请检查网络"**：失败原因可能是业务拒绝（如盘点单已结束）或
     * 未知作业类型，与网络无关；写"检查网络"会引导作业员反复切网络却始终无效
     * （BUG-2026-09-10-011 同类：把非网络原因说成网络原因）。
     * 具体原因由每条记录的 lastError 承载，UI 侧失败列表可见。
     */
    private fun buildSummary(ok: Int, fail: Int, total: Int): String = when {
        total == 0 -> "本次没有可补传记录"
        ok == total -> "已同步 $ok 条离线记录"
        ok > 0 -> "已同步 $ok 条，$fail 条待重试"
        else -> "$fail 条同步失败，已保留在本机待处理"
    }

    /** 人工重试失败记录（UI"重试"按钮）。 */
    fun retryFailed(requestId: String? = null) {
        scope.launch {
            val session = RetrofitClient.sessionSnapshot()
            val server = session.ownerServer ?: return@launch
            val userId = session.userId ?: return@launch
            try {
                dao.listAll().filter { it.isFailed && belongsTo(it, session) &&
                    (requestId == null || it.requestId == requestId) }
                    .forEach { dao.resetToPending(it.requestId, server, userId) }
            } catch (e: CancellationException) { throw e } catch (e: Exception) {
                _lastSyncMessage.value = "重试状态未保存，原记录已保留，请稍后再试"
                Log.e(TAG, "人工重试未完成", e)
                return@launch
            }
            syncPending()
        }
    }

    fun clearMessage() {
        _lastSyncMessage.value = null
    }

    private suspend fun refreshCounts(): Int {
        return try {
            _pendingCount.value = dao.countPending()
            _failedCount.value = dao.countFailed()
            val rows = dao.listAll()
            val session = RetrofitClient.sessionSnapshot()
            _canRetry.value = rows.any { belongsTo(it, session) && (it.isFailed || it.status == PendingOperationEntity.STATUS_PENDING) }
            val now = System.currentTimeMillis()
            val next = rows.filter { belongsTo(it, session) && it.status == PendingOperationEntity.STATUS_PENDING && it.nextRetryAt > now }
                .minOfOrNull { it.nextRetryAt }
            retryWakeup?.cancel()
            retryWakeup = next?.let { deadline -> scope.launch {
                delay(maxOf(1, deadline - System.currentTimeMillis()))
                syncPending()
            } }
            val reviewCount = rows.count { it.needsReview }
            _lastSyncMessage.value = if (reviewCount > 0)
                "$reviewCount 条历史记录待人工核对归属，禁止自动补传"
            else rows.firstOrNull { belongsTo(it, session) && it.isFailed }?.lastError
            reviewCount
        } catch (e: CancellationException) { throw e } catch (e: Exception) {
            _lastSyncMessage.value = "本地队列读取失败，不能确认待同步数量，请保留记录并核对"
            Log.e(TAG, "读取队列计数失败", e)
            0
        }
    }

    companion object {
        private const val TAG = "OfflineQueue"

        @Volatile
        private var instance: OfflineQueueManager? = null

        internal fun getInstance(
            dao: PendingOperationDao,
            apiProvider: (RetrofitClient.SessionSnapshot) -> WmsApiService,
            networkMonitor: NetworkMonitor
        ): OfflineQueueManager {
            return instance ?: synchronized(this) {
                instance ?: OfflineQueueManager(dao, apiProvider, networkMonitor::currentlyOnline,
                    networkMonitor.onlineChanges)
                    .also { instance = it }
            }
        }
    }
}
