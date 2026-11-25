package com.factory.wms.ui.components

import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.ui.viewmodel.sync.SyncStatusViewModel

/** Share the existing queue's read-only status outside the scan screens. */
@Composable
internal fun GlobalQueueStatus(
    session: RetrofitClient.SessionSnapshot,
    syncViewModel: SyncStatusViewModel = viewModel()
) {
    PendingNativeWriteStatus(session, syncViewModel)
    val queueState by syncViewModel.queueUiState.collectAsState()
    if (queueState.readError) {
        PendingSyncBanner(0, 0, {}, readError = true, canRetry = false,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp))
        return
    }
    val snapshot = queueState.snapshot ?: return
    val display = snapshot.forSession(session)
    PendingSyncBanner(display.pendingCount, display.failedCount, { syncViewModel.retryFailed() },
        message = display.message, canRetry = display.canRetry,
        needsReview = display.needsReview, readError = display.readError,
        modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp))
}
