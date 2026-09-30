package com.factory.wms

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.model.ScanLine
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import org.junit.Before
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * BUG-2026-09-13-018：扫码累加**数量反馈状态机**的真实可执行测试。
 *
 * ## 为什么需要它（M2' 替代 2：无真机的 Robolectric 补强）
 *
 * 台账登记的缺陷行为：
 * - 扫码累加时没有任何数量反馈，现场工人不知道"这一下扫上没有、累计到几了"；
 * - 移除按钮按**列表索引**直接删除，与工人眼睛看到的行可能错位（删除时清单已被
 *   重复扫码改变）→ 误删别的物料行。
 *
 * 修复契约（源码已修改，真机验收待完成）：
 * 1. 新物料行 → 反馈「{编码} 已加入 {数量}」；
 * 2. 同物料（编码+库位）重复扫 → **合并为一行**且反馈「{编码} 已累计 {总数}（本次 +{本次数}）」；
 * 3. 移除按**物料编码+库位**重新定位，且要求快照数量与当前一致，不一致 → 拒绝删除并提示
 *    「明细已变化，请重新核对后移除」（防误删）；
 * 4. 盘点替换确认（replaceScanLineQuantity）→ 数量**替换**而非累加（防实盘数翻倍）。
 *
 * 本文件锁死上述状态机的运行时行为，防止后续重构悄悄回退到"按索引删/无反馈/替换变累加"。
 * 之前 `tests/` 下的 Python 源码字符串匹配只能证明"代码里有这些字符串"，
 * 证明不了**状态机真的这么转移**——这正是本测试补的洞。
 *
 * 运行方式：`./gradlew testReleaseUnitTest`（CI Android APK Build / unit-test job）。
 *
 * 诚实边界（AGENTS.md R8）：本测试证明 JVM 级状态机正确，**不能替代真机验收**
 * （相机弹窗内反馈可见性、音效/震动体感、连续扫码节奏）。BUG-2026-09-13-018
 * 台账状态保持「待真机验收」。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31]) // 与现场设备 HUAWEI LIO-AN00（Android 12 / sdk 31）对齐
class ScanFeedbackTest {

    private lateinit var viewModel: ScanViewModel

    @Before
    fun setUp() {
        // 构造即覆盖 BUG-2026-09-13-023 的启动链：WmsRepository 建库失败降级、
        // offlineQueue 惰性解析 api（BUG-2026-09-14-029）都不能在此抛异常。
        // 无真机环境下，"ScanViewModel 可以在 Robolectric 沙箱里完整构造出来"
        // 本身就是对三层兜底的运行时证据。
        viewModel = ScanViewModel(ApplicationProvider.getApplicationContext<Application>())
        println("[DBG-S1] ScanFeedbackTest: ScanViewModel 构造完成") // 诊断探针（BUG-2026-10-01-001）
    }

    // ---------------------------------------------------------------
    // 工具
    // ---------------------------------------------------------------

    /**
     * 名称/规格**必须**填：addScanLine 对名称或规格为空的行走异步补全（enrich），
     * 会发起网络请求；填满后本测试纯状态机、零网络依赖。
     */
    private fun line(code: String, qty: Double, location: String? = null) = ScanLine(
        material_code = code,
        quantity = qty,
        location_code = location,
        material_name = "物料$code",
        material_spec = "规格"
    )

    // ---------------------------------------------------------------
    // 契约 1：新行反馈「已加入」
    // ---------------------------------------------------------------

    @Test
    fun `addScanLine new material shows joined feedback with code and quantity`() {
        viewModel.addScanLine(line("M001", 5.0))

        val state = viewModel.uiState.value
        assertEquals(1, state.scanLines.size)
        assertEquals("M001", state.scanLines[0].material_code)
        assertEquals(5.0, state.scanLines[0].quantity, 0.0)
        assertEquals(5.0, state.totalQuantity, 0.0)
        assertEquals("M001 已加入 5", state.scanFeedback)
    }

    // ---------------------------------------------------------------
    // 契约 2：同物料重复扫合并为一行，反馈带「累计 + 本次」
    // ---------------------------------------------------------------

    @Test
    fun `addScanLine same material accumulates into one line with total and delta feedback`() {
        viewModel.addScanLine(line("M001", 5.0))
        viewModel.addScanLine(line("M001", 3.0))

        val state = viewModel.uiState.value
        assertEquals(1, state.scanLines.size)
        assertEquals(8.0, state.scanLines[0].quantity, 0.0)
        assertEquals(8.0, state.totalQuantity, 0.0)
        assertEquals("M001 已累计 8（本次 +3）", state.scanFeedback)
    }

    @Test
    fun `addScanLine same code different location stays separate lines`() {
        // 库位维度：同编码不同库位是两条独立明细（BUG-021 的行级库位归属），
        // 不得被合并后丢失库位信息。
        viewModel.addScanLine(line("M001", 5.0, location = "A-01"))
        viewModel.addScanLine(line("M001", 2.0, location = "B-02"))

        val state = viewModel.uiState.value
        assertEquals(2, state.scanLines.size)
        assertEquals(7.0, state.totalQuantity, 0.0)
        assertEquals(5.0, state.scanLines.first { it.location_code == "A-01" }.quantity, 0.0)
        assertEquals(2.0, state.scanLines.first { it.location_code == "B-02" }.quantity, 0.0)
    }

    // ---------------------------------------------------------------
    // 契约 3：移除按编码+库位定位 + 数量快照复核，防误删
    // ---------------------------------------------------------------

    @Test
    fun `removeScanLine with stale quantity refuses and asks to recheck`() {
        viewModel.addScanLine(line("M001", 5.0))

        // 工人看到的是"数量 4"的旧快照（重复扫码已把它累到 5）→ 必须拒绝，不得误删
        viewModel.removeScanLine(line("M001", 4.0))

        val state = viewModel.uiState.value
        assertEquals(1, state.scanLines.size) // 未被删除
        assertEquals("明细已变化，请重新核对后移除", state.scanFeedback)
    }

    @Test
    fun `removeScanLine with matching snapshot removes and reports removal`() {
        viewModel.addScanLine(line("M001", 5.0))
        viewModel.addScanLine(line("M002", 2.0))

        viewModel.removeScanLine(line("M001", 5.0))

        val state = viewModel.uiState.value
        assertEquals(1, state.scanLines.size)
        assertEquals("M002", state.scanLines[0].material_code)
        assertEquals(2.0, state.totalQuantity, 0.0)
        assertEquals("M001 已移除", state.scanFeedback)
    }

    @Test
    fun `removeScanLine locates by code and location not by index`() {
        // 反例防回归：如果移除回退成"按索引删"，删第二行会命中 B-02 之外的目标。
        // 这里用编码+库位快照删 B-02，断言 A-01 完好。
        viewModel.addScanLine(line("M001", 5.0, location = "A-01"))
        viewModel.addScanLine(line("M001", 2.0, location = "B-02"))

        viewModel.removeScanLine(line("M001", 2.0, location = "B-02"))

        val state = viewModel.uiState.value
        assertEquals(1, state.scanLines.size)
        assertEquals("A-01", state.scanLines[0].location_code)
        assertEquals(5.0, state.scanLines[0].quantity, 0.0)
    }

    // ---------------------------------------------------------------
    // 契约 4：盘点替换确认——替换而非累加（防实盘数翻倍）
    // ---------------------------------------------------------------

    @Test
    fun `replaceScanLineQuantity replaces quantity instead of accumulating`() {
        viewModel.addScanLine(line("M001", 5.0))

        // 同物料第二次扫（盘点场景）：工人扫的是"现在还有 3 个"的实盘数，
        // 确认替换后必须是 3，而不是 5+3=8（翻倍=盘点事故）。
        viewModel.replaceScanLineQuantity(line("M001", 3.0))

        val state = viewModel.uiState.value
        assertEquals(1, state.scanLines.size)
        assertEquals(3.0, state.scanLines[0].quantity, 0.0)
        assertEquals(3.0, state.totalQuantity, 0.0)
    }

    @Test
    fun `existingLineQuantity reports current quantity per code and location`() {
        // 盘点重复扫码确认弹窗的判定依据：告诉工人"清单里这个码已经有 N 个"。
        viewModel.addScanLine(line("M001", 5.0, location = "A-01"))
        viewModel.addScanLine(line("M001", 2.0, location = "B-02"))
        viewModel.addScanLine(line("M002", 1.0))

        assertEquals(5.0, viewModel.existingLineQuantity("M001", "A-01")!!, 0.0)
        assertEquals(2.0, viewModel.existingLineQuantity("M001", "B-02")!!, 0.0)
        assertEquals(1.0, viewModel.existingLineQuantity("M002")!!, 0.0)
        assertNull(viewModel.existingLineQuantity("M003"))
        assertNull(viewModel.existingLineQuantity("M003", "A-01"))
    }

    @Test
    fun `existingLineQuantity trims code whitespace before matching`() {
        viewModel.addScanLine(line("M001", 5.0))
        assertEquals(5.0, viewModel.existingLineQuantity("  M001  ")!!, 0.0)
    }
}
