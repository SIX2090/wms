package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/**
 * AI-MOB-STOCK-F01：库存列表查询（分页）载荷。
 *
 * 对应服务端 `GET /api/mobile/stock/query` 的 data 节点：
 * `{items:[MaterialDto], total, page, page_size, total_pages}`。
 *
 * 服务端返回的是**仓库级账面库存**（实时聚合，非全局 Material.stock）。
 *
 * BUG-2026-09-12-003：此前注释写「不含库位分布」，与 BUG-2026-09-10-003
 * 的修复意图（所有物料消费点都要下发 locations）矛盾——列表接口漏下发，
 * 导致同一物料扫码看得到库位、列表里看不到。现已通过复用
 * build_material_locations_map 补齐 brand 与 locations，**列表与扫码字段对齐**。
 * 库位分布仅在开启库位管理时非空。
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
