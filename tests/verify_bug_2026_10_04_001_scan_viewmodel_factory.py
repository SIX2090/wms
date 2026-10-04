#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BUG-2026-10-04-001 回归守护：ScanViewModel 反射创建点必须传 Factory。

## 缺陷

现场真机（HUAWEI LIO-AN00, SDK 31, v3.9.4）打开入库/出库/库存查询/盘点
任一页面即进程闪退：

    java.lang.RuntimeException: Cannot create an instance of class
        com.factory.wms.ui.viewmodel.scan.ScanViewModel
    Caused by: java.lang.NoSuchMethodException:
        ScanViewModel.<init> [class android.app.Application]

根因：BUG-2026-10-002（7537b3d）给 ScanViewModel 构造函数新增第二参数
`dataStoreTimeoutMs: Long = WmsRepository.DATASTORE_TIMEOUT_MS`。Kotlin 默认参数
**不会**生成 (Application) 单参构造方法；NavGraph 的 5 处 `viewModel(key=...)`
均为无工厂创建，走 AndroidViewModelFactory 反射查找 <init>(Application)，
必然 NoSuchMethodException。单测全用手写构造（DataStoreTimeoutTest 等）而
NavGraph 反射路径无任何测试覆盖，故 4 个扫码页全部带病上线。

## 修复约定（本测试锁死）

1. ScanViewModel 必须声明 companion Factory（viewModelFactory DSL + APPLICATION_KEY）。
2. 主源码中**每一个** `XxxViewModel: ScanViewModel = viewModel(` 创建点都必须传
   `factory = ScanViewModel.Factory`——不允许再出现无工厂反射创建。
3. BUG-2026-10-04-001 必须登记进 WMS_BUG_BASELINE.md（含「生效确认」字段，A13）。

## 为什么是静态断言

沙箱/CI 无 Android SDK 与 Kotlin 工具链，无法编译运行 Compose（AGENTS.md §三
已知限制）；本测试以源码结构契约锁死修复，防后续提交新增无工厂创建点。
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
SCAN_VM = SRC / "ui" / "viewmodel" / "scan" / "ScanViewModel.kt"
NAVGRAPH = SRC / "ui" / "navigation" / "NavGraph.kt"
BASELINE = REPO_ROOT / "WMS_BUG_BASELINE.md"

SCAN_VM_CREATION_RE = re.compile(
    r"val\s+\w+\s*:\s*ScanViewModel\s*=\s*viewModel\(([^)]*)\)"
)


def _read(p: Path) -> str:
    assert p.exists(), f"文件不存在：{p}"
    return p.read_text(encoding="utf-8")


def _strip_comments(src: str) -> str:
    src = re.sub(r"(?<!\S)/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def test_001_scan_viewmodel_declares_companion_factory() -> None:
    """ScanViewModel 必须有 companion Factory，用 viewModelFactory DSL + APPLICATION_KEY。"""
    src = _strip_comments(_read(SCAN_VM))
    assert re.search(r"companion\s+object\s*\{[^}]*val\s+Factory", src, re.S), (
        "ScanViewModel 缺少 companion object { val Factory } —— "
        "两参构造下无工厂反射创建必然 NoSuchMethodException"
    )
    assert "viewModelFactory" in src and "initializer" in src, (
        "Factory 必须用 viewModelFactory { initializer { ... } } DSL 构建"
    )
    assert "APPLICATION_KEY" in src, (
        "Factory 必须从 CreationExtras 取 APPLICATION_KEY 构造，"
        "不得用全局单例 Application（进程重建/多实例语义会错）"
    )


def test_001_every_scan_vm_creation_passes_factory() -> None:
    """主源码全部 ScanViewModel = viewModel( 创建点必须传 factory（核心回归锁）。"""
    main_src = SRC
    offenders: list[str] = []
    checked = 0
    for kt in sorted(main_src.rglob("*.kt")):
        src = _strip_comments(_read(kt))
        for m in SCAN_VM_CREATION_RE.finditer(src):
            checked += 1
            args = m.group(1)
            if "factory" not in args:
                line_no = src[: m.start()].count("\n") + 1
                offenders.append(f"{kt.relative_to(SRC)}:{line_no} viewModel({args.strip()})")
    assert checked >= 5, (
        f"只发现 {checked} 处 ScanViewModel 创建点（NavGraph 应有 5 处：4 页面 + 盘点识别复用），"
        "测试口径失效"
    )
    assert not offenders, (
        "以下 ScanViewModel 创建点未传 factory，运行时会反射查找 <init>(Application) "
        "并 NoSuchMethodException 闪退：\n  " + "\n".join(offenders)
    )


def test_001_all_four_scan_keys_use_scan_factory() -> None:
    """4 个扫码页 key 必须各自带 factory 创建（缺一个页面就是一台真机闪退）。"""
    src = _strip_comments(_read(NAVGRAPH))
    for key in ["inbound_scan", "outbound_scan", "stock_query", "stocktake"]:
        assert re.search(
            rf'viewModel\(key\s*=\s*"{key}"\s*,\s*factory\s*=\s*ScanViewModel\.Factory\)',
            src,
        ), f'NavGraph 中 key="{key}" 未以 factory = ScanViewModel.Factory 创建'


def test_001_bug_registered_with_confirmation_field() -> None:
    """BUG-2026-10-04-001 必须登记台账且含「生效确认」字段（AGENTS.md A13）。"""
    content = _read(BASELINE)
    assert "BUG-2026-10-04-001" in content, "BUG-2026-10-04-001 未登记进 WMS_BUG_BASELINE.md"
    # 截取该条目段落（到下一个同级标题为止）检查生效确认字段
    m = re.search(r"(##[^\n]*BUG-2026-10-04-001[^\n]*\n.*?)(?=\n##\s|\Z)", content, re.S)
    assert m, "无法定位 BUG-2026-10-04-001 条目段落"
    assert "生效确认" in m.group(1), (
        "BUG-2026-10-04-001 条目缺少「生效确认」字段（A13 硬性要求，允许「待确认」占位）"
    )
