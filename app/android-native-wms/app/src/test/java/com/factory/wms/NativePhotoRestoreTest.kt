package com.factory.wms

import android.Manifest
import android.app.Application
import android.net.Uri
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivityResultRegistryOwner
import androidx.activity.compose.setContent
import androidx.activity.result.ActivityResultRegistry
import androidx.activity.result.ActivityResultRegistryOwner
import androidx.activity.result.contract.ActivityResultContract
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.core.app.ActivityOptionsCompat
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.ui.components.rememberCameraLauncherWithPermission
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[31], application=Application::class, shadows=[AuditCameraUri::class])
class NativePhotoRestoreTest {
    @get:Rule val compose = createEmptyComposeRule()
    @Test fun restoredCameraCallbackDeliversPendingOutput() {
        val activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        try {
            shadowOf(ApplicationProvider.getApplicationContext<Application>()).grantPermissions(Manifest.permission.CAMERA)
            var request = -1
            lateinit var output: Uri
            val registry = object : ActivityResultRegistry() {
                override fun <I,O> onLaunch(requestCode:Int, contract:ActivityResultContract<I,O>, input:I, options:ActivityOptionsCompat?) {
                    request = requestCode
                    output = input as Uri
                }
            }
            val owner = object : ActivityResultRegistryOwner { override val activityResultRegistry = registry }
            var visible by mutableStateOf(true)
            val delivered = mutableListOf<Uri>()
            lateinit var take: () -> Unit
            activity.get().setContent {
                val holder = rememberSaveableStateHolder()
                if (visible) holder.SaveableStateProvider("camera") {
                    CompositionLocalProvider(LocalActivityResultRegistryOwner provides owner) {
                        take = rememberCameraLauncherWithPermission(remember { SnackbarHostState() }) { delivered.add(it) }
                    }
                }
            }
            compose.runOnIdle { take(); assertTrue(registry.dispatchResult(request,true)) }
            assertEquals(listOf(output),delivered.toList())
            compose.runOnIdle { take(); visible = false }
            compose.waitForIdle()
            compose.runOnIdle { visible = true }
            compose.waitForIdle()
            compose.runOnIdle { assertTrue(registry.dispatchResult(request,true)) }
            assertEquals(2, delivered.size)
            assertEquals(output, delivered.last())
            assertNotEquals(delivered.first(), delivered.last())
        } finally { disposeComposeActivity(activity) }
    }
}

@org.robolectric.annotation.Implements(value=androidx.core.content.FileProvider::class, isInAndroidSdk=false)
class AuditCameraUri {
    companion object {
        // Supply the platform output URI. Photo delivery and saved-state handling are real.
        @JvmStatic @org.robolectric.annotation.Implementation
        fun getUriForFile(context:android.content.Context, authority:String, file:java.io.File):Uri =
            Uri.parse("content://$authority/camera/${file.name}")
    }
}