package com.factory.wms.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

// ─────────────────────────────────────────────────────────────────────────────
// WMS 移动端设计令牌（AI-APP-UI-002）
//
// 问题背景：此前各屏的间距 / 圆角 / 按钮高度都是散落的面值（14、16、18、22dp…
// 各自凭手感取），同一类元素在不同页面尺寸不一致。这里把高频取值收敛成令牌，
// 新代码一律引用令牌，改一处即可全 App 联动。
//
// 迁移策略：存量代码不强制重写（避免大面积 diff 引入回归），新增/重构 UI 时使用。
// ─────────────────────────────────────────────────────────────────────────────

object WmsDimens {
    // ── 间距阶梯（4dp 基网） ──
    val SpaceXs = 4.dp
    val SpaceSm = 8.dp
    val SpaceMd = 12.dp
    val SpaceLg = 16.dp
    val SpaceXl = 20.dp
    val Space2xl = 24.dp
    val Space3xl = 32.dp

    // ── 圆角阶梯 ──
    val CornerSm = 10.dp
    val CornerMd = 14.dp
    val CornerLg = 18.dp
    val CornerXl = 22.dp

    // ── 触控目标 ──
    // Android 无障碍指南最小 48dp。现场作业戴手套，低于此值误触率明显上升。
    val TouchTargetMin = 48.dp

    // ── 按钮高度 ──
    val ButtonHeightPrimary = 52.dp
    val ButtonHeightSecondary = 46.dp

    // ── 卡片内边距 ──
    val CardPadding = 16.dp

    // ── 页面水平边距 ──
    val PagePaddingHorizontal = 20.dp
}

/**
 * 全 App 统一形状：MaterialTheme 默认形状与 [WmsDimens] 圆角阶梯对齐。
 * 不显式指定 shape 的 Material 组件（Card/Dialog/BottomSheet 等）自动获得一致圆角。
 */
val WmsShapes = Shapes(
    small = RoundedCornerShape(WmsDimens.CornerSm),
    medium = RoundedCornerShape(WmsDimens.CornerMd),
    large = RoundedCornerShape(WmsDimens.CornerLg),
    extraLarge = RoundedCornerShape(WmsDimens.CornerXl)
)
