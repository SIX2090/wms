package com.factory.wms.ui.viewmodel.report

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.DailyReportData
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

/** 每日报表类型：采购入库 / 领料单 */
enum class ReportType(val apiType: String, val label: String) {
    PURCHASE_IN("purchase_in", "采购入库"),
    REQUISITION("requisition", "领料单")
}

data class ReportUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    /** 当前查询日期，格式 yyyy-MM-dd */
    val date: String = "",
    /** 日期是否处于「今天模式」：true 时每次加载自动跟随系统当天（跨天不重启也生效） */
    val dateIsToday: Boolean = true,
    val reportType: ReportType = ReportType.PURCHASE_IN,
    /** 可选仓库列表（进入报表页时加载一次，供顶部下拉切换） */
    val warehouses: List<WarehouseDto> = emptyList(),
    /**
     * 当前查询仓库：null = 跟随系统默认仓（旧行为），"all" = 全部仓库汇总，
     * 其余为仓库 id 字符串（BUG-2026-09-10-009：多仓用户此前只能看默认仓）。
     */
    val selectedWarehouseId: String? = null,
    val report: DailyReportData? = null
)

class ReportViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = WmsRepository(application)
    private val _uiState = MutableStateFlow(ReportUiState())
    val uiState: StateFlow<ReportUiState> = _uiState.asStateFlow()

    private val apiDateFormat = SimpleDateFormat("yyyy-MM-dd", Locale.US)

    init {
        // BUG-2026-08-24-006：不在 init 自动加载。reportViewModel 在 AppNavGraph
        // 组合阶段（App 启动时）即被创建，此时可能尚未登录或会话尚未还原，
        // 提前加载只会留下过期错误态，等用户首次进入报表页时弹出误导性报错。
        // 加载统一由 DailyReportScreen 进入时触发（LaunchedEffect）。
        _uiState.value = _uiState.value.copy(date = apiDateFormat.format(Date()))
    }

    fun load() {
        // BUG-2026-09-10-003：ViewModel 在 App 启动时即被创建，date 只在 init 取一次；
        // App 跨天未重启（Android 进程常在后台存活数日）时，进入报表页仍按旧日期查询，
        // 表现为「今天的记录查不到」。处于今天模式时，每次加载前校正为系统当天。
        if (_uiState.value.dateIsToday) {
            val today = apiDateFormat.format(Date())
            if (today != _uiState.value.date) {
                _uiState.value = _uiState.value.copy(date = today)
            }
        }
        val state = _uiState.value
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            repository.getDailyReport(
                state.reportType.apiType, state.date, state.selectedWarehouseId
            ).fold(
                onSuccess = { data ->
                    _uiState.value = _uiState.value.copy(isLoading = false, report = data)
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = e.message ?: "加载失败"
                    )
                }
            )
        }
    }

    /** 进入报表页时加载可选仓库；已加载过则不重复请求。失败静默（不影响按默认仓查询）。 */
    fun loadWarehouses() {
        if (_uiState.value.warehouses.isNotEmpty()) return
        viewModelScope.launch {
            repository.ensureSession()
            repository.getWarehouses().fold(
                onSuccess = { list ->
                    _uiState.value = _uiState.value.copy(warehouses = list)
                },
                onFailure = { /* 静默：仓库列表失败不阻断报表查询 */ }
            )
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
        // 手动翻天后脱离「今天模式」，避免用户翻到的日期被自动校正覆盖
        _uiState.value = _uiState.value.copy(
            date = apiDateFormat.format(cal.time),
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

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
