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
    @SerializedName("reorder_point") val reorderPoint: Double?
)
