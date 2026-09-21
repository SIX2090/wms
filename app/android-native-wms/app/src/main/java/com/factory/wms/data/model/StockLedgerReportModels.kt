package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/**
 * 移动端库存台账模型（AI-MOB-LDG-F01）。
 * 对应服务端 GET /api/mobile/report/stock_ledger 的 data 载荷：
 * 按单一物料查看库存流水账（期初结存/逐笔入出/行级结存/期末结存），
 * 只读、零写操作，口径与电脑端库存台账 _collect_ledger_rows 同源。
 *
 * 可空字段与 BUG-2026-08-24-007 同理由：Gson 经 Unsafe 分配实例，服务端
 * 缺字段/显式 null 时非空声明会被运行时置 null，UI 层裸用即 NPE。
 */
data class StockLedgerReportData(
    @SerializedName("warehouse") val warehouse: StockLedgerWarehouse? = null,
    @SerializedName("material") val material: StockLedgerMaterial? = null,
    /** 空串 = 全部流水（从建账起算，用户决策口径） */
    @SerializedName("start_date") val startDate: String? = null,
    @SerializedName("end_date") val endDate: String? = null,
    /** 汇总基于过滤后全集，与分页解耦（R1） */
    @SerializedName("summary") val summary: StockLedgerSummary,
    @SerializedName("items") val items: List<StockLedgerItem>,
    @SerializedName("total") val total: Int,
    @SerializedName("page") val page: Int,
    @SerializedName("page_size") val pageSize: Int,
    @SerializedName("total_pages") val totalPages: Int,
    /** 服务端 5 万行截断告警（BUG-2026-09-07-003 通道），未超限缺省/null */
    @SerializedName("truncated") val truncated: Boolean? = null,
    @SerializedName("truncated_total") val truncatedTotal: Int? = null
)

data class StockLedgerWarehouse(
    @SerializedName("id") val id: Int? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("code") val code: String? = null
)

data class StockLedgerMaterial(
    @SerializedName("id") val id: Int? = null,
    @SerializedName("code") val code: String? = null,
    @SerializedName("name") val name: String? = null,
    /** spec 可空列（BUG-2026-08-24-007），UI 必须判空 */
    @SerializedName("spec") val spec: String? = null,
    @SerializedName("unit") val unit: String? = null,
    /** 当前仓库级结存（A11/R2：仓库级口径，绝不回退全局总账 material.stock） */
    @SerializedName("warehouse_stock") val warehouseStock: Double? = null
)

data class StockLedgerSummary(
    /** 流水笔数（不含期初/合计 marker 行——服务端已剔除） */
    @SerializedName("count") val count: Int,
    /** 期初结存（start_date 前的累计；全部流水时为 0 = 从建账起算） */
    @SerializedName("opening_balance") val openingBalance: Double,
    @SerializedName("total_in_quantity") val totalInQuantity: Double,
    @SerializedName("total_out_quantity") val totalOutQuantity: Double,
    /** 期末结存 = 期初 + 本期入库 − 本期出库（勾稽关系由单测锁定） */
    @SerializedName("ending_balance") val endingBalance: Double
)

data class StockLedgerItem(
    /** 服务端格式化 yyyy-MM-dd，只用于显示 */
    @SerializedName("date") val date: String? = null,
    /** 单据类型中文标签（如 采购入库/销售出库/库存调整），直接展示 */
    @SerializedName("reference_type") val referenceType: String? = null,
    @SerializedName("reference_no") val referenceNo: String? = null,
    @SerializedName("in_quantity") val inQuantity: Double,
    @SerializedName("out_quantity") val outQuantity: Double,
    /** 该行发生后的结存（running balance，台账核心列） */
    @SerializedName("balance_quantity") val balanceQuantity: Double,
    @SerializedName("operator") val operator: String? = null,
    @SerializedName("location") val location: String? = null,
    @SerializedName("remark") val remark: String? = null
)
