package com.factory.wms.ui.viewmodel.scan

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.factory.wms.data.model.*
import com.factory.wms.data.repository.WmsRepository
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.repository.WmsRepository.Companion.OfflineQueuedException
import com.factory.wms.util.formatQuantity
import kotlinx.coroutines.Job
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.cancelAndJoin
import java.util.UUID

/** Keep a small owner-scoped write alive across navigation destroying a screen ViewModel. */
private object QuantityDraftWriteFence {
    private val scope = CoroutineScope(SupervisorJob())
    private val jobs = mutableMapOf<String, Job>()
    private var nextVersion = 0L
    private val recoveries = mutableMapOf<String, Pair<Long, Any>>()

    fun record(key: String, snapshot: Any) = synchronized(jobs) {
        nextVersion += 1
        recoveries[key] = nextVersion to snapshot
    }
    fun recovery(key: String): Any? = synchronized(jobs) { recoveries[key]?.second }
    fun version(key: String): Long? = synchronized(jobs) { recoveries[key]?.first }
    fun saved(key: String, version: Long?) = synchronized(jobs) {
        if (version != null && recoveries[key]?.first == version) recoveries.remove(key)
    }
    fun discard(key: String) = synchronized(jobs) { recoveries.remove(key) }

    fun enqueue(key: String, write: suspend () -> Unit) {
        synchronized(jobs) {
            val previous = jobs[key]
            val job = scope.launch(context = Dispatchers.Main.immediate, start = CoroutineStart.LAZY) { previous?.join(); write() }
            jobs[key] = job
            job.invokeOnCompletion { synchronized(jobs) { if (jobs[key] === job) jobs.remove(key) } }
            job.start()
        }
    }

    fun hasPendingWrites(): Boolean = synchronized(jobs) { jobs.isNotEmpty() }

    suspend fun await(key: String) {
        while (true) {
            val job = synchronized(jobs) { jobs[key] } ?: return
            job.join()
        }
    }
}

/** Test fixture must finish app-scoped writes before closing its isolated DataStore. */
internal fun hasPendingQuantityDraftWrites(): Boolean = QuantityDraftWriteFence.hasPendingWrites()

data class ScanUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val success: String? = null,
    // Material scan result
    val scannedMaterial: MaterialDto? = null,
    // Scan list for batch operations
    val materialSuggestions: List<MaterialDto> = emptyList(),
    val materialSuggestionsLoading: Boolean = false,
    val truncatedMaterialTotal: Int? = null,
    val scanLines: List<ScanLine> = emptyList(),
    val quantityDrafts: Map<String, QuantityDraft> = emptyMap(),
    val totalQuantity: Double = 0.0,
    val scanFeedback: String? = null,
    val pendingSubmissionId: String? = null,
    val inboundBusinessType: String = "采购入库",
    val draftSaveError: String? = null,
    val selectedLocation: String = "",
    val locationEnabled: Boolean? = null,
    val locationOptions: List<String> = emptyList(),
    val locationError: String? = null,
    val evidence: List<String> = emptyList(),
    // 仓库选择（出入库必填，透传给后端）
    val warehouses: List<WarehouseDto> = emptyList(),
    val warehousesLoading: Boolean = false,
    val selectedWarehouse: WarehouseDto? = null,
    // INV-BATCH-001-E：盘点必须先选电脑端建好的进行中盘点单（统一挂一张盘点单）
    val checkOrders: List<CheckOrderDto> = emptyList(),
    val checkOrdersLoading: Boolean = false,
    /** AI-APP-FIX-201：盘点单加载失败的持久错误（选单弹窗内展示 + 重试） */
    val checkOrdersError: String? = null,
    val selectedCheckOrder: CheckOrderDto? = null,
    val stocktakeIdentityError: String? = null,
    val stocktakeDraftUnreadable: Boolean = false,
    val editDraftUnreadable: Boolean = false,
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
    // BUG-2026-09-18-008 入库「供应商」下拉（选填）：
    // 手机端入库单此前 supplier_id 恒为空，导致每日报表「采购入库」的供应商列
    // 永远为空、采购对账断链。此处提供下拉；同时允许手输备注记录送货单号。
    val suppliers: List<SupplierDto> = emptyList(),
    val suppliersLoading: Boolean = false,
    val selectedSupplier: SupplierDto? = null,
    /** 入库备注（选填，现场常用来记送货单号/采购单号） */
    val inboundRemark: String = "",
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
     * 取值 all / nonzero / zero / low（AI-CI-GREEN-005-F04：low = 两级告警口径，
     * 即「库存 <= 安全库存」）。
     */
    val stockListFilter: String = "",
    /**
     * AI-MOB-STOCK-F03（清单 P1-3）：物料档案里命中当前关键词的条数，不看仓库、
     * 不看库存。仅在 total=0 时用于区分「档案里没这个物料」与「这个仓没货 /
     * 被筛选排除」——两种情形的正确动作完全不同（建档 vs 换仓改筛选）。
     */
    val stockListKeywordMaterialTotal: Int? = null,
    /** AI-MOB-STOCK-F03（清单 P2-3）：服务端数据截止时刻（hh:mm），纯展示。 */
    val stockListServerTime: String? = null,
    // ── AI-MOB-OFFLINE-01：离线待同步队列状态 ──
    /** 待自动补传条数（断网提交已暂存）。>0 时页面提示"已保存，联网后自动提交" */
    val offlinePendingCount: Int = 0,
    /** 重试耗尽的失败条数，需人工介入 */
    val offlineFailedCount: Int = 0,
    val offlineNeedsReview: Boolean = false,
    val offlineReadError: Boolean = false,
    val offlineSyncMessage: String? = null,
    val offlineRetryAvailable: Boolean = false
)

/** 提交成功后可再次触发打印的单据信息。 */
data class SubmittedPrintInfo(
    /** out_order / in_order */
    val jobType: String,
    /** 单据主键 ID */
    val targetId: Int,
    val orderNo: String?
)

class ScanViewModel(
    application: Application,
    /** BUG-2026-10-002：测试注入 0ms 超时，复现 DataStore actor 死亡。 */
    dataStoreTimeoutMs: Long = WmsRepository.DATASTORE_TIMEOUT_MS
) : AndroidViewModel(application) {

    private val repository = WmsRepository(application, dataStoreTimeoutMs)

    companion object {
        /**
         * BUG-2026-10-04-001：BUG-2026-10-002 给构造函数新增 dataStoreTimeoutMs 第二参数后，
         * Kotlin 默认参数不会生成 (Application) 单参构造方法；NavGraph 无工厂 viewModel()
         * 走 AndroidViewModelFactory 反射查找 <init>(Application) 必然抛
         * NoSuchMethodException —— 入库/出库/库存查询/盘点四个页面一打开即进程闪退。
         * 因此全部创建点必须经本工厂：viewModel(key = ..., factory = ScanViewModel.Factory)。
         */
        val Factory: ViewModelProvider.Factory = viewModelFactory {
            initializer {
                ScanViewModel(
                    this[ViewModelProvider.AndroidViewModelFactory.APPLICATION_KEY]
                        ?: error("APPLICATION_KEY missing in CreationExtras")
                )
            }
        }
    }

    private val _uiState = MutableStateFlow(ScanUiState())
    val uiState: StateFlow<ScanUiState> = _uiState.asStateFlow()
    private var materialSearchSequence = 0
    private var materialSearchJob: Job? = null
    private var employeeRequestVersion = 0L
    private var checkOrderRequestVersion = 0L
    private var stockQueryJob: Job? = null
    private var locationOptionsJob: Job? = null
    private var contractSearchSequence = 0
    private var contractSearchJob: Job? = null
    // AI-MOB-STOCK-F03（清单 P2-2）：查库存列表的防抖查询此前没有可取消的 Job。
    // 中文输入法逐字上屏，弱网下一个请求可能要几百毫秒，先发的慢请求会后到并
    // 覆盖后发的结果，列表会闪回旧数据。沿用 materialSearchJob 的同一套模式：
    // 取消 + 序号双保险（取消只管协程，序号兜住已发出、无法撤回的响应）。
    private var stockListSequence = 0
    private var stockListJob: Job? = null
    private val draftMutex = Mutex()
    private val restoreMutex = Mutex()
    private val stocktakeDraftMutex = Mutex()
    private var stocktakeKey: String? = null
    private var stocktakeRestoreStarted = false
    private var stocktakeRestoreComplete = false
    private var stocktakeDraftReadComplete = false
    private var stocktakeSourceWarehouse: String? = null
    private var stocktakeSourceCheckId: Long? = null
    private var editDraftKey: String? = null
    private var editDraftOperation: String? = null
    private var editDraftJob: Job? = null
    private var editDraftRestored = false
    private var editDraftClearJob: Job? = null

    private fun editDraftSnapshot(): ScanEditDraft {
        val state = _uiState.value
        return ScanEditDraft(
            state.scanLines.map { DraftScanLine(it, it.material_name, it.material_spec, it.material_brand, it.material_unit) },
            state.selectedWarehouse, state.selectedDepartment, state.selectedEmployee,
            state.contractNo, state.pendingSubmissionId, state.inboundBusinessType,
            state.selectedLocation, state.locationEnabled
            ,state.evidence
            // BUG-2026-09-18-008：供应商/备注一并快照，断点续传不丢单头信息
            ,state.selectedSupplier
            ,state.inboundRemark
            ,state.quantityDrafts
        )
    }

    suspend fun restoreEditDraft(operation: String) = restoreMutex.withLock {
        try {
            val key = repository.editDraftKey(operation)
            editDraftKey?.takeIf { it != key }?.let { QuantityDraftWriteFence.await(it) }
            QuantityDraftWriteFence.await(key)
            if (key == editDraftKey && editDraftRestored) return@withLock
            editDraftJob?.cancelAndJoin()
            editDraftRestored = false
            editDraftKey = key
            editDraftOperation = operation
            _uiState.value = ScanUiState(isLoading = true)
            val storedDraft = repository.loadEditDraft(key)
            check(storedDraft != null || !repository.hasEditDraft(key)) { "原草稿未能读取，已保留原内容，请先核对或明确清空" }
            val recovery = QuantityDraftWriteFence.recovery(key) as? ScanEditDraft
            val draft = recovery ?: storedDraft
            if (draft != null) {
                val lines = draft.lines.map {
                    it.line.copy(material_name = it.name, material_spec = it.spec, material_brand = it.brand, material_unit = it.unit)
                }
                _uiState.value = _uiState.value.copy(
                    scanLines = lines, totalQuantity = lines.sumOf { it.quantity },
                    selectedWarehouse = draft.warehouse, selectedDepartment = draft.department,
                    selectedEmployee = draft.employee, contractNo = draft.contractNo,
                    pendingSubmissionId = draft.requestId, inboundBusinessType = draft.inboundBusinessType,
                    selectedLocation = draft.selectedLocation.orEmpty(), locationEnabled = draft.locationEnabled,
                    evidence = draft.evidence,
                    // BUG-2026-09-18-008：恢复供应商/备注（旧草稿无此字段时 Gson 给 null/空串，等价于未选）
                    selectedSupplier = draft.supplier,
                    inboundRemark = draft.inboundRemark,
                    quantityDrafts = draft.quantityDrafts.orEmpty(),
                    draftSaveError = if (recovery != null) "数量输入尚未保存到本机，请勿退出" else null,
                    success = if (draft.requestId == null) "已恢复上次未提交清单，请核对仓库和数量"
                    else "已恢复待核实提交，请点提交核实原请求；核实前不可修改清单"
                )
            }
            editDraftRestored = true
            _uiState.value = _uiState.value.copy(isLoading = false)
            editDraftJob = viewModelScope.launch {
                _uiState.map { editDraftSnapshot() }.distinctUntilChanged().collect {
                    persistEditDraft()
                }
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            _uiState.value = _uiState.value.copy(isLoading = true, editDraftUnreadable = editDraftKey != null,
                error = "未能安全恢复清单，原内容保持不变：${error.message}")
        }
    }

    internal suspend fun persistEditDraft(): Boolean = draftMutex.withLock {
        if (_uiState.value.editDraftUnreadable) return@withLock false
        // BUG-2026-10-002：DataStore 超时已由仓库层转换为非取消型 DataStoreTimeoutException。
        // 编辑草稿必须走失败分支，绝不把未落盘清单误报为已保存。
        val key = editDraftKey ?: return@withLock false
        try {
            val version = QuantityDraftWriteFence.version(key)
            val snapshot = editDraftSnapshot()
            repository.saveEditDraft(key, snapshot)
            QuantityDraftWriteFence.saved(key, version)
            _uiState.value = _uiState.value.copy(draftSaveError = null)
            true
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            _uiState.value = _uiState.value.copy(draftSaveError = "清单未保存到本机，请勿退出：${error.message}")
            false
        }
    }

    internal suspend fun prepareDraftSubmission(): String? {
        if (_uiState.value.quantityDrafts.isNotEmpty()) {
            _uiState.value = _uiState.value.copy(error = "请先确定或取消数量修改")
            return null
        }
        val operation = editDraftOperation
        val currentKey = try {
            operation?.let { repository.editDraftKey(it) }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            null
        }
        if (currentKey == null || currentKey != editDraftKey) {
            _uiState.value = _uiState.value.copy(isLoading = false, error = "登录账号或服务器已变更，请重新进入本页")
            return null
        }
        val requestId = _uiState.value.pendingSubmissionId ?: UUID.randomUUID().toString()
        _uiState.value = _uiState.value.copy(pendingSubmissionId = requestId)
        if (!persistEditDraft()) {
            _uiState.value = _uiState.value.copy(isLoading = false, error = "清单未安全保存，暂不提交，请重试")
            return null
        }
        return requestId
    }

    private suspend fun finishDraftSubmission(result: Result<SubmitResult>) {
        val failure = result.exceptionOrNull()
        if (result.isSuccess || failure is OfflineQueuedException ||
            (failure is WmsRepository.Companion.BusinessException && failure.safeToEdit)) {
            _uiState.value = _uiState.value.copy(pendingSubmissionId = null)
        }
        persistEditDraft()
    }

    private fun draftEditingBlocked(allowUnreadableClear: Boolean = false): Boolean {
        if (stocktakeKey != null && runCatching { repository.stocktakeDraftKey() }.getOrNull() != stocktakeKey) {
            _uiState.value = _uiState.value.copy(error = "当前清单属于原账号，请重新进入本页；原草稿已保留")
            return true
        }
        if (_uiState.value.isLoading) return true
        if (_uiState.value.pendingSubmissionId != null) {
            _uiState.value = _uiState.value.copy(error = "上次提交结果待核实，请先点提交核实，不可改动原清单")
            return true
        }
        if (_uiState.value.stocktakeDraftUnreadable && !allowUnreadableClear) {
            _uiState.value = _uiState.value.copy(error = "原盘点草稿未能读取，已保留原内容；请先核对或明确清空后重新盘点")
            return true
        }
        return false
    }

    private fun canChangeQuantityContext(changed: Boolean): Boolean {
        if (changed && _uiState.value.quantityDrafts.isNotEmpty()) {
            _uiState.value = _uiState.value.copy(error = "请先确定或取消数量修改")
            return false
        }
        return true
    }

    fun updateStocktakeArea(value: String) {
        if (draftEditingBlocked() || !canChangeQuantityContext(value.trim() != _uiState.value.selectedLocation)) return
        _uiState.value = _uiState.value.copy(selectedLocation = value.trim())
    }

    fun selectLocation(value: String) {
        val location = value.trim()
        val changesAnyLine = _uiState.value.scanLines.any { it.location_code.orEmpty() != location }
        if (draftEditingBlocked() || !canChangeQuantityContext(location != _uiState.value.selectedLocation || changesAnyLine)) return
        if (location.length > 100) {
            _uiState.value = _uiState.value.copy(locationError = "库位编码最长100字")
            return
        }
        val lines = _uiState.value.scanLines.map { it.copy(location_code = location.ifBlank { null }) }
        _uiState.value = _uiState.value.copy(selectedLocation = location, scanLines = lines, locationError = null)
    }

    fun addEvidence(encodedJpeg: String) {
        if (draftEditingBlocked()) return
        if (_uiState.value.evidence.size >= 3) {
            _uiState.value = _uiState.value.copy(error = "每张单据最多3张取证照片")
            return
        }
        _uiState.value = _uiState.value.copy(evidence = _uiState.value.evidence + encodedJpeg)
    }

    fun loadLocationOptions() {
        if (editDraftOperation == null) return
        val code = _uiState.value.selectedWarehouse?.code ?: return
        locationOptionsJob?.cancel()
        val owner = RetrofitClient.sessionSnapshot()
        locationOptionsJob = viewModelScope.launch {
            _uiState.value = _uiState.value.copy(locationError = null)
            val result = repository.getLocationOptions(code)
            kotlinx.coroutines.currentCoroutineContext().ensureActive()
            if (_uiState.value.selectedWarehouse?.code != code ||
                owner.generation != RetrofitClient.sessionSnapshot().generation) return@launch
            result.fold(onSuccess = { options ->
                val state = _uiState.value
                _uiState.value = state.copy(locationEnabled = options.enabled,
                    locationOptions = options.items.orEmpty(), locationError = null)
                if (state.pendingSubmissionId == null && !state.isLoading) {
                    if (options.enabled == false) selectLocation("")
                    else if (state.selectedLocation.isBlank()) options.defaultLocation?.let { selectLocation(it) }
                }
            }, onFailure = { error ->
                _uiState.value = _uiState.value.copy(locationError = error.message ?: "库位配置加载失败，请重试")
            })
        }
    }

    private fun locationReadyForSubmission(): Boolean {
        val state = _uiState.value
        if (state.pendingSubmissionId != null) return true
        val error = when {
            state.locationEnabled == null -> "请先联网确认库位配置，再提交"
            state.locationEnabled == true && (state.selectedLocation.isBlank() ||
                state.scanLines.any { it.location_code != state.selectedLocation }) -> "请先选择本单库位，全部明细必须属于同一库位"
            else -> null
        }
        if (error != null) _uiState.value = state.copy(error = error)
        return error == null
    }

    /**
     * AI-MOB-OFFLINE-01：观察离线队列计数，驱动页面"待同步"提示条。
     *
     * 断网提交的数据已安全暂存，必须让作业员**看见**这个事实：
     * 否则他会以为提交失败而重扫一遍，反而制造重复单据。
     */
    init {
        // BUG-2026-09-13-023：本地库不可用时 offlineQueue 为 null（降级为无离线能力），
        // 此时不订阅计数流，页面按"无待同步"呈现，不得因此崩溃。
        // 注意：init 块内不允许 `return`（'return' is prohibited here），只能以 if 包裹。
        val queue = repository.offlineQueue
        if (queue != null) {
            viewModelScope.launch {
                queue.displayState.collect { snapshot ->
                    val display = snapshot.forSession(RetrofitClient.sessionSnapshot())
                    _uiState.value = _uiState.value.copy(
                        offlinePendingCount = display.pendingCount,
                        offlineFailedCount = display.failedCount,
                        offlineNeedsReview = display.needsReview,
                        offlineReadError = display.readError,
                        offlineSyncMessage = display.message,
                        offlineRetryAvailable = display.canRetry
                    )
                }
            }
        }
    }

    /** AI-MOB-OFFLINE-01：人工重试全部失败记录并立即尝试补传。 */
    fun retryOfflineSync() {
        repository.offlineQueue?.retryFailed()
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
        stockQueryJob?.cancel()
        _uiState.value = _uiState.value.copy(scannedMaterial = null, isLoading = false, error = null)
    }

    fun onStockQueryKeywordChange(keyword: String) {
        clearScannedMaterial()
        searchMaterialSuggestions(keyword, requireWarehouse = true)
    }

    fun searchMaterialSuggestions(keyword: String, requireWarehouse: Boolean = false) {
        val normalizedKeyword = keyword.trim()
        val warehouse = _uiState.value.selectedWarehouse?.code
        clearMaterialSuggestions()
        if (normalizedKeyword.isEmpty() || (requireWarehouse && warehouse.isNullOrBlank())) return

        val searchSequence = materialSearchSequence
        val owner = RetrofitClient.sessionSnapshot()
        materialSearchJob = viewModelScope.launch {
            delay(180)
            _uiState.value = _uiState.value.copy(materialSuggestionsLoading = true)
            val result = repository.searchMaterialMatches(normalizedKeyword, warehouse)
            kotlinx.coroutines.currentCoroutineContext().ensureActive()
            if (searchSequence != materialSearchSequence ||
                owner.generation != RetrofitClient.sessionSnapshot().generation) return@launch
            val matches = result.getOrNull()
            _uiState.value = _uiState.value.copy(
                materialSuggestions = matches?.items.orEmpty(),
                truncatedMaterialTotal = matches?.takeIf { it.truncated }?.total,
                materialSuggestionsLoading = false
            )
        }
    }

    fun clearMaterialSuggestions() {
        materialSearchSequence += 1
        materialSearchJob?.cancel()
        _uiState.value = _uiState.value.copy(
            materialSuggestions = emptyList(),
            truncatedMaterialTotal = null,
            materialSuggestionsLoading = false
        )
    }

    /** Retain unconfirmed text with the same account-scoped draft as the committed lines. */
    fun setQuantityDraft(key: String, draft: QuantityDraft?) {
        if (draftEditingBlocked()) return
        val current = _uiState.value.quantityDrafts
        _uiState.value = _uiState.value.copy(quantityDrafts = if (draft == null) current - key else current + (key to draft))
        scheduleQuantityDraftPersistence()
    }

    fun clearQuantityDrafts() {
        if (draftEditingBlocked()) return
        _uiState.value = _uiState.value.copy(quantityDrafts = emptyMap())
        scheduleQuantityDraftPersistence()
    }

    private fun hasPendingQuantityRecovery(): Boolean {
        val key = editDraftKey ?: stocktakeKey
        return _uiState.value.quantityDrafts.isNotEmpty() ||
            (key != null && QuantityDraftWriteFence.recovery(key) != null)
    }

    private fun scheduleQuantityDraftPersistence() {
        editDraftKey?.let { key ->
            QuantityDraftWriteFence.record(key, editDraftSnapshot())
            QuantityDraftWriteFence.enqueue(key) { persistEditDraft() }
        } ?: stocktakeKey?.let { key ->
            QuantityDraftWriteFence.record(key, stocktakeDraftSnapshot())
            QuantityDraftWriteFence.enqueue(key) { persistStocktakeDraftNow(expectedOwnerKey = key) }
        }
    }

    fun addScanLine(incoming: ScanLine): Boolean {
        if (_uiState.value.isLoading) return false
        if (draftEditingBlocked()) return false
        val line = if (editDraftOperation != null) incoming.copy(location_code =
            if (_uiState.value.locationEnabled == false) null else _uiState.value.selectedLocation.ifBlank { null }) else incoming
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
            scanFeedback = if (existingIndex >= 0) {
                "${line.material_code} 已累计 ${formatQuantity(current[existingIndex].quantity)}（本次 +${formatQuantity(line.quantity)}）"
            } else {
                "${line.material_code} 已加入 ${formatQuantity(line.quantity)}"
            },
            totalQuantity = current.sumOf { it.quantity }
        )

        if (line.material_name.isNullOrBlank() || line.material_spec.isNullOrBlank()) {
            enrichScanLineMaterial(line.material_code)
        }
        return true
    }

    /** 连续扫码每次只计一件，与手动输入中的数量互不影响。 */
    fun addCameraScanLine(code: String, location: String?): Boolean {
        val trimmed = code.trim()
        if (trimmed.isEmpty()) return false
        return addScanLine(ScanLine(material_code = trimmed, quantity = 1.0, location_code = location))
    }

    private fun quantityDraftKey(line: ScanLine): String {
        val location = line.location_code.orEmpty()
        return "${line.material_code.length}:${line.material_code}${location.length}:$location"
    }

    fun hasPendingQuantityDraft(line: ScanLine): Boolean =
        _uiState.value.quantityDrafts.containsKey(quantityDraftKey(line))

    /** 修改清单行的确切数量；保留扫码累加语义，并拒绝覆盖打开弹窗后变化的行。 */
    fun updateScanLineQuantity(expected: ScanLine, quantity: Double, allowZero: Boolean = false): Boolean {
        if (draftEditingBlocked()) return false
        if (!quantity.isFinite() || quantity < 0.0 || (!allowZero && quantity == 0.0)) {
            _uiState.value = _uiState.value.copy(error = if (allowZero)
                "请输入大于或等于 0 的有效数量" else "请输入大于 0 的有效数量")
            return false
        }
        val current = _uiState.value.scanLines.toMutableList()
        val matches = current.indices.filter {
            current[it].material_code == expected.material_code &&
                current[it].location_code.orEmpty() == expected.location_code.orEmpty()
        }
        val index = matches.singleOrNull()
        if (index == null || current[index].quantity != expected.quantity) {
            _uiState.value = _uiState.value.copy(error = "清单已变化，请取消后重新打开修改数量")
            return false
        }
        current[index] = current[index].copy(quantity = quantity)
        val total = current.sumOf { it.quantity }
        if (!total.isFinite()) {
            _uiState.value = _uiState.value.copy(error = "数量合计过大，请重新输入")
            return false
        }
        _uiState.value = _uiState.value.copy(
            scanLines = current,
            quantityDrafts = _uiState.value.quantityDrafts - quantityDraftKey(expected),
            totalQuantity = total,
            error = null,
            scanFeedback = "${expected.material_code} 数量已修改为 ${formatQuantity(quantity)}"
        )
        scheduleQuantityDraftPersistence()
        return true
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
        if (draftEditingBlocked()) return
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
            if (exact.isSuccess) return exact.getOrThrow().code == code
            (exact.exceptionOrNull() as? WmsRepository.Companion.BusinessException)?.safeToEdit != true
        } catch (cancelled: kotlinx.coroutines.CancellationException) {
            throw cancelled
        } catch (e: Exception) {
            // 网络/服务异常 → 不拦截，交由提交环节暴露问题
            true
        }
    }

    /** 异步拉取物料信息补全清单行的名称/规格/品牌（扫码进入时通常只有编码）。 */
    private fun enrichScanLineMaterial(code: String) {
        val whCode = _uiState.value.selectedWarehouse?.code
        val owner = RetrofitClient.sessionSnapshot()
        viewModelScope.launch {
            val material = repository.getMaterialInfo(code, whCode).getOrNull()?.takeIf { it.code == code }
            kotlinx.coroutines.currentCoroutineContext().ensureActive()
            if (owner.generation != RetrofitClient.sessionSnapshot().generation ||
                whCode != _uiState.value.selectedWarehouse?.code) return@launch
            material?.let {
                val enriched = _uiState.value.scanLines.map { existing ->
                    if (existing.material_code == code) {
                        existing.copy(
                            material_code = existing.material_code,
                            material_name = it.name,
                            material_spec = it.spec,
                            material_brand = it.brand,
                            material_unit = it.unit
                        )
                    } else {
                        existing
                    }
                }
                _uiState.value = _uiState.value.copy(scanLines = enriched)
            }
        }
    }

    fun removeScanLine(expected: ScanLine) {
        if (draftEditingBlocked()) return
        if (_uiState.value.isLoading) return
        val current = _uiState.value.scanLines.toMutableList()
        val index = current.indexOfFirst {
            it.material_code == expected.material_code &&
                it.location_code.orEmpty() == expected.location_code.orEmpty()
        }
        if (index < 0 || current[index].quantity != expected.quantity) {
            _uiState.value = _uiState.value.copy(scanFeedback = "明细已变化，请重新核对后移除")
            return
        }
        if (index in current.indices) {
            val needsQuantityPersistence = hasPendingQuantityRecovery()
            current.removeAt(index)
            _uiState.value = _uiState.value.copy(
                scanLines = current,
                quantityDrafts = _uiState.value.quantityDrafts - quantityDraftKey(expected),
                scanFeedback = "${expected.material_code} 已移除",
                totalQuantity = current.sumOf { it.quantity }
            )
            if (needsQuantityPersistence) scheduleQuantityDraftPersistence()
            if (stocktakeKey != null || stocktakeRestoreStarted) persistStocktakeDraft()
        }
    }

    fun clearScanLines() {
        if (_uiState.value.editDraftUnreadable) {
            clearUnreadableEditDraft()
            return
        }
        if (draftEditingBlocked(allowUnreadableClear = true)) return
        val needsQuantityPersistence = hasPendingQuantityRecovery()
        stocktakeDraftReadComplete = true
        _uiState.value = _uiState.value.copy(scanLines = emptyList(), quantityDrafts = emptyMap(), totalQuantity = 0.0,
            error = if (_uiState.value.stocktakeDraftUnreadable) null else _uiState.value.error,
            stocktakeIdentityError = null, stocktakeDraftUnreadable = false)
        stocktakeSourceWarehouse = null
        stocktakeSourceCheckId = null
        if (needsQuantityPersistence) scheduleQuantityDraftPersistence()
        if (stocktakeKey != null || stocktakeRestoreStarted) persistStocktakeDraft()
    }

    private fun clearUnreadableEditDraft() {
        if (editDraftClearJob?.isActive == true) return
        editDraftClearJob = viewModelScope.launch {
            try {
                val operation = editDraftOperation ?: error("尚未确认原草稿类型")
                restoreMutex.withLock {
                    val key = editDraftKey ?: error("尚未确认原草稿归属")
                    repository.clearOwnedEditDraft(key, operation)
                    QuantityDraftWriteFence.discard(key)
                    editDraftKey = null
                    editDraftRestored = false
                }
                restoreEditDraft(operation)
            } catch (cancelled: CancellationException) { throw cancelled
            } catch (error: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = true, editDraftUnreadable = true,
                    error = "原草稿未清空，请保留并核对：${error.message}")
            }
        }
    }

    fun loadWarehouses() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(warehousesLoading = true, error = null)
            val result = repository.getWarehouses()
            result.fold(
                onSuccess = { warehouses ->
                    val selected = _uiState.value.selectedWarehouse
                    val first = if (selected != null) warehouses.firstOrNull { it.code == selected.code }
                        ?: selected else if ((stocktakeRestoreStarted && !stocktakeRestoreComplete) || stocktakeSourceWarehouse != null) null else warehouses.singleOrNull { it.isDefault }
                    _uiState.value = _uiState.value.copy(
                        warehousesLoading = false,
                        warehouses = warehouses,
                        selectedWarehouse = first ?: _uiState.value.selectedWarehouse
                    )
                    if (first?.code != selected?.code) clearMaterialSuggestions()
                    // INV-BATCH-001-E：选择配置默认仓库后即拉取该仓进行中盘点单
                    if (first?.code != null) loadPendingCheckOrders()
                    loadLocationOptions()
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
                        selectedDepartment = if (_uiState.value.pendingSubmissionId != null)
                            _uiState.value.selectedDepartment else keep
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
        val department = _uiState.value.selectedDepartment?.id
        val version = ++employeeRequestVersion
        val owner = RetrofitClient.sessionSnapshot()
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(employeesLoading = true)
            repository.getEmployees(department) .let { response ->
                kotlinx.coroutines.currentCoroutineContext().ensureActive()
                if (version != employeeRequestVersion || department != _uiState.value.selectedDepartment?.id || owner.generation != RetrofitClient.sessionSnapshot().generation) return@launch
                response
            }.fold(
                onSuccess = { employees ->
                    val keep = _uiState.value.selectedEmployee
                        ?.let { sel -> employees.firstOrNull { it.id == sel.id } }
                    _uiState.value = _uiState.value.copy(
                        employeesLoading = false,
                        employees = employees,
                        selectedEmployee = if (_uiState.value.pendingSubmissionId != null)
                            _uiState.value.selectedEmployee else keep
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
        if (draftEditingBlocked()) return
        _uiState.value = _uiState.value.copy(selectedDepartment = department,
            selectedEmployee = if (_uiState.value.selectedDepartment?.id == department?.id) _uiState.value.selectedEmployee else null,
            employees = if (_uiState.value.selectedDepartment?.id == department?.id) _uiState.value.employees else emptyList())
        loadEmployees()
    }

    /** 选择领料人（可传 null 清除）。 */
    fun selectEmployee(employee: EmployeeDto?) {
        if (draftEditingBlocked()) return
        _uiState.value = _uiState.value.copy(selectedEmployee = employee)
    }

    // ── BUG-2026-09-18-008：入库「供应商」下拉 + 备注（选填） ──

    /**
     * 拉取供应商列表（入库页进入时调用）。
     *
     * 与 [loadDepartments] 同一条保守策略：已选中的供应商若在新列表里仍存在则保留，
     * 否则清空——避免主数据被改名/停用后，界面上还挂着一个后端已经不认的选项，
     * 提交时才吃「请选择有效的供应商」。草稿待复核期间（pendingSubmissionId 非空）
     * 一律**保留原选择**，因为此时禁止改单，清空会让用户无法按原内容重放。
     */
    fun loadSuppliers() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(suppliersLoading = true)
            repository.getSuppliers().fold(
                onSuccess = { suppliers ->
                    val keep = _uiState.value.selectedSupplier
                        ?.let { sel -> suppliers.firstOrNull { it.id == sel.id } }
                    _uiState.value = _uiState.value.copy(
                        suppliersLoading = false,
                        suppliers = suppliers,
                        selectedSupplier = if (_uiState.value.pendingSubmissionId != null)
                            _uiState.value.selectedSupplier else keep
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        suppliersLoading = false,
                        error = e.message
                    )
                }
            )
        }
    }

    /** 选择供应商（可传 null 清除）。 */
    fun selectSupplier(supplier: SupplierDto?) {
        if (draftEditingBlocked()) return
        _uiState.value = _uiState.value.copy(selectedSupplier = supplier)
    }

    /** 入库备注（送货单号等），与草稿同步落盘。 */
    fun onInboundRemarkChange(value: String) {
        if (draftEditingBlocked()) return
        _uiState.value = _uiState.value.copy(inboundRemark = value)
    }

    // ── INV-BATCH-001-E：盘点单选单（电脑端创建进行中盘点单后手机选择） ──

    /** 拉取当前所选仓库的进行中盘点单列表。 */
    fun loadPendingCheckOrders() {
        val code = _uiState.value.selectedWarehouse?.code ?: return

        val version = ++checkOrderRequestVersion
        val owner = RetrofitClient.sessionSnapshot()
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(checkOrdersLoading = true, checkOrdersError = null)
            repository.loadPendingCheckOrders(code) .let { response ->
                kotlinx.coroutines.currentCoroutineContext().ensureActive()
                if (version != checkOrderRequestVersion || code != _uiState.value.selectedWarehouse?.code || owner.generation != RetrofitClient.sessionSnapshot().generation) return@launch
                response
            }.fold(
                onSuccess = { orders ->
                    val selected = _uiState.value.selectedCheckOrder
                    val keep = if (selected == null) null
                    else orders.firstOrNull { it.id == selected.id }
                    _uiState.value = _uiState.value.copy(
                        checkOrdersLoading = false,
                        checkOrders = orders,
                        selectedCheckOrder = if (_uiState.value.pendingSubmissionId != null) selected else keep
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        checkOrdersLoading = false,
                        checkOrders = emptyList(),
                        selectedCheckOrder = if (_uiState.value.pendingSubmissionId != null || stocktakeSourceCheckId != null)
                            _uiState.value.selectedCheckOrder else null,
                        // AI-APP-FIX-201：失败必须留在弹窗里可见（Snackbar 被弹窗
                        // 遮挡且一闪而过，用户会误以为"该仓没有进行中盘点单"）。
                        checkOrdersError = e.message ?: "加载失败"
                    )
                }
            )
        }
    }

    /** 选中一张进行中盘点单（结果统一挂到该单，由电脑端完成统一出调整草稿）。 */
    fun selectCheckOrder(order: CheckOrderDto) {
        if (draftEditingBlocked() || !canChangeQuantityContext(_uiState.value.selectedCheckOrder?.id != order.id)) return
        if (_uiState.value.scanLines.isNotEmpty() && stocktakeSourceCheckId != null && stocktakeSourceCheckId != order.id) {
            _uiState.value = _uiState.value.copy(error = "恢复的清单属于原盘点单，请先核对或清空后重新盘点")
            return
        }
        _uiState.value = _uiState.value.copy(selectedCheckOrder = order, stocktakeIdentityError = null)
    }

    fun selectWarehouse(warehouse: WarehouseDto) {
        if (_uiState.value.selectedWarehouse?.code != warehouse.code && stockQueryJob?.isActive == true) {
            clearScannedMaterial()
        }
        if (draftEditingBlocked() || !canChangeQuantityContext(_uiState.value.selectedWarehouse?.code != warehouse.code)) return
        if (stocktakeSourceWarehouse != null && _uiState.value.scanLines.isNotEmpty() && stocktakeSourceWarehouse != warehouse.code) {
            _uiState.value = _uiState.value.copy(error = "恢复的清单属于原仓库，请先核对或清空后重新盘点")
            return
        }
        val changed = _uiState.value.selectedWarehouse?.code != warehouse.code
        _uiState.value = _uiState.value.copy(
            selectedWarehouse = warehouse,
            selectedLocation = if (changed) "" else _uiState.value.selectedLocation,
            locationEnabled = if (changed) null else _uiState.value.locationEnabled,
            locationOptions = if (changed) emptyList() else _uiState.value.locationOptions,
            locationError = if (changed) null else _uiState.value.locationError,
            scannedMaterial = if (changed) null else _uiState.value.scannedMaterial,
            scanLines = if (changed && editDraftOperation != null)
                _uiState.value.scanLines.map { it.copy(location_code = null) } else _uiState.value.scanLines,
            checkOrders = if (changed) emptyList() else _uiState.value.checkOrders,
            selectedCheckOrder = if (changed) null else _uiState.value.selectedCheckOrder
        )
        if (changed) {
            clearMaterialSuggestions()
            loadLocationOptions()
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
        // P2-2：先取消上一个列表请求再发新的，并用序号丢弃迟到响应
        val seq = ++stockListSequence
        stockListJob?.cancel()
        _uiState.value = _uiState.value.copy(
            stockListKeyword = kw,
            stockListLoading = true,
            stockListError = null,
            stockListItems = emptyList(),
            stockListPage = 0,
            stockListTotalPages = 0,
            stockListTotal = 0,
            // 翻页请求可能还在飞，这里必须一并复位，否则它失败后没人把
            // 底部转圈关掉（其响应已因序号过期被丢弃）
            stockListLoadingMore = false,
            stockListKeywordMaterialTotal = null,
            stockListServerTime = null,
            stockListLoaded = false
        )
        stockListJob = viewModelScope.launch {
            repository.queryStockPage(
                whParam, kw.trim(), page = 1, pageSize = STOCK_LIST_PAGE_SIZE,
                sort = _uiState.value.stockListSort.takeIf { it.isNotBlank() },
                stockFilter = _uiState.value.stockListFilter.takeIf { it.isNotBlank() }
            )
                .fold(
                    onSuccess = { data ->
                        if (seq == stockListSequence) {
                            _uiState.value = _uiState.value.copy(
                                stockListLoading = false,
                                stockListItems = data.items,
                                stockListPage = data.page,
                                stockListTotalPages = data.totalPages,
                                stockListTotal = data.total,
                                stockListKeywordMaterialTotal = data.keywordMaterialTotal,
                                stockListServerTime = data.serverTime,
                                stockListLoaded = true
                            )
                        }
                    },
                    onFailure = { e ->
                        if (seq == stockListSequence) {
                            _uiState.value = _uiState.value.copy(
                                stockListLoading = false,
                                stockListError = e.message ?: "加载失败",
                                stockListLoaded = true
                            )
                        }
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
        // 序号在 loadStockList 里自增；用户改了关键词/排序后本页结果即为过期，
        // 不能再往新列表上追加（否则会出现"搜 A 却混入 B 的物料"）。
        val seq = stockListSequence
        _uiState.value = state.copy(stockListLoadingMore = true)
        viewModelScope.launch {
            repository.queryStockPage(
                whParam, state.stockListKeyword.trim(), page = nextPage,
                pageSize = STOCK_LIST_PAGE_SIZE,
                sort = state.stockListSort.takeIf { it.isNotBlank() },
                stockFilter = state.stockListFilter.takeIf { it.isNotBlank() }
            ).fold(
                onSuccess = { data ->
                    if (seq == stockListSequence) {
                        _uiState.value = _uiState.value.copy(
                            stockListLoadingMore = false,
                            // 追加去重，避免翻页期间数据变动导致重复行
                            stockListItems = (_uiState.value.stockListItems + data.items)
                                .distinctBy { it.id },
                            stockListPage = data.page,
                            // total_pages 每页都取：它是翻页边界判定依据，数据变动时需随之更新
                            stockListTotalPages = data.totalPages,
                            // 数据截止时间每页都刷新（用户看到的是最新一页的时点）
                            stockListServerTime = data.serverTime,
                            // BUG-2026-09-12-004（R1）：总数在首页确定后不再被翻页响应覆盖。
                            // 服务端 total 为全量 count()、跨页恒定，但本字段是"共 N 条"统计值，
                            // 语义上应与分页解耦（R1：汇总统计必须与分页解耦）。此处用
                            // takeIf 保护：本页返回 0（字段缺失/异常）时不覆盖既有值，
                            // 避免非空原生类型反序列化缺省为 0 导致统计静默归零。
                            stockListTotal = data.total.takeIf { it > 0 }
                                ?: _uiState.value.stockListTotal
                        )
                    }
                },
                onFailure = { e ->
                    if (seq == stockListSequence) {
                        _uiState.value = _uiState.value.copy(
                            stockListLoadingMore = false,
                            stockListError = e.message ?: "加载失败"
                        )
                    }
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
        if (draftEditingBlocked()) return
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
        if (draftEditingBlocked()) return
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

    fun searchMaterialByCode(code: String, onResult: (Boolean) -> Unit = {}) {
        runStockQuery(code, allowFuzzy = false, onResult = onResult)
    }

    fun queryMaterialByKeyword(keyword: String) {
        runStockQuery(keyword, allowFuzzy = true)
    }

    /** 查库存只走当前仓。更换输入或仓库会取消上一条查询及其反馈。 */
    private fun runStockQuery(keyword: String, allowFuzzy: Boolean, onResult: (Boolean) -> Unit = {}) {
        val code = keyword.trim()
        if (code.isEmpty()) return
        clearScannedMaterial()
        clearMaterialSuggestions()
        val warehouse = _uiState.value.selectedWarehouse?.code?.takeIf { it.isNotBlank() }
        if (warehouse == null) {
            _uiState.value = _uiState.value.copy(error = "请先选择仓库后再查询库存")
            onResult(false)
            return
        }
        val owner = RetrofitClient.sessionSnapshot()
        _uiState.value = _uiState.value.copy(isLoading = true)
        stockQueryJob = viewModelScope.launch {
            val exact = repository.getMaterialInfo(code, warehouse)
            val fuzzy = if (exact.isFailure && allowFuzzy) repository.searchMaterialMatches(code, warehouse) else null
            kotlinx.coroutines.currentCoroutineContext().ensureActive()
            if (warehouse != _uiState.value.selectedWarehouse?.code ||
                owner.generation != RetrofitClient.sessionSnapshot().generation) {
                _uiState.value = _uiState.value.copy(isLoading = false)
                return@launch
            }
            val matches = fuzzy?.getOrNull()
            _uiState.value = _uiState.value.copy(
                isLoading = false,
                scannedMaterial = exact.getOrNull(),
                materialSuggestions = matches?.items.orEmpty(),
                truncatedMaterialTotal = matches?.takeIf { it.truncated }?.total,
                error = (fuzzy ?: exact).exceptionOrNull()?.message
            )
            onResult(exact.isSuccess)
        }
    }

    fun submitInbound(businessType: String = "采购入库") {
        viewModelScope.launch {
            if (!locationReadyForSubmission()) return@launch
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
            _uiState.value = _uiState.value.copy(inboundBusinessType =
                if (state.pendingSubmissionId == null) businessType else state.inboundBusinessType)
            val requestId = prepareDraftSubmission() ?: return@launch
            // BUG-2026-09-18-008：单头字段随请求体下发。
            // 离线补传走的也是同一份 payloadJson，因此断网时选的供应商/备注同样保留。
            val request = InboundRequest(
                lines = lines,
                businessType = _uiState.value.inboundBusinessType,
                warehouse = warehouse.code,
                warehouseCode = warehouse.code,
                supplierId = _uiState.value.selectedSupplier?.id,
                supplier = _uiState.value.selectedSupplier?.name,
                contractNo = _uiState.value.contractNo.ifBlank { null },
                remark = _uiState.value.inboundRemark.ifBlank { null },
                evidence = _uiState.value.evidence
            )
            val result = repository.submitInbound(request, requestId)
            result.fold(
                onSuccess = { submitResult ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        success = "入库成功！单号: ${submitResult.order_no}",
                        scanLines = emptyList(),
                        evidence = emptyList(),
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
                            submittedPrint = null,
                            error = null,
                                scanLines = emptyList(),
                            evidence = emptyList(),
                            totalQuantity = 0.0
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                    }
                }
            )
            finishDraftSubmission(result)
        }
    }

    fun submitOutbound() {
        viewModelScope.launch {
            if (!locationReadyForSubmission()) return@launch
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
            val requestId = prepareDraftSubmission() ?: return@launch
            val request = OutboundRequest(
                lines = lines,
                receiver = null,
                department = state.selectedDepartment?.name,
                departmentId = state.selectedDepartment?.id,
                picker = state.selectedEmployee?.name,
                warehouse = warehouse.code,
                warehouseCode = warehouse.code,
                contractNo = state.contractNo.trim().ifBlank { null }
                ,evidence = _uiState.value.evidence
            )
            val result = repository.submitOutbound(request, requestId, replay = state.pendingSubmissionId != null)
            result.fold(
                onSuccess = { submitResult ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        success = "出库成功！单号: ${submitResult.order_no}",
                        scanLines = emptyList(),
                        evidence = emptyList(),
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
                            submittedPrint = null,
                            error = null,
                                scanLines = emptyList(),
                            evidence = emptyList(),
                            totalQuantity = 0.0
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                    }
                }
            )
            finishDraftSubmission(result)
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
            if (stocktakeKey != null && runCatching { repository.stocktakeDraftKey() }.getOrNull() != stocktakeKey) {
                _uiState.value = _uiState.value.copy(error = "当前清单属于原账号，请使用原账号恢复核实")
                return@launch
            }
            val submissionOwner = RetrofitClient.sessionSnapshot()
            val state = _uiState.value
            if (state.quantityDrafts.isNotEmpty()) {
                _uiState.value = state.copy(error = "请先确定或取消数量修改")
                return@launch
            }
            if (state.stocktakeIdentityError != null && state.pendingSubmissionId == null) {
                _uiState.value = state.copy(error = state.stocktakeIdentityError)
                return@launch
            }
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
            val stored = try { repository.pendingNativeWrites().singleOrNull { it.operation == "stocktake" } }
                catch (cancelled: CancellationException) { throw cancelled }
                catch (error: Exception) {
                    _uiState.value = _uiState.value.copy(isLoading = false, error = "原请求无法读取，请保留清单：${error.message}")
                    return@launch
                }
            val requestId = state.pendingSubmissionId ?: stored?.requestId ?: UUID.randomUUID().toString()
            _uiState.value = _uiState.value.copy(pendingSubmissionId = requestId)
            if (!persistStocktakeDraftNow()) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = "盘点清单未安全保存，暂不提交")
                return@launch
            }
            val result = repository.submitStocktake(request, requestId)
            kotlinx.coroutines.currentCoroutineContext().ensureActive()
            if (submissionOwner.generation != RetrofitClient.sessionSnapshot().generation) return@launch
            result.fold(
                onSuccess = { submitResult ->
                    val msg = if (submitResult.check_no != null)
                        "盘点成功！盘点单号: ${submitResult.check_no}"
                    else "盘点提交成功"
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        success = msg,
                        pendingSubmissionId = null,
                        scanLines = emptyList(),
                        totalQuantity = 0.0
                    )
                    // BUG-2026-09-03-003：提交成功即清除断点续盘草稿，防止下次进入盘点误恢复
                    persistStocktakeDraftNow()
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
                            pendingSubmissionId = null,
                            scanLines = emptyList(),
                            totalQuantity = 0.0
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                    }
                }
            )
            val failure = result.exceptionOrNull()
            if (result.isSuccess || failure is OfflineQueuedException) {
                stocktakeSourceWarehouse = null
                stocktakeSourceCheckId = null
            }
            if (failure is WmsRepository.Companion.BusinessException && failure.safeToEdit)
                _uiState.value = _uiState.value.copy(pendingSubmissionId = null)
            persistStocktakeDraftNow()
            if (result.isSuccess) repository.acknowledgeNativeWrite("stocktake", requestId)
        }
    }

    // ============ 断点续盘（BUG-2026-09-03-003） ============

    private fun stocktakeDraftSnapshot(): StocktakeDraft {
        val state = _uiState.value
        return StocktakeDraft(
            warehouseCode = state.selectedWarehouse?.code ?: stocktakeSourceWarehouse,
            warehouseName = state.selectedWarehouse?.name,
            checkId = state.selectedCheckOrder?.id ?: stocktakeSourceCheckId,
            lines = state.scanLines, requestId = state.pendingSubmissionId,
            selectedArea = state.selectedLocation, quantityDrafts = state.quantityDrafts,
            materialUnits = state.scanLines.mapNotNull { line ->
                line.material_unit?.takeIf { it.isNotBlank() }?.let { quantityDraftKey(line) to it }
            }.toMap()
        )
    }

    /** 将当前盘点清单、仓库与所选盘点单写入本地草稿（盘点页在清单变化时调用）。 */
    private suspend fun persistStocktakeDraftNow(expectedOwnerKey: String? = null): Boolean = stocktakeDraftMutex.withLock {
        if (stocktakeRestoreStarted && !stocktakeRestoreComplete) return@withLock false
        if (stocktakeRestoreStarted && !stocktakeDraftReadComplete) {
            _uiState.value = _uiState.value.copy(draftSaveError = "原盘点草稿未安全读取，未自动覆盖；请先核对或明确清空")
            return@withLock false
        }
        return@withLock try {
            val currentKey = expectedOwnerKey ?: repository.stocktakeDraftKey()
            val key = stocktakeKey ?: currentKey.also { stocktakeKey = it }
            check(key == currentKey) { "账号已变化，原盘点草稿保持不变，请使用原账号恢复" }
            val version = QuantityDraftWriteFence.version(key)
            val snapshot = stocktakeDraftSnapshot()
            repository.saveStocktakeDraft(snapshot, key)
            QuantityDraftWriteFence.saved(key, version)
            _uiState.value = _uiState.value.copy(draftSaveError = null)
            true
        } catch (cancelled: CancellationException) { throw cancelled
        } catch (error: Exception) {
            _uiState.value = _uiState.value.copy(draftSaveError = "盘点清单未保存，请勿退出：${error.message}")
            false
        }
    }

    fun persistStocktakeDraft() { viewModelScope.launch { persistStocktakeDraftNow() } }

    fun clearStocktakeDraft() {
        viewModelScope.launch {
            val key = stocktakeKey ?: repository.stocktakeDraftKey()
            QuantityDraftWriteFence.await(key)
            stocktakeDraftMutex.withLock {
                repository.clearStocktakeDraft(key)
                QuantityDraftWriteFence.discard(key)
            }
        }
    }

    fun maybeRestoreStocktakeDraft() {
        if (stocktakeRestoreStarted) return
        stocktakeRestoreStarted = true
        _uiState.value = _uiState.value.copy(isLoading = true)
        viewModelScope.launch {
            try {
                val key = repository.stocktakeDraftKey()
                QuantityDraftWriteFence.await(key)
                stocktakeKey = key
                val storedDraft = repository.loadStocktakeDraft(key)
                val recovery = QuantityDraftWriteFence.recovery(key) as? StocktakeDraft
                val draft = recovery ?: storedDraft
                if (draft == null || draft.lines.isEmpty()) {
                    stocktakeDraftReadComplete = true
                    val legacy = repository.hasUnownedStocktakeDraft()
                    stocktakeRestoreComplete = true
                    _uiState.value = _uiState.value.copy(isLoading = false,
                        success = if (legacy) "本机保留历史盘点草稿，缺少账号来源，未自动恢复；请联系维护人员核对归属，勿重复录入" else null)
                    if (_uiState.value.warehouses.isNotEmpty() && _uiState.value.selectedWarehouse == null)
                        _uiState.value = _uiState.value.copy(selectedWarehouse = _uiState.value.warehouses.singleOrNull { it.isDefault })
                    return@launch
                }
                stocktakeSourceWarehouse = draft.warehouseCode
                stocktakeSourceCheckId = draft.checkId
                val restoredLines = draft.lines.map { line ->
                    line.copy(material_unit = draft.materialUnits?.get(quantityDraftKey(line)))
                }
                _uiState.value = _uiState.value.copy(scanLines = restoredLines, quantityDrafts = draft.quantityDrafts.orEmpty(),
                    totalQuantity = draft.lines.sumOf { it.quantity }, selectedWarehouse = null,
                    selectedCheckOrder = null, selectedLocation = draft.selectedArea.orEmpty(),
                    pendingSubmissionId = draft.requestId, stocktakeDraftUnreadable = false,
                    draftSaveError = if (recovery != null) "数量输入尚未保存到本机，请勿退出" else null)
                stocktakeDraftReadComplete = true
                val warehouses = if (_uiState.value.warehouses.isNotEmpty()) _uiState.value.warehouses
                    else repository.getWarehouses().getOrThrow()
                val warehouse = warehouses.singleOrNull { it.code == draft.warehouseCode }
                _uiState.value = _uiState.value.copy(warehouses = warehouses, selectedWarehouse = warehouse)
                if (warehouse == null) {
                    // A pending request may already have succeeded; retain its exact warehouse for receipt verification.
                    if (draft.requestId != null && !draft.warehouseCode.isNullOrBlank())
                        _uiState.value = _uiState.value.copy(selectedWarehouse = WarehouseDto(null, draft.warehouseCode, draft.warehouseName))
                    else throw IllegalStateException("原盘点仓库已停用或不存在，请保留清单核对，不可改挂其他仓库")
                }
                if (draft.checkId != null) {
                    val orders = warehouse?.code?.let { repository.loadPendingCheckOrders(it).getOrThrow() }.orEmpty()
                    val check = orders.singleOrNull { it.id == draft.checkId }
                    if (check == null && draft.requestId == null)
                        throw IllegalStateException("原盘点单已不在进行中列表，请保留清单核对")
                    _uiState.value = _uiState.value.copy(checkOrders = orders,
                        selectedCheckOrder = check ?: CheckOrderDto(draft.checkId, "待核实 #${draft.checkId}"))
                }
                _uiState.value = _uiState.value.copy(success = if (draft.requestId == null)
                    "已恢复原仓库盘点清单，请核对后继续" else "已恢复待核实提交，请使用原请求核实结果")
            } catch (cancelled: CancellationException) { throw cancelled
            } catch (error: Exception) {
                _uiState.value = _uiState.value.copy(stocktakeIdentityError = error.message,
                    stocktakeDraftUnreadable = stocktakeKey != null && !stocktakeDraftReadComplete,
                    error = "盘点恢复未完成：${error.message}")
            } finally {
                stocktakeRestoreComplete = true
                _uiState.value = _uiState.value.copy(isLoading = false)
            }
        }
    }

}

/**
 * AI-MOB-STOCK-F01：查库存列表模式每页条数。
 * 与服务端 MOBILE_API_PAGE_SIZE_DEFAULT 口径一致；仅作为单页请求大小，
 * 不作业务上限（R1：按响应 total_pages 翻页取全）。
 *
 * 清单 P2-1：原为 20。仓库物料常在数百到数千，一页 20 条意味着滑到底要翻十
 * 几次，而手机一屏能放 8~10 行——改成 50（仍在服务端上限 100 之内），翻页
 * 次数降到约 1/2.5，弱网下的体感差别最明显。
 */
private const val STOCK_LIST_PAGE_SIZE = 50
