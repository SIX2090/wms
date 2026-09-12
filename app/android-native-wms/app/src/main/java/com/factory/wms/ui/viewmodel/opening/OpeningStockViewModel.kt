package com.factory.wms.ui.viewmodel.opening

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.MaterialDto
import com.factory.wms.data.model.OpeningStockLine
import com.factory.wms.data.model.OpeningStockRequest
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
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
    val lines: List<OpeningStockLine> = emptyList(),
    // AI-MOB-ADD-KEYWORD-01：「添加期初物料」弹窗的关键词模糊候选
    // （与查库存同口径：名称/规格/品牌都能搜）
    val materialSuggestions: List<MaterialDto> = emptyList(),
    val materialSuggestionsLoading: Boolean = false
)

class OpeningStockViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(OpeningStockUiState())
    val uiState: StateFlow<OpeningStockUiState> = _uiState.asStateFlow()

    private val dateFormatter = DateTimeFormatter.ISO_LOCAL_DATE

    // 关键词联想的防抖与竞态控制（与 ScanViewModel.searchMaterialSuggestions 同实现）
    private var materialSearchSequence = 0
    private var materialSearchJob: Job? = null

    /**
     * AI-MOB-ADD-KEYWORD-01：「添加期初物料」弹窗输入联想。
     * 与查库存同口径——后端 /api/material/search 按 code|name|spec|brand
     * 四字段 LIKE 匹配，输入名称/规格/品牌也能列出候选。
     * 防抖 180ms + 序号防竞态（后发请求先到时丢弃旧结果）。
     * 不传 warehouse：期初建账是全局口径，候选不带仓库级账面库存。
     */
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

    /**
     * 校验扫码得到的编码是否命中建档物料（AI-MOB-SCAN-UX-01）。
     *
     * 用途：给期初建账扫码的声音/震动反馈判成功还是失败。
     * 与 [ScanViewModel.materialExists] 同语义：网络异常时返回 true ——
     * 断网时不该把「查不到」误报成「物料不存在」。
     * 期初建账是全局口径，不带仓库（与 [searchMaterialSuggestions] 一致）。
     */
    suspend fun materialExists(code: String): Boolean {
        return try {
            val exact = repository.getMaterialInfo(code)
            if (exact.isSuccess) return true
            val fuzzy = repository.searchMaterial(code)
            fuzzy.getOrNull()?.isNotEmpty() ?: true
        } catch (e: Exception) {
            // 网络/服务异常 → 不拦截，交由提交环节暴露问题
            true
        }
    }

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
