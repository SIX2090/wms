package com.factory.wms.ui.components

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.view.Window
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowInsetsControllerCompat
import java.util.WeakHashMap

// ─────────────────────────────────────────────────────────────────────────────
// 状态栏图标对比度适配（AI-APP-UI-002）
//
// 问题背景：MainActivity 调用了 enableEdgeToEdge()，内容会延伸到状态栏之下。
// 浅色主题下系统默认给「深色状态栏图标」，这对白色顶栏是正确的；
// 但 App 里大量使用**深色模块色渐变头部**（入库蓝 / 出库绿 / 盘点紫、登录页、
// 首页 Hero），深色图标压在深蓝渐变上几乎不可读——时间与电量都看不清。
//
// 方案：在需要反转图标的页面/头部组合期调用 [StatusBarIconEffect]，
// 退出组合时自动还原进入前的值，避免跨页面串色。
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 页面切换动画可能让新旧页面同时存在；移除旧页面时必须保留新页面的设置。
 *
 * @param darkIcons true = 深色图标（适合白色/浅色头部）；false = 浅色图标（适合深色渐变头部）
 */
@Composable
fun StatusBarIconEffect(darkIcons: Boolean) {
    val view = LocalView.current
    val token = remember(view) { Any() }
    DisposableEffect(view, token, darkIcons) {
        val activity = view.context.findActivity()
        val window = activity?.window
        if (window != null) StatusBarIconOwners.add(window, view, token, darkIcons)
        onDispose {
            if (window != null) StatusBarIconOwners.remove(window, token)
        }
    }
}

internal object StatusBarIconOwners {
    private data class Owner(val token: Any, val darkIcons: Boolean)
    private class State(val controller: WindowInsetsControllerCompat, val original: Boolean) {
        val owners = mutableListOf<Owner>()
    }
    private val states = WeakHashMap<Window, State>()

    fun add(window: Window, view: android.view.View, token: Any, darkIcons: Boolean) {
        val state = states.getOrPut(window) {
            val controller = WindowInsetsControllerCompat(window, view)
            State(controller, controller.isAppearanceLightStatusBars)
        }
        state.owners.removeAll { it.token === token }
        state.owners.add(Owner(token, darkIcons))
        state.controller.isAppearanceLightStatusBars = darkIcons
    }

    fun remove(window: Window, token: Any) {
        val state = states[window] ?: return
        state.owners.removeAll { it.token === token }
        state.controller.isAppearanceLightStatusBars = state.owners.lastOrNull()?.darkIcons ?: state.original
        if (state.owners.isEmpty()) states.remove(window)
    }
}

/** 沿 ContextWrapper 链向上找到宿主 Activity（Compose 下 context 可能被包了一层主题包装）。 */
private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}
