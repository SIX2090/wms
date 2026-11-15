package com.factory.wms

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.ScanLine
import com.factory.wms.ui.viewmodel.opening.OpeningStockViewModel
import com.factory.wms.ui.viewmodel.scan.ScanUiState
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class NativeContinuousScanAccuracyTest {
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    private lateinit var scan: ScanViewModel
    private lateinit var opening: OpeningStockViewModel
    private lateinit var state: MutableStateFlow<ScanUiState>

    @Suppress("UNCHECKED_CAST")
    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        val app = ApplicationProvider.getApplicationContext<Application>()
        scan = ScanViewModel(app); opening = OpeningStockViewModel(app)
        state = ScanViewModel::class.java.getDeclaredField("_uiState").also { it.isAccessible = true }.get(scan) as MutableStateFlow<ScanUiState>
    }
    @After fun after() {
        closeWmsTestViewModels(listOf(scan, opening)); RetrofitClient.setToken(null); RetrofitClient.setBaseUrl("")
    }
    @Test fun eachAcceptedCameraScanAddsExactlyOneInTheSelectedLocation() {
        state.value = ScanUiState(scanLines = listOf(ScanLine("WL-1", 5.5, location_code = "A-01")), totalQuantity = 5.5)
        assertTrue(scan.addCameraScanLine(" WL-1 ", "A-01"))
        assertEquals(6.5, scan.uiState.value.scanLines.single().quantity, 0.0)
        assertTrue(scan.addCameraScanLine("WL-1", "B-01"))
        assertEquals(1.0, scan.uiState.value.scanLines.single { it.location_code == "B-01" }.quantity, 0.0)
        assertFalse(scan.addCameraScanLine("  ", "B-01"))
        assertEquals(7.5, scan.uiState.value.totalQuantity, 0.0)
    }
    @Test fun unresolvedSubmissionCannotAcceptOrCountAnotherCameraScan() {
        state.value = ScanUiState(scanLines = listOf(ScanLine("WL-1", 5.0)), totalQuantity = 5.0,
            pendingSubmissionId = "REQ-SYNTHETIC")
        assertFalse(scan.addCameraScanLine("WL-1", null))
        assertEquals(5.0, scan.uiState.value.totalQuantity, 0.0)
        assertTrue(scan.uiState.value.error!!.contains("待核实"))
    }
    @Test fun openingScanReportsAcceptanceWithoutCountingBlankCodes() {
        assertFalse(opening.addLine("  ", 1.0))
        assertTrue(opening.uiState.value.lines.isEmpty())
        assertTrue(opening.addLine("WL-1", 1.0))
        assertTrue(opening.addLine("WL-1", 1.0))
        assertEquals(2.0, opening.uiState.value.lines.single().quantity, 0.0)
    }
}
