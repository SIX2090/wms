package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/**
 * 移动端每日明细报表模型。
 * 对应服务端 GET /api/mobile/report/daily_detail 的 data 载荷：
 * type=purchase_in（当日采购入库明细）/ requisition（当日领料单明细）。
 */
data class DailyReportData(
    @SerializedName("date") val date: String,
    @SerializedName("type") val type: String,
    @SerializedName("type_label") val typeLabel: String,
    @SerializedName("summary") val summary: DailyReportSummary,
    @SerializedName("items") val items: List<DailyReportItem>,
    @SerializedName("total") val total: Int,
    @SerializedName("page") val page: Int,
    @SerializedName("page_size") val pageSize: Int,
    @SerializedName("total_pages") val totalPages: Int
)

data class DailyReportSummary(
    @SerializedName("order_count") val orderCount: Int,
    @SerializedName("item_count") val itemCount: Int,
    @SerializedName("quantity") val quantity: Double,
    @SerializedName("amount") val amount: Double
)

data class DailyReportItem(
    @SerializedName("order_id") val orderId: Int,
    @SerializedName("order_no") val orderNo: String,
    @SerializedName("date") val date: String,
    @SerializedName("material_code") val materialCode: String,
    @SerializedName("material_name") val materialName: String,
    @SerializedName("spec") val spec: String,
    @SerializedName("unit") val unit: String,
    @SerializedName("quantity") val quantity: Double,
    @SerializedName("price") val price: Double,
    @SerializedName("amount") val amount: Double,
    /** 采购入库时返回供应商名称 */
    @SerializedName("supplier") val supplier: String? = null,
    /** 领料单时返回领用部门名称 */
    @SerializedName("department") val department: String? = null,
    @SerializedName("operator") val operator: String,
    @SerializedName("remark") val remark: String
)
