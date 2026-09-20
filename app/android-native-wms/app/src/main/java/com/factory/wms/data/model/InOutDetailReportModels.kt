package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/**
 * 移动端出入库明细模型（AI-MOB-RPT-F01 收尾：Android 消费页）。
 * 对应服务端 GET /api/mobile/report/in_out_detail 的 data 载荷：
 * 按仓库查看指定日期范围内的出入库流水明细（只读，零写操作）。
 *
 * 可空字段与 BUG-2026-08-24-007 同理由：Gson 经 Unsafe 分配实例，服务端
 * 缺字段/显式 null 时非空声明会被运行时置 null，UI 层裸用即 NPE。
 */
data class InOutDetailReportData(
    @SerializedName("warehouse") val warehouse: InOutDetailWarehouse? = null,
    @SerializedName("start_date") val startDate: String? = null,
    @SerializedName("end_date") val endDate: String? = null,
    @SerializedName("direction") val direction: String? = null,
    /** 汇总基于过滤后全集，与分页解耦（R1） */
    @SerializedName("summary") val summary: InOutDetailSummary,
    @SerializedName("items") val items: List<InOutDetailItem>,
    @SerializedName("total") val total: Int,
    @SerializedName("page") val page: Int,
    @SerializedName("page_size") val pageSize: Int,
    @SerializedName("total_pages") val totalPages: Int
)

data class InOutDetailWarehouse(
    @SerializedName("id") val id: Int? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("code") val code: String? = null
)

data class InOutDetailSummary(
    @SerializedName("total_count") val totalCount: Int,
    @SerializedName("total_in_quantity") val totalInQuantity: Double,
    @SerializedName("total_out_quantity") val totalOutQuantity: Double
)

data class InOutDetailItem(
    @SerializedName("id") val id: Int,
    /** 服务端格式化 yyyy-MM-dd HH:mm:ss，只用于显示 */
    @SerializedName("created_at") val createdAt: String? = null,
    @SerializedName("material_id") val materialId: Int? = null,
    @SerializedName("material_code") val materialCode: String? = null,
    @SerializedName("material_name") val materialName: String? = null,
    /** spec 可空列（BUG-2026-08-24-007），UI 必须判空 */
    @SerializedName("spec") val spec: String? = null,
    @SerializedName("unit") val unit: String? = null,
    @SerializedName("transaction_type") val transactionType: String? = null,
    /** 服务端已映射好的中文标签（如 采购入库/销售出库），直接展示 */
    @SerializedName("transaction_type_label") val transactionTypeLabel: String? = null,
    @SerializedName("reference_type") val referenceType: String? = null,
    @SerializedName("reference_id") val referenceId: Int? = null,
    /** 带符号数量：>0 入库，<0 出库（服务端 direction 字段同源） */
    @SerializedName("quantity") val quantity: Double,
    /** in / out / zero（与服务端口径一致，UI 着色用） */
    @SerializedName("direction") val direction: String? = null,
    @SerializedName("operator") val operator: String? = null,
    @SerializedName("location") val location: String? = null,
    @SerializedName("remark") val remark: String? = null
)
