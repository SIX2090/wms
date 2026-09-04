package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

data class ScanLine(
    val material_code: String,
    val quantity: Double,
    val price: Double? = null,
    val warehouse_code: String? = null,
    val location_code: String? = null,
    @Transient val material_name: String? = null,
    @Transient val material_spec: String? = null,
    @Transient val material_brand: String? = null
)

data class InboundRequest(
    val lines: List<ScanLine>,
    @SerializedName("business_type") val businessType: String = "采购入库",
    val warehouse: String? = null,
    @SerializedName("warehouse_code") val warehouseCode: String? = null
)

data class OutboundRequest(
    val lines: List<ScanLine>,
    @SerializedName("business_type") val businessType: String = "Android扫码出库",
    val warehouse: String? = null,
    @SerializedName("warehouse_code") val warehouseCode: String? = null,
    val receiver: String? = null,
    val department: String? = null,
    /** 合同编号（选填）：命中合同档案由后端回填 contract_id/工程名称 */
    @SerializedName("contract_no") val contractNo: String? = null
)

data class StocktakeLine(
    val material_code: String,
    val actual_stock: Double,
    val system_stock: Double? = null
)

data class StocktakeRequest(
    val lines: List<StocktakeLine>,
    val mode: String = "scan",
    val warehouse: String? = null,
    @SerializedName("warehouse_code") val warehouseCode: String? = null,
    /** INV-BATCH-001-E：所选 PC 进行中盘点单 id（必填，后端强制校验） */
    @SerializedName("check_id") val checkId: Long? = null
)

/** INV-BATCH-001-E 盘点单选单列表项（GET /api/stocktake/check_orders data.orders 元素）。 */
data class CheckOrderDto(
    val id: Long,
    @SerializedName("check_no") val checkNo: String,
    val warehouse: String? = null,
    val date: String? = null,
    val remark: String? = null,
    @SerializedName("frozen_at") val frozenAt: String? = null,
    @SerializedName("item_count") val itemCount: Int? = null
)

/** INV-BATCH-001-E 盘点单列表响应（data.orders）。 */
data class CheckOrdersListData(
    val orders: List<CheckOrderDto> = emptyList()
)

/**
 * 盘点草稿持久化负载（断点续盘，BUG-2026-09-03-003）：
 * 盘点进行中 APP 被系统回收/误关后，重新进入盘点页可恢复上次未提交清单。
 */
data class StocktakeDraft(
    @SerializedName("warehouse_code") val warehouseCode: String? = null,
    @SerializedName("warehouse_name") val warehouseName: String? = null,
    /** INV-BATCH-001-E：上次所选盘点单（恢复后自动回选，仍进行中才可提交） */
    @SerializedName("check_id") val checkId: Long? = null,
    val lines: List<ScanLine> = emptyList()
)
