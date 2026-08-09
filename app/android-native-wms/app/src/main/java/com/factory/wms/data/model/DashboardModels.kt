package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/** 移动端首页今日概览数据（对应后端 GET /api/mobile/dashboard）。 */
data class DashboardDto(
    @SerializedName("today_in_orders") val todayInOrders: Int = 0,
    @SerializedName("today_in_quantity") val todayInQuantity: Double = 0.0,
    @SerializedName("today_out_orders") val todayOutOrders: Int = 0,
    @SerializedName("today_out_quantity") val todayOutQuantity: Double = 0.0,
    @SerializedName("pending_in_orders") val pendingInOrders: Int = 0,
    @SerializedName("pending_out_orders") val pendingOutOrders: Int = 0,
    @SerializedName("alert_count") val alertCount: Int = 0,
    val date: String? = null
)