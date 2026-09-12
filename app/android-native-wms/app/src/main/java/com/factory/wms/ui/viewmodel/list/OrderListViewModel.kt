package com.factory.wms.ui.viewmodel.list

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.AlertItemDto
import com.factory.wms.data.model.MobileOrderDto
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * 首页概览下钻列表（AI-MOB-DRILLDOWN-01）。
 *
 * 一个 ViewModel 同时承载三种列表——库存告警 / 入库单 / 出库单，
 * 因为它们的分页加载、状态筛选、错误处理逻辑完全一致，只是端点与
 * 字段不同。用 [ListKind] 区分，避免三份近乎重复的代码。
 */

/** 下钻列表类型。 */
enum class ListKind {
    /** 库存告警（GET /api/mobile/alert/list） */
    ALERT,
    /** 入库单（GET /api/mobile/in_order/list） */
    IN_ORDER,
    /** 出库单（GET /api/mobile/out_order/list） */
    OUT_ORDER
}

data class ListUiState(
    val kind: ListKind = ListKind.ALERT,
    val isLoading: Boolean = false,
    /** 首屏加载（区别于翻页加载），用于首次骨架/菊花 */
    val isFirstLoad: Boolean = true,
    val isLoadingMore: Boolean = false,
    val error: String? = null,
    /** 库存告警列表为空时后端可能带业务提示（如"库存预警未启用"） */
    val notice: String? = null,
    /** 告警项（kind == ALERT 时有值） */
    val alerts: List<AlertItemDto> = emptyList(),
    /** 单据项（kind == IN_ORDER / OUT_ORDER 时有值） */
    val orders: List<MobileOrderDto> = emptyList(),
    val page: Int = 1,
    val totalPages: Int = 0,
    val total: Int = 0,
    /**
     * 状态筛选：null = 全部，pending = 待处理，completed = 已完成。
     * 从首页「待处理单据」进来时初始为 pending（用户要看的就是待处理）。
     */
    val statusFilter: String? = null,
    /** 当前仓库（首页下钻时带入，列表按仓隔离） */
    val warehouseId: String = "",
    /** 当前仓库名（标题展示用） */
    val warehouseName: String = ""
)

class OrderListViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(ListUiState())
    val uiState: StateFlow<ListUiState> = _uiState.asStateFlow()

    /**
     * 用仓库与类型初始化并立即加载。
     * 首页下钻时调用，重复调用同一 (kind, warehouseId) 不重复请求。
     */
    fun start(kind: ListKind, warehouseId: String, warehouseName: String = "") {
        val s = _uiState.value
        if (s.kind == kind && s.warehouseId == warehouseId && !s.isFirstLoad) return
        _uiState.value = ListUiState(
            kind = kind,
            warehouseId = warehouseId,
            warehouseName = warehouseName,
            // 从首页「待处理单据」进来默认只看待处理，用户可切「全部」
            statusFilter = if (kind == ListKind.ALERT) null else "pending",
            isFirstLoad = true
        )
        load(reset = true)
    }

    /** 切换状态筛选（全部 / 待处理 / 已完成）。 */
    fun setStatusFilter(status: String?) {
        if (_uiState.value.statusFilter == status) return
        _uiState.value = _uiState.value.copy(statusFilter = status)
        load(reset = true)
    }

    fun retry() = load(reset = true)

    /** 翻到下一页；已在加载中或已是最后一页则忽略。 */
    fun loadMore() {
        val s = _uiState.value
        if (s.isLoadingMore || s.isLoading) return
        if (s.page >= s.totalPages) return
        load(reset = false)
    }

    private fun load(reset: Boolean) {
        val s = _uiState.value
        if (s.warehouseId.isBlank()) {
            _uiState.value = s.copy(
                isFirstLoad = false,
                isLoading = false,
                error = "缺少仓库上下文"
            )
            return
        }
        val nextPage = if (reset) 1 else s.page + 1
        viewModelScope.launch {
            _uiState.value = s.copy(
                isLoading = true,
                isFirstLoad = reset && s.alerts.isEmpty() && s.orders.isEmpty(),
                isLoadingMore = !reset,
                error = if (reset) null else s.error
            )
            when (s.kind) {
                ListKind.ALERT -> loadAlerts(nextPage, reset)
                ListKind.IN_ORDER -> loadOrders(nextPage, reset, inbound = true)
                ListKind.OUT_ORDER -> loadOrders(nextPage, reset, inbound = false)
            }
        }
    }

    private suspend fun loadAlerts(page: Int, reset: Boolean) {
        val s = _uiState.value
        repository.getAlertList(warehouseId = s.warehouseId, page = page).fold(
            onSuccess = { data ->
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isFirstLoad = false,
                    isLoadingMore = false,
                    // 首页已按仓库过滤，这里是同一口径的明细，不再叠加
                    alerts = if (reset) data.items else _uiState.value.alerts + data.items,
                    page = data.page,
                    totalPages = data.totalPages,
                    total = data.total,
                    error = null,
                    notice = if (data.items.isEmpty() && data.total == 0) {
                        "本仓暂无低于最低库存的物料"
                    } else null
                )
            },
            onFailure = { e -> onLoadFailed(e.message, reset) }
        )
    }

    private suspend fun loadOrders(page: Int, reset: Boolean, inbound: Boolean) {
        val s = _uiState.value
        val result = if (inbound) {
            repository.getInOrderList(
                warehouseId = s.warehouseId, status = s.statusFilter, page = page
            )
        } else {
            repository.getOutOrderList(
                warehouseId = s.warehouseId, status = s.statusFilter, page = page
            )
        }
        result.fold(
            onSuccess = { data ->
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isFirstLoad = false,
                    isLoadingMore = false,
                    orders = if (reset) data.items else _uiState.value.orders + data.items,
                    page = data.page,
                    totalPages = data.totalPages,
                    total = data.total,
                    error = null
                )
            },
            onFailure = { e -> onLoadFailed(e.message, reset) }
        )
    }

    private fun onLoadFailed(message: String?, reset: Boolean) {
        _uiState.value = _uiState.value.copy(
            isLoading = false,
            isFirstLoad = false,
            isLoadingMore = false,
            // 翻页失败不清空已有数据，只提示；首屏失败才置 error
            error = if (reset) (message ?: "加载失败") else _uiState.value.error
        )
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
