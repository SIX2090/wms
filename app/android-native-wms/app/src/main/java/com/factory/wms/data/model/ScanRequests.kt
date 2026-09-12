package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

data class ScanLine(
    val material_code: String,
    val quantity: Double,
    val price: Double? = null,
    val warehouse_code: String? = null,
    val location_code: String? = null,
    @Transient val material_name: String? = null,
    @Transient val material_spec: String? = null,
    @Transient val material_brand: String? = null
)

data class InboundRequest(
    val lines: List<ScanLine>,
    @SerializedName("business_type") val businessType: String = "采购入库",
    val warehouse: String? = null,
    @SerializedName("warehouse_code") val warehouseCode: String? = null
)

data class OutboundRequest(
    val lines: List<ScanLine>,
    // BUG-2026-09-10-002：手机端出库即仓库领料，业务类型与 PC 领料单统一为「领料单」；
    // 旧的 "Android扫码出库" 会让手机出的库进不了每日报表、PC 领料列表也看不到。
    @SerializedName("business_type") val businessType: String = "领料单",
    val warehouse: String? = null,
    @SerializedName("warehouse_code") val warehouseCode: String? = null,
    val receiver: String? = null,
    val department: String? = null,
    /** 2026-09-12 领料部门（选填）：Department 主键，后端写入 OutOrder.department_id */
    @SerializedName("department_id") val departmentId: Long? = null,
    /** 2026-09-12 领料人（选填）：员工姓名，后端写入 OutOrder.picker */
    val picker: String? = null,
    /** 合同编号（选填）：命中合同档案由后端回填 contract_id/工程名称 */
    @SerializedName("contract_no") val contractNo: String? = null
)

data class StocktakeLine(
    val material_code: String,
    val actual_stock: Double,
    val system_stock: Double? = null,
    /** 启用库位管理时作为盘点区域/库位写入盘点明细。 */
    val area: String? = null
)

data class StocktakeRequest(
    val lines: List<StocktakeLine>,
    val mode: String = "scan",
    val warehouse: String? = null,
    @SerializedName("warehouse_code") val warehouseCode: String? = null,
    /** INV-BATCH-001-E：所选 PC 进行中盘点单 id（必填，后端强制校验） */
    @SerializedName("check_id") val checkId: Long? = null
)

/** INV-BATCH-001-E 盘点单选单列表项（GET /api/stocktake/check_orders data.orders 元素）。 */
data class CheckOrderDto(
    val id: Long,
    @SerializedName("check_no") val checkNo: String,
    val warehouse: String? = null,
    val date: String? = null,
    val remark: String? = null,
    @SerializedName("frozen_at") val frozenAt: String? = null,
    @SerializedName("item_count") val itemCount: Int? = null
)

/** INV-BATCH-001-E 盘点单列表响应（data.orders）。 */
data class CheckOrdersListData(
    val orders: List<CheckOrderDto> = emptyList()
)

/**
 * AI-MOB-CHECK-F01 盘点记录回查项（GET /api/mobile/stocktake/list data.items 元素）。
 *
 * 后端仅返回本人（operator_id == 当前登录用户）提交的记录。
 * 注意 BUG-2026-08-24-007：后端可空列在 Kotlin 侧必须声明为可空，
 * Gson 绕过 Kotlin 默认值，非空声明会在反序列化时抛异常。
 */
data class StocktakeRecordDto(
    val id: Long = 0,
    @SerializedName("check_no") val checkNo: String? = null,
    val date: String? = null,
    val warehouse: String? = null,
    /** completed（正常）/ void（已作废留痕） */
    val status: String? = null,
    val remark: String? = null,
    @SerializedName("created_at") val createdAt: String? = null,
    /** 本单盘点明细条数 */
    @SerializedName("item_count") val itemCount: Int? = null,
    /** 其中有差异的条数 */
    @SerializedName("diff_count") val diffCount: Int? = null,
    /** 关联的 PC 盘点批次单号（INV-BATCH-001-E 后手机盘点一律挂批次） */
    @SerializedName("batch_no") val batchNo: String? = null,
    @SerializedName("batch_status") val batchStatus: String? = null,
    @SerializedName("batch_status_label") val batchStatusLabel: String? = null,
    /** 调整草稿审核状态：pending 待审核 / completed 已审核 / 空串 未生成 */
    @SerializedName("adjustment_status") val adjustmentStatus: String? = null
)

/** AI-MOB-CHECK-F01 盘点记录回查响应（分页信封，R1）。 */
data class StocktakeRecordListData(
    val items: List<StocktakeRecordDto> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    @SerializedName("page_size") val pageSize: Int = 20,
    @SerializedName("total_pages") val totalPages: Int = 0
)

/**
 * 盘点草稿持久化负载（断点续盘，BUG-2026-09-03-003）：
 * 盘点进行中 APP 被系统回收/误关后，重新进入盘点页可恢复上次未提交清单。
 */
data class StocktakeDraft(
    @SerializedName("warehouse_code") val warehouseCode: String? = null,
    @SerializedName("warehouse_name") val warehouseName: String? = null,
    /** INV-BATCH-001-E：上次所选盘点单（恢复后自动回选，仍进行中才可提交） */
    @SerializedName("check_id") val checkId: Long? = null,
    val lines: List<ScanLine> = emptyList()
)
