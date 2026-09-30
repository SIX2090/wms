package com.factory.wms

import android.app.Application
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.model.DraftScanLine
import com.factory.wms.data.model.ScanEditDraft
import com.factory.wms.data.model.ScanLine
import com.factory.wms.data.repository.WmsRepository
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * BUG-2026-09-13-021：扫码行**库位选择**的真实可执行测试。
 *
 * ## 为什么需要它（M2' 替代 2：无真机的 Robolectric 补强）
 *
 * 台账登记的缺陷：Android 入出库扫码行没有库位选择，启用库位管理时只能提交
 * 空库位（后端必填闸拒单，现场白扫一单）。
 *
 * 修复契约（源码已修改，真机验收待完成）：
 * 1. `selectLocation` 是**单头库位**：写入 state.selectedLocation 并**同步落到
 *    每一行扫码行的 location_code**（移动端一单同库位，跨库位分单——与
 *    BUG-2026-09-13-022 的表头库位持久化配套）；
 * 2. 输入防御：去首尾空白；超过 100 字给明确错误且**不改写已选值**；
 * 3. 清空库位（空串）→ 行级 location_code 同步清空；
 * 4. 草稿模式下新扫的行自动盖上当前所选库位（locationEnabled=false 时写 null）。
 *
 * 运行方式：`./gradlew testReleaseUnitTest`。
 *
 * 诚实边界（AGENTS.md R8）：本测试证明 JVM 级状态联动正确，**不能替代真机验收**
 * （ScanLocationSelector 相机扫库位标签、分页候选列表的真实交互）。
 * BUG-2026-09-13-021 台账状态保持「待真机验收」；独立库位列表/扫码标签解析
 * 仍是台账登记的"下一阶段增强"。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31])
class LocationSelectionTest {

    private lateinit var context: Context
    private lateinit var repository: WmsRepository
    private lateinit var viewModel: ScanViewModel

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        repository = WmsRepository(context)
        println("[DBG-L1] LocationTest: WmsRepository 构造完成") // 诊断探针（BUG-2026-10-01-001）
        viewModel = ScanViewModel(ApplicationProvider.getApplicationContext<Application>())
        println("[DBG-L2] LocationTest: ScanViewModel 构造完成") // 诊断探针
    }

    @After
    fun tearDown() {
        RetrofitClient.setToken(null)
        RetrofitClient.setBaseUrl("")
    }

    // ---------------------------------------------------------------
    // 工具
    // ---------------------------------------------------------------

    private fun line(code: String) = ScanLine(
        material_code = code,
        quantity = 1.0,
        material_name = "物料$code",
        material_spec = "规格"
    )

    /** 草稿模式必需：seedLogin + 落一份带库位设置的草稿再恢复。 */
    private suspend fun enterDraftMode(location: String, enabled: Boolean) {
        println("[DBG-L3] enterDraftMode 进入") // 诊断探针（BUG-2026-10-01-001）
        repository.saveLoginInfo(token = "token-x", baseUrl = "https://srv.example.com",
            username = "userA", role = "admin")
        println("[DBG-L4] saveLoginInfo 返回") // 诊断探针
        val key = repository.editDraftKey("inbound")
        println("[DBG-L5] editDraftKey=$key") // 诊断探针
        // 草稿至少要有一行才落得住（空行清单会被 saveEditDraft 删除）
        repository.saveEditDraft(key, ScanEditDraft(
            lines = listOf(DraftScanLine(line("M001"), "轴承", "608", "SKF")),
            warehouse = null, department = null, employee = null,
            contractNo = "", requestId = null,
            inboundBusinessType = "采购入库",
            selectedLocation = location, locationEnabled = enabled
        ))
        println("[DBG-L6] saveEditDraft 返回") // 诊断探针
        viewModel.restoreEditDraft("inbound")
        println("[DBG-L7] restoreEditDraft 返回") // 诊断探针
    }

    // ---------------------------------------------------------------
    // 契约 1：表头库位落到每一行
    // ---------------------------------------------------------------

    @Test
    fun `selectLocation stamps location onto every scan line`() {
        viewModel.addScanLine(line("M001"))
        viewModel.addScanLine(line("M002"))

        viewModel.selectLocation("A-01")

        val state = viewModel.uiState.value
        assertEquals("A-01", state.selectedLocation)
        assertEquals(2, state.scanLines.size)
        state.scanLines.forEach { assertEquals("A-01", it.location_code) }
    }

    // ---------------------------------------------------------------
    // 契约 2：输入防御
    // ---------------------------------------------------------------

    @Test
    fun `selectLocation trims surrounding whitespace`() {
        viewModel.selectLocation("  A-01  ")
        assertEquals("A-01", viewModel.uiState.value.selectedLocation)
    }

    @Test
    fun `selectLocation rejects codes longer than 100 chars and keeps previous value`() {
        viewModel.addScanLine(line("M001"))
        viewModel.selectLocation("A-01")

        viewModel.selectLocation("L".repeat(101))

        val state = viewModel.uiState.value
        assertEquals("库位编码最长100字", state.locationError)
        // 拒绝时不得改写已选库位，也不得碰行级数据
        assertEquals("A-01", state.selectedLocation)
        assertEquals("A-01", state.scanLines[0].location_code)
    }

    // ---------------------------------------------------------------
    // 契约 3：清空库位同步清行
    // ---------------------------------------------------------------

    @Test
    fun `blank selectLocation clears location from all lines`() {
        viewModel.addScanLine(line("M001"))
        viewModel.selectLocation("A-01")
        assertEquals("A-01", viewModel.uiState.value.scanLines[0].location_code)

        viewModel.selectLocation("")

        val state = viewModel.uiState.value
        assertEquals("", state.selectedLocation)
        assertNull(state.scanLines[0].location_code)
        assertNull(state.locationError)
    }

    // ---------------------------------------------------------------
    // 契约 4：草稿模式下新扫的行自动盖当前库位
    // ---------------------------------------------------------------

    @Test
    fun `addScanLine in draft mode stamps current selected location onto new line`() = runBlocking {
        enterDraftMode(location = "A-01", enabled = true)

        viewModel.addScanLine(line("M003"))

        val state = viewModel.uiState.value
        assertEquals(2, state.scanLines.size)
        val newLine = state.scanLines.first { it.material_code == "M003" }
        assertEquals("A-01", newLine.location_code)
    }

    @Test
    fun `addScanLine in draft mode writes null location when location management disabled`() = runBlocking {
        // 库位管理关闭：控件隐藏、行级库位必须写 null（后端按关闭模式忽略库位）
        enterDraftMode(location = "A-01", enabled = false)

        viewModel.addScanLine(line("M003"))

        val state = viewModel.uiState.value
        val newLine = state.scanLines.first { it.material_code == "M003" }
        assertNull(newLine.location_code)
    }
}
