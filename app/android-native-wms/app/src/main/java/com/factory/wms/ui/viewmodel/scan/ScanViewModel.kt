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
    // INV-BATCH-001-E：盘点必须先选电脑端建好的进行中盘点单（统一挂一张盘点单）
    val checkOrders: List<CheckOrderDto> = emptyList(),
    val checkOrdersLoading: Boolean = false,
    val selectedCheckOrder: CheckOrderDto? = null,
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
            // BUG-2026-09-03-004：搜索建议带当前仓库，返回仓库级账面库存
            repository.searchMaterial(normalizedKeyword, _uiState.value.selectedWarehouse?.code).fold(
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
            enrichScanLineMaterial(line.material_code)
        }
    }

    /** 清单中同物料行的当前数量；不存在返回 null（用于盘点重复扫码确认）。 */
    fun existingLineQuantity(code: String): Double? {
        val clean = code.trim()
        return _uiState.value.scanLines.firstOrNull { it.material_code == clean }?.quantity
    }

    /**
     * 盘点重复扫码确认后"替换"为本次实盘数量：保留原行的物料名称/规格等已补全字段，
     * 仅把数量改为本次扫码数量（防误把已盘物料再次累加导致实盘数翻倍）。
     */
    fun replaceScanLineQuantity(line: ScanLine) {
        val current = _uiState.value.scanLines.toMutableList()
        val existingIndex = current.indexOfFirst { it.material_code == line.material_code }
        if (existingIndex >= 0) {
            current[existingIndex] = current[existingIndex].copy(quantity = line.quantity)
        } else {
            current.add(line)
        }
        _uiState.value = _uiState.value.copy(
            scanLines = current,
            totalQuantity = current.sumOf { it.quantity }
        )
        if (line.material_name.isNullOrBlank() || line.material_spec.isNullOrBlank()) {
            enrichScanLineMaterial(line.material_code)
        }
    }

    /** 异步拉取物料信息补全清单行的名称/规格/品牌（扫码进入时通常只有编码）。 */
    private fun enrichScanLineMaterial(code: String) {
        viewModelScope.launch {
            val whCode = _uiState.value.selectedWarehouse?.code
            val material = repository.getMaterialInfo(code, whCode).getOrNull()
                ?: repository.searchMaterial(code, whCode).getOrNull()?.firstOrNull()
            material?.let {
                val enriched = _uiState.value.scanLines.map { existing ->
                    if (existing.material_code == code) {
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
                    // INV-BATCH-001-E：默认选中首仓后即拉取该仓进行中盘点单
                    if (first?.code != null) loadPendingCheckOrders()
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

    // ── INV-BATCH-001-E：盘点单选单（电脑端创建进行中盘点单后手机选择） ──

    /** 拉取当前所选仓库的进行中盘点单列表。 */
    fun loadPendingCheckOrders() {
        val code = _uiState.value.selectedWarehouse?.code ?: return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(checkOrdersLoading = true)
            repository.loadPendingCheckOrders(code).fold(
                onSuccess = { orders ->
                    val selected = _uiState.value.selectedCheckOrder
                    val keep = if (selected == null) null
                    else orders.firstOrNull { it.id == selected.id }
                    _uiState.value = _uiState.value.copy(
                        checkOrdersLoading = false,
                        checkOrders = orders,
                        selectedCheckOrder = keep
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        checkOrdersLoading = false,
                        checkOrders = emptyList(),
                        selectedCheckOrder = null,
                        error = e.message
                    )
                }
            )
        }
    }

    /** 选中一张进行中盘点单（结果统一挂到该单，由电脑端完成统一出调整草稿）。 */
    fun selectCheckOrder(order: CheckOrderDto) {
        _uiState.value = _uiState.value.copy(selectedCheckOrder = order)
    }

    fun selectWarehouse(warehouse: WarehouseDto) {
        val changed = _uiState.value.selectedWarehouse?.code != warehouse.code
        _uiState.value = _uiState.value.copy(
            selectedWarehouse = warehouse,
            checkOrders = if (changed) emptyList() else _uiState.value.checkOrders,
            selectedCheckOrder = if (changed) null else _uiState.value.selectedCheckOrder
        )
        if (changed) loadPendingCheckOrders()
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
            val whCode = _uiState.value.selectedWarehouse?.code
            val result = repository.getMaterialInfo(code, whCode)
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
            // INV-BATCH-001-E：盘点必须已选择电脑端建好的进行中盘点单
            val checkOrder = state.selectedCheckOrder
            if (checkOrder == null) {
                _uiState.value = _uiState.value.copy(
                    error = "请选择盘点单（在电脑端创建盘点单后选择，结果统一挂该单）"
                )
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
                warehouseCode = warehouse.code,
                checkId = checkOrder.id
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
                    // BUG-2026-09-03-003：提交成功即清除断点续盘草稿，防止下次进入盘点误恢复
                    viewModelScope.launch { repository.clearStocktakeDraft() }
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                }
            )
        }
    }

    // ============ 断点续盘（BUG-2026-09-03-003） ============

    /** 将当前盘点清单、仓库与所选盘点单写入本地草稿（盘点页在清单变化时调用）。 */
    fun persistStocktakeDraft() {
        val s = _uiState.value
        if (s.scanLines.isEmpty()) return
        val draft = StocktakeDraft(
            warehouseCode = s.selectedWarehouse?.code,
            warehouseName = s.selectedWarehouse?.name,
            checkId = s.selectedCheckOrder?.id,
            lines = s.scanLines
        )
        viewModelScope.launch { repository.saveStocktakeDraft(draft) }
    }

    /** 主动清除本地草稿（离开盘点场景/放弃盘点时调用）。 */
    fun clearStocktakeDraft() {
        viewModelScope.launch { repository.clearStocktakeDraft() }
    }

    /**
     * 进入盘点页时尝试恢复上次未提交草稿：仅当本地有草稿且当前清单为空时恢复
     * （含仓库，若仓库列表已加载且能匹配则一并带回），恢复后通过 success 提示。
     */
    fun maybeRestoreStocktakeDraft() {
        viewModelScope.launch {
            val draft = repository.loadStocktakeDraft() ?: return@launch
            if (draft.lines.isEmpty()) return@launch
            val s = _uiState.value
            if (s.scanLines.isNotEmpty()) return@launch
            var newState = s.copy(
                scanLines = draft.lines,
                totalQuantity = draft.lines.sumOf { it.quantity }
            )
            if (s.selectedWarehouse == null && draft.warehouseCode != null) {
                val match = s.warehouses.firstOrNull {
                    it.code == draft.warehouseCode || (draft.warehouseName != null && it.name == draft.warehouseName)
                }
                if (match != null) newState = newState.copy(selectedWarehouse = match)
            }
            _uiState.value = newState.copy(
                success = "已恢复上次未提交的盘点清单（${draft.lines.size} 项），请核对后继续盘点"
            )
            // INV-BATCH-001-E：若草稿记录了盘点单，回拉列表尝试自动回选
            val checkId = draft.checkId
            if (checkId != null) restoreStocktakeCheckOrder(checkId)
        }
    }

    /** INV-BATCH-001-E：断点续盘按草稿记录的盘点单 id 重新拉取并回选（仍进行中才选中）。 */
    private fun restoreStocktakeCheckOrder(checkId: Long) {
        val code = _uiState.value.selectedWarehouse?.code ?: return
        viewModelScope.launch {
            repository.loadPendingCheckOrders(code).fold(
                onSuccess = { orders ->
                    val hit = orders.firstOrNull { it.id == checkId }
                    _uiState.value = _uiState.value.copy(
                        checkOrders = orders,
                        checkOrdersLoading = false,
                        selectedCheckOrder = hit,
                        success = if (hit == null)
                            "已恢复盘点清单，但原盘点单已不在进行中列表，请重新选择盘点单"
                        else null
                    )
                },
                onFailure = { }
            )
        }
    }
}
