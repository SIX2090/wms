#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BUG-2026-09-12-002 回归守护：物料规格不允许单行省略号截断。

背景（用户现场反馈，截图：扫码入库 → 添加物料弹窗）：
    搜索 1*25 命中 201034/201035/201036 三条「宝胜电线」，规格一律显示成
    `ZB-BVR-450/750V 1*25...` —— 规格尾部（线径/颜色等差异）被 Ellipsis 吃掉，
    候选看起来完全一样，无法区分该选哪条。电线电缆类物料的区分信息恰恰在尾部。

根因：
    「添加物料」候选列表的规格行写死 maxLines = 1 + TextOverflow.Ellipsis。
    对照组：查库存候选/结果卡（无 maxLines 限制，完整显示）、库存列表行与
    物料档案（maxLines = 2）——只有弹窗候选漏了。

修复口径：
    规格是「选物料/领料」场景防拿错货的关键信息，放开到 maxLines = 2
    （弹窗候选区本身 heightIn 限高 + 内部滚动，不会撑破弹窗）。
    修复点：ScanScreenBase（入库/出库/盘点共用添加物料弹窗）、
    OpeningStockScreen（添加期初物料弹窗）、OverviewListScreen（缺货预警卡片，
    照单领料同样需要规格区分）。

守护点：
    三处规格 Text 必须允许 ≥2 行；若未来改布局（如换组件），请同步更新本测试。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _strip_comments(src: str) -> str:
    src = re.sub(r"(?<!\S)/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    # 行注释剥离后残留空行会把目标参数推出后续窗口，压缩之
    src = re.sub(r"\n[ \t]*\n+", "\n", src)
    return src


def _block_after(src: str, anchor: str, window_chars: int = 800) -> str:
    """取 anchor 首次出现之后的一小段窗口（规格 Text 的参数区就在其中）。"""
    idx = src.find(anchor)
    assert idx >= 0, f"锚点丢失，布局可能被重构，需同步更新本测试：{anchor!r}"
    return src[idx: idx + window_chars]


def test_scan_screen_base_dialog_spec_allows_two_lines():
    """添加物料弹窗（入库/出库/盘点共用）候选规格行必须 ≥2 行。"""
    src = _strip_comments(_read(SRC / "ui" / "screens" / "ScanScreenBase.kt"))
    block = _block_after(src, "if (specBrand.isNotBlank()) {")
    assert re.search(r"maxLines\s*=\s*2", block), (
        "ScanScreenBase 添加物料弹窗规格行被改回单行/换布局了 —— "
        "规格尾部差异被省略号吃掉会导致候选无法区分（BUG-2026-09-12-002）"
    )


def test_opening_stock_dialog_spec_allows_two_lines():
    """添加期初物料弹窗候选规格行必须 ≥2 行。"""
    src = _strip_comments(_read(SRC / "ui" / "screens" / "OpeningStockScreen.kt"))
    block = _block_after(src, "if (specBrand.isNotBlank()) {")
    assert re.search(r"maxLines\s*=\s*2", block), (
        "OpeningStockScreen 添加期初物料弹窗规格行被改回单行/换布局了 —— "
        "同 BUG-2026-09-12-002"
    )


def test_overview_alert_row_spec_allows_two_lines():
    """缺货预警卡片规格行必须 ≥2 行（照单领料防拿错货）。"""
    src = _strip_comments(_read(SRC / "ui" / "screens" / "OverviewListScreen.kt"))
    block = _block_after(src, '"规格: ${item.spec}"')
    assert re.search(r"maxLines\s*=\s*2", block), (
        "OverviewListScreen 缺货预警规格行被改回单行/换布局了 —— "
        "同 BUG-2026-09-12-002"
    )


def test_no_new_single_line_spec_truncation_in_pick_flows():
    """反向扫描：挑物料流程的「规格: 」渲染点不得出现 maxLines = 1 + Ellipsis。

    允许的既有口径：无 maxLines（完整显示）或 maxLines ≥ 2。
    """
    screens = SRC / "ui" / "screens"
    offenders = []
    for kt in sorted(screens.glob("*.kt")):
        src = _strip_comments(_read(kt))
        for m in re.finditer(r'"规格: \$\{[^}]+\}"', src):
            window = src[m.start(): m.start() + 400]
            if re.search(r"maxLines\s*=\s*1\b", window):
                offenders.append(f"{kt.name}: {src[m.start():m.start()+60]!r}…")
    assert not offenders, (
        "以下「规格: 」渲染点仍是单行截断，会吞掉区分物料的尾部差异：\n"
        + "\n".join(offenders)
    )
