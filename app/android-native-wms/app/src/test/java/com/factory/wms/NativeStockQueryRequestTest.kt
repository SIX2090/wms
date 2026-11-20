package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.screens.StockQueryScreen
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.scan.ScanUiState
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.*
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(org.robolectric.RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class, qualifiers = "w360dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeStockQueryRequestTest {
    @get:Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var scan: ScanViewModel
    private val server = okhttp3.mockwebserver.MockWebServer()
    private val requestCodes = java.util.concurrent.CopyOnWriteArrayList<String>()
    @Before fun before() {
        server.dispatcher = object : okhttp3.mockwebserver.Dispatcher() {
            override fun dispatch(request: okhttp3.mockwebserver.RecordedRequest): okhttp3.mockwebserver.MockResponse {
                val code = request.requestUrl!!.queryParameter("code") ?: return okhttp3.mockwebserver.MockResponse().setResponseCode(404)
                requestCodes.add(code)
                return okhttp3.mockwebserver.MockResponse().setHeader("Content-Type","application/json")
                    .setBody("""{"status":"success","data":{"id":1,"code":"TEST","name":"Synthetic","stock":23}}""")
            }
        }
        server.start()
        RetrofitClient.setSession(server.url("/").toString(), "synthetic-owner", 91)
        scan = ScanViewModel(ApplicationProvider.getApplicationContext<Application>())
        val warehouse = WarehouseDto(1, "WH1", "一号仓")
        val field = ScanViewModel::class.java.getDeclaredField("_uiState").apply { isAccessible = true }
        @Suppress("UNCHECKED_CAST")
        (field.get(scan) as MutableStateFlow<ScanUiState>).value = ScanUiState(selectedWarehouse = warehouse, warehouses = listOf(warehouse))
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { WmsTheme { StockQueryScreen(scan, {}) } }
        compose.waitForIdle()
    }
    @After fun after() {
        closeWmsTestViewModels(listOf(scan)); disposeComposeActivity(activity)
        RetrofitClient.setSession("", null); server.shutdown()
    }
    @Test fun oneScanCallbackTriggersOneInfoRequest() {
        // Invoke the same ViewModel entry used after the camera has decoded one barcode.
        compose.runOnIdle { scan.searchMaterialByCode("TEST") {} }
        val until = System.nanoTime() + java.util.concurrent.TimeUnit.SECONDS.toNanos(12)
        while (scan.uiState.value.scannedMaterial?.code != "TEST" && System.nanoTime() < until) {
            org.robolectric.Shadows.shadowOf(android.os.Looper.getMainLooper()).idle()
            compose.mainClock.advanceTimeByFrame()
            compose.waitForIdle()
            Thread.sleep(15)
        }
        Assert.assertEquals("TEST", scan.uiState.value.scannedMaterial?.code)
        // Give any query queued by a recomposition time to reach the mock server.
        repeat(10) {
            org.robolectric.Shadows.shadowOf(android.os.Looper.getMainLooper()).idle()
            compose.mainClock.advanceTimeByFrame()
            compose.waitForIdle()
            Thread.sleep(15)
        }
        Assert.assertEquals(listOf("TEST"), requestCodes.toList())
    }
}