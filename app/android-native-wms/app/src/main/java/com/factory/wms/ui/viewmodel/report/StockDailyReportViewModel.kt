package com.factory.wms.ui.viewmodel.report

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.StockDailyItem
import com.factory.wms.data.model.StockDailySummary
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

/**
 * 库存日报分页状态机（AI-MOB-RPT-F02）：纯 Kotlin 逻辑，不依赖 Android 运行时，
 * 单元测试直接覆盖（与 OfflineQueueStateMachine 同一"抽逻辑出来测"模式）。
 *
 * 语义：nextPage 从 1 开始；服务端返回第 N 页后 nextPage = N+1；
 * totalPages=0 表示"尚未拉过任何一页"（此时 hasMore=true，允许首次加载）。
 */
class StockDailyPager {
    var nextPage: Int = 1
        private set
    var totalPages: Int = 0
        private set

    /** 是否还有页可拉：未拉过（totalPages=0）或下一页不超过总页数 */
    val hasMore: Boolean
        get() = totalPages == 0 || nextPage <= totalPages

    /** 记录一页加载成功：fetchedPage 为服务端返回的 page 字段 */
    fun onPageLoaded(fetchedPage: Int, totalPages: Int) {
        require(fetchedPage >= 1) { "fetchedPage 必须 >= 1" }
        require(totalPages >= 0) { "totalPages 必须 >= 0" }
        nextPage = fetchedPage + 1
        this.totalPages = totalPages
    }

    /** 换仓/换关键字/刷新时重置，从第 1 页重新拉 */
    fun reset() {
        nextPage = 1
        totalPages = 0
    }
}

data class StockDailyReportUiState(
    /** 首次加载 / 下拉刷新中（整页 loading） */
    val isLoading: Boolean = false,
    /** 滚动翻页加载中（列表底部 footer） */
    val isLoadingMore: Boolean = false,
    val error: String? = null,
    /** 当前查询日期（yyyy-MM-dd）。AI-MOB-RPT-F03：可翻日期，历史日期为当天收市结存 */
    val date: String = "",
    /** 日期是否处于「今天模式」：true 时每次刷新自动跟随系统当天（跨天不重启也生效） */
    val dateIsToday: Boolean = true,
    /** 数据截止时间（服务端下发 hh:mm，只用于显示） */
    val generatedAt: String? = null,
    val warehouses: List<WarehouseDto> = emptyList(),
    /**
     * 当前查询仓库：只提供真实仓库（不含"默认仓库"/"全部仓库"——结存跨仓
     * 无意义），进入页加载仓库后若为空则默认选中第一个仓库（与每日报表同模式）
     */
    val selectedWarehouseId: String? = null,
    val keyword: String = "",
    val summary: StockDailySummary? = null,
    val items: List<StockDailyItem> = emptyList(),
    val hasMore: Boolean = true,
    /** 是否已完成过一次查询（区分"还没查"与"查了确实为空"两种空态） */
    val queried: Boolean = false
)

/**
 * 库存日报 ViewModel（AI-MOB-RPT-F02）：按仓库查看当天各物料结存明细。
 * 服务端：GET /api/mobile/report/stock_daily（只读，零写操作）。
 */
class StockDailyReportViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = WmsRepository(application)
    private val _uiState = MutableStateFlow(StockDailyReportUiState())
    val uiState: StateFlow<StockDailyReportUiState> = _uiState.asStateFlow()

    private val pager = StockDailyPager()
    private val apiDateFormat = SimpleDateFormat("yyyy-MM-dd", Locale.US)

    init {
        // BUG-2026-08-24-006 模式：不在 init 自动加载（ViewModel 在 App 启动组合
        // 期即被创建，可能尚未登录）；加载统一由 Screen LaunchedEffect 触发。
        _uiState.value = _uiState.value.copy(date = apiDateFormat.format(Date()))
    }

    /** 进入页面时加载可选仓库；已加载过则不重复请求。失败静默（不阻断查询）。 */
    fun loadWarehouses() {
        if (_uiState.value.warehouses.isNotEmpty()) return
        viewModelScope.launch {
            repository.ensureSession()
            repository.getWarehouses().fold(
                onSuccess = { list ->
                    val current = _uiState.value.selectedWarehouseId
                    // 默认选中第一个真实仓库（与每日报表页同模式），并立即查询
                    val nextSelected = if (current.isNullOrBlank() && list.isNotEmpty()) {
                        list.first().id?.toString()
                    } else current
                    _uiState.value = _uiState.value.copy(
                        warehouses = list,
                        selectedWarehouseId = nextSelected
                    )
                    if (nextSelected != current) refresh()
                },
                onFailure = { /* 静默：仓库列表失败不阻断按已选仓查询 */ }
            )
        }
    }

    fun selectWarehouse(warehouseId: String?) {
        if (_uiState.value.selectedWarehouseId == warehouseId) return
        _uiState.value = _uiState.value.copy(selectedWarehouseId = warehouseId)
        refresh()
    }

    /** 搜索框输入时只更新关键字，点「搜索」才发请求（避免逐字打满接口） */
    fun updateKeyword(keyword: String) {
        _uiState.value = _uiState.value.copy(keyword = keyword)
    }

    /** 点搜索 / 换仓 / 下拉刷新：从第 1 页重新拉 */
    fun refresh() {
        // BUG-2026-09-10-003 模式：App 跨天未重启时进入页面仍按旧日期展示，
        // 处于今天模式时每次刷新前校正为系统当天（历史翻页模式不强制校正）
        if (_uiState.value.dateIsToday) {
            val today = apiDateFormat.format(Date())
            if (today != _uiState.value.date) {
                _uiState.value = _uiState.value.copy(date = today)
            }
        }
        // 仓库必填（AGENTS.md §二）：未选仓不发请求（不拉全量、不回退默认仓）
        val warehouseId = _uiState.value.selectedWarehouseId ?: return
        pager.reset()
        loadPage(warehouseId, page = 1, append = false)
    }

    /** 日期前后翻页（AI-MOB-RPT-F03）：翻到历史日期看当天收市结存；不允许翻到未来 */
    fun shiftDay(offset: Int) {
        val current = apiDateFormat.parse(_uiState.value.date) ?: Date()
        val cal = Calendar.getInstance().apply {
            time = current
            add(Calendar.DAY_OF_YEAR, offset)
        }
        val today = apiDateFormat.format(Date())
        val next = apiDateFormat.format(cal.time)
        if (next > today) return // 服务端对未来日期 400，此处直接钳制
        _uiState.value = _uiState.value.copy(date = next, dateIsToday = next == today)
        refresh()
    }

    /** 回到今天并切回「今天模式」（跨天自动跟随恢复） */
    fun resetToday() {
        val today = apiDateFormat.format(Date())
        if (_uiState.value.date == today && _uiState.value.dateIsToday) return
        _uiState.value = _uiState.value.copy(date = today, dateIsToday = true)
        refresh()
    }

    /** 滚动到底翻页：只在还有页、不在加载中、且已查出过数据时才拉下一页 */
    fun loadMore() {
        val s = _uiState.value
        if (s.isLoading || s.isLoadingMore || !pager.hasMore || !s.queried) return
        val warehouseId = s.selectedWarehouseId ?: return
        loadPage(warehouseId, page = pager.nextPage, append = true)
    }

    private fun loadPage(warehouseId: String, page: Int, append: Boolean) {
        viewModelScope.launch {
            _uiState.value = if (append) {
                _uiState.value.copy(isLoadingMore = true, error = null)
            } else {
                _uiState.value.copy(isLoading = true, error = null)
            }
            repository.getStockDailyReport(
                warehouseId = warehouseId,
                keyword = _uiState.value.keyword,
                page = page,
                date = _uiState.value.date.takeIf { it.isNotBlank() }
            ).fold(
                onSuccess = { data ->
                    pager.onPageLoaded(data.page, data.totalPages)
                    val merged = if (append) _uiState.value.items + data.items else data.items
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isLoadingMore = false,
                        generatedAt = data.generatedAt,
                        summary = data.summary,
                        items = merged,
                        hasMore = pager.hasMore,
                        queried = true
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isLoadingMore = false,
                        error = e.message ?: "加载失败"
                    )
                }
            )
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
