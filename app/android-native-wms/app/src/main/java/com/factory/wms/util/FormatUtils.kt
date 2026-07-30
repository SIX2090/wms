package com.factory.wms.util

/**
 * 格式化数量：整数时不显示小数位 (1.0 → "1", 2.5 → "2.5")
 */
fun formatQuantity(value: Double): String {
    return if (value == value.toLong().toDouble()) {
        value.toLong().toString()
    } else {
        value.toString()
    }
}

fun formatQuantity(value: Double?): String {
    return value?.let { formatQuantity(it) } ?: "-"
}