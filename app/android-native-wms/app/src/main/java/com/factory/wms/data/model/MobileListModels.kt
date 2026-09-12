package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/**
 * 首页「今日概览」四项数据可下钻（AI-MOB-DRILLDOWN-01）。
 *
 * 后端 app/routes/native_api.py 早已提供三个列表接口，但手机端一直没接，
 * 导致首页四个数字里：
 * - 「待处理单据」点了完全没反应（screen = null）
 * - 「库存告警」只跳到查库存的空白搜索框，用户不知道到底哪些物料告警
 *
 * 本文件对应后端：
 * - GET /api/mobile/alert/list        库存告警清单（含缺口 gap）
 * - GET /api/mobile/in_order/list     入库单列表（status 筛选）
 * - GET /api/mobile/out_order/list    出库单列表（status 筛选）
 */

/** 库存告警项（GET /api/mobile/alert/list，仓库级口径）。 */
data class AlertItemDto(
    val id: Int?,
    val code: String?,
    val name: String?,
    val spec: String?,
    val unit: String?,
    /** 当前仓库账面库存 */
    val stock: Double?,
    @SerializedName("min_stock") val minStock: Double?,
    @SerializedName("reorder_point") val reorderPoint: Double?,
    /** 缺口 = 最低库存 - 现有库存（后端已保证 >= 0），用于排序与提示 */
    val gap: Double?
)

data class AlertListData(
    val items: List<AlertItemDto> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    @SerializedName("page_size") val pageSize: Int = 20,
    @SerializedName("total_pages") val totalPages: Int = 0
)

/** 单据列表项（GET /api/mobile/in_order/list 与 out_order/list 同结构）。 */
data class MobileOrderDto(
    val id: Int?,
    @SerializedName("order_no") val orderNo: String?,
    val date: String?,
    @SerializedName("business_type") val businessType: String?,
    val warehouse: String?,
    /** 出库单为领料部门，入库单该字段为空 */
    val department: String?,
    val status: String?,
    @SerializedName("total_amount") val totalAmount: Double?,
    val operator: String?,
    val remark: String?,
    @SerializedName("created_at") val createdAt: String?,
    @SerializedName("item_count") val itemCount: Int?
)

data class MobileOrderListData(
    val items: List<MobileOrderDto> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    @SerializedName("page_size") val pageSize: Int = 20,
    @SerializedName("total_pages") val totalPages: Int = 0
)
