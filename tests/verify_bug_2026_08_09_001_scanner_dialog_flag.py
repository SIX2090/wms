# -*- coding: utf-8 -*-
"""
BUG-2026-08-09-001 回归测试：Android App 扫码无法识别条码

根因：
  app/android-native-wms/.../ui/components/ScannerDialog.kt 的 ML Kit 成功回调中，
  `scannedFlag.compareAndSet(false, true)` 无条件置位。ML Kit 对未识别到条码的帧
  同样回调成功（barcodes 为空列表），相机打开后的首帧（用户尚未对准，几乎必为
  空结果）就把 scannedFlag 置为 true；analyzer 入口 `if (scannedFlag.get())`
  随后丢弃所有后续帧，ML Kit 从此不再分析任何画面，表现为"扫码无法识别条码"。

修复：
  仅在真正解码出非空条码值时才置位 scannedFlag；空结果继续分析后续帧；
  并补充 addOnFailureListener 记录识别失败日志以便现场诊断。

具体断言：
  T1. compareAndSet 必须被 rawValue 非空判断守卫（修复后模式存在）
  T2. 旧的无条件置位模式不复存在（回调体首语句即 compareAndSet）
  T3. rawValue 取自 barcode.rawValue 局部变量并做非空校验
  T4. 存在 addOnFailureListener 失败日志，识别失败不再静默

使用方法：
  cd /workspace && python -m pytest tests/verify_bug_2026_08_09_001_scanner_dialog_flag.py -xvs
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCANNER_KT = (
    ROOT
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
    / "components"
    / "ScannerDialog.kt"
)


def _source() -> str:
    return SCANNER_KT.read_text(encoding="utf-8")


def test_t1_compare_and_set_guarded_by_raw_value():
    """compareAndSet 必须与 rawValue 非空判断在同一条件中（先判值再置位）"""
    src = _source()
    assert re.search(
        r"!\s*rawValue\.isNullOrEmpty\(\)\s*&&\s*scannedFlag\.compareAndSet\(false,\s*true\)",
        src,
    ), "修复后模式缺失：compareAndSet 必须被 rawValue 非空守卫"


def test_t2_unconditional_latch_pattern_removed():
    """旧模式：成功回调体首语句无条件 compareAndSet —— 不得复现"""
    src = _source()
    assert not re.search(
        r"addOnSuccessListener\s*\{\s*barcodes\s*->\s*"
        r"if\s*\(\s*scannedFlag\.compareAndSet\(false,\s*true\)\s*\)",
        src,
    ), "旧的无条件置位模式仍在：首帧空结果会永久关闭扫码分析"


def test_t3_raw_value_extracted_and_checked():
    """rawValue 通过局部变量取自 barcode.rawValue 并做非空校验后才回调"""
    src = _source()
    assert "val rawValue = barcode.rawValue" in src
    assert "onBarcodeScanned(rawValue)" in src


def test_t4_failure_listener_present():
    """ML Kit 识别失败必须有日志，不再静默吞掉"""
    src = _source()
    assert ".addOnFailureListener" in src, "缺少 addOnFailureListener 失败日志"
