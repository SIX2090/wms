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
    val amount: Double?,
    val remark: String? = null
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

/** 期初库存列表响应（data.items）。
 *
 * P1-C：已建账列表改为标准分页（R1），补 total/page/page_size/total_pages，
 * 并新增 built_total / built_quantity —— 本仓建账明细条数与期初数量合计。
 * 这两个汇总字段由后端基于**仓库全集**计算，与分页和 keyword 都解耦：
 * 用户翻到第 3 页时，顶部仍然显示"本仓已建账 N 项 / 合计 Q"，
 * 不会因为只加载了当前页而缩水。
 */
data class OpeningStockListData(
    val items: List<OpeningStockDto> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    @SerializedName("page_size") val pageSize: Int = 20,
    @SerializedName("total_pages") val totalPages: Int = 0,
    @SerializedName("built_total") val builtTotal: Int = 0,
    @SerializedName("built_quantity") val builtQuantity: Double = 0.0
)

/** 期初库存编辑请求（P1-C）：三个字段都可选，缺省保留原值（PATCH 语义）。 */
data class OpeningStockUpdateRequest(
    val quantity: Double? = null,
    val price: Double? = null,
    val remark: String? = null
)

/** 期初库存编辑响应（data）。[delta] 是本次数量变动差额，供提示"减少 40"。 */
data class OpeningStockUpdateResult(
    val id: Int?,
    @SerializedName("material_code") val materialCode: String?,
    val quantity: Double?,
    val price: Double?,
    val amount: Double?,
    val delta: Double?
)

/** 仓库列表响应（data.items）。后端 /api/warehouses 返回 {items: [...]} 对象。 */
data class WarehousesListData(
    val items: List<WarehouseDto> = emptyList()
)
