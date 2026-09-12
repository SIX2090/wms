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
    @SerializedName("total_pages") val totalPages: Int,
    /**
     * AI-MOB-STOCK-F03（清单 P1-3）：物料档案里命中该关键词的条数——**不看仓库、
     * 不看库存**。仅用于 `total == 0` 时区分两种空态：档案里根本没这个编码
     * （该去建档）／档案里有但这个仓没货或被筛选排除（该换仓或改筛选）。
     * 无关键词时服务端不下发，为 null。
     *
     * 声明为可空（BUG-2026-08-24-007）：Gson 走反射绕过 Kotlin 默认值，
     * 若声明成非空 Int，服务端不下发时会静默变 0，空态就会被误判成
     * "档案里没有"，把"该换仓"说成"该建档"——比不改还糟。
     */
    @SerializedName("keyword_material_total") val keywordMaterialTotal: Int? = null,
    /**
     * AI-MOB-STOCK-F03（清单 P2-3）：服务端数据截止时刻（hh:mm），纯展示用。
     * 查库存是要拿来决策（要不要领、领多少）的，没有截止时间用户无法判断
     * 看到的是实时值还是几分钟前的。
     */
    @SerializedName("server_time") val serverTime: String? = null
)
