package com.factory.wms.ui.viewmodel.scan

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.*
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ScanUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val success: String? = null,
    // Material scan result
    val scannedMaterial: MaterialDto? = null,
    val scannedCode: String = "",
    // Scan list for batch operations
    val scanLines: List<ScanLine> = emptyList(),
    val totalQuantity: Double = 0.0,
    // 仓库选择（出入库必填，透传给后端）
    val warehouses: List<WarehouseDto> = emptyList(),
    val warehousesLoading: Boolean = false,
    val selectedWarehouse: WarehouseDto? = null
)

class ScanViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(ScanUiState())
    val uiState: StateFlow<ScanUiState> = _uiState.asStateFlow()

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun clearSuccess() {
        _uiState.value = _uiState.value.copy(success = null)
    }

    fun clearScannedMaterial() {
        _uiState.value = _uiState.value.copy(scannedMaterial = null, scannedCode = "")
    }

    fun addScanLine(line: ScanLine) {
        val current = _uiState.value.scanLines.toMutableList()
        val existingIndex = current.indexOfFirst { it.material_code == line.material_code }
        if (existingIndex >= 0) {
            val existing = current[existingIndex]
            current[existingIndex] = existing.copy(quantity = existing.quantity + line.quantity)
        } else {
            current.add(line)
        }
        _uiState.value = _uiState.value.copy(
            scanLines = current,
            totalQuantity = current.sumOf { it.quantity }
        )
    }

    fun removeScanLine(index: Int) {
        val current = _uiState.value.scanLines.toMutableList()
        if (index in current.indices) {
            current.removeAt(index)
            _uiState.value = _uiState.value.copy(
                scanLines = current,
                totalQuantity = current.sumOf { it.quantity }
            )
        }
    }

    fun clearScanLines() {
        _uiState.value = _uiState.value.copy(scanLines = emptyList(), totalQuantity = 0.0)
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

    fun searchMaterialByCode(code: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val result = repository.getMaterialInfo(code)
            result.fold(
                onSuccess = { material ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        scannedMaterial = material,
                        scannedCode = code
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = e.message,
                        scannedMaterial = null,
                        scannedCode = code
                    )
                }
            )
        }
    }

    fun submitInbound(businessType: String = "采购入库") {
        viewModelScope.launch {
            val state = _uiState.value
            val warehouse = state.selectedWarehouse
            if (warehouse == null) {
                _uiState.value = _uiState.value.copy(error = "请选择仓库")
                return@launch
            }
            val lines = state.scanLines
            if (lines.isEmpty()) {
                _uiState.value = _uiState.value.copy(error = "请先扫描物料")
                return@launch
            }
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val request = InboundRequest(
                lines = lines,
                businessType = businessType,
                warehouse = warehouse.code,
                warehouseCode = warehouse.code
            )
            val result = repository.submitInbound(request)
            result.fold(
                onSuccess = { submitResult ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        success = "入库成功！单号: ${submitResult.order_no}",
                        scanLines = emptyList(),
                        totalQuantity = 0.0
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                }
            )
        }
    }

    fun submitOutbound(receiver: String? = null, department: String? = null) {
        viewModelScope.launch {
            val state = _uiState.value
            val warehouse = state.selectedWarehouse
            if (warehouse == null) {
                _uiState.value = _uiState.value.copy(error = "请选择仓库")
                return@launch
            }
            val lines = state.scanLines
            if (lines.isEmpty()) {
                _uiState.value = _uiState.value.copy(error = "请先扫描物料")
                return@launch
            }
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val request = OutboundRequest(
                lines = lines,
                receiver = receiver,
                department = department,
                warehouse = warehouse.code,
                warehouseCode = warehouse.code
            )
            val result = repository.submitOutbound(request)
            result.fold(
                onSuccess = { submitResult ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        success = "出库成功！单号: ${submitResult.order_no}",
                        scanLines = emptyList(),
                        totalQuantity = 0.0
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                }
            )
        }
    }

    fun submitStocktake() {
        viewModelScope.launch {
            val lines = _uiState.value.scanLines
            if (lines.isEmpty()) {
                _uiState.value = _uiState.value.copy(error = "请先扫描盘点物料")
                return@launch
            }
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val stocktakeLines = lines.map { line ->
                StocktakeLine(
                    material_code = line.material_code,
                    actual_stock = line.quantity,
                    system_stock = null
                )
            }
            val request = StocktakeRequest(lines = stocktakeLines, mode = "scan")
            val result = repository.submitStocktake(request)
            result.fold(
                onSuccess = { submitResult ->
                    val msg = if (submitResult.check_no != null)
                        "盘点成功！盘点单号: ${submitResult.check_no}"
                    else "盘点提交成功"
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        success = msg,
                        scanLines = emptyList(),
                        totalQuantity = 0.0
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                }
            )
        }
    }
}