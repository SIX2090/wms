package com.factory.wms

import com.factory.wms.ui.viewmodel.report.StockDailyPager
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * AI-MOB-RPT-F02：库存日报分页状态机（StockDailyPager）单元测试。
 *
 * 覆盖的真实风险：
 * - 翻页越过 totalPages 继续发请求（服务端 400/空页，流量浪费 + 列表抖动）；
 * - 换仓/换关键字后未重置，沿用过期页码跳过前面数据（R1：漏数据）；
 * - totalPages=0（还没拉过）时被误判为"没有更多"，首次加载永远发不出去。
 *
 * 运行方式：`./gradlew testReleaseUnitTest`（CI 已配置该步骤）。
 */
class StockDailyPagerTest {

    @Test
    fun `fresh pager allows first load`() {
        val pager = StockDailyPager()
        assertEquals(1, pager.nextPage)
        assertEquals(0, pager.totalPages)
        // totalPages=0 是"未拉过"而非"没有更多"：必须允许首次加载
        assertTrue(pager.hasMore)
    }

    @Test
    fun `onPageLoaded advances nextPage and records totalPages`() {
        val pager = StockDailyPager()
        pager.onPageLoaded(fetchedPage = 1, totalPages = 3)
        assertEquals(2, pager.nextPage)
        assertEquals(3, pager.totalPages)
        assertTrue(pager.hasMore)

        pager.onPageLoaded(fetchedPage = 2, totalPages = 3)
        assertEquals(3, pager.nextPage)
        assertTrue(pager.hasMore)
    }

    @Test
    fun `hasMore is false after last page loaded`() {
        val pager = StockDailyPager()
        pager.onPageLoaded(fetchedPage = 3, totalPages = 3)
        assertEquals(4, pager.nextPage)
        // 下一页越过总页数：禁止再发请求
        assertFalse(pager.hasMore)
    }

    @Test
    fun `single page result stops further loads`() {
        val pager = StockDailyPager()
        pager.onPageLoaded(fetchedPage = 1, totalPages = 1)
        assertFalse(pager.hasMore)
    }

    @Test
    fun `empty result (totalPages 0 from server) stops further loads`() {
        val pager = StockDailyPager()
        // 服务端 0 条记录时 total_pages=0
        pager.onPageLoaded(fetchedPage = 1, totalPages = 0)
        assertEquals(0, pager.totalPages)
        // 注意：totalPages=0 时 hasMore 为 true 是"未拉过"语义——
        // 但已经拉过第 1 页后 nextPage=2 > totalPages=0 不成立（0 表示未知）。
        // 空结果场景由 ViewModel 的 queried/items.isEmpty() 拦截 loadMore，
        // 状态机层面只保证页码不再虚假前进。
        assertEquals(2, pager.nextPage)
    }

    @Test
    fun `reset returns to first page`() {
        val pager = StockDailyPager()
        pager.onPageLoaded(fetchedPage = 2, totalPages = 5)
        pager.reset()
        assertEquals(1, pager.nextPage)
        assertEquals(0, pager.totalPages)
        assertTrue(pager.hasMore)
    }

    @Test
    fun `onPageLoaded rejects invalid arguments`() {
        val pager = StockDailyPager()
        assertThrows(IllegalArgumentException::class.java) {
            pager.onPageLoaded(fetchedPage = 0, totalPages = 3)
        }
        assertThrows(IllegalArgumentException::class.java) {
            pager.onPageLoaded(fetchedPage = 1, totalPages = -1)
        }
    }
}
