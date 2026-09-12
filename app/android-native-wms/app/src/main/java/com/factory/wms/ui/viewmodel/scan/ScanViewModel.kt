package com.factory.wms.ui.viewmodel.scan

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.*
import com.factory.wms.data.repository.WmsRepository
import com.factory.wms.data.repository.WmsRepository.Companion.OfflineQueuedException
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
    // 2026-09-12 出库「领料部门/领料人」下拉（选填）：
    // 选部门后员工列表联动只显示该部门员工；两者均可不选（后端兼容）
    val departments: List<DepartmentDto> = emptyList(),
    val departmentsLoading: Boolean = false,
    val selectedDepartment: DepartmentDto? = null,
    val employees: List<EmployeeDto> = emptyList(),
    val employeesLoading: Boolean = false,
    val selectedEmployee: EmployeeDto? = null,
    // 提交成功后待打印的单据信息（"打印单据"按钮）
    val submittedPrint: SubmittedPrintInfo? = null,
    val printLoading: Boolean = false,
    // ── AI-MOB-STOCK-F01：查库存列表模式（分页） ──
    /** 列表模式结果（仓库级账面库存，按页加载） */
    val stockListItems: List<MaterialDto> = emptyList(),
    val stockListLoading: Boolean = false,
    val stockListLoadingMore: Boolean = false,
    val stockListError: String? = null,
    val stockListKeyword: String = "",
    /** 已加载页数 / 总页数（R1：按 total_pages 翻页取全，不把默认 page_size 当上限） */
    val stockListPage: Int = 0,
    val stockListTotalPages: Int = 0,
    val stockListTotal: Int = 0,
    /** 是否已完成过一次列表查询（区分"未查询"与"查询结果为空"两种空态） */
    val stockListLoaded: Boolean = false,
    /**
     * AI-MOB-STOCK-F02：列表排序方式。空串表示不传（服务端维持原编码升序）。
     * 取值 code_asc / code_desc / stock_asc / stock_desc。
     */
    val stockListSort: String = "",
    /**
     * AI-MOB-STOCK-F02：库存筛选。空串表示不筛选。
     * 取值 all / nonzero / zero / low（low = 低于最低库存）。
     */
    val stockListFilter: String = "",
    // ── AI-MOB-OFFLINE-01：离线待同步队列状态 ──
    /** 待自动补传条数（断网提交已暂存）。>0 时页面提示"已保存，联网后自动提交" */
    val offlinePendingCount: Int = 0,
    /** 重试耗尽的失败条数，需人工介入 */
    val offlineFailedCount: Int = 0
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

    /**
     * AI-MOB-OFFLINE-01：观察离线队列计数，驱动页面"待同步"提示条。
     *
     * 断网提交的数据已安全暂存，必须让作业员**看见**这个事实：
     * 否则他会以为提交失败而重扫一遍，反而制造重复单据。
     */
    init {
        viewModelScope.launch {
            repository.offlineQueue.pendingCount.collect { count ->
                _uiState.value = _uiState.value.copy(offlinePendingCount = count)
            }
        }
        viewModelScope.launch {
            repository.offlineQueue.failedCount.collect { count ->
                _uiState.value = _uiState.value.copy(offlineFailedCount = count)
            }
        }
    }

    /** AI-MOB-OFFLINE-01：人工重试全部失败记录并立即尝试补传。 */
    fun retryOfflineSync() {
        repository.offlineQueue.retryFailed()
    }

    /**
     * AI-VOICE-OUT-F01：出库页换仓回调。
     *
     * 语音建单流程复用同一个出库 ScanViewModel，但建单草稿带着自己的仓库
     * （VoiceOutDraftViewModel.selectedWarehouse）。用户若在出库页把仓库改成别的，
     * 语音流程下次建单必须跟着变——否则"界面显示 A 仓，草稿落在 B 仓"。
     * 这里不做反向同步（语音改仓不必回写出库页），单向广播即可。
     */
    private var _onWarehouseChanged: ((WarehouseDto) -> Unit)? = null

    /** 注册出库/入库换仓监听（仅出库页需要，用于回写语音建单的仓库）。 */
    fun setOnWarehouseChanged(listener: ((WarehouseDto) -> Unit)?) {
        _onWarehouseChanged = listener
    }

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
        val existingIndex = current.indexOfFirst { it.material_code == line.material_code && it.location_code.orEmpty() == line.location_code.orEmpty() }
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
    fun existingLineQuantity(code: String, location: String? = null): Double? {
        val clean = code.trim()
        val normalizedLocation = location.orEmpty()
        return _uiState.value.scanLines.firstOrNull {
            it.material_code == clean && it.location_code.orEmpty() == normalizedLocation
        }?.quantity
    }

    /**
     * 盘点重复扫码确认后"替换"为本次实盘数量：保留原行的物料名称/规格等已补全字段，
     * 仅把数量改为本次扫码数量（防误把已盘物料再次累加导致实盘数翻倍）。
     */
    fun replaceScanLineQuantity(line: ScanLine) {
        val current = _uiState.value.scanLines.toMutableList()
        val existingIndex = current.indexOfFirst { it.material_code == line.material_code && it.location_code.orEmpty() == line.location_code.orEmpty() }
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

    /**
     * 校验扫码得到的编码是否命中建档物料（AI-MOB-SCAN-UX-01）。
     *
     * 用途：给扫码的**声音/震动反馈**判成功还是失败。
     * 仓库现场工人不看屏幕，扫到未建档的码必须能靠体感立刻分辨出来，
     * 否则会一路扫下去、到提交时才发现有行是"查无此物"。
     *
     * 与 [enrichScanLineMaterial] 的区别：那个是补全清单行的名称/规格（有副作用、异步），
     * 这个只回答"这个码认不认识"，不写任何状态，可安全地在扫码回调里 await。
     * 网络异常时返回 true —— 断网时不该把"查不到"误报成"物料不存在"。
     */
    suspend fun materialExists(code: String): Boolean {
        val whCode = _uiState.value.selectedWarehouse?.code
        return try {
            val exact = repository.getMaterialInfo(code, whCode)
            if (exact.isSuccess) return true
            val fuzzy = repository.searchMaterial(code, whCode)
            fuzzy.getOrNull()?.isNotEmpty() ?: true
        } catch (e: Exception) {
            // 网络/服务异常 → 不拦截，交由提交环节暴露问题
            true
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

    // ── 2026-09-12：出库「领料部门/领料人」下拉（选填，选部门联动过滤员工） ──

    /** 拉取启用部门列表（出库页进入时调用）。 */
    fun loadDepartments() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(departmentsLoading = true)
            repository.getDepartments().fold(
                onSuccess = { departments ->
                    val keep = _uiState.value.selectedDepartment
                        ?.let { sel -> departments.firstOrNull { it.id == sel.id } }
                    _uiState.value = _uiState.value.copy(
                        departmentsLoading = false,
                        departments = departments,
                        selectedDepartment = keep
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        departmentsLoading = false,
                        error = e.message
                    )
                }
            )
        }
    }

    /** 拉取员工列表；selectedDepartment 存在时按部门过滤（联动）。 */
    fun loadEmployees() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(employeesLoading = true)
            repository.getEmployees(_uiState.value.selectedDepartment?.id).fold(
                onSuccess = { employees ->
                    val keep = _uiState.value.selectedEmployee
                        ?.let { sel -> employees.firstOrNull { it.id == sel.id } }
                    _uiState.value = _uiState.value.copy(
                        employeesLoading = false,
                        employees = employees,
                        selectedEmployee = keep
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        employeesLoading = false,
                        error = e.message
                    )
                }
            )
        }
    }

    /** 选择领料部门（可传 null 清除）；换部门后联动刷新员工列表。 */
    fun selectDepartment(department: DepartmentDto?) {
        _uiState.value = _uiState.value.copy(selectedDepartment = department)
        loadEmployees()
    }

    /** 选择领料人（可传 null 清除）。 */
    fun selectEmployee(employee: EmployeeDto?) {
        _uiState.value = _uiState.value.copy(selectedEmployee = employee)
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
        if (changed) {
            _onWarehouseChanged?.invoke(warehouse)
            loadPendingCheckOrders()
            // AI-MOB-STOCK-F01：换仓后清空列表结果，避免展示上一仓数据误导用户；
            // 已查询过则按新仓自动重查（未查询过不主动拉取，保持"输入后才查"体验）。
            val hadLoaded = _uiState.value.stockListLoaded
            clearStockList()
            if (hadLoaded) loadStockList()
        }
    }

    // ── AI-MOB-STOCK-F01：查库存列表模式（分页，复用 /api/mobile/stock/query） ──

    /**
     * 列表模式查询首屏（重置分页）。
     *
     * 仓库必填（AGENTS.md 第二节）：未选仓时不发请求，给出明确提示而非拉全量
     * 或用空数据误导。关键词为空表示"该仓全部物料"，由服务端分页返回。
     */
    fun loadStockList(keyword: String? = null) {
        val warehouse = _uiState.value.selectedWarehouse
        if (warehouse == null) {
            _uiState.value = _uiState.value.copy(
                stockListError = "请先选择仓库后再查询库存",
                stockListLoaded = false
            )
            return
        }
        val whParam = warehouse.code?.takeIf { it.isNotBlank() } ?: warehouse.name.orEmpty()
        if (whParam.isBlank()) {
            _uiState.value = _uiState.value.copy(stockListError = "所选仓库缺少编码，请重新选择仓库")
            return
        }
        val kw = keyword ?: _uiState.value.stockListKeyword
        _uiState.value = _uiState.value.copy(
            stockListKeyword = kw,
            stockListLoading = true,
            stockListError = null,
            stockListItems = emptyList(),
            stockListPage = 0,
            stockListTotalPages = 0,
            stockListTotal = 0,
            stockListLoaded = false
        )
        viewModelScope.launch {
            repository.queryStockPage(
                whParam, kw.trim(), page = 1, pageSize = STOCK_LIST_PAGE_SIZE,
                sort = _uiState.value.stockListSort.takeIf { it.isNotBlank() },
                stockFilter = _uiState.value.stockListFilter.takeIf { it.isNotBlank() }
            )
                .fold(
                    onSuccess = { data ->
                        _uiState.value = _uiState.value.copy(
                            stockListLoading = false,
                            stockListItems = data.items,
                            stockListPage = data.page,
                            stockListTotalPages = data.totalPages,
                            stockListTotal = data.total,
                            stockListLoaded = true
                        )
                    },
                    onFailure = { e ->
                        _uiState.value = _uiState.value.copy(
                            stockListLoading = false,
                            stockListError = e.message ?: "加载失败",
                            stockListLoaded = true
                        )
                    }
                )
        }
    }

    /**
     * 列表模式加载下一页（滚动到底部触发）。
     *
     * R1：显式按 total_pages 翻页合并，不把默认 page_size 当业务上限。
     * 已在加载中或已是最后一页时直接返回（幂等，避免重复请求）。
     */
    fun loadMoreStockList() {
        val state = _uiState.value
        if (state.stockListLoading || state.stockListLoadingMore) return
        if (state.stockListPage <= 0 || state.stockListPage >= state.stockListTotalPages) return
        val warehouse = state.selectedWarehouse ?: return
        val whParam = warehouse.code?.takeIf { it.isNotBlank() } ?: warehouse.name.orEmpty()
        if (whParam.isBlank()) return
        val nextPage = state.stockListPage + 1
        _uiState.value = state.copy(stockListLoadingMore = true)
        viewModelScope.launch {
            repository.queryStockPage(
                whParam, state.stockListKeyword.trim(), page = nextPage,
                pageSize = STOCK_LIST_PAGE_SIZE,
                sort = state.stockListSort.takeIf { it.isNotBlank() },
                stockFilter = state.stockListFilter.takeIf { it.isNotBlank() }
            ).fold(
                onSuccess = { data ->
                    _uiState.value = _uiState.value.copy(
                        stockListLoadingMore = false,
                        // 追加去重，避免翻页期间数据变动导致重复行
                        stockListItems = (_uiState.value.stockListItems + data.items)
                            .distinctBy { it.id },
                        stockListPage = data.page,
                        // total_pages 每页都取：它是翻页边界判定依据，数据变动时需随之更新
                        stockListTotalPages = data.totalPages,
                        // BUG-2026-09-12-004（R1）：总数在首页确定后不再被翻页响应覆盖。
                        // 服务端 total 为全量 count()、跨页恒定，但本字段是"共 N 条"统计值，
                        // 语义上应与分页解耦（R1：汇总统计必须与分页解耦）。此处用
                        // takeIf 保护：本页返回 0（字段缺失/异常）时不覆盖既有值，
                        // 避免非空原生类型反序列化缺省为 0 导致统计静默归零。
                        stockListTotal = data.total.takeIf { it > 0 }
                            ?: _uiState.value.stockListTotal
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        stockListLoadingMore = false,
                        stockListError = e.message ?: "加载失败"
                    )
                }
            )
        }
    }

    /** 列表模式关键词变化（仅更新输入框值，由页面防抖后调用 loadStockList 触发查询）。 */
    fun onStockListKeywordChange(text: String) {
        _uiState.value = _uiState.value.copy(stockListKeyword = text)
    }

    /**
     * AI-MOB-STOCK-F02：切换排序方式并重新查询。
     *
     * 排序在服务端对**全集**生效（不是只排当前页），故必须回到第 1 页重新拉取，
     * 不能只重排本地已加载的 items——那样用户看到的仍是"本页重排"的假排序。
     */
    fun setStockListSort(sort: String) {
        if (_uiState.value.stockListSort == sort) return
        _uiState.value = _uiState.value.copy(stockListSort = sort)
        loadStockList()
    }

    /** AI-MOB-STOCK-F02：切换库存筛选并重新查询（同为服务端全量筛选，回到第 1 页）。 */
    fun setStockListFilter(filter: String) {
        if (_uiState.value.stockListFilter == filter) return
        _uiState.value = _uiState.value.copy(stockListFilter = filter)
        loadStockList()
    }

    /** 切仓后清空列表结果，避免显示上一个仓库的数据误导用户。 */
    fun clearStockList() {
        _uiState.value = _uiState.value.copy(
            stockListItems = emptyList(),
            stockListPage = 0,
            stockListTotalPages = 0,
            stockListTotal = 0,
            stockListLoaded = false,
            stockListError = null
        )
    }

    fun clearStockListError() {
        _uiState.value = _uiState.value.copy(stockListError = null)
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

    /**
     * 查库存「查询」按钮/键盘搜索键统一入口（BUG-2026-09-10-002）。
     * 先按物料编码精确查询；未命中时回退名称/规格/品牌模糊搜索并列出全部候选，
     * 不再只弹「物料不存在」。模糊也无命中时清空结果交由页面空态提示
     * 「未找到包含「kw」的物料」，不写 error（避免 toast 与空态双重提示）。
     * 不触碰 scannedCode，避免触发 LaunchedEffect(scannedCode) 重复查询。
     */
    fun queryMaterialByKeyword(keyword: String) {
        val normalized = keyword.trim()
        if (normalized.isEmpty()) return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val whCode = _uiState.value.selectedWarehouse?.code
            repository.getMaterialInfo(normalized, whCode).fold(
                onSuccess = { material ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        scannedMaterial = material,
                        materialSuggestions = emptyList(),
                        materialSuggestionsLoading = false
                    )
                },
                onFailure = {
                    // 精确编码未命中：回退模糊搜索，列出包含关键词的全部物料
                    repository.searchMaterial(normalized, whCode).fold(
                        onSuccess = { materials ->
                            _uiState.value = _uiState.value.copy(
                                isLoading = false,
                                scannedMaterial = null,
                                materialSuggestions = materials,
                                materialSuggestionsLoading = false
                            )
                        },
                        onFailure = { e ->
                            _uiState.value = _uiState.value.copy(
                                isLoading = false,
                                scannedMaterial = null,
                                materialSuggestions = emptyList(),
                                materialSuggestionsLoading = false,
                                error = e.message
                            )
                        }
                    )
                }
            )
        }
    }

    /**
     * 查库存：点选模糊联想候选后直接展示该物料。
     * 候选来自后端 api/material/search 实时查询，与 api/material/info 返回同一 payload，
     * 字段一致，无需二次请求；同时不触碰 scannedCode，避免触发 LaunchedEffect(scannedCode) 重复查询。
     */
    fun selectMaterialSuggestion(material: MaterialDto) {
        clearMaterialSuggestions()
        _uiState.value = _uiState.value.copy(
            isLoading = false,
            error = null,
            scannedMaterial = material,
            scannedCode = ""
        )
    }

    fun submitInbound(businessType: String = "采购入库") {
        viewModelScope.launch {
            // BUG-2026-09-12-010：防重复提交守卫。
            // 每次提交都会 newRequestId() 生成**新**幂等键，后端只能靠幂等键去重，
            // 重复触发即两张单据、库存扣两次。此前仅靠 UI 关弹窗遮蔽（时序侥幸），
            // ViewModel 层无任何防护；此处补上源头守卫（UI 层同时禁用按钮为第二道）。
            if (_uiState.value.isLoading) return@launch
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
                    // AI-MOB-OFFLINE-01：断网但已暂存 → 当"成功"对待，
                    // 清空已扫明细（数据已安全落本地队列，用户不必重扫），
                    // 只在提示里说明"联网后自动提交"。
                    // 若不区分，用户看到"失败"会重扫一遍 → 重复单据。
                    if (e is OfflineQueuedException) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            success = e.message,
                            error = null,
                            scanLines = emptyList(),
                            totalQuantity = 0.0
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                    }
                }
            )
        }
    }

    fun submitOutbound() {
        viewModelScope.launch {
            // BUG-2026-09-12-010：防重复提交守卫（同 submitInbound，重复点按＝新幂等键＝重复单据）
            if (_uiState.value.isLoading) return@launch
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
                receiver = null,
                department = state.selectedDepartment?.name,
                departmentId = state.selectedDepartment?.id,
                picker = state.selectedEmployee?.name,
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
                    // AI-MOB-OFFLINE-01：断网但已暂存 → 当"成功"对待，
                    // 清空已扫明细（数据已安全落本地队列，用户不必重扫），
                    // 只在提示里说明"联网后自动提交"。
                    // 若不区分，用户看到"失败"会重扫一遍 → 重复单据。
                    if (e is OfflineQueuedException) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            success = e.message,
                            error = null,
                            scanLines = emptyList(),
                            totalQuantity = 0.0
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                    }
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
            // BUG-2026-09-12-010：防重复提交守卫（同 submitInbound）
            if (_uiState.value.isLoading) return@launch
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
                    system_stock = null,
                    area = line.location_code?.trim()?.ifBlank { null }
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
                    // AI-MOB-OFFLINE-01：断网但已暂存 → 当"成功"对待，
                    // 清空已扫明细（数据已安全落本地队列，用户不必重扫），
                    // 只在提示里说明"联网后自动提交"。
                    // 若不区分，用户看到"失败"会重扫一遍 → 重复单据。
                    if (e is OfflineQueuedException) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            success = e.message,
                            error = null,
                            scanLines = emptyList(),
                            totalQuantity = 0.0
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                    }
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

/**
 * AI-MOB-STOCK-F01：查库存列表模式每页条数。
 * 与服务端 MOBILE_API_PAGE_SIZE_DEFAULT 口径一致；仅作为单页请求大小，
 * 不作业务上限（R1：按响应 total_pages 翻页取全）。
 */
private const val STOCK_LIST_PAGE_SIZE = 20

