#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BUG-2026-10-04-003 回归守护：Hero 深蓝底上的 WarehouseSelector 必须白色前景。

## 缺陷

BUG-2026-10-04-002 把「项目仓」切换器收进 Hero 蓝底后，组件仍用默认主题色
（TextButton primary / onSurfaceVariant，均为深色）——深色文字压蓝底，
真机截图实证「项目仓」几乎不可读。这是 002 修复引入的对比度回退。

根因：WarehouseSelector 从报表页（浅底）提取为共享组件时未考虑深底场景，
没有前景色参数。

## 修复约定（本测试锁死）

1. WarehouseSelector 必须提供 contentColor 参数（默认 null=主题色，浅底调用方
   行为不变）。
2. HomeScreen Hero 内的调用点必须显式传 contentColor = Color.White。
3. BUG-2026-10-04-003 必须登记台账（含「生效确认」字段，A13）。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = (
    REPO_ROOT
    / "app" / "android-native-wms" / "app" / "src" / "main" / "java"
    / "com" / "factory" / "wms"
)
SELECTOR = SRC / "ui" / "components" / "WarehouseSelector.kt"
HOME = SRC / "ui" / "screens" / "HomeScreen.kt"
BASELINE = REPO_ROOT / "WMS_BUG_BASELINE.md"


def _read(p: Path) -> str:
    assert p.exists(), f"文件不存在：{p}"
    return p.read_text(encoding="utf-8")


def test_003_selector_has_content_color_param() -> None:
    """共享组件必须支持前景色注入（核心回归锁）。"""
    src = _read(SELECTOR)
    assert re.search(r"contentColor:\s*Color\?\s*=\s*null", src), (
        "WarehouseSelector 缺少 contentColor: Color? = null 参数——"
        "深底场景无法改色"
    )
    assert "ButtonDefaults.textButtonColors(contentColor = contentColor)" in src, (
        "TextButton 未使用 contentColor"
    )
    assert "tint = contentColor ?:" in src, "下拉箭头未跟随 contentColor"


def test_003_hero_call_passes_white() -> None:
    """HomeScreen Hero 内的调用点必须显式传白色前景（核心回归锁）。"""
    src = _read(HOME)
    # 调用参数内部也含 `)`（如 selectWarehouse(it)），用非贪婪全字符匹配
    assert re.search(
        r"WarehouseSelector\([\s\S]*?contentColor\s*=\s*Color\.White", src
    ), "Hero 深蓝底上的 WarehouseSelector 未传 contentColor = Color.White"


def test_003_report_call_unaffected() -> None:
    """浅底调用方（报表页）不得被强制改色——默认参数保持主题色行为。"""
    report = SRC / "ui" / "screens" / "ReportScreens.kt"
    if report.exists():
        src = _read(report)
        for m in re.finditer(r"WarehouseSelector\([^)]*\)", src, re.S):
            assert "contentColor" not in m.group(0), (
                "报表页（浅底）不应传 contentColor——默认主题色才是正确行为"
            )


def test_003_bug_registered_with_confirmation_field() -> None:
    """BUG-2026-10-04-003 必须登记台账且含「生效确认」字段（A13）。"""
    content = _read(BASELINE)
    assert "BUG-2026-10-04-003" in content, "BUG-2026-10-04-003 未登记进 WMS_BUG_BASELINE.md"
    m = re.search(r"(##[^\n]*BUG-2026-10-04-003[^\n]*\n.*?)(?=\n##\s|\Z)", content, re.S)
    assert m, "无法定位 BUG-2026-10-04-003 条目段落"
    assert "生效确认" in m.group(1), "BUG-2026-10-04-003 条目缺少「生效确认」字段（允许「待确认」占位）"
