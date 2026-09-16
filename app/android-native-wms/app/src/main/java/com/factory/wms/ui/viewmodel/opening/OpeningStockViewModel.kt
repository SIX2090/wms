package com.factory.wms.ui.viewmodel.opening

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.MaterialDto
import com.factory.wms.data.model.OpeningStockDto
import com.factory.wms.data.model.OpeningStockLine
import com.factory.wms.data.model.OpeningStockRequest
import com.factory.wms.data.model.OpeningStockUpdateRequest
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
    val materialSuggestionsLoading: Boolean = false,

    // ---- P1-C 已建账列表 ----
    /** 当前仓库已建账的明细（分页加载，滚动追加） */
    val builtItems: List<OpeningStockDto> = emptyList(),
    val builtLoading: Boolean = false,
    /** 首屏加载（区别于翻页加载），用于骨架/菊花 */
    val builtFirstLoad: Boolean = true,
    val builtLoadingMore: Boolean = false,
    val builtPage: Int = 1,
    val builtTotalPages: Int = 0,
    /** 本仓建账明细条数（后端按仓库全集算，不随分页缩小 —— R1） */
    val builtTotal: Int = 0,
    /** 本仓期初数量合计（同上，全集口径） */
    val builtQuantity: Double = 0.0,
    /** 已建账列表的关键字（前端防抖后传服务端） */
    val builtKeyword: String = "",
    /** 正在编辑的明细行（弹窗） */
    val editingItem: OpeningStockDto? = null,
    /** 编辑提交中（禁用确认按钮，防重复提交） */
    val updating: Boolean = false
)

class OpeningStockViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(OpeningStockUiState())
    val uiState: StateFlow<OpeningStockUiState> = _uiState.asStateFlow()

    private val dateFormatter = DateTimeFormatter.ISO_LOCAL_DATE

    // 关键词联想的防抖与竞态控制（与 ScanViewModel.searchMaterialSuggestions 同实现）
    private var materialSearchSequence = 0
    private var materialSearchJob: Job? = null

    // P1-C：已建账列表关键字筛选的防抖与竞态控制（同上策略）
    private var builtSearchSequence = 0
    private var builtSearchJob: Job? = null

    companion object {
        /** 已建账列表每页条数（与后端 MOBILE_API_PAGE_SIZE_DEFAULT 对齐） */
        private const val BUILT_PAGE_SIZE = 20
    }

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
                    // P1-C：默认仓库就位后立刻拉已建账列表，用户打开就能看到
                    // "本仓建了什么"，不用先手动选一次仓库。
                    if (_uiState.value.builtItems.isEmpty()) {
                        loadBuiltItems(reset = true)
                    }
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
        val changed = _uiState.value.selectedWarehouse?.id != warehouse.id
        _uiState.value = _uiState.value.copy(selectedWarehouse = warehouse)
        if (changed) {
            // P1-C：切仓库后已建账列表必须重拉——列表是仓库级视角，
            // 沿用上一个仓库的数据会让用户看到串仓的记录。
            _uiState.value = _uiState.value.copy(
                builtItems = emptyList(),
                builtPage = 1,
                builtTotalPages = 0,
                builtTotal = 0,
                builtQuantity = 0.0,
                builtFirstLoad = true
            )
            loadBuiltItems(reset = true)
        }
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
            // BUG-2026-09-16-010：同编码合并必须**累加**而非覆盖——
            // 连续扫描场景同一件货扫 N 次就是 N 件，覆盖会让扫 100 个
            // 轴承提交数量恒为 1，连续扫描名存实亡。要改成确切值请用
            // 行点击弹窗（updateLineQuantity），不要退回覆盖语义。
            val existing = current[existingIndex]
            current[existingIndex] = existing.copy(quantity = existing.quantity + quantity)
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

    /**
     * BUG-2026-09-16-010：行点击弹窗改数量（设为确切值）。
     *
     * 与 [addLine] 的累加语义互补：扫码/手动添加负责"加"，本函数负责
     * "改成对的数"——此前已录入行数量错了只能删行重扫，操作成本高。
     */
    fun updateLineQuantity(index: Int, quantity: Double) {
        if (quantity < 0) {
            _uiState.value = _uiState.value.copy(error = "数量不能小于 0")
            return
        }
        val current = _uiState.value.lines.toMutableList()
        if (index in current.indices) {
            current[index] = current[index].copy(quantity = quantity)
            _uiState.value = _uiState.value.copy(lines = current, error = null)
        }
    }

    fun clearLines() {
        _uiState.value = _uiState.value.copy(lines = emptyList())
    }

    // ==================================================================
    // P1-C 已建账列表 + 编辑
    //
    // 此前手机端只能"建账"：建完之后看不到自己建了什么（PC 单据列表才有），
    // 建错了也改不了。这一段补上"看"和"改"两个能力。
    // ==================================================================

    /**
     * 加载已建账明细（首屏 / 切换仓库时 reset=true）。
     *
     * 不传仓库直接忽略并提示——已建账列表是仓库级视角，
     * 没有仓库上下文时列表无意义（与后端 BUG-2026-08-12-004 口径一致）。
     */
    fun loadBuiltItems(reset: Boolean = true) {
        val warehouse = _uiState.value.selectedWarehouse
        if (warehouse?.id == null) {
            _uiState.value = _uiState.value.copy(
                builtFirstLoad = false,
                builtLoading = false,
                error = "请先选择仓库"
            )
            return
        }
        val state = _uiState.value
        if (!reset && (state.builtLoadingMore || state.builtLoading)) return
        if (!reset && state.builtPage >= state.builtTotalPages) return

        val nextPage = if (reset) 1 else state.builtPage + 1
        viewModelScope.launch {
            _uiState.value = state.copy(
                builtLoading = true,
                builtFirstLoad = reset && state.builtItems.isEmpty(),
                builtLoadingMore = !reset,
                error = null
            )
            repository.getOpeningStockPage(
                warehouseId = warehouse.id,
                keyword = state.builtKeyword,
                page = nextPage,
                pageSize = BUILT_PAGE_SIZE
            ).fold(
                onSuccess = { data ->
                    _uiState.value = _uiState.value.copy(
                        builtLoading = false,
                        builtFirstLoad = false,
                        builtLoadingMore = false,
                        builtItems = if (reset) data.items else _uiState.value.builtItems + data.items,
                        builtPage = data.page,
                        builtTotalPages = data.totalPages,
                        builtTotal = data.builtTotal,
                        builtQuantity = data.builtQuantity
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        builtLoading = false,
                        builtFirstLoad = false,
                        builtLoadingMore = false,
                        // 翻页失败保留已有数据，只提示；首屏失败才置 error
                        error = if (reset) (e.message ?: "加载失败") else _uiState.value.error
                    )
                }
            )
        }
    }

    /** 上滑加载下一页。 */
    fun loadMoreBuiltItems() = loadBuiltItems(reset = false)

    /**
     * 按关键字筛选已建账明细。
     *
     * 与录入弹窗的物料联想同策略：防抖 + 序号防竞态。注意关键字只筛明细，
     * builtTotal/builtQuantity 仍是整仓口径（由后端保证，见 R1）。
     */
    fun searchBuiltItems(keyword: String) {
        _uiState.value = _uiState.value.copy(builtKeyword = keyword)
        builtSearchJob?.cancel()
        val sequence = ++builtSearchSequence
        builtSearchJob = viewModelScope.launch {
            delay(300)
            if (sequence != builtSearchSequence) return@launch
            loadBuiltItems(reset = true)
        }
    }

    /** 打开编辑弹窗。 */
    fun startEditing(item: OpeningStockDto) {
        _uiState.value = _uiState.value.copy(editingItem = item, error = null)
    }

    fun cancelEditing() {
        _uiState.value = _uiState.value.copy(editingItem = null)
    }

    /**
     * 提交编辑（P1-C）：按差额调整数量/单价。
     *
     * 只提交变化过的字段（PATCH 语义，缺省字段服务端保留原值）。
     * 数量与单价都没变时直接关弹窗，不发无意义请求。
     * 成功后重新拉一次列表——差额调整会影响其他行的侧写（金额/流水），
     * 本地 patch 容易与服务端口径漂移，重拉最稳。
     */
    fun submitEdit(newQuantity: Double, newPrice: Double) {
        val state = _uiState.value
        val item = state.editingItem ?: return
        val lineId = item.id ?: return
        if (state.updating) return
        if (newQuantity < 0 || newPrice < 0) {
            _uiState.value = state.copy(error = "数量与单价不能小于 0")
            return
        }
        val oldQuantity = item.quantity ?: 0.0
        val oldPrice = item.price ?: 0.0
        if (newQuantity == oldQuantity && newPrice == oldPrice) {
            _uiState.value = state.copy(editingItem = null)
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(updating = true, error = null)
            repository.updateOpeningStock(
                lineId = lineId,
                request = OpeningStockUpdateRequest(
                    quantity = newQuantity,
                    price = newPrice
                )
            ).fold(
                onSuccess = { result ->
                    _uiState.value = _uiState.value.copy(
                        updating = false,
                        editingItem = null,
                        success = buildDeltaMessage(result.delta, result.quantity)
                    )
                    loadBuiltItems(reset = true)
                },
                onFailure = { e ->
                    // 失败保留弹窗，用户可直接改了重试，不用重新找这一行
                    _uiState.value = _uiState.value.copy(
                        updating = false,
                        error = e.message ?: "更新失败"
                    )
                }
            )
        }
    }

    /** 把差额翻译成人话：减少 40 / 增加 50。 */
    private fun buildDeltaMessage(delta: Double?, quantity: Double?): String {
        val absDelta = kotlin.math.abs(delta ?: 0.0)
        val suffix = "，现为 ${formatQuantityPlain(quantity ?: 0.0)}"
        return when {
            absDelta < 1e-9 -> "期初库存已更新$suffix"
            (delta ?: 0.0) > 0 -> "期初已增加 ${formatQuantityPlain(absDelta)}$suffix"
            else -> "期初已减少 ${formatQuantityPlain(absDelta)}$suffix"
        }
    }

    /** 去掉无意义的小数尾巴（100.00 → 100，1.50 → 1.5）。 */
    private fun formatQuantityPlain(value: Double): String {
        return if (kotlin.math.abs(value - value.toLong()) < 1e-9) {
            value.toLong().toString()
        } else {
            String.format(java.util.Locale.US, "%.2f", value)
        }
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
                    // P1-C：刚建的账要立刻出现在已建账列表里，否则用户会以为没存上
                    loadBuiltItems(reset = true)
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
