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
    @SerializedName("total_pages") val totalPages: Int,
    /**
     * BUG-2026-09-10-001：旧版后端不返回以下诊断字段（Gson 会置 null）。
     * 报表只统计「已完成」单据，PC 端保存后未点完成的单据不会计入，
     * 用户此前只能看到「当日暂无明细」却不知原因。可空声明，UI 必须判空。
     */
    @SerializedName("warehouse") val warehouse: String? = null,
    @SerializedName("server_today") val serverToday: String? = null,
    @SerializedName("diagnostics") val diagnostics: DailyReportDiagnostics? = null
)

/**
 * 报表空结果诊断信息：帮助现场判断「到底是没有单，还是单没完成/类型不对/查错仓」。
 * 全部字段可空：旧版后端无该节点时 Gson 直接置 null，UI 必须判空（见 BUG-2026-08-24-007）。
 */
data class DailyReportDiagnostics(
    /** 本报表纳入的业务类型（如 领料单 / Android扫码出库） */
    @SerializedName("business_types") val businessTypes: List<String>? = null,
    /** 当日该仓同方向「未完成」单据数（PC 保存后未点完成 → 不进报表） */
    @SerializedName("pending_orders") val pendingOrders: Int? = null,
    /** 当日该仓已完成但业务类型不在本报表口径内的单据分布 */
    @SerializedName("other_type_orders") val otherTypeOrders: List<DailyReportOtherType>? = null
)

data class DailyReportOtherType(
    @SerializedName("business_type") val businessType: String? = null,
    @SerializedName("orders") val orders: Int? = null
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
    // BUG-2026-08-24-007：Gson 经 Unsafe 分配实例（本类多数构造参数无默认值，
    // 不生成无参构造器，构造器默认值不会生效）。服务端响应缺字段（旧版后端
    // 无 contract_no）或字段显式为 null（material.spec 列可空）时，非空声明
    // 会被运行时置 null，UI 层 isNotBlank() 即抛 NPE 导致整 App 崩溃。
    // 故 spec / contractNo 必须声明为可空，与 supplier / department 同一模式。
    @SerializedName("spec") val spec: String? = null,
    @SerializedName("unit") val unit: String,
    @SerializedName("quantity") val quantity: Double,
    @SerializedName("price") val price: Double,
    @SerializedName("amount") val amount: Double,
    /** 采购入库时返回供应商名称 */
    @SerializedName("supplier") val supplier: String? = null,
    /** 领料单时返回领用部门名称 */
    @SerializedName("department") val department: String? = null,
    @SerializedName("operator") val operator: String,
    /** 合同编号（明细级优先，服务端回退单据头；手机端报表展示该字段） */
    @SerializedName("contract_no") val contractNo: String? = null,
    @SerializedName("remark") val remark: String,
    /**
     * BUG-2026-09-10-009：明细所属仓库（全部仓库汇总模式下逐行显示来源仓）。
     * 旧版后端不下发该字段（Gson 置 null），UI 必须判空。
     */
    @SerializedName("warehouse") val warehouse: String? = null
)
