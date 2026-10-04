#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BUG-2026-10-04-002 回归守护：首页「今日概览」标题行须在 Hero 内；语音 FAB 不得压底栏。

## 缺陷（真机截图实证，HUAWEI LIO-AN00）

1. **「今日概览」标题与「项目仓」切换器下半截被裁切**：
   标题行放在 `offset(y = (-28).dp)` 的半悬浮 Column 里，设计假定行高 ≤28dp；
   仓库切换器（~32dp 高）使行高超出预留，标题白字下半截落到 Hero 深蓝区之外
   的白底上——白字白底不可见，视觉上就是被卡片"切掉一半"。
2. **右下角语音 FAB 压住底部导航「我的」入口**：
   VoiceAssistantOverlay 叠加在 NavHost 之上、对底栏无感知，FAB 用
   `padding(20.dp)` 从屏幕底缘算起，正好盖住 WmsBottomBar 最右 tab。

## 修复约定（本测试锁死）

1. HomeScreen 的「今日概览」标题行渲染在 Hero（蓝底）内——不得再出现在
   半悬浮 offset Column 里；三态（成功/骨架/失败）的卡片仍各自保留
   `Column(modifier = Modifier.offset(y = (-28).dp))` 半悬浮。
2. VoiceAssistant 的 FAB modifier 必须含 `navigationBarsPadding()` 且
   底部 padding ≥ 80dp（M3 NavigationBar 高 80dp）。
3. BUG-2026-10-04-002 必须登记台账（含「生效确认」字段，A13）。

## 为什么是静态断言

沙箱/CI 无 Android SDK 与 Kotlin 工具链，无法编译运行 Compose；
本测试以源码结构契约锁死修复。
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
HOME = SRC / "ui" / "screens" / "HomeScreen.kt"
VOICE = SRC / "ui" / "components" / "VoiceAssistant.kt"
BASELINE = REPO_ROOT / "WMS_BUG_BASELINE.md"


def _read(p: Path) -> str:
    assert p.exists(), f"文件不存在：{p}"
    return p.read_text(encoding="utf-8")


def test_002_title_row_not_inside_floating_offset_column() -> None:
    """标题行不得再放进 offset(-28) 半悬浮 Column（核心回归锁）。"""
    src = _read(HOME)
    assert not re.search(
        r"Column\(modifier = Modifier\.offset\(y = \(-28\)\.dp\)\)\s*\{\s*Row",
        src,
    ), "「今日概览」标题 Row 仍在半悬浮 offset Column 内——行高超 28dp 时白字会落到白底被裁切"


def test_002_title_row_rendered_inside_hero() -> None:
    """「今日概览」标题必须在 Hero 区内渲染（在问候语之后、概览卡片之前）。"""
    src = _read(HOME)
    hero = src.find("// ── Hero Section ──")
    title = src.find('"今日概览"')
    card = src.find("TodayOverviewBar(")
    hero_end = src.find("今日概览卡片")
    assert -1 not in (hero, title, card, hero_end), "关键锚点缺失，HomeScreen 结构已变化需同步本测试"
    assert hero < title < hero_end < card, (
        "「今日概览」标题不在 Hero 区内（应位于 Hero Section 与半悬浮卡片之间）"
    )
    # 标题在 Hero 内必须是白字（蓝底上可读）
    seg = src[title : title + 300]
    assert "Color.White" in seg, "Hero 内的「今日概览」标题必须是白色（蓝底）"


def test_002_floating_card_offset_preserved() -> None:
    """半悬浮卡片 offset(-28) 结构必须保留（三态至少 2 处，防止误删悬浮效果）。"""
    src = _read(HOME)
    count = src.count("Column(modifier = Modifier.offset(y = (-28).dp))")
    assert count >= 2, f"半悬浮 offset 只剩 {count} 处，卡片悬浮效果被误删"


def test_002_voice_fab_clears_bottom_bar() -> None:
    """语音 FAB 必须抬过系统手势区 + 应用底栏（核心回归锁）。"""
    src = _read(VOICE)
    idx = src.find("FloatingActionButton(")
    assert idx != -1, "未找到 FloatingActionButton 定义"
    # FAB 的 modifier 链位于 onClick lambda（内部也有 `) {`）之后，
    # 取调用点之后到 shape 参数为止的片段，覆盖完整 modifier 链
    end = src.find("shape = RoundedCornerShape", idx)
    assert end != -1, "FAB 缺少 shape 参数，结构已变化需同步本测试"
    block = src[idx:end]
    assert "navigationBarsPadding()" in block, (
        "FAB 缺少 navigationBarsPadding()——会落进系统手势区"
    )
    m = re.search(r"bottom\s*=\s*(\d+)\.dp", block)
    assert m, "FAB 未声明底部 padding"
    assert int(m.group(1)) >= 80, (
        f"FAB 底部 padding 只有 {m.group(1)}dp，小于底栏 80dp，仍压住「我的」入口"
    )


def test_002_bug_registered_with_confirmation_field() -> None:
    """BUG-2026-10-04-002 必须登记台账且含「生效确认」字段（A13）。"""
    content = _read(BASELINE)
    assert "BUG-2026-10-04-002" in content, "BUG-2026-10-04-002 未登记进 WMS_BUG_BASELINE.md"
    m = re.search(r"(##[^\n]*BUG-2026-10-04-002[^\n]*\n.*?)(?=\n##\s|\Z)", content, re.S)
    assert m, "无法定位 BUG-2026-10-04-002 条目段落"
    assert "生效确认" in m.group(1), "BUG-2026-10-04-002 条目缺少「生效确认」字段（允许「待确认」占位）"
