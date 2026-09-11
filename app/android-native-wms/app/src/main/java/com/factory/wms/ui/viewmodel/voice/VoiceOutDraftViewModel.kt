package com.factory.wms.ui.viewmodel.voice

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.VoiceMaterialMatch
import com.factory.wms.data.model.VoiceOutDraftRequest
import com.factory.wms.data.model.VoiceOutDraftResult
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * 语音建单流程阶段。
 *
 * - [IDLE]       空闲
 * - [PARSING]    正在解析+匹配（调 dry_run=true）
 * - [NEED_CHOICE] 匹配到多个物料，等用户点选（R5：低置信度必须回退人工）
 * - [CONFIRMING] 已确定物料，等用户确认数量/仓库后建单
 * - [CREATING]   正在建草稿
 * - [CREATED]    草稿已建，等待跳转出库页核对
 * - [NOT_FOUND]  完全匹配不到（但仍展示"听成了什么+试过什么+最接近候选"）
 */
enum class VoiceDraftStage {
    IDLE, PARSING, NEED_CHOICE, CONFIRMING, CREATING, CREATED, NOT_FOUND
}

data class VoiceOutDraftUiState(
    val stage: VoiceDraftStage = VoiceDraftStage.IDLE,
    val loading: Boolean = false,
    val error: String? = null,
    /** 后端返回的原始语音听写内容（用于"我听到的是…"） */
    val heardText: String = "",
    /** 归一化后的文本（展示"我理解成…"，让用户知道 AI 做了什么） */
    val normalizedText: String = "",
    /** 解析出的物料关键词（如「螺丝」） */
    val keyword: String = "",
    /** 解析出的规格（如「8*25」） */
    val spec: String = "",
    /** 解析出的数量；null 表示用户没说数量，需人工填写 */
    val quantity: Double? = null,
    val unit: String = "",
    /** 候选物料（按规格相似度排序，来自后端） */
    val matches: List<VoiceMaterialMatch> = emptyList(),
    /** 用户已选中的物料（NEED_CHOICE 点选后 / 唯一命中时自动带入） */
    val selected: VoiceMaterialMatch? = null,
    /** 用户可编辑的数量（初始为解析值，可为空让用户填） */
    val editableQuantity: String = "",
    /** 后端尝试过的策略（用于向用户解释"我做过什么努力"，不编造） */
    val strategiesTried: List<String> = emptyList(),
    /** 是否发生过降级（提示结果可能不精确） */
    val degraded: Boolean = false,
    /** 可选仓库（语音建单需指定仓库） */
    val warehouses: List<WarehouseDto> = emptyList(),
    val selectedWarehouse: WarehouseDto? = null,
    /** 建单成功的草稿信息，供导航到出库页预填 */
    val createdOrderId: Int? = null,
    val createdOrderNo: String = "",
    val createdLines: List<Pair<String, Double>> = emptyList()
)

/**
 * 语音建领料单草稿的编排 ViewModel。
 *
 * 流程（两阶段协议，配合后端 /api/mobile/voice_out_draft）：
 *   ① 收到语音文本 → 调 dry_run=true 解析+匹配
 *      ├─ success    → 直接进 CONFIRMING（省用户一次点选）
 *      ├─ multiple   → 进 NEED_CHOICE，等用户点选（R5：不替用户决定）
 *      └─ not_found  → 进 NOT_FOUND，展示"听成了什么+试过什么+最接近候选"
 *   ② 用户确认物料+数量 → 调 dry_run=false 建 pending 草稿
 *   ③ CREATED → 由 UI 导航到出库页核对（提交/完成仍人工）
 *
 * 边界：只建草稿，不扣库存；数量为空时不猜、要求用户填写（R5）。
 */
class VoiceOutDraftViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(VoiceOutDraftUiState())
    val uiState: StateFlow<VoiceOutDraftUiState> = _uiState.asStateFlow()

    /** 记录本次语音原文，供消歧后回传后端（后端需要原文做别名学习/审计） */
    private var lastRawText: String = ""

    fun loadWarehouses() {
        if (_uiState.value.warehouses.isNotEmpty()) return
        viewModelScope.launch {
            repository.getWarehouses().fold(
                onSuccess = { list ->
                    _uiState.value = _uiState.value.copy(
                        warehouses = list,
                        // 默认选中第一个仓库（与出库页 loadWarehouses 行为一致）
                        selectedWarehouse = _uiState.value.selectedWarehouse
                            ?: list.firstOrNull()
                    )
                },
                onFailure = { /* 仓库加载失败不阻塞建单，建单时会再报具体错误 */ }
            )
        }
    }

    fun selectWarehouse(warehouse: WarehouseDto) {
        _uiState.value = _uiState.value.copy(selectedWarehouse = warehouse)
    }

    /**
     * 第一跳：解析语音文本并匹配物料（dry_run=true，不建单）。
     *
     * 这是"聪明 AI"的入口——后端会做六层降级匹配，尽量给出候选而不是空。
     */
    fun parseAndMatch(rawText: String) {
        val text = rawText.trim()
        if (text.isEmpty()) {
            _uiState.value = _uiState.value.copy(error = "没有听到内容，请再说一次")
            return
        }
        lastRawText = text
        _uiState.value = VoiceOutDraftUiState(
            stage = VoiceDraftStage.PARSING,
            loading = true,
            heardText = text,
            warehouses = _uiState.value.warehouses,
            selectedWarehouse = _uiState.value.selectedWarehouse,
        )
        viewModelScope.launch {
            val wh = _uiState.value.selectedWarehouse
            val request = VoiceOutDraftRequest(
                text = text,
                warehouse = wh?.code,
                warehouseCode = wh?.code,
                dryRun = true
            )
            repository.createVoiceOutDraft(request).fold(
                onSuccess = { result -> applyPreview(result) },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        loading = false,
                        stage = VoiceDraftStage.NOT_FOUND,
                        error = e.message ?: "解析失败，请重试"
                    )
                }
            )
        }
    }

    private fun applyPreview(result: VoiceOutDraftResult) {
        val matches = result.matches.orEmpty()
        val base = _uiState.value.copy(
            loading = false,
            heardText = result.heardText ?: _uiState.value.heardText,
            normalizedText = result.normalizedText.orEmpty(),
            keyword = result.keyword.orEmpty(),
            spec = result.spec.orEmpty(),
            quantity = result.quantity,
            unit = result.unit.orEmpty(),
            matches = matches,
            strategiesTried = result.strategiesTried.orEmpty(),
            degraded = result.degraded ?: false,
            editableQuantity = result.quantity?.let { formatQty(it) } ?: ""
        )
        _uiState.value = when (result.matchStatus) {
            // 唯一命中：直接进确认，省用户一次点选
            "success" -> base.copy(
                stage = VoiceDraftStage.CONFIRMING,
                selected = matches.firstOrNull()
            )
            // 多命中：等用户点选（R5 不替用户决定）
            "multiple" -> base.copy(stage = VoiceDraftStage.NEED_CHOICE)
            // 零命中：仍展示诊断信息与最接近候选，让用户能看懂发生了什么
            else -> base.copy(
                stage = VoiceDraftStage.NOT_FOUND,
                error = "没找到匹配的物料"
            )
        }
    }

    /** 用户在候选列表里点选某物料 → 进入确认阶段。 */
    fun chooseMaterial(match: VoiceMaterialMatch) {
        _uiState.value = _uiState.value.copy(
            stage = VoiceDraftStage.CONFIRMING,
            selected = match,
            error = null
        )
    }

    /** 从确认页返回候选列表（选错了）。 */
    fun backToChoice() {
        if (_uiState.value.matches.size > 1) {
            _uiState.value = _uiState.value.copy(stage = VoiceDraftStage.NEED_CHOICE)
        }
    }

    /** 用户编辑数量（语音没说数量时由人工填写）。 */
    fun onQuantityChange(text: String) {
        _uiState.value = _uiState.value.copy(editableQuantity = text)
    }

    /**
     * 第二跳：建草稿（dry_run=false）。
     *
     * 校验（不猜、不编造）：
     * - 必须已选定物料
     * - 数量必须 > 0（语音没说时要求用户填，符合 R5）
     */
    fun createDraft() {
        val state = _uiState.value
        val material = state.selected
        if (material?.code.isNullOrBlank()) {
            _uiState.value = state.copy(error = "请先选择物料")
            return
        }
        val qty = state.editableQuantity.trim().toDoubleOrNull()
        if (qty == null || qty <= 0) {
            _uiState.value = state.copy(error = "请填写领料数量（大于 0）")
            return
        }
        val wh = state.selectedWarehouse
        if (wh == null) {
            _uiState.value = state.copy(error = "请先选择仓库")
            return
        }

        _uiState.value = state.copy(stage = VoiceDraftStage.CREATING, loading = true, error = null)
        viewModelScope.launch {
            val request = VoiceOutDraftRequest(
                text = lastRawText,
                warehouse = wh.code,
                warehouseCode = wh.code,
                dryRun = false,
                materialCode = material.code,
                quantity = qty
            )
            repository.createVoiceOutDraft(request).fold(
                onSuccess = { result ->
                    val lines = result.items.orEmpty().mapNotNull { item ->
                        val code = item.code ?: return@mapNotNull null
                        code to (item.quantity ?: qty)
                    }
                    _uiState.value = _uiState.value.copy(
                        stage = VoiceDraftStage.CREATED,
                        loading = false,
                        createdOrderId = result.orderId,
                        createdOrderNo = result.orderNo.orEmpty(),
                        createdLines = lines,
                        error = null
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        stage = VoiceDraftStage.CONFIRMING,
                        loading = false,
                        error = e.message ?: "生成草稿失败，请重试"
                    )
                }
            )
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    /** 复位整个流程（关闭弹窗/重新开始）。 */
    fun reset() {
        _uiState.value = VoiceOutDraftUiState(
            warehouses = _uiState.value.warehouses,
            selectedWarehouse = _uiState.value.selectedWarehouse
        )
        lastRawText = ""
    }

    companion object {
        /** 数量显示：整数不显示小数点（1000.0 → "1000"）。 */
        fun formatQty(value: Double): String =
            if (value == value.toLong().toDouble()) value.toLong().toString()
            else value.toString()
    }
}
