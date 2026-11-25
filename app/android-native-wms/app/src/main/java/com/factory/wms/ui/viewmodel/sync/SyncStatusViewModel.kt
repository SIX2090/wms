package com.factory.wms.ui.viewmodel.sync

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.PendingNativeWrite
import com.factory.wms.data.model.QueueDisplayState
import com.factory.wms.data.repository.OfflineQueueManager
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

internal data class GlobalQueueUiState(
    val snapshot: QueueDisplayState? = null,
    val readError: Boolean = false
)

internal data class PendingNativeWriteUiState(
    val sessionGeneration: Long = -1L,
    val rows: List<PendingNativeWrite> = emptyList(),
    val readError: Boolean = false,
    val busy: Boolean = false,
    val message: String? = null
)

/**
 * A-01（2026-11-24）：集中管理全局离线队列与待核实原生写请求状态，
 * 避免 GlobalQueueStatus / PendingNativeWriteStatus 在 Composable 中直接构造 WmsRepository
 * 或发起磁盘/网络读写，并把队列初始化与核实解析移出主线程。
 *
 * 必须保留 public 单参 constructor(application: Application)，供 Android 默认
 * ViewModelProvider.AndroidViewModelFactory 反射实例化。
 */
class SyncStatusViewModel internal constructor(
    application: Application,
    private val queueProvider: (() -> OfflineQueueManager?)? = null,
    private val loadPendingWrites: (suspend () -> List<PendingNativeWrite>)? = null,
    private val verifyPendingWrite: (suspend (String) -> Result<String>)? = null,
    private val acknowledgePendingWrite: (suspend (String, String) -> Unit)? = null,
    private val sessionSnapshotProvider: () -> RetrofitClient.SessionSnapshot = {
        RetrofitClient.sessionSnapshot()
    },
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO
) : AndroidViewModel(application) {

    constructor(app: Application) : this(application = app)

    private val defaultRepository: WmsRepository by lazy { WmsRepository(application) }

    internal val queueUiState: StateFlow<GlobalQueueUiState>
        get() = _queueUiState.asStateFlow()

    internal val pendingWriteUiState: StateFlow<PendingNativeWriteUiState>
        get() = _pendingWriteUiState.asStateFlow()

    @Volatile
    private var queueManager: OfflineQueueManager? = null

    private val _queueUiState = MutableStateFlow(GlobalQueueUiState())
    private val _pendingWriteUiState = MutableStateFlow(PendingNativeWriteUiState())

    private var activeSessionGeneration: Long = -1L
    private var pendingLoadJob: Job? = null

    init {
        viewModelScope.launch {
            val queue = withContext(ioDispatcher) {
                runCatching {
                    if (queueProvider != null) queueProvider.invoke() else defaultRepository.offlineQueue
                }.getOrNull()
            }
            queueManager = queue
            if (queue == null) {
                _queueUiState.value = GlobalQueueUiState(snapshot = null, readError = true)
            } else {
                queue.displayState.collect { snapshot ->
                    _queueUiState.value = GlobalQueueUiState(snapshot = snapshot, readError = false)
                }
            }
        }
        viewModelScope.launch {
            WmsRepository.nativeWriteChanges.collect {
                val generation = activeSessionGeneration
                if (generation >= 0L) {
                    refreshPendingWrites(generation)
                }
            }
        }
    }

    internal fun retryFailed() {
        queueManager?.retryFailed()
    }

    internal fun bindSession(session: RetrofitClient.SessionSnapshot) {
        if (activeSessionGeneration != session.generation) {
            activeSessionGeneration = session.generation
            _pendingWriteUiState.value = PendingNativeWriteUiState(sessionGeneration = session.generation)
        }
        refreshPendingWrites(session.generation)
    }

    private fun refreshPendingWrites(generation: Long) {
        pendingLoadJob?.cancel()
        pendingLoadJob = viewModelScope.launch {
            try {
                val result = withContext(ioDispatcher) {
                    if (loadPendingWrites != null) loadPendingWrites.invoke() else defaultRepository.pendingNativeWrites()
                }
                if (generation == sessionSnapshotProvider().generation && generation == activeSessionGeneration) {
                    _pendingWriteUiState.update { it.copy(rows = result, readError = false) }
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                if (generation == activeSessionGeneration) {
                    _pendingWriteUiState.update { it.copy(readError = true) }
                }
            }
        }
    }

    internal fun verify(session: RetrofitClient.SessionSnapshot, requestId: String) {
        val current = _pendingWriteUiState.value
        if (session.generation != activeSessionGeneration) return
        if (current.sessionGeneration == session.generation && current.busy) return
        _pendingWriteUiState.update { state ->
            if (state.sessionGeneration == session.generation) state.copy(busy = true) else state
        }
        viewModelScope.launch {
            try {
                val result = withContext(ioDispatcher) {
                    if (verifyPendingWrite != null) verifyPendingWrite.invoke(requestId)
                    else defaultRepository.verifyPendingNativeWrite(requestId)
                }
                if (session.generation == sessionSnapshotProvider().generation &&
                    session.generation == activeSessionGeneration
                ) {
                    _pendingWriteUiState.update { state ->
                        if (state.sessionGeneration == session.generation) {
                            state.copy(message = result.getOrElse { err -> err.message ?: "核实未完成，原记录已保留" })
                        } else {
                            state
                        }
                    }
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } finally {
                _pendingWriteUiState.update { state ->
                    if (state.sessionGeneration == session.generation) state.copy(busy = false) else state
                }
            }
        }
    }

    internal fun acknowledge(session: RetrofitClient.SessionSnapshot, operation: String, requestId: String) {
        val current = _pendingWriteUiState.value
        if (session.generation != activeSessionGeneration) return
        if (current.sessionGeneration == session.generation && current.busy) return
        _pendingWriteUiState.update { state ->
            if (state.sessionGeneration == session.generation) state.copy(busy = true) else state
        }
        viewModelScope.launch {
            try {
                withContext(ioDispatcher) {
                    if (acknowledgePendingWrite != null) acknowledgePendingWrite.invoke(operation, requestId)
                    else defaultRepository.acknowledgeNativeWrite(operation, requestId)
                }
                if (session.generation == sessionSnapshotProvider().generation &&
                    session.generation == activeSessionGeneration
                ) {
                    _pendingWriteUiState.update { state ->
                        if (state.sessionGeneration == session.generation) {
                            state.copy(message = "已结束此请求，可以开始新单；请勿再次录入同一笔业务")
                        } else {
                            state
                        }
                    }
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                if (session.generation == activeSessionGeneration) {
                    _pendingWriteUiState.update { state ->
                        if (state.sessionGeneration == session.generation) state.copy(message = error.message) else state
                    }
                }
            } finally {
                _pendingWriteUiState.update { state ->
                    if (state.sessionGeneration == session.generation) state.copy(busy = false) else state
                }
            }
        }
    }
}
