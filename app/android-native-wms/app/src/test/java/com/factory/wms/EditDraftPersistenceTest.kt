package com.factory.wms

import android.app.Application
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.model.DraftScanLine
import com.factory.wms.data.model.ScanEditDraft
import com.factory.wms.data.model.ScanLine
import com.factory.wms.data.model.SupplierDto
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.data.repository.WmsRepository
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * BUG-2026-09-13-020：未提交清单**编辑草稿持久化与恢复**的真实可执行测试。
 *
 * ## 为什么需要它（M2' 替代 2：无真机的 Robolectric 补强）
 *
 * 台账登记的缺陷：手机入出库未提交清单只存在内存里，进程被系统回收/误关即全部丢失
 * （离线队列只保存"已点提交"的作业，救不了编辑中清单）。
 *
 * 修复契约（源码已修改，真机验收待完成）：
 * 1. 草稿键 = SHA-256(server + username + operation) → 换服务器 / 换账号 / 换作业类型
 *    各自隔离，互不可见（防串号恢复出别人的清单）；
 * 2. saveEditDraft / loadEditDraft 走 DataStore 落盘，进程重启后可恢复；
 * 3. 清单清空（lines 空 / null）→ 草稿键被**删除**（删空不复活）；
 * 4. 反序列化脏行防御（BUG-2026-09-14-026 同类）：material_code 为空白的坏行被剔除，
 *    不把脏值送进 UI；
 * 5. 恢复流程（restoreEditDraft）：普通草稿 → 恢复清单 + 提示核对；**带 requestId 的
 *    中断提交** → 恢复幂等键且**禁止修改清单**（必须先核实原请求，防双花）。
 *
 * 本文件用真实 DataStore（Robolectric 文件系统）+ 真实 ScanViewModel 验证上述链路；
 * Python 源码字符串匹配测不出"恢复后 addScanLine 真的被挡住了"这种运行时行为。
 *
 * 运行方式：`./gradlew testReleaseUnitTest`。
 *
 * 诚实边界（AGENTS.md R8）：本测试证明 JVM 级持久化/恢复逻辑正确，**不能替代真机验收**
 * （杀进程后真实冷启动恢复、换账号隔离的现场操作、弱网提交中断）。BUG-2026-09-13-020
 * 台账状态保持「待真机验收」。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31])
class EditDraftPersistenceTest {

    private lateinit var context: Context
    private lateinit var repository: WmsRepository

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        repository = WmsRepository(context)
    }

    @After
    fun tearDown() {
        // saveLoginInfo 会写 RetrofitClient 单例，复位防跨用例串扰
        com.factory.wms.data.api.RetrofitClient.setToken(null)
        com.factory.wms.data.api.RetrofitClient.setBaseUrl("")
    }

    // ---------------------------------------------------------------
    // 工具
    // ---------------------------------------------------------------

    private suspend fun seedLogin(server: String, user: String) {
        // editDraftKey 从 DataStore 读 base_url/username；saveLoginInfo 是唯一公开写入口
        repository.saveLoginInfo(token = "token-x", baseUrl = server, username = user, role = "admin")
    }

    private fun sampleLine(code: String, qty: Double, location: String? = null) = ScanLine(
        material_code = code,
        quantity = qty,
        location_code = location,
        material_name = "物料$code",
        material_spec = "规格",
        material_brand = "品牌"
    )

    private fun sampleDraft(requestId: String? = null) = ScanEditDraft(
        lines = listOf(
            DraftScanLine(sampleLine("M001", 5.0, location = "A-01"), "轴承", "608", "SKF"),
            DraftScanLine(sampleLine("M002", 2.5), "螺栓", "M8", null)
        ),
        warehouse = WarehouseDto(id = 1, code = "WH01", name = "主仓"),
        department = null,
        employee = null,
        contractNo = "HD2609001",
        requestId = requestId,
        inboundBusinessType = "采购入库",
        selectedLocation = "A-01",
        locationEnabled = true,
        evidence = listOf("jpeg-base64-1"),
        supplier = SupplierDto(id = 9, code = "S001", name = "华东钢材"),
        inboundRemark = "送货单 D-1024"
    )

    // ---------------------------------------------------------------
    // 契约 1：草稿键隔离（服务器 / 账号 / 作业类型）
    // ---------------------------------------------------------------

    @Test
    fun `editDraftKey is stable per scope and isolated across server user and operation`() = runBlocking {
        seedLogin("https://srv-a.example.com", "userA")
        val k1 = repository.editDraftKey("outbound")
        assertEquals(k1, repository.editDraftKey("outbound")) // 同 scope 确定性
        assertTrue(k1.startsWith("scan_edit_"))

        seedLogin("https://srv-b.example.com", "userA")
        val k2 = repository.editDraftKey("outbound")
        assertNotEquals(k1, k2) // 换服务器 → 不同键（服务器隔离）

        seedLogin("https://srv-b.example.com", "userB")
        val k3 = repository.editDraftKey("outbound")
        assertNotEquals(k2, k3) // 换账号 → 不同键（账号隔离）

        val k4 = repository.editDraftKey("inbound")
        assertNotEquals(k3, k4) // 换作业类型 → 不同键（入/出库隔离）
    }

    @Test
    fun `editDraftKey rejects unknown operation`() = runBlocking {
        seedLogin("https://srv-a.example.com", "userA")
        var rejected = false
        try {
            repository.editDraftKey("stocktake")
        } catch (expected: IllegalArgumentException) {
            rejected = true
        }
        assertTrue(rejected)
    }

    // ---------------------------------------------------------------
    // 契约 2：落盘往返（真实 DataStore 文件）
    // ---------------------------------------------------------------

    @Test
    fun `saveEditDraft then loadEditDraft roundtrips all header and line fields`() = runBlocking {
        seedLogin("https://srv-a.example.com", "userA")
        val key = repository.editDraftKey("inbound")
        val draft = sampleDraft(requestId = "req-42")

        repository.saveEditDraft(key, draft)
        val loaded = repository.loadEditDraft(key)

        assertNotNull(loaded)
        assertEquals(2, loaded!!.lines.size)
        val l1 = loaded.lines[0]
        assertEquals("M001", l1.line.material_code)
        assertEquals(5.0, l1.line.quantity, 0.0)
        assertEquals("A-01", l1.line.location_code)
        assertEquals("轴承", l1.name)
        assertEquals("608", l1.spec)
        assertEquals("WH01", loaded.warehouse?.code)
        assertEquals("主仓", loaded.warehouse?.name)
        assertEquals("HD2609001", loaded.contractNo)
        assertEquals("req-42", loaded.requestId)
        assertEquals("A-01", loaded.selectedLocation)
        assertEquals(true, loaded.locationEnabled)
        assertEquals(1, loaded.evidence.size)
        assertEquals("华东钢材", loaded.supplier?.name)
        assertEquals("送货单 D-1024", loaded.inboundRemark)
        assertEquals("采购入库", loaded.inboundBusinessType)
    }

    // ---------------------------------------------------------------
    // 契约 3：清空即删除（删空不复活）
    // ---------------------------------------------------------------

    @Test
    fun `saving empty draft removes the key and load returns null afterwards`() = runBlocking {
        seedLogin("https://srv-a.example.com", "userA")
        val key = repository.editDraftKey("outbound")

        repository.saveEditDraft(key, sampleDraft())
        assertNotNull(repository.loadEditDraft(key))

        // 清空清单（等价于用户删光所有行）→ 必须删除草稿，恢复页不得复活旧清单
        repository.saveEditDraft(key, sampleDraft().copy(lines = emptyList()))
        assertNull(repository.loadEditDraft(key))

        // null（提交成功后的显式清除）同样删除
        repository.saveEditDraft(key, sampleDraft())
        assertNotNull(repository.loadEditDraft(key))
        repository.saveEditDraft(key, null)
        assertNull(repository.loadEditDraft(key))
    }

    // ---------------------------------------------------------------
    // 契约 4：反序列化脏行防御（BUG-2026-09-14-026 同类故障模式）
    // ---------------------------------------------------------------

    @Test
    fun `loadEditDraft drops dirty lines with blank material code`() = runBlocking {
        seedLogin("https://srv-a.example.com", "userA")
        val key = repository.editDraftKey("inbound")

        // 磁盘 JSON 里混入 material_code 为空白的坏行（Gson 绕过构造器校验的场景）
        val dirty = sampleDraft().copy(
            lines = listOf(
                DraftScanLine(sampleLine("   ", 9.0), "坏行", null, null),
                DraftScanLine(sampleLine("M001", 5.0), "轴承", "608", "SKF")
            )
        )
        repository.saveEditDraft(key, dirty)

        val loaded = repository.loadEditDraft(key)
        assertNotNull(loaded)
        assertEquals(1, loaded!!.lines.size) // 坏行被剔除
        assertEquals("M001", loaded.lines[0].line.material_code)
    }

    // ---------------------------------------------------------------
    // 契约 5：恢复流程（模拟"进程被杀后重新进入页面"）
    // ---------------------------------------------------------------

    @Test
    fun `restoreEditDraft recovers plain draft lines header location and remains editable`() = runBlocking {
        seedLogin("https://srv-a.example.com", "userA")
        val key = repository.editDraftKey("outbound")
        repository.saveEditDraft(key, sampleDraft(requestId = null))

        // 新 ViewModel = 新进程：内存清单为空，只能从 DataStore 恢复
        val viewModel = ScanViewModel(ApplicationProvider.getApplicationContext<Application>())
        viewModel.restoreEditDraft("outbound")

        val state = viewModel.uiState.value
        assertEquals(2, state.scanLines.size)
        assertEquals(7.5, state.totalQuantity, 0.0)
        assertEquals("M001", state.scanLines[0].material_code)
        assertEquals("轴承", state.scanLines[0].material_name) // 名称/规格随草稿恢复
        assertEquals("WH01", state.selectedWarehouse?.code)
        assertEquals("HD2609001", state.contractNo)
        assertEquals("A-01", state.selectedLocation)
        assertEquals("华东钢材", state.selectedSupplier?.name)
        assertEquals("已恢复上次未提交清单，请核对仓库和数量", state.success)
        assertNull(state.pendingSubmissionId)

        // 未提交过的普通草稿：恢复后仍可继续编辑（可追加行）
        viewModel.addScanLine(sampleLine("M003", 1.0))
        assertEquals(3, viewModel.uiState.value.scanLines.size)
    }

    @Test
    fun `restoreEditDraft with pending requestId keeps idempotency key and blocks editing`() = runBlocking {
        seedLogin("https://srv-a.example.com", "userA")
        val key = repository.editDraftKey("inbound")
        // 提交中断场景：幂等键已落盘，进程被杀
        repository.saveEditDraft(key, sampleDraft(requestId = "req-interrupted"))

        val viewModel = ScanViewModel(ApplicationProvider.getApplicationContext<Application>())
        viewModel.restoreEditDraft("inbound")

        val state = viewModel.uiState.value
        // 幂等键恢复：核实必须复用原键，绝不生成新单
        assertEquals("req-interrupted", state.pendingSubmissionId)
        assertEquals("已恢复待核实提交，请点提交核实原请求；核实前不可修改清单", state.success)

        // 恢复后禁止修改原清单：追加行被拒绝并提示先核实
        viewModel.addScanLine(sampleLine("M999", 1.0))
        assertEquals(2, viewModel.uiState.value.scanLines.size)
        assertNotNull(viewModel.uiState.value.error)
        assertTrue(viewModel.uiState.value.error!!.contains("待核实"))
    }
}
