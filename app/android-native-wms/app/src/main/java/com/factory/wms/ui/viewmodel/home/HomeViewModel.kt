package com.factory.wms.ui.viewmodel.home

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.DashboardDto
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

data class HomeUiState(
    val isLoading: Boolean = true,
    val dashboard: DashboardDto? = null,
    val error: String? = null,
    /** 可选仓库列表（首页进入时加载一次，供顶部下拉切换） */
    val warehouses: List<WarehouseDto> = emptyList(),
    /**
     * 当前统计口径：首页下拉只提供真实仓库（不含"默认仓库"/"全部仓库（汇总）"），
     * 故此处恒为仓库 id 字符串；进入首页加载仓库后若为空则默认选中第一个仓库
     * （见 loadDashboard）。日报页同口径（见 ReportViewModel）。
     */
    val selectedWarehouseId: String? = null
)

class HomeViewModel internal constructor(
    application: Application,
    private val fetchWarehouses: suspend () -> Result<List<WarehouseDto>>,
    private val fetchDashboard: suspend (String?) -> Result<DashboardDto>
) : AndroidViewModel(application) {
    constructor(application: Application) : this(application, WmsRepository(application))

    private constructor(application: Application, repository: WmsRepository) : this(
        application, repository::getWarehouses, repository::getDashboard
    )

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    private var loadJob: Job? = null
    private var loadingWarehouseId: String? = null
    private var requestVersion = 0L

    /** 页面进入或重试只走此入口；仓库确定后再查一次概览。 */
    fun loadDashboard() {
        val selected = _uiState.value.selectedWarehouseId
        if (loadJob?.isActive == true && loadingWarehouseId == selected) return
        loadJob?.cancel()
        val version = ++requestVersion
        loadingWarehouseId = selected
        _uiState.value = _uiState.value.copy(isLoading = true, error = null)
        loadJob = viewModelScope.launch {
            try {
                if (_uiState.value.warehouses.isEmpty()) {
                    val list = fetchWarehouses().getOrNull()
                    currentCoroutineContext().ensureActive()
                    if (version != requestVersion) return@launch
                    val current = _uiState.value.selectedWarehouseId
                    val nextSelected = if (current.isNullOrBlank() && !list.isNullOrEmpty()) {
                        list.first().id?.toString()
                    } else current
                    _uiState.value = _uiState.value.copy(
                        warehouses = list.orEmpty(),
                        selectedWarehouseId = nextSelected
                    )
                }
                // 仓库列表失败时仍兼容服务端默认仓；下次重试会重新获取列表。
                val warehouseId = _uiState.value.selectedWarehouseId
                loadingWarehouseId = warehouseId
                val dashboard = fetchDashboard(warehouseId).getOrThrow()
                // Repository 可能把取消转成 Result，必须再次核对协程存活。
                currentCoroutineContext().ensureActive()
                if (version != requestVersion) return@launch
                _uiState.value = _uiState.value.copy(
                    isLoading = false, dashboard = dashboard, error = null
                )
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                currentCoroutineContext().ensureActive()
                if (version != requestVersion) return@launch
                _uiState.value = _uiState.value.copy(
                    isLoading = false, dashboard = null, error = e.message ?: "概览加载失败"
                )
            }
        }
    }

    /** 切换仓库：null 默认仓 / "all" 全部仓库 / 其余仓 id */
    fun selectWarehouse(warehouseId: String?) {
        if (_uiState.value.selectedWarehouseId == warehouseId) return
        _uiState.value = _uiState.value.copy(
            selectedWarehouseId = warehouseId, dashboard = null
        )
        loadDashboard()
    }
}
