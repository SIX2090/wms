# -*- coding: utf-8 -*-
"""BUG-2026-09-18-003 回归：Android 扫码/查库存的库存状态徽标两级化（源码锚点）。

背景（R6 同类点排查）：手机端「两级判定」（low=破最低库存红线、danger=破安全库存
预警线）在 AI-CI-GREEN-005-F04 统一到了预警列表/首页/库存查询，但**扫码结果卡徽标**
与**列表行数量色**仍是客户端单级重算 `stock > minStock` —— 低于安全库存（danger 档）
但高于最低库存的物料被误显示为绿色「库存充足」，现场按徽标拣货会误判。

修复：两处统一改两级，安全库存 safetyStock = max(reorderPoint, minStock)（与服务端
`safety_stock` 同口径），未设阈值的物料退回 充足/不足 二态（保持原行为）。

沙箱无 Android SDK 无法编译 Kotlin，按仓库先例（test_bug_2026_09_10_003 等）用源码
锚点锁定；Kotlin 括号平衡校验见下方 test_kotlin_brace_balance。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCREENS = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens/ScanScreens.kt"
COLOR = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/theme/Color.kt"

screens_src = SCREENS.read_text(encoding="utf-8")
color_src = COLOR.read_text(encoding="utf-8")


def test_result_card_badge_is_two_band():
    """T1：结果卡徽标按 safetyStock=max(reorderPoint,minStock) 两级判定。"""
    assert "val scanSafetyStock = maxOf(material.reorderPoint ?: 0.0, scanMinStock)" in screens_src
    assert "val scanHasThreshold = scanMinStock > 0.0 || scanSafetyStock > 0.0" in screens_src
    # 三态：破红线=红「低于最低库存」、破预警线=黄「低于安全库存」、其余=绿「库存充足」
    assert 'scanStock <= scanMinStock -> Triple("低于最低库存", Error, ErrorContainer)' in screens_src
    assert 'scanStock <= scanSafetyStock -> Triple("低于安全库存", Warning, WarningContainer)' in screens_src
    # 徽标消费统一的三元组，不再内联单级比较
    assert "color = scanBadge.third" in screens_src
    assert "scanBadge.first" in screens_src
    assert "color = scanBadge.second" in screens_src


def test_result_card_badge_no_threshold_falls_back_binary():
    """T2：未设阈值的物料退回 充足/不足 二态（不误标「低于最低库存」）。"""
    assert 'if (scanStock > 0.0)' in screens_src
    assert 'Triple("库存充足", Success, SuccessContainer)' in screens_src
    assert 'Triple("库存不足", Error, ErrorContainer)' in screens_src


def test_stock_list_row_quantity_color_is_two_band():
    """T3：列表行数量色同样两级——破红线红、破预警线黄、其余绿。"""
    assert "val safetyStock = maxOf(material.reorderPoint ?: 0.0, minStock)" in screens_src
    assert "else if (stock <= minStock) Error" in screens_src
    assert "else if (stock <= safetyStock) Warning" in screens_src


def test_no_leftover_single_level_badge_comparison():
    """T4：旧的单级徽标比较（只比 minStock 定充足/不足）必须已清除。"""
    assert "(material.stock ?: 0.0) > (material.minStock ?: 0.0)" not in screens_src
    assert "stock > minStock) Success else Error" not in screens_src


def test_warning_palette_available():
    """T5：danger 档黄色依赖主题 Warning/WarningContainer，必须存在（防误删）。"""
    assert "val Warning = Color(" in color_src
    assert "val WarningContainer = Color(" in color_src


def test_kotlin_brace_balance():
    """T6：改动后 ScanScreens.kt 括号仍平衡（无 SDK 的最低限度编译替代检查）。"""
    for open_ch, close_ch in [("{", "}"), ("(", ")"), ("[", "]")]:
        assert screens_src.count(open_ch) == screens_src.count(close_ch), (
            f"{open_ch}{close_ch} 不平衡：{screens_src.count(open_ch)} vs {screens_src.count(close_ch)}"
        )
