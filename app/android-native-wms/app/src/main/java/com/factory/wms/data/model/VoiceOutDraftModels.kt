package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/**
 * 语音建单（领料单草稿）请求。
 *
 * 对应后端 `POST /api/mobile/voice_out_draft` 的两阶段协议：
 * - [dryRun] = true  → 只解析+匹配，返回候选供用户点选（不建单）
 * - [dryRun] = false → 用用户确认的 [materialCode]/[quantity] 建草稿
 *
 * 边界：只建 pending 草稿，不扣库存；多命中必须由用户点选后才建单（R5）。
 */
data class VoiceOutDraftRequest(
    /** 语音原文，如「领8*25螺丝 1000个」 */
    val text: String,
    val warehouse: String? = null,
    @SerializedName("warehouse_code") val warehouseCode: String? = null,
    /** 领料人（手工输入） */
    val picker: String? = null,
    /** true=只解析匹配（消歧用）；false=建草稿 */
    @SerializedName("dry_run") val dryRun: Boolean = true,
    /** 消歧后用户选定的物料编码（dryRun=false 时必填） */
    @SerializedName("material_code") val materialCode: String? = null,
    /** 消歧后确认的数量（dryRun=false 时必填；语音未说数量时由用户填写） */
    val quantity: Double? = null
)

/** 语音匹配到的候选物料（含相似度与命中策略，用于排序与向用户解释）。 */
data class VoiceMaterialMatch(
    @SerializedName("material_id") val materialId: Int? = null,
    val code: String? = null,
    val name: String? = null,
    val spec: String? = null,
    val unit: String? = null,
    val category: String? = null,
    val price: Double? = null,
    /** 规格相似度 0~100，越大越像（后端排序依据） */
    val score: Int? = null,
    /** 命中策略：alias / exact_code / fuzzy_full / root_fallback / spec_only / ai_* */
    val strategy: String? = null
)

/** 建单成功后返回的明细行。 */
data class VoiceOutDraftItem(
    val code: String? = null,
    val name: String? = null,
    val spec: String? = null,
    val unit: String? = null,
    val quantity: Double? = null
)

/**
 * 语音建单结果（两阶段共用）。
 *
 * [stage] 取值：
 * - "preview" → 仅解析匹配（dry_run=true），看 [matchStatus]/[matches]
 * - "created" → 已建草稿，看 [orderNo]/[items]
 */
data class VoiceOutDraftResult(
    val stage: String? = null,
    // ── preview 阶段 ──
    @SerializedName("heard_text") val heardText: String? = null,
    @SerializedName("normalized_text") val normalizedText: String? = null,
    val keyword: String? = null,
    /** 关键词拆出的物料词根（如「螺丝」） */
    val root: String? = null,
    /** 识别到的规格（如「8*25」） */
    val spec: String? = null,
    val quantity: Double? = null,
    val unit: String? = null,
    /** success / multiple / not_found */
    @SerializedName("match_status") val matchStatus: String? = null,
    val matches: List<VoiceMaterialMatch>? = emptyList(),
    /** 后端尝试过的匹配策略，用于向用户解释"我做过哪些努力"（不编造） */
    @SerializedName("strategies_tried") val strategiesTried: List<String>? = emptyList(),
    /** 是否发生过降级（提示用户结果可能不精确） */
    val degraded: Boolean? = false,
    // ── created 阶段 ──
    @SerializedName("order_id") val orderId: Int? = null,
    @SerializedName("order_no") val orderNo: String? = null,
    val status: String? = null,
    val picker: String? = null,
    val items: List<VoiceOutDraftItem>? = emptyList()
)
