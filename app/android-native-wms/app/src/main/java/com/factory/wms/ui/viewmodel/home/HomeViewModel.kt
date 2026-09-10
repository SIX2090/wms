package com.factory.wms.ui.viewmodel.home

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.DashboardDto
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class HomeUiState(
    val isLoading: Boolean = false,
    val dashboard: DashboardDto? = null,
    val error: String? = null,
    /** 可选仓库列表（首页进入时加载一次，供顶部下拉切换） */
    val warehouses: List<WarehouseDto> = emptyList(),
    /**
     * 当前统计口径：null = 跟随系统默认仓（旧行为），"all" = 全部仓库汇总，
     * 其余为仓库 id 字符串（BUG-2026-09-10-010：多仓用户此前只能看默认仓）。
     */
    val selectedWarehouseId: String? = null
)

class HomeViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    init {
        loadDashboard()
    }

    fun loadDashboard() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val result = repository.getDashboard(_uiState.value.selectedWarehouseId)
            result.fold(
                onSuccess = { dashboard ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        dashboard = dashboard,
                        error = null
                    )
                },
                onFailure = { e ->
                    // 概览加载失败降级隐藏，不阻塞首页其余功能
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        dashboard = null,
                        error = e.message
                    )
                }
            )
        }
    }

    /** 进入首页时加载可选仓库；已加载过则不重复请求。失败静默（不影响默认仓查询）。 */
    fun loadWarehouses() {
        if (_uiState.value.warehouses.isNotEmpty()) return
        viewModelScope.launch {
            repository.ensureSession()
            repository.getWarehouses().fold(
                onSuccess = { list ->
                    _uiState.value = _uiState.value.copy(warehouses = list)
                },
                onFailure = { /* 静默：仓库列表失败不阻断首页概览 */ }
            )
        }
    }

    /** 切换仓库：null 默认仓 / "all" 全部仓库 / 其余仓 id */
    fun selectWarehouse(warehouseId: String?) {
        if (_uiState.value.selectedWarehouseId == warehouseId) return
        _uiState.value = _uiState.value.copy(selectedWarehouseId = warehouseId)
        loadDashboard()
    }
}
