package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/** 移动端仓库选项（期初建账等场景选择仓库）。 */
data class WarehouseDto(
    val id: Int?,
    val code: String?,
    val name: String?
)

/** 移动端期初库存列表项。 */
data class OpeningStockDto(
    val id: Int?,
    @SerializedName("material_code") val materialCode: String?,
    @SerializedName("material_name") val materialName: String?,
    val spec: String?,
    val unit: String?,
    @SerializedName("warehouse_id") val warehouseId: Int?,
    @SerializedName("warehouse_name") val warehouseName: String?,
    val date: String?,
    val quantity: Double?,
    val price: Double?,
    val amount: Double?
)

/** 期初库存单行明细（扫码录入）。 */
data class OpeningStockLine(
    @SerializedName("material_code") val materialCode: String,
    val quantity: Double,
    val price: Double? = null,
    val remark: String? = null,
    @Transient val materialName: String? = null,
    @Transient val materialSpec: String? = null,
    @Transient val materialBrand: String? = null
)

/** 期初建账提交请求。 */
data class OpeningStockRequest(
    val date: String,
    @SerializedName("warehouse_code") val warehouseCode: String,
    val lines: List<OpeningStockLine>
)

/** 期初库存列表响应（data.items）。 */
data class OpeningStockListData(
    val items: List<OpeningStockDto> = emptyList()
)

/** 仓库列表响应（data.items）。后端 /api/warehouses 返回 {items: [...]} 对象。 */
data class WarehousesListData(
    val items: List<WarehouseDto> = emptyList()
)
