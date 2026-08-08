package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/** 移动端识别单据确认后生成入库草稿的单行明细。 */
data class InboundDraftLine(
    @SerializedName("material_code") val materialCode: String,
    val quantity: Double,
    val price: Double? = null,
    // 自动建档字段：物料档案无此名称/型号时，据 name/spec/unit 自动建档
    val name: String? = null,
    val spec: String? = null,
    val unit: String? = null
)

/** 移动端识别单据确认后生成入库草稿的请求。 */
data class InboundDraftRequest(
    val lines: List<InboundDraftLine>,
    @SerializedName("business_type") val businessType: String? = null,
    val warehouse: String? = null,
    @SerializedName("warehouse_code") val warehouseCode: String? = null,
    val remark: String? = null,
    // 置 True 时，未匹配到建档物料的识别行将按 name/spec/unit 自动建档
    @SerializedName("auto_create_material") val autoCreateMaterial: Boolean = false
)

/** 移动端识别单据确认后生成入库草稿的结果行。 */
data class InboundDraftItem(
    val code: String?,
    val name: String?,
    val quantity: Double?
)

/** 自动建档成功的物料信息。 */
data class AutoCreatedMaterial(
    val code: String? = null,
    val name: String? = null
)

/** 移动端识别单据确认后生成入库草稿的结果。 */
data class InboundDraftResult(
    @SerializedName("order_no") val orderNo: String?,
    val status: String?,
    val items: List<InboundDraftItem>? = emptyList(),
    @SerializedName("auto_created") val autoCreated: List<AutoCreatedMaterial>? = emptyList()
)