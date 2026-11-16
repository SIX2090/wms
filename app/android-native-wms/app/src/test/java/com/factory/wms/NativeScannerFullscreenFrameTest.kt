package com.factory.wms

import android.app.Application
import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.requiredSize
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.layout.boundsInWindow
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import com.factory.wms.ui.components.ScannerFrameOverlay
import java.io.File
import kotlin.math.roundToInt
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.ParameterizedRobolectricTestRunner
import org.robolectric.ParameterizedRobolectricTestRunner.Parameters
import org.robolectric.Robolectric
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Render the exact production overlay; no camera, permission or barcode substitute is involved. */
@RunWith(ParameterizedRobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class, qualifiers = "w1000dp-h1900dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeScannerFullscreenFrameTest(private val width: Int, private val height: Int, private val density: Float) {
    companion object {
        @JvmStatic @Parameters(name = "{0}x{1}@{2}") fun cases() = listOf(
            arrayOf<Any>(320, 640, 1f), arrayOf<Any>(360, 800, 1f),
            arrayOf<Any>(800, 360, 1f), arrayOf<Any>(720, 1600, 2f)
        )
    }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private var bounds = Rect.Zero
    private val progress = mutableFloatStateOf(.25f)
    private val cameraPixel = Color(0xFF26424E).toArgb()

    @Before fun before() {
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent {
            CompositionLocalProvider(LocalDensity provides Density(density)) {
                Box(Modifier.requiredSize((width / density).dp, (height / density).dp)
                    .background(Color(cameraPixel)).onGloballyPositioned { bounds = it.boundsInWindow() }) {
                    ScannerFrameOverlay(progress.floatValue)
                }
            }
        }
    }
    @After fun after() = disposeComposeActivity(activity)

    private fun render(label: String): Bitmap {
        compose.waitForIdle()
        lateinit var result: Bitmap
        compose.runOnIdle {
            assertEquals(width.toFloat(), bounds.width, .5f)
            assertEquals(height.toFloat(), bounds.height, .5f)
            val view = activity.get().window.decorView
            val window = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
            view.draw(Canvas(window))
            result = Bitmap.createBitmap(window, bounds.left.roundToInt(), bounds.top.roundToInt(), width, height)
            if (result !== window) window.recycle()
        }
        System.getenv("WMS_NATIVE_SCANNER_CAPTURE_DIR")?.let { directory ->
            val file = File(directory, "${width}x${height}-${density}-$label.png")
            file.parentFile?.mkdirs()
            file.outputStream().use { result.compress(Bitmap.CompressFormat.PNG, 100, it) }
        }
        return result
    }

    @Test fun allFourCornersRemainAtTheScreenEdges() {
        val bitmap = render("corners")
        try {
            for ((x, y) in listOf(24 to 40, 40 to 24, width - 24 to 40, width - 40 to 24,
                24 to height - 40, 40 to height - 24, width - 24 to height - 40, width - 40 to height - 24)) {
                assertNotEquals("A visible corner must be 24px from this preview edge at ($x,$y)", cameraPixel, bitmap.getPixel(x, y))
            }
        } finally { bitmap.recycle() }
    }

    @Test fun scanningLineTraversesTheFullPreviewHeightAndWidth() {
        for (offset in listOf(.25f, .75f)) {
            compose.runOnIdle { progress.floatValue = offset }
            val bitmap = render("scan-${(offset * 100).roundToInt()}")
            try {
                val y = (24f + (height - 52f) * offset).roundToInt()
                for (x in listOf(40, width / 2, width - 40)) {
                    assertTrue("At progress $offset the line must reach ($x,$y) across the whole preview",
                        (y - 1..y + 1).any { bitmap.getPixel(x, it) != cameraPixel })
                }
            } finally { bitmap.recycle() }
        }
    }

    @Test fun originalBlueCornersLeaveOtherCameraPixelsUnmasked() {
        val bitmap = render("unmasked")
        try {
            assertEquals("Retain the original blue edge marker", Color(0xFF4361EE).toArgb(), bitmap.getPixel(24, 40))
            for ((x, y) in listOf(8 to height / 2, width / 2 to 8, width / 2 to height / 8)) {
                assertEquals("Do not shade or obscure camera pixels outside the guide", cameraPixel, bitmap.getPixel(x, y))
            }
        } finally { bitmap.recycle() }
    }
}
