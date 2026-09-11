package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/**
 * AI-MOB-STOCK-F01：库存列表查询（分页）载荷。
 *
 * 对应服务端 `GET /api/mobile/stock/query` 的 data 节点：
 * `{items:[MaterialDto], total, page, page_size, total_pages}`。
 *
 * 服务端返回的是**仓库级账面库存**（实时聚合，非全局 Material.stock），
 * 且**不含库位分布**——库位仅 `/mobile/api/material_lookup` 在开启库位管理时下发。
 *
 * 分页字段为 R1 要求：调用方必须按 total_pages 翻页取全，不得把默认
 * page_size 当作业务上限。
 */
data class StockQueryPageData(
    @SerializedName("items") val items: List<MaterialDto>,
    @SerializedName("total") val total: Int,
    @SerializedName("page") val page: Int,
    @SerializedName("page_size") val pageSize: Int,
    @SerializedName("total_pages") val totalPages: Int
)
