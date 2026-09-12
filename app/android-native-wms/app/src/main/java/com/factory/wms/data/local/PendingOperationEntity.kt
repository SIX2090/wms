package com.factory.wms.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * AI-MOB-OFFLINE-01：离线待提交作业队列。
 *
 * ## 为什么需要它
 *
 * 此前 App 的"离线"只有提示没有降级：`OperationLogEntity` 是**提交成功后**的审计日志，
 * 网络不可用时提交直接失败、已扫明细作废。仓库货架深处/地下室信号弱是常态，
 * 作业员扫完一单点提交失败就得回到有信号处重扫——这是手机 WMS 最劝退的体验。
 *
 * 本表把**人工已确认的提交动作**本地暂存，网络恢复后自动补传。
 *
 * ## 关键设计：主键 = requestId = X-Idempotency-Key
 *
 * 重放时携带**同一个** `X-Idempotency-Key` 请求头，后端 `mobile_api_idempotent`
 * （见 `app/app.py`）命中历史成功记录会直接回放原响应。因此即使用户在弱网下
 * 反复点击、或补传与手动提交并发，**都不会产生重复单据**。
 * 用主键唯一约束做本地去重，同一 requestId 重复入队只会覆盖，不会新增。
 *
 * ## 边界（AGENTS.md §一 / R5）
 *
 * 本队列**只承载用户已点击"提交"的动作**。AI 识别 / 语音生成的草稿走原流程，
 * 必须经人工确认后才可能进入本队列——绝不允许 AI 结果绕过人工确认直接落库。
 */
@Entity(
    tableName = "pending_operations",
    indices = [
        Index(value = ["status", "created_at"]),
        Index(value = ["operation_type"])
    ]
)
data class PendingOperationEntity(

    /**
     * 幂等键，同时作为主键。
     * 该值会原样作为 `X-Idempotency-Key` 发送，重放时保持不变。
     */
    @PrimaryKey
    @ColumnInfo(name = "request_id")
    val requestId: String,

    /** 作业类型：inbound / outbound / stocktake（对应后端三个提交端点）。 */
    @ColumnInfo(name = "operation_type")
    val operationType: String,

    /**
     * 请求体 JSON（Gson 序列化后的 *Request 对象）。
     *
     * 入队即固化，补传时**原样重放**，不做任何字段改写——
     * 尤其是 warehouse_code：断网时用户选定的仓库必须原样送达，
     * 不允许回退到默认仓或"全部仓库"口径（AGENTS.md 第二节）。
     */
    @ColumnInfo(name = "payload_json")
    val payloadJson: String,

    /**
     * 仓库编码（冗余存储，仅供列表展示与提交前校验）。
     * 为空表示该请求未带仓库——仓库必填规则下应拒绝入队。
     */
    @ColumnInfo(name = "warehouse_code")
    val warehouseCode: String? = null,

    /** 人类可读摘要，如「入库 3 项 · 主仓」，用于 UI 展示待同步列表。 */
    @ColumnInfo(name = "summary")
    val summary: String = "",

    /**
     * 队列状态。
     * - [STATUS_PENDING]：待补传（网络恢复后自动尝试）
     * - [STATUS_SYNCING]：补传中（进程被杀后残留可被重置回 pending）
     * - [STATUS_FAILED]：重试耗尽，**必须显式告警**，等待人工处理
     *
     * 补传成功即删除记录，故无"已完成"持久态。
     */
    @ColumnInfo(name = "status")
    val status: String = STATUS_PENDING,

    /** 已尝试次数，达 [MAX_ATTEMPTS] 转 failed。 */
    @ColumnInfo(name = "attempt_count")
    val attemptCount: Int = 0,

    /**
     * 最近一次失败原因（中文，直接面向作业员）。
     * 禁止静默丢弃失败——这是与 `operation_logs` 的 `onFailure = { }` 的关键区别。
     */
    @ColumnInfo(name = "last_error")
    val lastError: String? = null,

    /** 入队时间，补传按此升序保证与用户操作顺序一致。 */
    @ColumnInfo(name = "created_at")
    val createdAt: Long = System.currentTimeMillis(),

    /** 最后状态变更时间。 */
    @ColumnInfo(name = "updated_at")
    val updatedAt: Long = System.currentTimeMillis()
) {

    val isFailed: Boolean get() = status == STATUS_FAILED

    companion object {
        const val STATUS_PENDING = "pending"
        const val STATUS_SYNCING = "syncing"
        const val STATUS_FAILED = "failed"

        const val TYPE_INBOUND = "inbound"
        const val TYPE_OUTBOUND = "outbound"
        const val TYPE_STOCKTAKE = "stocktake"

        /**
         * 最大重试次数。
         *
         * 取 5 次是权衡：弱网抖动重试 2-3 次通常能过，而无限重试会在真正
         * 的业务/权限问题（如 token 失效）上无谓烧电、且掩盖真实故障。
         * 达上限转 failed 并显式告警，交给人工判断，符合 R5"失败必须让人知道"。
         */
        const val MAX_ATTEMPTS = 5
    }
}
