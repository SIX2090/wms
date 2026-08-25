package com.factory.wms.ui.viewmodel.report

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.DailyReportData
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
    val reportType: ReportType = ReportType.PURCHASE_IN,
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
        val state = _uiState.value
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            repository.getDailyReport(state.reportType.apiType, state.date).fold(
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
        _uiState.value = _uiState.value.copy(date = apiDateFormat.format(cal.time))
        load()
    }

    /** 回到今天 */
    fun resetToday() {
        _uiState.value = _uiState.value.copy(date = apiDateFormat.format(Date()))
        load()
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
