package com.factory.wms.ui.util

import java.util.Locale

/**
 * 报表/展示数量统一格式化（AI-APP-FIX-403）：千分位分组、整数去尾零、小数两位。
 *
 * 合并原六份同规则私有实现：HomeScreen.formatQty、ReportScreens.formatReportQty、
 * StockDailyReportScreen.formatStockQty、InOutDetailReportScreen.formatInOutQty、
 * StockLedgerReportViewModel.formatQty、ScanScreens.formatStockQty（盘点页局部）。
 *
 * ⚠️ 仅用于**展示**。输入框回填请用 [com.factory.wms.util.formatQuantity]——
 * 千分位逗号会让 `toDoubleOrNull()` 解析失败。
 */
fun formatQty(value: Double): String {
    return if (value % 1.0 == 0.0) {
        String.format(Locale.US, "%,.0f", value)
    } else {
        String.format(Locale.US, "%,.2f", value)
    }
}

/** 可空版本：null 显示占位符（与 [com.factory.wms.util.formatQuantity] 的 "? → -" 口径一致）。 */
fun formatQty(value: Double?): String = value?.let { formatQty(it) } ?: "-"
