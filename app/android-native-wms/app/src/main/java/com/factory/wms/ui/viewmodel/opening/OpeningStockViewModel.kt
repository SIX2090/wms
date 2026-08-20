package com.factory.wms.ui.viewmodel.opening

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.OpeningStockLine
import com.factory.wms.data.model.OpeningStockRequest
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeFormatter

data class OpeningStockUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val success: String? = null,
    // 仓库列表
    val warehouses: List<WarehouseDto> = emptyList(),
    val warehousesLoading: Boolean = false,
    // 选中的仓库
    val selectedWarehouse: WarehouseDto? = null,
    // 建账日期（ISO yyyy-MM-dd）
    val date: String = LocalDate.now().toString(),
    // 扫码/手动录入的行，按物料合并
    val lines: List<OpeningStockLine> = emptyList()
)

class OpeningStockViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(OpeningStockUiState())
    val uiState: StateFlow<OpeningStockUiState> = _uiState.asStateFlow()

    private val dateFormatter = DateTimeFormatter.ISO_LOCAL_DATE

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun clearSuccess() {
        _uiState.value = _uiState.value.copy(success = null)
    }

    fun loadWarehouses() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(warehousesLoading = true, error = null)
            val result = repository.getWarehouses()
            result.fold(
                onSuccess = { warehouses ->
                    val first = warehouses.firstOrNull() ?: _uiState.value.selectedWarehouse
                    _uiState.value = _uiState.value.copy(
                        warehousesLoading = false,
                        warehouses = warehouses,
                        selectedWarehouse = first ?: _uiState.value.selectedWarehouse
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        warehousesLoading = false,
                        error = e.message
                    )
                }
            )
        }
    }

    fun selectWarehouse(warehouse: WarehouseDto) {
        _uiState.value = _uiState.value.copy(selectedWarehouse = warehouse)
    }

    fun setDate(date: String) {
        _uiState.value = _uiState.value.copy(date = date)
    }

    fun addLine(code: String, quantity: Double) {
        val trimmed = code.trim()
        if (trimmed.isEmpty()) return
        if (quantity < 0) {
            _uiState.value = _uiState.value.copy(error = "数量不能小于 0")
            return
        }
        val current = _uiState.value.lines.toMutableList()
        val existingIndex = current.indexOfFirst { it.materialCode == trimmed }
        if (existingIndex >= 0) {
            val existing = current[existingIndex]
            current[existingIndex] = existing.copy(quantity = quantity)
        } else {
            current.add(OpeningStockLine(materialCode = trimmed, quantity = quantity))
        }
        _uiState.value = _uiState.value.copy(lines = current, error = null)

        viewModelScope.launch {
            val material = repository.getMaterialInfo(trimmed).getOrNull()
                ?: repository.searchMaterial(trimmed).getOrNull()?.firstOrNull()
            material?.let {
                val enriched = _uiState.value.lines.map { existing ->
                    if (existing.materialCode == trimmed) {
                        existing.copy(
                            materialCode = it.code ?: existing.materialCode,
                            materialName = it.name,
                            materialSpec = it.spec,
                            materialBrand = it.brand
                        )
                    } else {
                        existing
                    }
                }
                _uiState.value = _uiState.value.copy(lines = enriched)
            }
        }
    }

    fun removeLine(index: Int) {
        val current = _uiState.value.lines.toMutableList()
        if (index in current.indices) {
            current.removeAt(index)
            _uiState.value = _uiState.value.copy(lines = current)
        }
    }

    fun clearLines() {
        _uiState.value = _uiState.value.copy(lines = emptyList())
    }

    fun submit() {
        val state = _uiState.value
        val warehouse = state.selectedWarehouse
        if (warehouse == null) {
            _uiState.value = _uiState.value.copy(error = "请选择仓库")
            return
        }
        if (state.lines.isEmpty()) {
            _uiState.value = _uiState.value.copy(error = "请先扫码或手动添加期初物料")
            return
        }
        val date = try {
            LocalDate.parse(state.date).toString()
        } catch (_: Exception) {
            state.date
        }
        val request = OpeningStockRequest(
            date = date,
            warehouseCode = warehouse.code ?: "",
            lines = state.lines
        )
        viewModelScope.launch {
            _uiState.value = state.copy(isLoading = true, error = null)
            val result = repository.submitOpeningStock(request)
            result.fold(
                onSuccess = { msg ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        success = msg,
                        lines = emptyList()
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = e.message
                    )
                }
            )
        }
    }
}
