package com.factory.wms.ui.util

/**
 * AI-APP-FIX-105 / BUG-2026-09-26-001：数量输入统一校验。
 *
 * 此前入库/出库/盘点/识物盘点四处手动加行均为 `toDoubleOrNull() ?: 1.0`：
 * 输入 "abc" 会被静默按 1 入库，输入 "0"、负数 "-5" 直接放行，现场无感知即错账。
 * 统一改由本函数解析：非法或 <=0 返回 null，调用方必须拦截提示，禁止静默兜底。
 */
fun String.toPositiveQtyOrNull(): Double? = trim().toDoubleOrNull()?.takeIf { it > 0.0 }
