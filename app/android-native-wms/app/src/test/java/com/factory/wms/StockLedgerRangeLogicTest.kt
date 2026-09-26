package com.factory.wms

import com.factory.wms.ui.util.formatQty
import com.factory.wms.ui.viewmodel.report.StockLedgerRangeLogic
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * AI-MOB-LDG-F01：库存台账日期范围与勾稽纯逻辑（StockLedgerRangeLogic）单元测试。
 *
 * 覆盖的真实风险（服务端口径：start_date 缺省=全部流水；end_date 缺省=今天；
 * start > end / end > 今天 → 400）：
 * - 空白开始日期（全部流水）翻日期时必须从今天起算，不能对空串 parse 崩掉；
 * - 开始后翻越过结束 / 结束后翻越过今天 / 结束前翻越过开始 → 服务端 400；
 * - 勾稽关系「期初 + 入 − 出 = 期末」是台账数据的根本正确性，必须可校验。
 *
 * 运行方式：`./gradlew testReleaseUnitTest`（CI 已配置该步骤）。
 */
class StockLedgerRangeLogicTest {

    private val today = "2026-09-21"

    @Test
    fun `display falls back for blank range`() {
        assertEquals("全部", StockLedgerRangeLogic.displayStart(""))
        assertEquals("2026-09-01", StockLedgerRangeLogic.displayStart("2026-09-01"))
        assertEquals(today, StockLedgerRangeLogic.displayEnd("", today))
        assertEquals("2026-09-20", StockLedgerRangeLogic.displayEnd("2026-09-20", today))
    }

    @Test
    fun `shiftStart from blank starts at today`() {
        // 全部流水状态下前翻一天 = 昨天起算
        assertEquals("2026-09-20", StockLedgerRangeLogic.shiftStart("", "", -1, today))
        // 空白起翻不得越过结束日期
        assertEquals("2026-09-20", StockLedgerRangeLogic.shiftStart("", "2026-09-20", 1, today))
    }

    @Test
    fun `shiftStart never crosses end date`() {
        assertEquals("2026-09-15", StockLedgerRangeLogic.shiftStart("2026-09-16", "2026-09-20", -1, today))
        // 越过结束 → 钳到结束日期（防服务端 400）
        assertEquals("2026-09-20", StockLedgerRangeLogic.shiftStart("2026-09-20", "2026-09-20", 1, today))
    }

    @Test
    fun `shiftEnd from blank starts at today and never future`() {
        assertEquals("2026-09-20", StockLedgerRangeLogic.shiftEnd("", "", -1, today))
        // 今天后翻 → 钳回今天（未来日期服务端 400）
        assertEquals(today, StockLedgerRangeLogic.shiftEnd("", "", 1, today))
        assertEquals(today, StockLedgerRangeLogic.shiftEnd("2026-09-01", today, 1, today))
    }

    @Test
    fun `shiftEnd never goes before start date`() {
        // 结束前翻越过开始 → 钳到开始日期（防范围倒置 400）
        assertEquals("2026-09-10", StockLedgerRangeLogic.shiftEnd("2026-09-10", "2026-09-10", -1, today))
        // 开始为空白（全部流水）时不钳下限
        assertEquals("2026-09-10", StockLedgerRangeLogic.shiftEnd("", "2026-09-11", -1, today))
    }

    @Test
    fun `clampPickedStart never crosses end date`() {
        // 选了越过结束日期的开始 → 钳到结束（防 start>end 400）
        assertEquals("2026-09-20", StockLedgerRangeLogic.clampPickedStart("2026-09-25", "2026-09-20", today))
        // 正常不越界的原样生效
        assertEquals("2026-09-10", StockLedgerRangeLogic.clampPickedStart("2026-09-10", "2026-09-20", today))
        // 结束空白 = 今天：越过今天则钳到今天
        assertEquals(today, StockLedgerRangeLogic.clampPickedStart("2026-12-31", "", today))
    }

    @Test
    fun `clampPickedEnd never future and never before start`() {
        // 选了未来日期 → 钳回今天（防 end>今天 400）
        assertEquals(today, StockLedgerRangeLogic.clampPickedEnd("2026-12-31", "2026-09-01", today))
        // 选了早于开始的结束 → 钳到开始（防范围倒置 400）
        assertEquals("2026-09-10", StockLedgerRangeLogic.clampPickedEnd("2026-09-05", "2026-09-10", today))
        // 开始空白（全部流水）不钳下限，正常生效
        assertEquals("2026-09-05", StockLedgerRangeLogic.clampPickedEnd("2026-09-05", "", today))
        // 正常不越界原样生效
        assertEquals("2026-09-15", StockLedgerRangeLogic.clampPickedEnd("2026-09-15", "2026-09-10", today))
    }

    @Test
    fun `reconciliation holds for valid ledger`() {
        // 期初 0 + 入 15 − 出 3 = 期末 12
        assertTrue(StockLedgerRangeLogic.reconciles(0.0, 15.0, 3.0, 12.0))
        // 期初 20 + 入 5 − 出 0 = 期末 25
        assertTrue(StockLedgerRangeLogic.reconciles(20.0, 5.0, 0.0, 25.0))
        // 两位小数容差内
        assertTrue(StockLedgerRangeLogic.reconciles(0.0, 0.01, 0.0, 0.014))
    }

    @Test
    fun `reconciliation fails for broken ledger`() {
        assertFalse(StockLedgerRangeLogic.reconciles(0.0, 15.0, 3.0, 11.0))
        assertFalse(StockLedgerRangeLogic.reconciles(20.0, 5.0, 1.0, 25.0))
    }

    @Test
    fun `formatQty keeps integers plain and decimals at two places`() {
        // AI-APP-FIX-403：formatQty 已从 StockLedgerRangeLogic 成员合并为
        // ui/util/Format.kt 顶层函数（六份同规则实现合一），行为不变。
        assertEquals("12", formatQty(12.0))
        assertEquals("0", formatQty(0.0))
        assertEquals("2.50", formatQty(2.5))
        assertEquals("0.75", formatQty(0.75))
    }
}
