package com.factory.wms.ui.viewmodel.report

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.MaterialDto
import com.factory.wms.data.model.StockLedgerItem
import com.factory.wms.data.model.StockLedgerMaterial
import com.factory.wms.data.model.StockLedgerSummary
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.Locale

/**
 * 库存台账日期范围与勾稽纯逻辑（AI-MOB-LDG-F01）：不依赖 Android 运行时，
 * 单元测试直接覆盖（与 StockDailyPager / InOutDetailDateLogic 同一
 * "抽逻辑出来测"模式）。
 *
 * 服务端口径（native_api.py mobile_api_report_stock_ledger）：
 * start_date 缺省 = 全部流水（从建账起算）；end_date 缺省 = 今天；
 * start > end / end > 今天 → 400。客户端翻日期前置钳制，不制造 400。
 */
object StockLedgerRangeLogic {

    /** 显示用开始日期：空串 = 全部流水 */
    fun displayStart(start: String): String = start.ifBlank { "全部" }

    /** 显示用结束日期：空串 = 今天 */
    fun displayEnd(end: String, today: String): String = end.ifBlank { today }

    /** 平移开始日期：空白时从今天起翻；结果不得越过结束日期（结束空白视为今天） */
    fun shiftStart(start: String, end: String, offsetDays: Int, today: String): String {
        val base = start.ifBlank { today }
        val next = InOutDetailDateLogic.shift(base, offsetDays)
        val endBound = end.ifBlank { today }
        return if (next > endBound) endBound else next
    }

    /** 平移结束日期：空白时从今天起翻；上限今天、下限不早于开始日期（开始空白不钳） */
    fun shiftEnd(start: String, end: String, offsetDays: Int, today: String): String {
        val base = end.ifBlank { today }
        var next = InOutDetailDateLogic.shift(base, offsetDays)
        if (next > today) next = today
        if (start.isNotBlank() && next < start) next = start
        return next
    }

    /** 日期选择器选定开始日期后的钳制：不得越过结束日期（结束空白视为今天，防 start>end 400） */
    fun clampPickedStart(picked: String, end: String, today: String): String {
        val endBound = end.ifBlank { today }
        return if (picked > endBound) endBound else picked
    }

    /** 日期选择器选定结束日期后的钳制：上限今天、下限不早于开始日期（开始空白不钳，防 400） */
    fun clampPickedEnd(picked: String, start: String, today: String): String {
        var d = if (picked > today) today else picked
        if (start.isNotBlank() && d < start) d = start
        return d
    }

    /** 勾稽自检：期初 + 本期入库 − 本期出库 = 期末结存（容差 0.005，两位小数口径） */
    fun reconciles(opening: Double, totalIn: Double, totalOut: Double, ending: Double): Boolean {
        return kotlin.math.abs(opening + totalIn - totalOut - ending) < 0.005
    }

    // AI-APP-FIX-403：formatQty 已迁出为 ui/util/Format.kt 的顶层共享实现（千分位）
}

data class StockLedgerReportUiState(
    /** 首次加载 / 刷新中（整页 loading） */
    val isLoading: Boolean = false,
    /** 滚动翻页加载中（列表底部 footer） */
    val isLoadingMore: Boolean = false,
    val error: String? = null,
    /** AI-APP-FIX-201：首屏（列表为空时）查询失败的持久错误（全屏错误态 + 重试） */
    val loadError: String? = null,
    val warehouses: List<WarehouseDto> = emptyList(),
    /** 当前查询仓库：只提供真实仓库（仓库必填，AGENTS.md §二），默认选中第一个 */
    val selectedWarehouseId: String? = null,
    /** 物料选择：台账按单一物料查询（AI-OS-LD-001 口径），未选不查询 */
    val selectedMaterial: MaterialDto? = null,
    /** 物料搜索对话框：关键词 + 候选列表 */
    val materialKeyword: String = "",
    val materialSuggestions: List<MaterialDto> = emptyList(),
    val materialSearching: Boolean = false,
    /** 日期范围（yyyy-MM-dd）：start 空串=全部流水（默认），end 空串=今天 */
    val startDate: String = "",
    val endDate: String = "",
    val summary: StockLedgerSummary? = null,
    val material: StockLedgerMaterial? = null,
    val items: List<StockLedgerItem> = emptyList(),
    val hasMore: Boolean = true,
    /** 结果是否被服务端 5 万行上限截断（BUG-2026-09-07-003 透传通道） */
    val truncated: Boolean = false,
    /** 是否已完成过一次查询（区分"还没查"与"查了确实为空"两种空态） */
    val queried: Boolean = false
)

/**
 * 库存台账 ViewModel（AI-MOB-LDG-F01）。
 * 服务端：GET /api/mobile/report/stock_ledger（只读，零写操作）。
 * 分页状态机复用 [StockDailyPager]（通用翻页语义，已有 StockDailyPagerTest 覆盖）。
 */
class StockLedgerReportViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = WmsRepository(application)
    private val _uiState = MutableStateFlow(StockLedgerReportUiState())
    val uiState: StateFlow<StockLedgerReportUiState> = _uiState.asStateFlow()

    private val pager = StockDailyPager()

    init {
        // BUG-2026-08-24-006 模式：不在 init 自动加载（ViewModel 在 App 启动组合
        // 期即被创建，可能尚未登录）；加载统一由 Screen LaunchedEffect 触发。
    }

    /** 进入页面时加载可选仓库；已加载过则不重复请求。失败静默（不阻断后续查询）。 */
    fun loadWarehouses() {
        if (_uiState.value.warehouses.isNotEmpty()) return
        viewModelScope.launch {
            repository.ensureSession()
            repository.getWarehouses().fold(
                onSuccess = { list ->
                    val current = _uiState.value.selectedWarehouseId
                    // 默认选中第一个真实仓库（与每日报表/库存日报/出入库明细同模式）
                    val nextSelected = if (current.isNullOrBlank() && list.isNotEmpty()) {
                        list.first().id?.toString()
                    } else current
                    _uiState.value = _uiState.value.copy(
                        warehouses = list,
                        selectedWarehouseId = nextSelected
                    )
                },
                onFailure = { /* 静默：仓库列表失败不阻断已选仓查询 */ }
            )
        }
    }

    fun selectWarehouse(warehouseId: String?) {
        if (_uiState.value.selectedWarehouseId == warehouseId) return
        _uiState.value = _uiState.value.copy(selectedWarehouseId = warehouseId)
        refresh()
    }

    // ── 物料选择（台账按单一物料查询，未选物料不发请求）──

    fun updateMaterialKeyword(keyword: String) {
        _uiState.value = _uiState.value.copy(materialKeyword = keyword)
    }

    /** 物料搜索对话框点「搜索」：走既有 /api/material/search（四字段 LIKE） */
    fun searchMaterials() {
        val keyword = _uiState.value.materialKeyword.trim()
        if (keyword.isEmpty()) {
            _uiState.value = _uiState.value.copy(materialSuggestions = emptyList())
            return
        }
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(materialSearching = true, error = null)
            repository.searchMaterial(keyword).fold(
                onSuccess = { list ->
                    _uiState.value = _uiState.value.copy(
                        materialSearching = false,
                        materialSuggestions = list
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        materialSearching = false,
                        error = e.message ?: "搜索物料失败"
                    )
                }
            )
        }
    }

    /** 选定物料并立即查询台账 */
    fun selectMaterial(material: MaterialDto) {
        _uiState.value = _uiState.value.copy(
            selectedMaterial = material,
            materialSuggestions = emptyList(),
            materialKeyword = ""
        )
        refresh()
    }

    /** 换物料：清空当前物料与结果（引导重新选择） */
    fun clearMaterial() {
        pager.reset()
        _uiState.value = _uiState.value.copy(
            selectedMaterial = null,
            summary = null,
            material = null,
            items = emptyList(),
            queried = false,
            truncated = false
        )
    }

    // ── 日期范围（默认全部流水：start 空白；end 空白=今天）──

    fun shiftStartDay(offset: Int) {
        val s = _uiState.value
        val today = InOutDetailDateLogic.today()
        val next = StockLedgerRangeLogic.shiftStart(s.startDate, s.endDate, offset, today)
        if (next == s.startDate) return
        _uiState.value = s.copy(startDate = next)
        refresh()
    }

    fun shiftEndDay(offset: Int) {
        val s = _uiState.value
        val today = InOutDetailDateLogic.today()
        val next = StockLedgerRangeLogic.shiftEnd(s.startDate, s.endDate, offset, today)
        if (next == s.endDate) return
        _uiState.value = s.copy(endDate = next)
        refresh()
    }

    /** 日期选择器选定开始日期（钳制后生效；与翻日期同一 refresh 口径） */
    fun setStartDate(date: String) {
        val s = _uiState.value
        val today = InOutDetailDateLogic.today()
        val next = StockLedgerRangeLogic.clampPickedStart(date, s.endDate, today)
        if (next == s.startDate) return
        _uiState.value = s.copy(startDate = next)
        refresh()
    }

    /** 日期选择器选定结束日期（钳制后生效） */
    fun setEndDate(date: String) {
        val s = _uiState.value
        val today = InOutDetailDateLogic.today()
        val next = StockLedgerRangeLogic.clampPickedEnd(date, s.startDate, today)
        if (next == s.endDate) return
        _uiState.value = s.copy(endDate = next)
        refresh()
    }

    /** 回到「全部流水」（用户决策的默认口径） */
    fun resetAllDates() {
        val s = _uiState.value
        if (s.startDate.isBlank() && s.endDate.isBlank()) return
        _uiState.value = s.copy(startDate = "", endDate = "")
        refresh()
    }

    /** 点搜索物料 / 换仓 / 翻日期 / 下拉刷新：从第 1 页重新拉 */
    fun refresh() {
        val s = _uiState.value
        // 仓库必填（AGENTS.md §二）+ 物料必填（AI-OS-LD-001）：缺一不发请求
        val warehouseId = s.selectedWarehouseId ?: return
        val material = s.selectedMaterial ?: return
        val materialCode = material.code ?: return
        pager.reset()
        loadPage(warehouseId, materialCode, page = 1, append = false)
    }

    /** 滚动到底翻页：只在还有页、不在加载中、且已查出过数据时才拉下一页 */
    fun loadMore() {
        val s = _uiState.value
        if (s.isLoading || s.isLoadingMore || !pager.hasMore || !s.queried) return
        val warehouseId = s.selectedWarehouseId ?: return
        val materialCode = s.selectedMaterial?.code ?: return
        loadPage(warehouseId, materialCode, page = pager.nextPage, append = true)
    }

    private fun loadPage(warehouseId: String, materialCode: String, page: Int, append: Boolean) {
        viewModelScope.launch {
            _uiState.value = if (append) {
                _uiState.value.copy(isLoadingMore = true, error = null)
            } else {
                _uiState.value.copy(isLoading = true, error = null, loadError = null)
            }
            val s = _uiState.value
            repository.getStockLedgerReport(
                warehouseId = warehouseId,
                materialCode = materialCode,
                startDate = s.startDate.takeIf { it.isNotBlank() },
                endDate = s.endDate.takeIf { it.isNotBlank() },
                page = page
            ).fold(
                onSuccess = { data ->
                    pager.onPageLoaded(data.page, data.totalPages)
                    val merged = if (append) _uiState.value.items + data.items else data.items
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isLoadingMore = false,
                        summary = data.summary,
                        material = data.material,
                        items = merged,
                        hasMore = pager.hasMore,
                        truncated = data.truncated == true,
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
