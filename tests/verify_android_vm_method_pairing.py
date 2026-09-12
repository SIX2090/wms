#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BUG-2026-09-12-001 回归守护：Screen 调用的 viewModel 方法必须有真实声明。

背景（CI Android APK Build 首次失败，run 34677163004）：
    AI-MOB-SCAN-UX-01 三件套首次接线时，OpeningStockScreen.kt 直接调用了
    `viewModel.materialExists(barcode)`，但该方法只加在了 ScanViewModel 上，
    OpeningStockScreen 的 viewModel 实际是 OpeningStockViewModel —— 方法不存在，
    Kotlin 编译失败，assembleRelease exit 1，APK 未产出。

为什么静态契约测试（正则扫描）没拦住：
    verify_android_scan_feedback.py T5 只断言「Screen 里出现了 materialExists 调用」，
    不检查被调对象（OpeningStockViewModel）上是否有该方法声明 —— 这是文本断言的盲区。
    本测试补上「调用点 ↔ 声明点」的配对检查。

口径：
    对每个「调用了 viewModel.materialExists(...)」的 Screen 文件，反查该页绑定的
    ViewModel 类型，并要求对应 ViewModel 文件里存在 `fun materialExists(` 声明。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _strip_comments(src: str) -> str:
    """去掉块/行注释（沿用仓库约定：约束块注释起点必须顶格或空白后出现，
    避免把字符串里的 image/* 当注释起点吞掉半个文件）。"""
    src = re.sub(r"(?<!\S)/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    return src


# viewModel 形参类型 → 对应 ViewModel 源文件（相对 src 根）
KNOWN_VIEWMODELS = {
    "ScanViewModel": "ui/viewmodel/scan/ScanViewModel.kt",
    "OpeningStockViewModel": "ui/viewmodel/opening/OpeningStockViewModel.kt",
    "StockQueryViewModel": "ui/viewmodel/scan/StockQueryViewModel.kt",
}

# 所有绑定已知 ViewModel 的 Screen（扫描全部 screens 更稳，这里按目录全扫）
SCREEN_DIR = SRC / "ui" / "screens"


def _screen_vm_type(screen_src: str, m: re.Match) -> str | None:
    """在 Screen 的函数签名里找该 viewModel 形参的真实类型。

    先按行向上找最近的 `viewModel: XViewModel,` 声明；找不到则回退全文件第一个。
    """
    lines = screen_src[: m.start()].count("\n")
    all_decls = re.findall(r"(\w+ViewModel)\s*\)?\s*,?\s*$", screen_src, re.M)
    for back in range(lines, -1, -1):
        seg = screen_src.splitlines()
        idx = lines - back
        if 0 <= idx < len(seg):
            dm = re.search(r"viewModel:\s*(\w+ViewModel)", seg[idx])
            if dm:
                return dm.group(1)
    # 回退：文件里第一个 XViewModel 类型
    fm = re.search(r"viewModel:\s*(\w+ViewModel)", screen_src)
    return fm.group(1) if fm else None


def test_every_materialExists_call_site_has_declaration():
    """所有 `viewModel.materialExists(` 调用点，其 ViewModel 必须声明该方法。"""
    offenders: list[str] = []
    checked = 0
    for screen in sorted(SCREEN_DIR.glob("*.kt")):
        src = _strip_comments(_read(screen))
        calls = list(re.finditer(r"viewModel\.materialExists\s*\(", src))
        if not calls:
            continue
        for m in calls:
            checked += 1
            vm = _screen_vm_type(src, m)
            if vm is None:
                offenders.append(f"{screen.name}: 无法定位 viewModel 类型")
                continue
            vm_rel = KNOWN_VIEWMODELS.get(vm)
            if vm_rel is None:
                offenders.append(f"{screen.name}: 未知 ViewModel 类型 {vm}")
                continue
            vm_src = _strip_comments(_read(SRC / vm_rel))
            if not re.search(r"fun\s+materialExists\s*\(", vm_src):
                offenders.append(
                    f"{screen.name} 调用 viewModel.materialExists()，但 {vm} "
                    f"（{vm_rel}）没有该声明 —— Kotlin 编译必失败"
                )
    assert checked > 0, "未发现任何 materialExists 调用点，测试口径失效"
    assert not offenders, "存在无声明的调用点：\n" + "\n".join(offenders)


def test_known_viewmodels_declare_material_exists():
    """本轮接线的两个 ViewModel 都必须声明 materialExists（网络异常时返回 true）。"""
    for vm in ["ScanViewModel", "OpeningStockViewModel"]:
        vm_src = _strip_comments(_read(SRC / KNOWN_VIEWMODELS[vm]))
        assert re.search(r"suspend\s+fun\s+materialExists\s*\(", vm_src), (
            f"{vm} 缺少 suspend fun materialExists —— 扫码反馈（AI-MOB-SCAN-UX-01）依赖它判成功/失败"
        )
        # 网络异常返回 true 的语义必须保留（catch 分支返回 true 或隐式 true）
        seg = re.search(
            r"suspend\s+fun\s+materialExists\s*\([^)]*\)\s*:\s*Boolean\s*\{(?P<body>.*?)\n    \}",
            vm_src, re.S,
        )
        assert seg, f"{vm}.materialExists 函数体未找到"
        body = seg.group("body")
        assert "catch" in body, f"{vm}.materialExists 必须捕获异常（反馈是锦上添花，不能让扫码崩）"
        assert re.search(r"catch\s*\([^)]*\)\s*\{?\s*(true|return\s+true)", body), (
            f"{vm}.materialExists 网络异常分支必须返回 true —— "
            "断网时不应把「查不到」误报成「物料不存在」"
        )


def test_opening_stock_screen_binds_opening_stock_viewmodel():
    """固定配对：OpeningStockScreen ↔ OpeningStockViewModel（本次事故的直接配对）。"""
    src = _strip_comments(_read(SRC / "ui" / "screens" / "OpeningStockScreen.kt"))
    assert re.search(r"viewModel:\s*OpeningStockViewModel", src), (
        "OpeningStockScreen 的 viewModel 类型发生变化，需同步更新 KNOWN_VIEWMODELS 映射"
    )
    vm_src = _strip_comments(_read(SRC / KNOWN_VIEWMODELS["OpeningStockViewModel"]))
    assert re.search(r"fun\s+materialExists\s*\(", vm_src), (
        "OpeningStockScreen 调用了 materialExists，OpeningStockViewModel 必须声明"
    )
