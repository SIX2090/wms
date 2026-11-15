package com.factory.wms

import android.app.Application
import android.content.Context
import android.os.VibratorManager
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.util.ScanFeedback
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowToneGenerator
import org.robolectric.shadows.ShadowVibrator

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class ScanFeedbackIndependentTest {
    private val app get() = ApplicationProvider.getApplicationContext<Application>()
    @Before fun before() {
        app.getSharedPreferences("wms_settings", Context.MODE_PRIVATE).edit().clear().commit()
        ShadowToneGenerator.reset(); ShadowVibrator.reset(); ScanFeedback.warmUp(app)
    }
    @After fun after() {
        app.getSharedPreferences("wms_settings", Context.MODE_PRIVATE).edit().clear().commit()
        ScanFeedback.warmUp(app); ShadowToneGenerator.reset(); ShadowVibrator.reset()
    }
    @Test fun legacyDisabledStateMigratesToBothAndEachSettingPersistsIndependently() {
        app.getSharedPreferences("wms_settings", Context.MODE_PRIVATE).edit().putBoolean("scan_feedback_enabled", false).commit()
        ScanFeedback.warmUp(app)
        assertFalse(ScanFeedback.soundEnabled); assertFalse(ScanFeedback.vibrationEnabled)
        ScanFeedback.setSoundEnabled(app, true); ScanFeedback.warmUp(app)
        assertTrue(ScanFeedback.soundEnabled); assertFalse(ScanFeedback.vibrationEnabled)
        ScanFeedback.setVibrationEnabled(app, true); ScanFeedback.setSoundEnabled(app, false); ScanFeedback.warmUp(app)
        assertFalse(ScanFeedback.soundEnabled); assertTrue(ScanFeedback.vibrationEnabled)
        ScanFeedback.setEnabled(app, false); ScanFeedback.warmUp(app)
        assertFalse(ScanFeedback.soundEnabled); assertFalse(ScanFeedback.vibrationEnabled)
    }
    @Test fun successAndFailureUseOnlyTheEnabledFeedbackChannel() {
        val vibrator = (app.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
        val shadow = shadowOf(vibrator); shadow.setHasVibrator(true)
        ScanFeedback.setSoundEnabled(app, false); ScanFeedback.setVibrationEnabled(app, true)
        ScanFeedback.success(app)
        assertTrue(shadow.isVibrating); assertTrue(ShadowToneGenerator.getPlayedTones().isEmpty())
        ShadowVibrator.reset(); shadow.setHasVibrator(true); ShadowToneGenerator.reset()
        ScanFeedback.setSoundEnabled(app, true); ScanFeedback.setVibrationEnabled(app, false)
        ScanFeedback.failure(app)
        assertFalse(shadow.isVibrating); assertEquals(1, ShadowToneGenerator.getPlayedTones().size)
    }
}
