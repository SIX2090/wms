package com.factory.wms.ui.viewmodel.scan

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.*
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
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
    val materialSuggestions: List<MaterialDto> = emptyList(),
    val materialSuggestionsLoading: Boolean = false,
    val scanLines: List<ScanLine> = emptyList(),
    val totalQuantity: Double = 0.0,
    // 仓库选择（出入库必填，透传给后端）
    val warehouses: List<WarehouseDto> = emptyList(),
    val warehousesLoading: Boolean = false,
    val selectedWarehouse: WarehouseDto? = null,
    // 合同编号（出库选填）：输入片段快速匹配完整合同编号（如 0709 → HD260709）
    val contractNo: String = "",
    val contractSuggestions: List<ContractDto> = emptyList(),
    val contractSuggestionsLoading: Boolean = false,
    // 提交成功后待打印的单据信息（"打印单据"按钮）
    val submittedPrint: SubmittedPrintInfo? = null,
    val printLoading: Boolean = false
)

/** 提交成功后可再次触发打印的单据信息。 */
data class SubmittedPrintInfo(
    /** out_order / in_order */
    val jobType: String,
    /** 单据主键 ID */
    val targetId: Int,
    val orderNo: String?
)

class ScanViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(ScanUiState())
    val uiState: StateFlow<ScanUiState> = _uiState.asStateFlow()
    private var materialSearchSequence = 0
    private var materialSearchJob: Job? = null
    private var contractSearchSequence = 0
    private var contractSearchJob: Job? = null

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun clearSuccess() {
        _uiState.value = _uiState.value.copy(success = null)
    }

    fun clearScannedMaterial() {
        _uiState.value = _uiState.value.copy(scannedMaterial = null, scannedCode = "")
    }

    fun clearScannedCode() {
        _uiState.value = _uiState.value.copy(scannedCode = "")
    }

    fun searchMaterialSuggestions(keyword: String) {
        val normalizedKeyword = keyword.trim()
        val searchSequence = ++materialSearchSequence
        materialSearchJob?.cancel()
        if (normalizedKeyword.isBlank()) {
            _uiState.value = _uiState.value.copy(
                materialSuggestions = emptyList(),
                materialSuggestionsLoading = false
            )
            return
        }

        materialSearchJob = viewModelScope.launch {
            delay(180)
            _uiState.value = _uiState.value.copy(materialSuggestionsLoading = true)
            repository.searchMaterial(normalizedKeyword).fold(
                onSuccess = { materials ->
                    if (searchSequence == materialSearchSequence) {
                        _uiState.value = _uiState.value.copy(
                            materialSuggestions = materials,
                            materialSuggestionsLoading = false
                        )
                    }
                },
                onFailure = {
                    if (searchSequence == materialSearchSequence) {
                        _uiState.value = _uiState.value.copy(
                            materialSuggestions = emptyList(),
                            materialSuggestionsLoading = false
                        )
                    }
                }
            )
        }
    }

    fun clearMaterialSuggestions() {
        materialSearchSequence += 1
        materialSearchJob?.cancel()
        _uiState.value = _uiState.value.copy(
            materialSuggestions = emptyList(),
            materialSuggestionsLoading = false
        )
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

        if (line.material_name.isNullOrBlank() || line.material_spec.isNullOrBlank()) {
            viewModelScope.launch {
                val material = repository.getMaterialInfo(line.material_code).getOrNull()
                    ?: repository.searchMaterial(line.material_code).getOrNull()?.firstOrNull()
                material?.let {
                    val enriched = _uiState.value.scanLines.map { existing ->
                        if (existing.material_code == line.material_code) {
                            existing.copy(
                                material_code = it.code ?: existing.material_code,
                                material_name = it.name,
                                material_spec = it.spec,
                                material_brand = it.brand
                            )
                        } else {
                            existing
                        }
                    }
                    _uiState.value = _uiState.value.copy(scanLines = enriched)
                }
            }
        }
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

    // ── 合同编号（出库选填）快速匹配 ──

    /** 输入变化时调用：防抖 180ms 后模糊搜索合同（片段如 0709 可匹配 HD260709）。 */
    fun onContractNoChange(text: String) {
        _uiState.value = _uiState.value.copy(contractNo = text)
        val keyword = text.trim()
        val searchSequence = ++contractSearchSequence
        contractSearchJob?.cancel()
        if (keyword.isBlank()) {
            _uiState.value = _uiState.value.copy(
                contractSuggestions = emptyList(),
                contractSuggestionsLoading = false
            )
            return
        }
        contractSearchJob = viewModelScope.launch {
            delay(180)
            _uiState.value = _uiState.value.copy(contractSuggestionsLoading = true)
            repository.searchContracts(keyword).fold(
                onSuccess = { contracts ->
                    if (searchSequence == contractSearchSequence) {
                        _uiState.value = _uiState.value.copy(
                            contractSuggestions = contracts,
                            contractSuggestionsLoading = false
                        )
                    }
                },
                onFailure = {
                    if (searchSequence == contractSearchSequence) {
                        _uiState.value = _uiState.value.copy(
                            contractSuggestions = emptyList(),
                            contractSuggestionsLoading = false
                        )
                    }
                }
            )
        }
    }

    /** 选中建议项：回填完整合同编号并收起建议列表。 */
    fun selectContract(contract: ContractDto) {
        contractSearchSequence += 1
        contractSearchJob?.cancel()
        _uiState.value = _uiState.value.copy(
            contractNo = contract.contractNo.orEmpty(),
            contractSuggestions = emptyList(),
            contractSuggestionsLoading = false
        )
    }

    fun clearContractSuggestions() {
        contractSearchSequence += 1
        contractSearchJob?.cancel()
        _uiState.value = _uiState.value.copy(
            contractSuggestions = emptyList(),
            contractSuggestionsLoading = false
        )
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
                        totalQuantity = 0.0,
                        submittedPrint = submitResult.id?.let {
                            SubmittedPrintInfo(
                                jobType = "in_order",
                                targetId = it,
                                orderNo = submitResult.order_no
                            )
                        }
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
                warehouseCode = warehouse.code,
                contractNo = state.contractNo.trim().ifBlank { null }
            )
            val result = repository.submitOutbound(request)
            result.fold(
                onSuccess = { submitResult ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        success = "出库成功！单号: ${submitResult.order_no}",
                        scanLines = emptyList(),
                        totalQuantity = 0.0,
                        contractNo = "",
                        contractSuggestions = emptyList(),
                        submittedPrint = submitResult.id?.let {
                            SubmittedPrintInfo(
                                jobType = "out_order",
                                targetId = it,
                                orderNo = submitResult.order_no
                            )
                        }
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                }
            )
        }
    }

    /** 清除提交后待打印信息（新开一单或离开页面时调用）。 */
    fun clearSubmittedPrint() {
        _uiState.value = _uiState.value.copy(submittedPrint = null, printLoading = false)
    }

    /** 对最近一次提交成功的单据创建远程打印任务（"打印单据"按钮）。 */
    fun printSubmittedOrder() {
        val info = _uiState.value.submittedPrint ?: return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(printLoading = true, error = null)
            val result = repository.createPrintJob(
                PrintJobRequest(jobType = info.jobType, targetId = info.targetId)
            )
            result.fold(
                onSuccess = { _ ->
                    _uiState.value = _uiState.value.copy(
                        printLoading = false,
                        success = "已加入打印队列，请到桌面端打印工作站查看"
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(printLoading = false, error = e.message)
                }
            )
        }
    }

    fun submitStocktake() {
        viewModelScope.launch {
            val state = _uiState.value
            val warehouse = state.selectedWarehouse
            if (warehouse == null) {
                _uiState.value = _uiState.value.copy(error = "请选择仓库")
                return@launch
            }
            val lines = state.scanLines
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
            val request = StocktakeRequest(
                lines = stocktakeLines,
                mode = "scan",
                warehouse = warehouse.code,
                warehouseCode = warehouse.code
            )
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
