package com.factory.wms

import android.app.Application
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.model.DraftScanLine
import com.factory.wms.data.model.ScanEditDraft
import com.factory.wms.data.model.ScanLine
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.data.repository.WmsRepository
import com.factory.wms.data.repository.WmsRepository.Companion.DataStoreTimeoutException
import com.factory.wms.ui.viewmodel.scan.ScanUiState
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * BUG-2026-10-002：Android DataStore 访问无超时的回归锁。
 *
 * #762 已证明 actor 死亡时 dataStore.edit 是永久挂起，而不是异常；生产侧必须用
 * withTimeout 把挂起转换为可处理结果。0ms 注入只验证超时链路，不代表真实磁盘故障。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31])
class DataStoreTimeoutTest {

    private lateinit var context: Context
    private lateinit var repository: WmsRepository

    @Before
    fun setUp() {
        DataStoreTestReset.resetWmsSettingsDataStore()
        context = ApplicationProvider.getApplicationContext()
        repository = WmsRepository(context, dataStoreTimeoutMs = 0L)
    }

    @After
    fun tearDown() {
        RetrofitClient.setToken(null)
        RetrofitClient.setBaseUrl("")
    }

    private fun line(code: String) = ScanLine(
        material_code = code,
        quantity = 1.0,
        material_name = "物料$code",
        material_spec = "规格"
    )

    private fun draft() = ScanEditDraft(
        lines = listOf(DraftScanLine(line("M001"), "轴承", "608", "SKF")),
        warehouse = WarehouseDto(id = 1, code = "WH01", name = "主仓"),
        department = null,
        employee = null,
        contractNo = "",
        requestId = null,
        inboundBusinessType = "采购入库"
    )

    @Test
    fun `saveEditDraft timeout throws non cancellation exception`() = runBlocking {
        var timeout = false
        try {
            repository.saveEditDraft("scan_edit_timeout", draft())
        } catch (expected: DataStoreTimeoutException) {
            timeout = true
            assertTrue(expected.message!!.contains("DataStore 访问超时"))
        }
        assertTrue(timeout)
    }

    @Test
    fun `editDraftKey timeout degrades to logged out semantics`() = runBlocking {
        var rejected = false
        try {
            repository.editDraftKey("inbound")
        } catch (expected: IllegalStateException) {
            rejected = true
            assertEquals("请先登录再恢复清单", expected.message)
        }
        assertTrue(rejected)
    }

    @Test
    fun `normal DataStore roundtrip is unaffected by default timeout`() = runBlocking {
        val normalRepository = WmsRepository(context)
        normalRepository.saveLoginInfo(
            token = "token-normal",
            baseUrl = "https://srv-timeout.example.com",
            username = "userA",
            role = "admin"
        )
        val key = normalRepository.editDraftKey("inbound")
        normalRepository.saveEditDraft(key, draft())
        assertEquals(1, normalRepository.loadEditDraft(key)!!.lines.size)
    }

    @Test
    fun `prepareDraftSubmission degrades read timeout to account change`() = runBlocking {
        val viewModel = ScanViewModel(
            ApplicationProvider.getApplicationContext<Application>(),
            dataStoreTimeoutMs = 0L
        )
        forceDraftSubmissionState(viewModel)

        assertNull(viewModel.prepareDraftSubmission())

        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertEquals("登录账号或服务器已变更，请重新进入本页", state.error)
        assertNull(state.draftSaveError)
    }

    @Test
    fun `saveEditDraft timeout reuses draft failure branch`() = runBlocking {
        val viewModel = ScanViewModel(
            ApplicationProvider.getApplicationContext<Application>(),
            dataStoreTimeoutMs = 0L
        )
        forceDraftSubmissionState(viewModel)

        assertFalse(viewModel.persistEditDraft())

        val state = viewModel.uiState.value
        assertTrue(state.draftSaveError!!.contains("清单未保存到本机"))
        assertTrue(state.draftSaveError!!.contains("DataStore 访问超时"))
    }

    @Test
    fun `external cancellation remains transparent across DataStore wrappers`() = runBlocking {
        val normalRepository = WmsRepository(context)

        val required = launch(start = CoroutineStart.UNDISPATCHED) {
            normalRepository.requireDataStore<Unit> { awaitCancellation() }
        }
        required.cancelAndJoin()
        assertTrue(required.isCancelled)

        val degraded = launch(start = CoroutineStart.UNDISPATCHED) {
            normalRepository.withDataStoreFallback(Unit) { awaitCancellation() }
        }
        degraded.cancelAndJoin()
        assertTrue(degraded.isCancelled)
    }


    /** 只为测试注入提交前状态；生产状态仍保持私有，不扩大公开 API。 */
    @Suppress("UNCHECKED_CAST")
    private fun forceDraftSubmissionState(viewModel: ScanViewModel) {
        val stateField = ScanViewModel::class.java.getDeclaredField("_uiState").apply {
            isAccessible = true
        }
        val flow = stateField.get(viewModel) as MutableStateFlow<ScanUiState>
        flow.value = flow.value.copy(
            scanLines = listOf(line("M001")),
            selectedWarehouse = WarehouseDto(id = 1, code = "WH01", name = "主仓"),
            locationEnabled = false,
            isLoading = true,
            pendingSubmissionId = "req-timeout"
        )
        val keyField = ScanViewModel::class.java.getDeclaredField("editDraftKey").apply {
            isAccessible = true
        }
        keyField.set(viewModel, "scan_edit_timeout")

        val operationField = ScanViewModel::class.java.getDeclaredField("editDraftOperation").apply {
            isAccessible = true
        }
        operationField.set(viewModel, "inbound")
    }
}