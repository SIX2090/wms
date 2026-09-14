#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BUG-2026-09-14-032 回归：NavGraph 不得在组合根饿汉创建全部 ViewModel。

## 缺陷

`AppNavGraph()` 原先在其函数体开头一次性创建 14 个 ViewModel：

    val authViewModel: AuthViewModel = viewModel()
    val inboundScanViewModel: ScanViewModel = viewModel(key = "inbound_scan")
    ... 共 14 行 ...
    val overviewListViewModel: OrderListViewModel = viewModel(key = "overview_list")

`AppNavGraph` 是**全 App 的组合根**，在 `MainActivity.setContent` 第一帧就被调用。
因此这 14 行意味着「App 一启动就构造所有页面的 ViewModel」。

三个具体危害：
1. **崩溃放大**：任一 VM 构造期抛异常 = 进程闪退。BUG-2026-09-14-029 的
   `ScanViewModel.<init>` 崩溃正是被这里放大成"打开应用即闪退"的。
2. **启动开销与内存常驻**：14 个 VM（含 4 个 ScanViewModel 副本）及其依赖的
   Repository / DAO / 协程作用域全部常驻，用户可能从不打开其中大半页面。
3. **竞态温床**：VM 在"会话尚未还原"时即被构造，init 中发起网络请求必然读到空
   baseUrl。BUG-2026-08-24-006 已记录该竞态（报表页报「服务器地址未配置」），
   当时只给 ReportViewModel 打"不在 init 加载"的局部补丁，**饿汉创建这个根因从未消除**。

## 修复约定（本测试锁死）

- `AppNavGraph` 函数**顶层**只允许创建 `authViewModel`（startDestination 依赖其
  登录态，且必须在导航建立前存在）。
- 其余 ViewModel 必须下沉到各自 `composable(...)` 路由内按需创建。
- 允许在 `if (authState.isLoggedIn)` 分支内的惰性创建（语音悬浮层）。

## 为什么是静态断言

沙箱/CI 无 Android SDK 与 Kotlin 工具链，无法编译运行 Compose；
本测试以"源码结构契约"锁死修复，防后续提交把 VM 重新堆回顶层。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
NAVGRAPH = (
    REPO_ROOT
    / "app"
    / "android-native-wms"
    / "app"
    / "src"
    / "main"
    / "java"
    / "com"
    / "factory"
    / "wms"
    / "ui"
    / "navigation"
    / "NavGraph.kt"
)

# 顶层（AppNavGraph 函数体起点 ~ 第一个 composable 路由之前）允许出现的 VM 创建
TOP_LEVEL_ALLOWED = {"authViewModel"}

VM_ASSIGN_RE = re.compile(r"val\s+(\w+)\s*:\s*\w*ViewModel\s*=\s*viewModel\(")


def _src() -> str:
    assert NAVGRAPH.exists(), f"NavGraph.kt 不存在：{NAVGRAPH}"
    return NAVGRAPH.read_text(encoding="utf-8")


def _appnavgraph_top_region(src: str) -> str:
    """截取 AppNavGraph 函数体开头，到第一个 composable( 路由为止。"""
    start = src.find("fun AppNavGraph()")
    assert start != -1, "未找到 AppNavGraph() 函数"
    first_route = src.find("composable(", start)
    assert first_route != -1, "AppNavGraph 内未找到 composable( 路由"
    return src[start:first_route]


def test_032_no_eager_vm_creation_at_composition_root() -> None:
    """核心断言：组合根顶层不得堆叠 ViewModel 创建（仅允许 authViewModel）。"""
    top = _appnavgraph_top_region(_src())
    created = [m.group(1) for m in VM_ASSIGN_RE.finditer(top)]
    offenders = [name for name in created if name not in TOP_LEVEL_ALLOWED]
    assert not offenders, (
        "AppNavGraph 组合根顶层仍存在饿汉创建的 ViewModel（应下沉到各 composable 路由内）：\n  "
        + "\n  ".join(offenders)
        + f"\n\n顶层实际创建：{created}\n仅允许：{sorted(TOP_LEVEL_ALLOWED)}"
    )


def test_032_auth_viewmodel_still_at_top_level() -> None:
    """反向保证：authViewModel 必须留在顶层——startDestination 依赖其登录态。

    若被误下沉，登录态判定会晚于 NavHost 建立，导致启动落错页面。
    """
    top = _appnavgraph_top_region(_src())
    assert re.search(r"val\s+authViewModel\s*:\s*AuthViewModel\s*=\s*viewModel\(", top), (
        "authViewModel 必须保留在 AppNavGraph 顶层（startDestination 依赖其 isLoggedIn）"
    )


@pytest.mark.parametrize(
    "route_key",
    [
        "inbound_scan",
        "outbound_scan",
        "stock_query",
        "stocktake",
        "overview_list",
    ],
)
def test_032_scan_vms_created_inside_routes_with_distinct_keys(route_key: str) -> None:
    """4 个 ScanViewModel 与下钻列表必须带 key 在**路由内**创建。

    key 是语义隔离的关键：4 个扫码 VM 必须各自独立（不能共用一个实例，
    否则入库页的扫描明细会串到出库页）。
    """
    src = _src()
    top = _appnavgraph_top_region(src)
    assert f'viewModel(key = "{route_key}")' not in top, (
        f'key="{route_key}" 的 ViewModel 仍在组合根顶层创建，应下沉到路由内'
    )
    assert f'viewModel(key = "{route_key}")' in src, (
        f'未找到 key="{route_key}" 的 ViewModel 创建（路由内应存在）'
    )


def test_032_every_vm_created_inside_composable_or_login_branch() -> None:
    """每个 VM 创建点都必须位于 composable 路由内、或已登录分支内。"""
    src = _src()
    lines = src.split("\n")
    # 记录 composable( 行号 与 if (authState.isLoggedIn) 行号，及其后续块范围（粗判）
    composable_lines = [i for i, l in enumerate(lines, 1) if "composable(" in l]
    login_branch = [i for i, l in enumerate(lines, 1) if "authState.isLoggedIn" in l]

    unguarded: list[str] = []
    for m in re.finditer(r"val\s+(\w+)\s*:\s*\w*ViewModel\s*=\s*viewModel\(", src):
        line_no = src[: m.start()].count("\n") + 1
        name = m.group(1)
        if name in TOP_LEVEL_ALLOWED:
            continue  # authViewModel 是顶层允许的例外，由 test_032_no_eager_... 单独约束
        # 该创建点之前，是否已有 composable( 或登录分支开启
        has_ctx = any(cl < line_no for cl in composable_lines) or any(
            bl < line_no for bl in login_branch
        )
        if not has_ctx:
            unguarded.append(f"L{line_no} val {name}")

    assert not unguarded, (
        "以下 ViewModel 创建点不在任何 composable 路由或已登录分支内（仍属组合根饿汉创建）：\n  "
        + "\n  ".join(unguarded)
    )


def test_032_voice_vms_only_when_logged_in() -> None:
    """语音悬浮层 VM 必须在已登录分支内创建（未登录时不构造）。"""
    src = _src()
    idx = src.find("VoiceAssistantOverlay(")
    assert idx != -1, "未找到 VoiceAssistantOverlay 调用"
    # 往上找最近的 isLoggedIn 判断
    head = src[:idx]
    last_guard = head.rfind("authState.isLoggedIn")
    assert last_guard != -1, "VoiceAssistantOverlay 未受 isLoggedIn 守卫"
    # 守卫与调用之间不应出现 composable 边界（说明确实在分支内）
    between = head[last_guard:]
    assert "composable(" not in between, (
        "VoiceAssistantOverlay 的 isLoggedIn 守卫与调用之间跨越了 composable 边界，疑似不在分支内"
    )


def test_032_no_duplicate_viewmodel_key_collision() -> None:
    """同一 key 不得被赋予不同 VM 类型——否则 ViewModelStore 实例错乱。"""
    src = _src()
    key_types: dict[str, set[str]] = {}
    for m in re.finditer(r"val\s+\w+\s*:\s*(\w*ViewModel)\s*=\s*viewModel\(key\s*=\s*\"([^\"]+)\"", src):
        vm_type, key = m.group(1), m.group(2)
        key_types.setdefault(key, set()).add(vm_type)
    conflicts = {k: v for k, v in key_types.items() if len(v) > 1}
    assert not conflicts, f"同一 key 被赋予多个 VM 类型：{conflicts}"


def test_032_baseline_registered() -> None:
    """BUG-2026-09-14-032 必须已登记进基线（AGENTS.md BUG 流程要求）。"""
    baseline = REPO_ROOT / "WMS_BUG_BASELINE.md"
    assert baseline.exists(), "WMS_BUG_BASELINE.md 不存在"
    content = baseline.read_text(encoding="utf-8")
    assert "BUG-2026-09-14-032" in content, (
        "BUG-2026-09-14-032 未登记进 WMS_BUG_BASELINE.md"
    )
