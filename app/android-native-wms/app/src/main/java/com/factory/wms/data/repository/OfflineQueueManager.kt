package com.factory.wms.data.repository

import android.content.Context
import android.util.Log
import com.factory.wms.data.api.ApiEnvelope
import com.factory.wms.data.api.WmsApiService
import com.factory.wms.data.local.PendingOperationDao
import com.factory.wms.data.local.PendingOperationEntity
import com.factory.wms.data.model.InboundRequest
import com.factory.wms.data.model.OutboundRequest
import com.factory.wms.data.model.StocktakeRequest
import com.factory.wms.data.model.SubmitResult
import com.factory.wms.util.NetworkMonitor
import com.google.gson.Gson
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import retrofit2.Response

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
class OfflineQueueManager private constructor(
    context: Context,
    private val dao: PendingOperationDao,
    private val api: WmsApiService,
    private val networkMonitor: NetworkMonitor
) {

    private val appContext = context.applicationContext
    private val gson = Gson()

    /** 补传互斥：网络抖动会频繁触发 onlineChanges，不加锁会并发重放同一批记录。 */
    private val syncMutex = Mutex()

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private val _pendingCount = MutableStateFlow(0)

    /** 待补传条数（UI 展示"待同步 N 条"）。 */
    val pendingCount: StateFlow<Int> = _pendingCount.asStateFlow()

    private val _failedCount = MutableStateFlow(0)

    /** 失败条数（重试耗尽，UI 必须显式告警）。 */
    val failedCount: StateFlow<Int> = _failedCount.asStateFlow()

    private val _lastSyncMessage = MutableStateFlow<String?>(null)

    /** 最近一次补传结果的中文摘要（UI 提示条用）。 */
    val lastSyncMessage: StateFlow<String?> = _lastSyncMessage.asStateFlow()

    init {
        // 启动即复位进程被杀残留的 syncing，否则这些记录永远补传不出去（静默丢数据）
        scope.launch {
            runCatching { dao.resetStuckSyncing() }
            refreshCounts()
        }
        // 网络恢复自动补传
        scope.launch {
            networkMonitor.onlineChanges.collect { online ->
                if (online) syncPending()
            }
        }
    }

    // ───────────────────────── 入队 ─────────────────────────

    /**
     * 入队一条已由人工确认的提交动作。
     *
     * @param requestId 与请求头 `X-Idempotency-Key` 一致（同一次提交必须复用同值）
     * @param warehouseCode 仓库编码；为空时**拒绝入队**——仓库必填（AGENTS.md 第二节），
     *        断网时更不得回退默认仓，否则补传会落到错误仓库。
     * @return true 已入队；false 参数不合法未入队
     */
    fun enqueue(
        requestId: String,
        operationType: String,
        payload: Any,
        warehouseCode: String?,
        summary: String
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

        scope.launch {
            runCatching {
                dao.upsert(
                    PendingOperationEntity(
                        requestId = requestId,
                        operationType = operationType,
                        payloadJson = gson.toJson(payload),
                        warehouseCode = warehouseCode,
                        summary = summary,
                        status = PendingOperationEntity.STATUS_PENDING
                    )
                )
                refreshCounts()
            }.onFailure { Log.e(TAG, "入队失败: ${it.message}", it) }
        }
        return true
    }

    // ───────────────────────── 补传 ─────────────────────────

    /** 手动触发补传（UI"立即重试"按钮与 App 启动时调用）。 */
    fun syncPending() {
        scope.launch { doSync() }
    }

    private suspend fun doSync() {
        // 先确认确实在线：网络回调有系统延迟，避免空发
        if (!networkMonitor.currentlyOnline()) {
            _lastSyncMessage.value = "当前离线，${_pendingCount.value} 条已暂存待同步"
            return
        }

        syncMutex.withLock {
            val pending = runCatching { dao.listPending() }.getOrDefault(emptyList())
            if (pending.isEmpty()) {
                refreshCounts()
                return@withLock
            }

            var okCount = 0
            var failCount = 0

            for (op in pending) {
                // 每条补传前重新确认在线：中途断网应立即停止，剩余保持 pending
                if (!networkMonitor.currentlyOnline()) break

                runCatching { dao.markSyncing(op.requestId) }

                val success = try {
                    replay(op)
                } catch (e: WmsRepository.BusinessException) {
                    // 业务类失败：重试无意义，直接判失败并保留服务端给出的中文原因
                    markFailure(op, e.message ?: "服务端拒绝该请求", forceFail = true)
                    failCount++
                    continue
                } catch (e: Exception) {
                    markFailure(op, e.message ?: "网络不可用")
                    failCount++
                    continue
                }

                if (success) {
                    runCatching { dao.deleteByRequestId(op.requestId) }
                    okCount++
                } else {
                    failCount++
                }
            }

            refreshCounts()
            _lastSyncMessage.value = buildSummary(okCount, failCount, pending.size)
        }
    }

    /**
     * 重放单条记录。
     *
     * @return true 表示服务端已确认成功（含幂等回放）
     * @throws WmsRepository.BusinessException 服务端明确业务拒绝
     */
    private suspend fun replay(op: PendingOperationEntity): Boolean {
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
            response.body()?.displayMessage()
        }.getOrNull() ?: "服务端返回 $code"

        if (code in 400..499) {
            throw WmsRepository.BusinessException(msg)
        }
        throw Exception(msg)
    }

    /** 记录一次失败：累计次数，未达上限回 pending 等下次，达上限转 failed 显式告警。 */
    private suspend fun markFailure(
        op: PendingOperationEntity,
        error: String,
        forceFail: Boolean = false
    ) {
        val attempts = op.attemptCount + 1
        val exhausted = forceFail || attempts >= PendingOperationEntity.MAX_ATTEMPTS
        val nextStatus =
            if (exhausted) PendingOperationEntity.STATUS_FAILED
            else PendingOperationEntity.STATUS_PENDING

        runCatching {
            dao.markFailed(
                requestId = op.requestId,
                nextStatus = nextStatus,
                attemptCount = attempts,
                error = error
            )
        }.onFailure { Log.e(TAG, "标记失败状态出错: ${it.message}", it) }

        if (exhausted) {
            Log.w(TAG, "补传放弃（已试 $attempts 次）: ${op.summary} / $error")
        }
    }

    private fun buildSummary(ok: Int, fail: Int, total: Int): String = when {
        ok == total -> "已同步 $ok 条离线记录"
        ok > 0 -> "已同步 $ok 条，$fail 条待重试"
        else -> "$fail 条同步失败，请检查网络后重试"
    }

    /** 人工重试失败记录（UI"重试"按钮）。 */
    fun retryFailed(requestId: String? = null) {
        scope.launch {
            runCatching {
                if (requestId == null) {
                    dao.listAll()
                        .filter { it.isFailed }
                        .forEach { dao.resetToPending(it.requestId) }
                } else {
                    dao.resetToPending(requestId)
                }
            }
            syncPending()
        }
    }

    fun clearMessage() {
        _lastSyncMessage.value = null
    }

    private suspend fun refreshCounts() {
        runCatching {
            _pendingCount.value = dao.countPending()
            _failedCount.value = dao.countFailed()
        }
    }

    companion object {
        private const val TAG = "OfflineQueue"

        @Volatile
        private var instance: OfflineQueueManager? = null

        fun getInstance(
            context: Context,
            dao: PendingOperationDao,
            api: WmsApiService,
            networkMonitor: NetworkMonitor
        ): OfflineQueueManager {
            return instance ?: synchronized(this) {
                instance ?: OfflineQueueManager(context, dao, api, networkMonitor)
                    .also { instance = it }
            }
        }
    }
}
