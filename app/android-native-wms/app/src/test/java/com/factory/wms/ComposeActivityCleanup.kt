package com.factory.wms

import androidx.activity.ComponentActivity
import androidx.compose.ui.platform.ComposeView
import org.robolectric.Shadows
import org.robolectric.android.controller.ActivityController

/** Manually visible Robolectric windows also own a window recomposer and cursor jobs. */
internal fun disposeComposeActivity(controller: ActivityController<ComponentActivity>) {
    val activity = controller.get()
    val decor = activity.window.decorView
    decor.clearFocus()
    val content = activity.findViewById<android.view.ViewGroup>(android.R.id.content)
    for (index in 0 until content.childCount) {
        (content.getChildAt(index) as? ComposeView)?.disposeComposition()
    }
    controller.pause().stop().destroy()
    // ActivityController drives lifecycle; explicit window detachment ends its frame clock.
    if (decor.isAttachedToWindow) activity.windowManager.removeViewImmediate(decor)
    Shadows.shadowOf(android.os.Looper.getMainLooper()).idle()
}
