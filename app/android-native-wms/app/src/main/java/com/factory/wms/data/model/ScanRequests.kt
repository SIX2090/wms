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
    @SerializedName("warehouse_code") val warehouseCode: String? = null
)

/**
 * 盘点草稿持久化负载（断点续盘，BUG-2026-09-03-003）：
 * 盘点进行中 APP 被系统回收/误关后，重新进入盘点页可恢复上次未提交清单。
 */
data class StocktakeDraft(
    @SerializedName("warehouse_code") val warehouseCode: String? = null,
    @SerializedName("warehouse_name") val warehouseName: String? = null,
    val lines: List<ScanLine> = emptyList()
)
