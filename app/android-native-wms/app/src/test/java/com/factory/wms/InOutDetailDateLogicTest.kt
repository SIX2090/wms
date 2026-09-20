package com.factory.wms

import com.factory.wms.ui.viewmodel.report.InOutDetailDateLogic
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * AI-MOB-RPT-F01 收尾：出入库明细日期范围纯逻辑（InOutDetailDateLogic）单元测试。
 *
 * 覆盖的真实风险（服务端口径：start_date > end_date → 400；end_date > 今天 → 400）：
 * - 开始日期后翻越过结束日期 → 服务端 400，用户看到裸报错；
 * - 结束日期后翻越过今天 → 服务端 400，同上；
 * - 结束日期前翻越过开始日期 → 范围倒置 400；
 * - 平移跨月/跨年（如 01-31 +1 天、01-01 -1 天）日期错乱。
 *
 * 运行方式：`./gradlew testReleaseUnitTest`（CI 已配置该步骤）。
 */
class InOutDetailDateLogicTest {

    @Test
    fun `today returns yyyy-MM-dd format`() {
        val today = InOutDetailDateLogic.today()
        assertTrue(today.matches(Regex("\\d{4}-\\d{2}-\\d{2}")))
    }

    @Test
    fun `shift moves date within same month`() {
        assertEquals("2026-09-21", InOutDetailDateLogic.shift("2026-09-20", 1))
        assertEquals("2026-09-19", InOutDetailDateLogic.shift("2026-09-20", -1))
    }

    @Test
    fun `shift crosses month and year boundary`() {
        // 跨月：01-31 后翻一天进入 02-01
        assertEquals("2026-02-01", InOutDetailDateLogic.shift("2026-01-31", 1))
        // 跨月：03-01 前翻一天回到 02-28（2026 非闰年）
        assertEquals("2026-02-28", InOutDetailDateLogic.shift("2026-03-01", -1))
        // 跨年：01-01 前翻一天回到上一年 12-31
        assertEquals("2025-12-31", InOutDetailDateLogic.shift("2026-01-01", -1))
        assertEquals("2027-01-01", InOutDetailDateLogic.shift("2026-12-31", 1))
    }

    @Test
    fun `shiftStart clamps to end date (no inverted range)`() {
        // 开始日期后翻越过结束日期：钳到结束日期（服务端 400 前置钳制）
        assertEquals("2026-09-20", InOutDetailDateLogic.shiftStart("2026-09-20", "2026-09-20", 1))
        assertEquals("2026-09-20", InOutDetailDateLogic.shiftStart("2026-09-19", "2026-09-20", 5))
        // 未越过时正常平移
        assertEquals("2026-09-18", InOutDetailDateLogic.shiftStart("2026-09-15", "2026-09-20", 3))
        // 前翻不受结束日期限制
        assertEquals("2026-09-01", InOutDetailDateLogic.shiftStart("2026-09-15", "2026-09-20", -14))
    }

    @Test
    fun `shiftEnd clamps to today (no future date)`() {
        val today = "2026-09-20"
        // 结束日期后翻越过今天：钳到今天（服务端 400 前置钳制）
        assertEquals(today, InOutDetailDateLogic.shiftEnd("2026-09-18", today, 1, today))
        assertEquals(today, InOutDetailDateLogic.shiftEnd("2026-09-18", "2026-09-19", 7, today))
        // 未越过时正常平移
        assertEquals("2026-09-19", InOutDetailDateLogic.shiftEnd("2026-09-15", "2026-09-18", 1, today))
    }

    @Test
    fun `shiftEnd clamps to start date (no inverted range)`() {
        val today = "2026-09-20"
        // 结束日期前翻越过开始日期：钳到开始日期
        assertEquals("2026-09-15", InOutDetailDateLogic.shiftEnd("2026-09-15", "2026-09-15", -1, today))
        assertEquals("2026-09-15", InOutDetailDateLogic.shiftEnd("2026-09-15", "2026-09-18", -30, today))
    }

    @Test
    fun `shift with blank input falls back to today (no crash)`() {
        // ymd.parse 失败回退 Date()：不抛异常，返回合法日期
        val result = InOutDetailDateLogic.shift("", 0)
        assertTrue(result.matches(Regex("\\d{4}-\\d{2}-\\d{2}")))
    }
}
