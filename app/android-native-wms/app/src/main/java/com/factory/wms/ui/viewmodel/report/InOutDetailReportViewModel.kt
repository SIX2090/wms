package com.factory.wms.ui.viewmodel.report

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.InOutDetailItem
import com.factory.wms.data.model.InOutDetailSummary
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
 * 出入库明细日期范围纯逻辑（AI-MOB-RPT-F01 收尾）：不依赖 Android 运行时，
 * 单元测试直接覆盖（与 StockDailyPager 同一"抽逻辑出来测"模式）。
 *
 * 服务端口径（native_api.py mobile_api_report_in_out_detail）：
 * start_date > end_date → 400；end_date > 今天 → 400。客户端翻日期时前置钳制，
 * 不给用户制造出 400 的机会。
 */
object InOutDetailDateLogic {
    private val ymd = SimpleDateFormat("yyyy-MM-dd", Locale.US)

    fun today(): String = ymd.format(Date())

    /** 把 yyyy-MM-dd 平移 offsetDays 天（跨月/跨年由 Calendar 处理）
     *
     * ⚠️ 解析失败必须兜住：`SimpleDateFormat.parse` 对空串/非法串是**抛
     * ParseException**，不是返回 null——只写 `ymd.parse(s) ?: Date()` 兜不住
     * （CI #658 `InOutDetailDateLogicTest` 实测 ParseException）。日期串来自
     * UI 状态，空/脏值不应让整页崩，故回退到今天。
     */
    fun shift(dateStr: String, offsetDays: Int): String {
        val base = runCatching { ymd.parse(dateStr) }.getOrNull() ?: Date()
        val cal = Calendar.getInstance().apply {
            time = base
            add(Calendar.DAY_OF_YEAR, offsetDays)
        }
        return ymd.format(cal.time)
    }

    /** 平移开始日期：不允许越过当前结束日期（否则服务端 400） */
    fun shiftStart(start: String, end: String, offsetDays: Int): String {
        val next = shift(start, offsetDays)
        return if (next > end) end else next
    }

    /** 平移结束日期：上限今天（未来日期服务端 400），下限不早于开始日期 */
    fun shiftEnd(start: String, end: String, offsetDays: Int, todayStr: String): String {
        var next = shift(end, offsetDays)
        if (next > todayStr) next = todayStr
        if (next < start) next = start
        return next
    }
}

/** 方向过滤：与服务端 direction 参数一一对应 */
enum class InOutDirection(val apiValue: String, val label: String) {
    ALL("all", "全部"),
    IN("in", "入库"),
    OUT("out", "出库")
}

data class InOutDetailReportUiState(
    /** 首次加载 / 刷新中（整页 loading） */
    val isLoading: Boolean = false,
    /** 滚动翻页加载中（列表底部 footer） */
    val isLoadingMore: Boolean = false,
    val error: String? = null,
    /** AI-APP-FIX-201：首屏（列表为空时）查询失败的持久错误（全屏错误态 + 重试） */
    val loadError: String? = null,
    /** 日期范围（yyyy-MM-dd），默认都是今天 */
    val startDate: String = "",
    val endDate: String = "",
    val warehouses: List<WarehouseDto> = emptyList(),
    /**
     * 当前查询仓库：只提供真实仓库（仓库必填，AGENTS.md §二；与每日报表/
     * 库存日报同模式，进入页加载仓库后默认选中第一个）
     */
    val selectedWarehouseId: String? = null,
    val keyword: String = "",
    val direction: InOutDirection = InOutDirection.ALL,
    val summary: InOutDetailSummary? = null,
    val items: List<InOutDetailItem> = emptyList(),
    val hasMore: Boolean = true,
    /** 是否已完成过一次查询（区分"还没查"与"查了确实为空"两种空态） */
    val queried: Boolean = false
)

/**
 * 出入库明细 ViewModel（AI-MOB-RPT-F01 收尾：Android 消费页）。
 * 服务端：GET /api/mobile/report/in_out_detail（只读，零写操作）。
 * 分页状态机复用 [StockDailyPager]（通用翻页语义，已有 StockDailyPagerTest 覆盖）。
 */
class InOutDetailReportViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = WmsRepository(application)
    private val _uiState = MutableStateFlow(InOutDetailReportUiState())
    val uiState: StateFlow<InOutDetailReportUiState> = _uiState.asStateFlow()

    private val pager = StockDailyPager()

    init {
        // BUG-2026-08-24-006 模式：不在 init 自动加载（ViewModel 在 App 启动组合
        // 期即被创建，可能尚未登录）；加载统一由 Screen LaunchedEffect 触发。
        val today = InOutDetailDateLogic.today()
        _uiState.value = _uiState.value.copy(startDate = today, endDate = today)
    }

    /** 进入页面时加载可选仓库；已加载过则不重复请求。失败静默（不阻断查询）。 */
    fun loadWarehouses() {
        if (_uiState.value.warehouses.isNotEmpty()) return
        viewModelScope.launch {
            repository.ensureSession()
            repository.getWarehouses().fold(
                onSuccess = { list ->
                    val current = _uiState.value.selectedWarehouseId
                    // 默认选中第一个真实仓库（与每日报表/库存日报同模式），并立即查询
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

    fun selectDirection(direction: InOutDirection) {
        if (_uiState.value.direction == direction) return
        _uiState.value = _uiState.value.copy(direction = direction)
        refresh()
    }

    /** 开始日期前后翻：不允许越过结束日期（服务端 400 前置钳制） */
    fun shiftStartDay(offset: Int) {
        val s = _uiState.value
        val next = InOutDetailDateLogic.shiftStart(s.startDate, s.endDate, offset)
        if (next == s.startDate) return
        _uiState.value = s.copy(startDate = next)
        refresh()
    }

    /** 结束日期前后翻：上限今天、下限开始日期（服务端 400 前置钳制） */
    fun shiftEndDay(offset: Int) {
        val s = _uiState.value
        val next = InOutDetailDateLogic.shiftEnd(
            s.startDate, s.endDate, offset, InOutDetailDateLogic.today()
        )
        if (next == s.endDate) return
        _uiState.value = s.copy(endDate = next)
        refresh()
    }

    /** 回到「只看今天」 */
    fun resetToday() {
        val today = InOutDetailDateLogic.today()
        val s = _uiState.value
        if (s.startDate == today && s.endDate == today) return
        _uiState.value = s.copy(startDate = today, endDate = today)
        refresh()
    }

    /** AI-APP-FIX-402：DatePicker 直接选开始日（钳制同 shiftStartDay：不越过结束日期） */
    fun setStartDate(date: String) {
        val s = _uiState.value
        if (date > s.endDate || date == s.startDate) return
        _uiState.value = s.copy(startDate = date)
        refresh()
    }

    /** AI-APP-FIX-402：DatePicker 直接选结束日（钳制同 shiftEndDay：上限今天、下限开始日期） */
    fun setEndDate(date: String) {
        val s = _uiState.value
        var next = date
        val todayStr = InOutDetailDateLogic.today()
        if (next > todayStr) next = todayStr
        if (next < s.startDate || next == s.endDate) return
        _uiState.value = s.copy(endDate = next)
        refresh()
    }

    /** 点搜索 / 换仓 / 换方向 / 翻日期 / 下拉刷新：从第 1 页重新拉 */
    fun refresh() {
        // 仓库必填（AGENTS.md §二）：未选仓不发请求（不拉全量、不回退默认仓）
        val warehouseId = _uiState.value.selectedWarehouseId ?: return
        pager.reset()
        loadPage(warehouseId, page = 1, append = false)
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
                _uiState.value.copy(isLoading = true, error = null, loadError = null)
            }
            val s = _uiState.value
            repository.getInOutDetailReport(
                warehouseId = warehouseId,
                startDate = s.startDate.takeIf { it.isNotBlank() },
                endDate = s.endDate.takeIf { it.isNotBlank() },
                direction = s.direction.apiValue,
                keyword = s.keyword,
                page = page
            ).fold(
                onSuccess = { data ->
                    pager.onPageLoaded(data.page, data.totalPages)
                    val merged = if (append) _uiState.value.items + data.items else data.items
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isLoadingMore = false,
                        summary = data.summary,
                        items = merged,
                        hasMore = pager.hasMore,
                        queried = true
                    )
                },
                onFailure = { e ->
                    // AI-APP-FIX-201：首屏失败（列表还空着）→ 全屏错误态；
                    // 带数据刷新/翻页失败 → Snackbar，保留已有数据。
                    if (!append && _uiState.value.items.isEmpty()) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            isLoadingMore = false,
                            loadError = e.message ?: "加载失败"
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            isLoadingMore = false,
                            error = e.message ?: "加载失败"
                        )
                    }
                }
            )
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
