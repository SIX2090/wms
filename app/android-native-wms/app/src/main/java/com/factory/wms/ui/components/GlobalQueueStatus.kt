package com.factory.wms.ui.components

import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.repository.WmsRepository

/** Share the existing queue's read-only status outside the scan screens. */
@Composable
internal fun GlobalQueueStatus(session: RetrofitClient.SessionSnapshot) {
    val context = LocalContext.current.applicationContext
    val queue = remember(context) { runCatching { WmsRepository(context).offlineQueue }.getOrNull() }
    if (queue == null) {
        PendingSyncBanner(0, 0, {}, readError = true, canRetry = false,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp))
        return
    }
    val snapshot by queue.displayState.collectAsState()
    val display = snapshot.forSession(session)
    PendingSyncBanner(display.pendingCount, display.failedCount, { queue.retryFailed() },
        message = display.message, canRetry = display.canRetry,
        needsReview = display.needsReview, readError = display.readError,
        modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp))
}
