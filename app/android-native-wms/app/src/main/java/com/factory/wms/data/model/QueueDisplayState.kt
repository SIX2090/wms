package com.factory.wms.data.model

import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.local.PendingOperationEntity

/** Read-only display projection; it does not select or modify requests for replay. */
internal data class QueueDisplayState(
    val server: String? = null,
    val userId: Int? = null,
    val generation: Long = -1,
    val pendingCount: Int = 0,
    val failedCount: Int = 0,
    val needsReview: Boolean = false,
    val readError: Boolean = false,
    val message: String? = null,
    val canRetry: Boolean = false
) {
    fun forSession(session: RetrofitClient.SessionSnapshot): QueueDisplayState =
        if (!session.token.isNullOrBlank() && server == session.ownerServer &&
            userId == session.userId && generation == session.generation) this else QueueDisplayState()
}

internal fun queueDisplayState(
    rows: List<PendingOperationEntity>,
    session: RetrofitClient.SessionSnapshot
): QueueDisplayState {
    if (session.token.isNullOrBlank() || session.ownerServer == null || session.userId == null) return QueueDisplayState()
    val owned = rows.filter { !it.needsReview && it.ownerServer == session.ownerServer && it.ownerUserId == session.userId }
    val pending = owned.count { it.status == PendingOperationEntity.STATUS_PENDING || it.status == PendingOperationEntity.STATUS_SYNCING }
    val failed = owned.filter { it.isFailed }
    // Unassigned legacy records get only a generic notice; never expose another account's details.
    val review = rows.any { it.needsReview &&
        ((it.ownerServer == null && it.ownerUserId == null) ||
            (it.ownerServer == session.ownerServer && it.ownerUserId == session.userId)) }
    return QueueDisplayState(session.ownerServer, session.userId, session.generation,
        pending, failed.size, review, message = failed.firstOrNull()?.lastError,
        canRetry = owned.any { it.isFailed || it.status == PendingOperationEntity.STATUS_PENDING })
}
