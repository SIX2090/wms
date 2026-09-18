# -*- coding: utf-8 -*-
"""BUG-2026-09-18-007 回归：手机端扫码页标题写死「扫码」，与手动添加路径矛盾。

现场现象：用户从「出库 → 手工添加」进入，页面顶部却写着「扫码出库」，
底部 Tab 又写「出库」，三套口径并存，会怀疑进错页面 / 以为手工添加走错了地方。

根因：标题写成"扫码+动作"，但**扫码只是录入手式之一**——
    入库/出库页另有「手动添加」（ScanScreenBase 弹窗）与语音建单（AI-VOICE-OUT-F01）；
    盘点页另有「识物盘点」；入库/出库/盘点还都能从首页卡片或概览下钻进入。
把一种录入手式写进业务页标题，对另外几种入口就是错的。

修复契约（R6：同根因消费点必须一次修干净，不留下游第二套口径）：
    T1 三个扫描页标题为业务动作名（入库/出库/盘点），副标题说明录入方式；
    T2 Screen.kt 的路由标题同步（这是本页之外第二套标题口径）；
    T3 底部 Tab 与首页功能卡与 Screen 标题一致，不留跨页口径分裂；
    T4 登录页功能范围陈述不再只把"扫码"挂在入库上；
    T5 route 字符串不被标题改动波及（标题是展示层，不能改变路由）；
    T6 Kotlin 括号平衡。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms"
SCREENS = SRC / "ui/screens/ScanScreens.kt"
SCREEN = SRC / "ui/navigation/Screen.kt"
NAV = SRC / "ui/navigation/NavGraph.kt"
HOME = SRC / "ui/screens/HomeScreen.kt"
LOGIN = SRC / "ui/screens/LoginScreen.kt"

screens_src = SCREENS.read_text(encoding="utf-8")
screen_src = SCREEN.read_text(encoding="utf-8")
nav_src = NAV.read_text(encoding="utf-8")
home_src = HOME.read_text(encoding="utf-8")
login_src = LOGIN.read_text(encoding="utf-8")


def test_scan_page_titles_are_action_names():
    """T1：三个页面标题去掉「扫码」前缀，副标题补回录入手式。"""
    assert 'title = "入库",' in screens_src
    assert 'title = "出库",' in screens_src
    assert 'title = "盘点",' in screens_src
    # 副标题必须说明支持扫码与手动，信息不丢失
    assert 'subtitle = "扫码或手动添加物料，完成入库",' in screens_src
    assert 'subtitle = "扫码或手动添加物料，完成出库",' in screens_src
    assert 'subtitle = "扫码或手动录入实际库存，生成盘点差异",' in screens_src
    # 标题里不得再出现写死的扫码
    assert 'title = "扫码入库"' not in screens_src
    assert 'title = "扫码出库"' not in screens_src
    assert 'title = "扫码盘点"' not in screens_src


def test_screen_route_titles_match():
    """T2：Screen.kt 的 title 是第二套标题口径，必须同步。"""
    assert 'data object Inbound : Screen("inbound", "入库")' in screen_src
    assert 'data object Outbound : Screen("outbound", "出库")' in screen_src
    assert 'data object Stocktake : Screen("stocktake", "盘点")' in screen_src
    assert 'Screen("inbound", "扫码入库")' not in screen_src
    assert 'Screen("outbound", "扫码出库")' not in screen_src
    assert 'Screen("stocktake", "扫码盘点")' not in screen_src


def test_bottom_tab_and_home_card_consistent():
    """T3：底部 Tab 与首页功能卡与 Screen 标题统一，不留口径分裂。"""
    # 底部 Tab 本来就是动作名，锁住防止回退
    assert 'BottomTab(Screen.Inbound, "入库"' in nav_src
    assert 'BottomTab(Screen.Outbound, "出库"' in nav_src
    # 首页功能卡的"扫码盘点"是同一根因的第三个消费点
    assert 'title = "盘点",' in home_src
    assert 'title = "扫码盘点"' not in home_src


def test_login_scope_text_not_scan_only():
    """T4：登录页功能范围陈述不再把"扫码"只挂在入库上。"""
    assert '"入库 · 出库 · 盘点 · 识物"' in login_src
    assert '"扫码入库 · 出库 · 盘点 · 识物"' not in login_src


def test_route_strings_unchanged():
    """T5：只改展示标题，不得波及路由字符串（否则导航直接失效）。"""
    for route in ["inbound", "outbound", "stock_query", "stocktake"]:
        assert f'"{route}"' in screen_src
    # 导航图仍按 route 注册
    assert "Screen.Inbound.route" in nav_src
    assert "Screen.Outbound.route" in nav_src
    assert "Screen.Stocktake.route" in nav_src


def test_kotlin_brace_balance():
    """T6：改动文件括号平衡。"""
    for name, src in (
        ("ScanScreens.kt", screens_src),
        ("Screen.kt", screen_src),
        ("HomeScreen.kt", home_src),
        ("LoginScreen.kt", login_src),
    ):
        for open_ch, close_ch in [("{", "}"), ("(", ")"), ("[", "]")]:
            assert src.count(open_ch) == src.count(close_ch), (
                f"{name} 的 {open_ch}{close_ch} 不平衡："
                f"{src.count(open_ch)} vs {src.count(close_ch)}"
            )
