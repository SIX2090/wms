package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

data class MaterialDto(
    val id: Int?,
    val code: String?,
    val name: String?,
    val brand: String?,
    val spec: String?,
    val unit: String?,
    val category: String?,
    val supplier: String?,
    val stock: Double?,
    val price: Double?,
    @SerializedName("min_stock") val minStock: Double?,
    @SerializedName("reorder_point") val reorderPoint: Double?,
    // BUG-2026-09-10-003：库位分布（开启库位管理时后端下发，未开启为空列表）。
    // 默认 null 保持 MaterialEntity.toDto() 等存量构造调用兼容。
    @SerializedName("locations") val locations: List<MaterialLocationDto>? = null
)

/** 单个库位的库存量（查库存结果卡「库位分布」展示）。 */
data class MaterialLocationDto(
    @SerializedName("location") val location: String?,
    @SerializedName("quantity") val quantity: Double?
)
