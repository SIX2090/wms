package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

data class ScanLine(
    val material_code: String,
    val quantity: Double,
    val price: Double? = null,
    val warehouse_code: String? = null,
    val location_code: String? = null
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
    val department: String? = null
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