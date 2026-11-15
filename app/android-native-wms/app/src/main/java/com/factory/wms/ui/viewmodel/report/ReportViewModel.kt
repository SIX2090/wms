package com.factory.wms.ui.viewmodel.report

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.DailyReportData
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

/** 每日报表类型：采购入库 / 领料单 */
enum class ReportType(val apiType: String, val label: String) {
    PURCHASE_IN("purchase_in", "采购入库"),
    REQUISITION("requisition", "领料单")
}

data class ReportUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    /** AI-APP-FIX-201：尚无报表数据时加载失败的持久错误（全屏错误态 + 重试） */
    val loadError: String? = null,
    /** 当前查询日期，格式 yyyy-MM-dd */
    val date: String = "",
    /** 日期是否处于「今天模式」：true 时每次加载自动跟随系统当天（跨天不重启也生效） */
    val dateIsToday: Boolean = true,
    val reportType: ReportType = ReportType.PURCHASE_IN,
    /** 可选仓库列表（进入报表页时加载一次，供顶部下拉切换） */
    val warehouses: List<WarehouseDto> = emptyList(),
    /**
     * 当前查询仓库：每日报表下拉只提供真实仓库（不含"默认仓库"/"全部仓库（汇总）"），
     * 故此处恒为仓库 id 字符串；进入报表页加载仓库后若为空则默认选中第一个仓库
     * （见 load）。仓库列表失败时仍兼容服务端默认仓。
     */
    val selectedWarehouseId: String? = null,
    val report: DailyReportData? = null
)

class ReportViewModel internal constructor(
    application: Application,
    private val fetchWarehouses: suspend () -> Result<List<WarehouseDto>>,
    private val fetchReport: suspend (String, String?, String?) -> Result<DailyReportData>
) : AndroidViewModel(application) {
    constructor(application: Application) : this(application, WmsRepository(application))

    private constructor(application: Application, repository: WmsRepository) : this(
        application, repository::getWarehouses, repository::getDailyReport
    )

    private val _uiState = MutableStateFlow(ReportUiState())
    val uiState: StateFlow<ReportUiState> = _uiState.asStateFlow()
    private val apiDateFormat = SimpleDateFormat("yyyy-MM-dd", Locale.US)
    private var loadJob: Job? = null
    private var loadingQuery: Triple<ReportType, String, String?>? = null
    private var displayedQuery: Triple<ReportType, String, String?>? = null
    private var requestVersion = 0L

    init {
        // 页面进入时才查询，构造时只设置日期。
        _uiState.value = _uiState.value.copy(date = apiDateFormat.format(Date()))
    }

    /** 确定仓库后加载一次，返回页面时仍刷新当天数据。 */
    fun load() {
        if (_uiState.value.dateIsToday) {
            val today = apiDateFormat.format(Date())
            if (today != _uiState.value.date) {
                _uiState.value = _uiState.value.copy(date = today)
            }
        }
        val current = _uiState.value
        val query = Triple(current.reportType, current.date, current.selectedWarehouseId)
        if (loadJob?.isActive == true && loadingQuery == query) return
        loadJob?.cancel()
        val version = ++requestVersion
        loadingQuery = query
        _uiState.value = current.copy(
            isLoading = true, error = null, loadError = null,
            report = if (displayedQuery == loadingQuery) current.report else null
        )
        loadJob = viewModelScope.launch {
            try {
                if (_uiState.value.warehouses.isEmpty()) {
                    val list = fetchWarehouses().getOrNull()
                    currentCoroutineContext().ensureActive()
                    if (version != requestVersion) return@launch
                    val selected = _uiState.value.selectedWarehouseId
                    val nextSelected = if (selected.isNullOrBlank() && !list.isNullOrEmpty()) {
                        list.first().id?.toString()
                    } else selected
                    _uiState.value = _uiState.value.copy(
                        warehouses = list.orEmpty(), selectedWarehouseId = nextSelected
                    )
                }
                val state = _uiState.value
                val resolvedQuery = Triple(state.reportType, state.date, state.selectedWarehouseId)
                loadingQuery = resolvedQuery
                val data = fetchReport(
                    state.reportType.apiType, state.date, state.selectedWarehouseId
                ).getOrThrow()
                currentCoroutineContext().ensureActive()
                if (version != requestVersion) return@launch
                displayedQuery = resolvedQuery
                _uiState.value = _uiState.value.copy(isLoading = false, report = data)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                currentCoroutineContext().ensureActive()
                if (version != requestVersion) return@launch
                // 同一查询刷新失败保留已有数据；新查询失败显示可重试错误。
                if (_uiState.value.report == null) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false, loadError = e.message ?: "加载失败"
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false, error = e.message ?: "加载失败"
                    )
                }
            }
        }
    }

    /** 切换仓库：null 默认仓 / "all" 全部仓库 / 其余仓 id */
    fun selectWarehouse(warehouseId: String?) {
        if (_uiState.value.selectedWarehouseId == warehouseId) return
        _uiState.value = _uiState.value.copy(selectedWarehouseId = warehouseId)
        load()
    }

    fun selectType(type: ReportType) {
        if (_uiState.value.reportType == type) return
        _uiState.value = _uiState.value.copy(reportType = type)
        load()
    }

    /** 日期前后移动：offset=-1 前一天 / +1 后一天 */
    fun shiftDay(offset: Int) {
        val cal = Calendar.getInstance()
        cal.time = apiDateFormat.parse(_uiState.value.date) ?: Date()
        cal.add(Calendar.DAY_OF_YEAR, offset)
        val next = apiDateFormat.format(cal.time)
        // AI-APP-FIX-206：不允许翻到未来（服务端对未来日期 400，前置钳制，
        // 与库存日报 shiftDay 同策略；UI 层「后一天」按钮另有禁用兜底）
        val today = apiDateFormat.format(Date())
        if (next > today) return
        // 手动翻天后脱离「今天模式」，避免用户翻到的日期被自动校正覆盖
        _uiState.value = _uiState.value.copy(
            date = next,
            dateIsToday = false
        )
        load()
    }

    /** 回到今天 */
    fun resetToday() {
        _uiState.value = _uiState.value.copy(
            date = apiDateFormat.format(Date()),
            dateIsToday = true
        )
        load()
    }

    /** AI-APP-FIX-402：DatePicker 直接跳日（与 shiftDay 同钳制：不允许未来日期） */
    fun setDate(date: String) {
        val today = apiDateFormat.format(Date())
        if (date > today || date == _uiState.value.date) return
        _uiState.value = _uiState.value.copy(date = date, dateIsToday = date == today)
        load()
    }

    /** AI-APP-FIX-402：今天日期串由 ViewModel 提供（页面层不再每次重组新建 SimpleDateFormat） */
    fun today(): String = apiDateFormat.format(Date())

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
