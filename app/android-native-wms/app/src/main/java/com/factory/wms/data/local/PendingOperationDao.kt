package com.factory.wms.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

/**
 * AI-MOB-OFFLINE-01：离线待提交作业队列 DAO。
 *
 * 设计约束：
 * - 入队用 [OnConflictStrategy.REPLACE]：同一 requestId 重复入队只覆盖，不产生重复单据；
 * - 补传取用按 `created_at ASC`，保证与用户实际操作顺序一致（先扫的先提交，
 *   避免同一物料的入库/出库顺序颠倒导致账实不符）；
 * - 补传成功即 [deleteByRequestId]（队列保持精简），失败才留记录并累计次数。
 */
@Dao
interface PendingOperationDao {

    /** 入队（同 requestId 覆盖，幂等）。 */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(operation: PendingOperationEntity)

    /**
     * 取待补传记录（pending），按入队顺序升序。
     *
     * 不含 syncing：进程被杀后残留的 syncing 记录由 [resetStuckSyncing] 复位，
     * 避免它们永远卡住不被重试。
     */
    @Query("SELECT * FROM pending_operations WHERE status = :pending ORDER BY created_at ASC")
    suspend fun listPending(pending: String = PendingOperationEntity.STATUS_PENDING): List<PendingOperationEntity>

    /** 全部记录（含 failed），供 UI 展示与人工重试。 */
    @Query("SELECT * FROM pending_operations ORDER BY created_at ASC")
    suspend fun listAll(): List<PendingOperationEntity>

    /** 待补传条数，用于 badge 与首页提示。 */
    @Query("SELECT COUNT(*) FROM pending_operations WHERE status = :pending")
    suspend fun countPending(pending: String = PendingOperationEntity.STATUS_PENDING): Int

    /** 失败条数（重试耗尽，需人工介入）。 */
    @Query("SELECT COUNT(*) FROM pending_operations WHERE status = :failed")
    suspend fun countFailed(failed: String = PendingOperationEntity.STATUS_FAILED): Int

    @Query("SELECT * FROM pending_operations WHERE request_id = :requestId LIMIT 1")
    suspend fun getByRequestId(requestId: String): PendingOperationEntity?

    /** 补传成功：直接删除（无"已完成"持久态）。 */
    @Query("DELETE FROM pending_operations WHERE request_id = :requestId")
    suspend fun deleteByRequestId(requestId: String)

    /**
     * 进程被杀导致残留在 syncing 的记录复位为 pending。
     *
     * App 启动时调用一次：这些记录既不会被 listPending 取到（状态不符）也不会
     * 自动消失，不复位就永远补传不出去——静默丢数据，正是本任务要根治的问题。
     */
    @Query("UPDATE pending_operations SET status = :pending, updated_at = :now WHERE status = :syncing")
    suspend fun resetStuckSyncing(
        pending: String = PendingOperationEntity.STATUS_PENDING,
        syncing: String = PendingOperationEntity.STATUS_SYNCING,
        now: Long = System.currentTimeMillis()
    )

    /** 标记补传中。 */
    @Query("UPDATE pending_operations SET status = :syncing, updated_at = :now WHERE request_id = :requestId")
    suspend fun markSyncing(
        requestId: String,
        now: Long = System.currentTimeMillis(),
        syncing: String = PendingOperationEntity.STATUS_SYNCING
    )

    /** 补传失败：累计次数、记录原因、按是否达上限落 pending 或 failed。 */
    @Query(
        """
        UPDATE pending_operations
        SET status = :nextStatus, attempt_count = :attemptCount, last_error = :error, updated_at = :now
        WHERE request_id = :requestId
        """
    )
    suspend fun markFailed(
        requestId: String,
        nextStatus: String,
        attemptCount: Int,
        error: String?,
        now: Long = System.currentTimeMillis()
    )

    /**
     * 人工把 failed 记录重置为 pending 以便重试。
     * 同时清零次数，避免刚重置就被下一次失败立刻打回 failed。
     */
    @Query(
        """
        UPDATE pending_operations
        SET status = :pending, attempt_count = 0, last_error = NULL, updated_at = :now
        WHERE request_id = :requestId
        """
    )
    suspend fun resetToPending(
        requestId: String,
        now: Long = System.currentTimeMillis(),
        pending: String = PendingOperationEntity.STATUS_PENDING
    )

    @Query("DELETE FROM pending_operations")
    suspend fun deleteAll()
}
