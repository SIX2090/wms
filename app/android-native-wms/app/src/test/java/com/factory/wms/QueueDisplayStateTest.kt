package com.factory.wms

import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.local.PendingOperationEntity
import com.factory.wms.data.model.queueDisplayState
import org.junit.Assert.*
import org.junit.Test

class QueueDisplayStateTest {
    private fun session(user: Int = 1, server: String = "https://synthetic.invalid/", generation: Long = 1) =
        RetrofitClient.SessionSnapshot(server, "synthetic-token", generation, user)

    private fun row(id: String, user: Int?, server: String? = "https://synthetic.invalid",
                    status: String = "pending", review: Boolean = false) = PendingOperationEntity(
        id, "inbound", "{}", "W-A", status = status, ownerServer = server,
        ownerUserId = user, needsReview = review, lastError = "仅 $user 可见的合成失败原因")

    @Test fun accountsAndServersNeverShareCountsOrFailureDetails() {
        val rows = listOf(row("a", 1), row("b", 2, status = "failed"), row("c", 1, "https://other.invalid", "failed"))
        val first = queueDisplayState(rows, session())
        assertEquals(1, first.pendingCount)
        assertEquals(0, first.failedCount)
        assertNull(first.message)
        val second = queueDisplayState(rows, session(2))
        assertEquals(0, second.pendingCount)
        assertEquals(1, second.failedCount)
        assertEquals("仅 2 可见的合成失败原因", second.message)
        assertEquals(0, first.forSession(session(2)).pendingCount)
        assertEquals(0, second.forSession(session(2, generation = 2)).failedCount)
        assertNull(second.forSession(session(1)).message)
    }

    @Test fun legacyRecordsRemainForReviewWithoutInventedOwnershipOrRetry() {
        val legacy = row("legacy", null, null, review = true)
        val display = queueDisplayState(listOf(legacy), session())
        assertTrue(display.needsReview)
        assertFalse(display.canRetry)
        assertEquals(0, display.failedCount)
        assertNull(display.message)
        assertTrue(legacy.needsReview)
        assertNull(legacy.ownerUserId)
    }

    @Test fun syncingAndAuthRequiredRemainVisibleUntilServerAcceptance() {
        val display = queueDisplayState(listOf(row("sending", 1, status = "syncing"),
            row("auth", 1, status = "auth_required")), session())
        assertEquals(1, display.pendingCount)
        assertEquals(1, display.failedCount)
        assertTrue(display.canRetry)
    }
}
