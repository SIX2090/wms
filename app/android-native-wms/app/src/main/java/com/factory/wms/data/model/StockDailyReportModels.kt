package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/**
 * 移动端库存日报模型（AI-MOB-RPT-F02）。
 * 对应服务端 GET /api/mobile/report/stock_daily 的 data 载荷：
 * 按仓库查看当天各物料结存明细（只读）。
 *
 * 可空字段与 BUG-2026-08-24-007 同理由：Gson 经 Unsafe 分配实例，服务端
 * 缺字段/显式 null 时非空声明会被运行时置 null，UI 层裸用即 NPE。
 */
data class StockDailyReportData(
    @SerializedName("date") val date: String,
    /** 数据截止时间（服务端格式化 hh:mm，只用于显示） */
    @SerializedName("generated_at") val generatedAt: String? = null,
    @SerializedName("warehouse") val warehouse: StockDailyWarehouse? = null,
    @SerializedName("summary") val summary: StockDailySummary,
    @SerializedName("items") val items: List<StockDailyItem>,
    @SerializedName("total") val total: Int,
    @SerializedName("page") val page: Int,
    @SerializedName("page_size") val pageSize: Int,
    @SerializedName("total_pages") val totalPages: Int
)

data class StockDailyWarehouse(
    @SerializedName("id") val id: Int? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("code") val code: String? = null
)

/** 汇总基于过滤后全集，与分页解耦（R1） */
data class StockDailySummary(
    @SerializedName("total_materials") val totalMaterials: Int,
    @SerializedName("in_stock_materials") val inStockMaterials: Int,
    @SerializedName("zero_materials") val zeroMaterials: Int,
    @SerializedName("total_quantity") val totalQuantity: Double
)

data class StockDailyItem(
    @SerializedName("id") val id: Int,
    @SerializedName("code") val code: String,
    @SerializedName("name") val name: String,
    @SerializedName("brand") val brand: String? = null,
    /** spec 可空列（BUG-2026-08-24-007），UI 必须判空 */
    @SerializedName("spec") val spec: String? = null,
    @SerializedName("unit") val unit: String? = null,
    @SerializedName("category") val category: String? = null,
    /** 结存 = 该仓库当前库存（仓库级口径，不回退全局总账） */
    @SerializedName("stock") val stock: Double
)
