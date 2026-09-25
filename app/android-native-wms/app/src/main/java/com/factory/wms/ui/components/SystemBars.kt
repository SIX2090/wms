package com.factory.wms.ui.components

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowInsetsControllerCompat

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
 * 在组合期间设置状态栏图标明暗，退出组合时还原为进入前的值。
 *
 * @param darkIcons true = 深色图标（适合白色/浅色头部）；false = 浅色图标（适合深色渐变头部）
 */
@Composable
fun StatusBarIconEffect(darkIcons: Boolean) {
    val view = LocalView.current
    val isDark = isSystemInDarkTheme()
    DisposableEffect(view, darkIcons, isDark) {
        val activity = view.context.findActivity()
        val window = activity?.window
        val controller = window?.let { WindowInsetsControllerCompat(it, view) }
        val previous = controller?.isAppearanceLightStatusBars
        controller?.isAppearanceLightStatusBars = darkIcons
        onDispose {
            // 还原进入前的值；取不到时回落到主题默认值（浅色主题 → 深色图标）。
            controller?.isAppearanceLightStatusBars = previous ?: !isDark
        }
    }
}

/** 沿 ContextWrapper 链向上找到宿主 Activity（Compose 下 context 可能被包了一层主题包装）。 */
private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}
