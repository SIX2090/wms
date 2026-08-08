package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/** 移动端识别单据确认后生成入库草稿的单行明细。 */
data class InboundDraftLine(
    @SerializedName("material_code") val materialCode: String,
    val quantity: Double,
    val price: Double? = null
)

/** 移动端识别单据确认后生成入库草稿的请求。 */
data class InboundDraftRequest(
    val lines: List<InboundDraftLine>,
    @SerializedName("business_type") val businessType: String? = null,
    val warehouse: String? = null,
    @SerializedName("warehouse_code") val warehouseCode: String? = null,
    val remark: String? = null
)

/** 移动端识别单据确认后生成入库草稿的结果行。 */
data class InboundDraftItem(
    val code: String?,
    val name: String?,
    val quantity: Double?
)

/** 移动端识别单据确认后生成入库草稿的结果。 */
data class InboundDraftResult(
    @SerializedName("order_no") val orderNo: String?,
    val status: String?,
    val items: List<InboundDraftItem>? = emptyList()
)