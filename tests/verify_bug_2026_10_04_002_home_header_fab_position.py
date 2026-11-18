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

1. HomeScreen 的 Hero 标题区渲染在 Hero（主题主色底）内——不得再出现在
   半悬浮 offset Column 里；2026-10-30用户新要求将三态（成功/骨架/失败）
   卡片改为正常文档流，原标题可读及语音避让断言保留。
   2026-11-18 用户授权改为沉浸式品牌头（时段问候语 + 单行仓库切换器 + 退出），
   本守则由「锁死旧标题文案」改为「锁死业务意图」：无 offset、深底白字、
   仓库切换器仍在 Hero 内且可点。旧文案锁（仓库工作台/今日概览/当前仓库）
   随之退役，见 test_002_title_and_warehouse_use_theme_surface。
2. VoiceAssistant 的 FAB modifier 必须含 `navigationBarsPadding()` 且
   底部 padding ≥ 80dp（M3 NavigationBar 高 80dp）。
3. BUG-2026-10-04-002 必须登记台账（含「生效确认」字段，A13）。

## 为什么是静态断言

本地无 Android SDK 与 Kotlin 工具链；Android CI另做真实编译及Compose测量；
本测试以源码结构契约锁死修复。
"""

# 2026-11-15 用户授权中性工作台：旧蓝底白字约束改为实际主题表面/前景，
# 原标题不裁切、仓库可用和语音 FAB 避让的业务与布局要求继续保留。
# 2026-11-16 用户确认恢复蓝色首页，守卫回到蓝底白字并保留上述业务约束。
# 2026-11-18 用户授权沉浸式品牌头，改写 4 条旧字符串锁（保留无 offset / 白字 / 可点）。
from __future__ import annotations

import re
from pathlib import Path

from tests.ledger_reader import bug_section_text, read_bug_baseline

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = (
    REPO_ROOT
    / "app" / "android-native-wms" / "app" / "src" / "main" / "java"
    / "com" / "factory" / "wms"
)
HOME = SRC / "ui" / "screens" / "HomeScreen.kt"
VOICE = SRC / "ui" / "components" / "VoiceAssistant.kt"


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


def test_002_title_and_warehouse_use_theme_surface() -> None:
    # 2026-11-18 用户明确授权把首页 Hero 改为沉浸式品牌头（时段问候语 + 单行仓库切换器 + 退出），
    # 并授权同步改写本节 4 条旧字符串锁。**业务意图一条不丢**：
    #   ① 标题不得进入 offset 悬浮列（行高超预留就会被白底裁切）；
    #   ② Hero 深底必须白字，且底色必须来自 Primary.readableOn(Color.White)；
    #   ③ 仓库切换器必须仍在 Hero 内、仍带白色前景、仍可点（onSelect 未被丢弃）。
    src = _read(HOME)
    hero = src.split('internal fun HomeWorkbench(', 1)[1].split('HomeSectionTitle("常用操作")', 1)[0]
    greeter = src.split('internal fun greetingForHour(', 1)[1].split('internal fun HomeWorkbench(', 1)[0]
    # ① 时段问候语：四条分支齐全，避免夜班人员看到「早上好」
    for branch in ('"早上好"', '"上午好"', '"下午好"', '"晚上好"'):
        assert branch in greeter, f"问候语缺少 {branch} 分支"
    assert "Text(greeting" in hero, "问候语未渲染到 Hero 内"
    # ② 副标题保留日期与当日待处理单量（原「仓库工作台 · 日期」的信息不丢）
    assert "$today · 今天有 " in hero, "副标题丢失日期"
    assert "单入库待处理" in hero, "副标题丢失当日待处理单量"
    # ③ Hero 底色与白字前景（BUG-002 的裁切/不可见根因）
    assert ".background(Primary.readableOn(Color.White))" in hero
    assert "color = Color.White" in hero, "Hero 内文字未显式使用白色前景"
    # ④ 仓库切换器：Hero 内唯一、白字、可点
    selectors = re.findall(r"WarehouseSelector\((.*?)\)", hero, re.S)
    assert len(selectors) == 1, f"Hero 内应只有一个仓库切换器，实际 {len(selectors)}"
    assert "contentColor = Color.White" in selectors[0], "仓库切换器缺少白色前景（对比度回退）"
    assert "onSelect = onSelectWarehouse" in selectors[0], "仓库切换器失去切换回调"
    assert "selectedId = selectedWarehouseId" in selectors[0], "仓库切换器失去当前选中态"
    assert "allowAll = false" in selectors[0], "仓库切换器不应出现「全部仓库」"
    # ⑤ 正常文档流：不得用负偏移把标题骑到深底与白底交界处
    assert "verticalScroll(rememberScrollState())" in hero
    assert "Modifier.offset" not in src


def test_002_overview_states_have_no_floating_overlap() -> None:
    src = _read(HOME)
    assert "Modifier.offset" not in src
    for state in ('dashboard != null -> TodayOverviewBar', 'isLoading -> DashboardOverviewSkeleton', 'else -> DashboardOverviewError'):
        assert state in src


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
    # F4.4 拆分后台账详情在 docs/ledger/bugs/ 分片，须用兼容读取器，见 tests/ledger_reader.py
    content = read_bug_baseline()
    assert "BUG-2026-10-04-002" in content, "BUG-2026-10-04-002 未登记进 BUG 台账"
    section = bug_section_text(content, "BUG-2026-10-04-002")
    assert "生效确认" in section, "BUG-2026-10-04-002 条目缺少「生效确认」字段（允许「待确认」占位）"
