# -*- coding: utf-8 -*-
"""连续扫描模式 —— 静态契约测试（AI-MOB-CONTINUOUS-SCAN-01）。

需求背景（用户原话：「wms手机端app怎么把它打造一个很好用很实用的app?」→「按你的思路来做」）：

改造前后对比
--------------------------------------------------------------------
|            | 改造前                              | 改造后                    |
|------------|-------------------------------------|---------------------------|
| 扫中一条码 | `showScannerDialog = false` 立即关  | 弹窗保持，相机不中断      |
| 扫下一件   | 必须再点一次"扫码"按钮              | 直接扫，无需任何点击      |
| 节流       | 靠"关弹窗"天然阻断重复              | scannedFlag 置位 + 延迟复位 |
| 回显       | 无（弹窗已关）                      | 顶部"已扫 N 件"+ 已加入回显 |
| 退出       | 自动                                | 用户点"完成"              |

为什么这是移动端最大的一处效率损耗
--------------------------------------------------------------------
仓库现场一个托盘常 20~50 件货。改造前每件货要「扫 → 关 → 点开 → 扫」，
一次收货净增 40~100 次点击。这不是"不顺手"，是把工作量翻倍。

本测试锁定的契约（任何一条被改坏都要红）
--------------------------------------------------------------------
T1. `ScannerDialog` 暴露 `continuous` / `scannedCount` / `lastScannedCode` 三个参数，
    `continuous` 默认值为 true（连续是常态，查库这类单码场景才显式关）。
T2. 分析回调里，**连续模式下必须重新武装 scannedFlag**（`releaseFlag.arm()`），
    否则弹窗不关 + flag 永久置位 = 只能扫到第一条码，比改造前更糟。
T3. 非连续模式必须**保持旧行为**（不 arm），否则"扫一个就退出"的页面会失去原有保护。
T4. 节流窗口常量存在且取值合理（>300ms 挡住同码多帧命中，<2000ms 不拖慢人手换件）。
T5. BUG-2026-08-09-001 的保护不能被破坏：**仍然只在 `rawValue` 非空时才置位**
    （ML Kit 对空结果帧也回调成功，无条件置位会永久关闭分析）。
T6. 仍用 `compareAndSet(false, true)` 原子抢占，不得退化成 `if (!flag) { flag = true }`。
T7. 顶部标题区回显"已扫 N 件"，底部提供"完成"按钮与"继续扫"手动放行。
T8. 三种扫码场景接线正确：
    - 入库/出库/盘点（走 `ScanScreenBase`）→ continuous = true
    - 期初库存 `OpeningStockScreen` → continuous = true
    - 查库存 `ScanScreens`（扫一个看一个）→ **continuous = false**
T9. 弹窗的 `onDismiss` 不承担计数职责；计数由调用方持有，且**每次打开相机时复位**
    （否则上一轮的 N 会串到本轮，与清单行数对不上）。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"

SCANNER = SRC / "ui" / "components" / "ScannerDialog.kt"
SCAN_BASE = SRC / "ui" / "screens" / "ScanScreenBase.kt"
SCAN_SCREENS = SRC / "ui" / "screens" / "ScanScreens.kt"
OPENING = SRC / "ui" / "screens" / "OpeningStockScreen.kt"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _no_comments(src: str) -> str:
    """去掉 Kotlin 注释，避免契约文本本身（如本文件在源码里的说明）触发误判。

    块注释必须用 `(?<!\\S)/\\*` 约束 —— 否则会把字符串里的 `image/*"` 当成注释起点，
    一路匹配到后面某个 `*/` 从而吞掉大半个文件。本批测试在 verify_android_qty_keyboard.py
    上真实踩过一次（AiScreens.kt 77KB 被削到 14KB），这里一并加固，
    避免将来这几个文件出现 `image/*` 之类字面量时静默失效。
    """
    no_block = re.sub(r"(?<!\S)/\*.*?\*/", "", src, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", no_block)


# ---------------------------------------------------------------------------
# T1. 参数签名
# ---------------------------------------------------------------------------
def test_t1_scanner_dialog_exposes_continuous_params():
    src = _no_comments(_read(SCANNER))
    assert re.search(r"fun\s+ScannerDialog\s*\(", src), "ScannerDialog 函数签名丢失"
    # 三个参数
    for name in ("continuous", "scannedCount", "lastScannedCode"):
        assert re.search(rf"\b{name}\s*:", src), f"ScannerDialog 缺少参数 {name}"
    # continuous 默认 true：连续是常态
    m = re.search(r"continuous\s*:\s*Boolean\s*=\s*(true|false)", src)
    assert m, "continuous 未声明 Boolean 默认值"
    assert m.group(1) == "true", (
        "continuous 默认应为 true —— 连续扫描是仓库常态，"
        "单码场景（如查库存）应显式传 false"
    )


# ---------------------------------------------------------------------------
# T2 + T3. 只有连续模式才重新武装 flag
# ---------------------------------------------------------------------------
def test_t2_continuous_mode_rearms_flag():
    src = _no_comments(_read(SCANNER))
    # 必须存在一个"重新武装"动作
    assert re.search(r"\barm\s*\(\s*\)", src), (
        "缺少节流重新武装调用（arm()）—— 弹窗不关 + flag 永久置位 = 只能扫到第一条码"
    )
    # 且它必须被 continuous 守卫
    m = re.search(
        r"if\s*\(\s*continuous\w*\.value\s*\)\s*\{[^}]*arm\s*\(\s*\)",
        src, re.DOTALL,
    )
    assert m, (
        "arm() 必须由 continuous 守卫 —— 非连续模式要保持旧行为（扫中即退出），"
        "无条件 arm 会让只扫一码的页面失去原有保护"
    )


def test_t2b_manual_release_wins_over_pending_timer():
    """「继续扫」按钮的立即放行不得被先前排队的定时复位反噬。

    这是一个真实竞态：用户在 900ms 窗口内又扫了一件 -> releaseNow() 复位 flag
    并 arm() 新窗口；但**上一次** arm() 排队的 postDelayed 还没执行，它到点后会把
    刚扫中的那一件的置位又抹掉，导致下一条码被重复放行（同一件货计两次）。
    修法是给窗口编号（令牌），定时复位只在"自己仍是当前窗口"时才生效。
    """
    src = _no_comments(_read(SCANNER))
    assert re.search(r"\breleaseNow\s*\(\s*\)", src), (
        "缺少立即放行入口 releaseNow() —— 用户手速快于节流窗口时会白等 900ms"
    )
    # 必须有窗口令牌自增
    assert re.search(r"requestId\s*\+\+", src), (
        "节流窗口缺少令牌自增：postDelayed 与手动放行会互相覆盖（竞态）"
    )
    # 定时复位必须带令牌校验
    assert re.search(
        r"postDelayed\s*\(\s*\{[^}]*requestId\s*==\s*\w+[^}]*\}",
        src, re.DOTALL,
    ), (
        "postDelayed 的复位体里缺少 requestId 相等校验 —— "
        "过期的定时复位会误放行后续条码，造成同一件货重复入库"
    )


def test_t3_non_continuous_keeps_legacy_behavior():
    """非连续模式：调用方负责关弹窗，弹窗自身不得强制关。"""
    src = _no_comments(_read(SCANNER))
    # 弹窗内部不得自己调 onDismiss 来结束扫描（只允许权限不足/完成按钮两处）
    dismiss_calls = re.findall(r"\bonDismiss\s*\(\)", src)
    assert len(dismiss_calls) <= 2, (
        f"弹窗内 onDismiss() 调用点过多（{len(dismiss_calls)} 处）—— "
        "连续模式下必须由用户点完成/关闭来退出，不能在扫码回调里自动关"
    )
    # 关键：扫码成功回调路径上不得出现 onDismiss()
    on_scan_region = re.search(
        r"compareAndSet\s*\(\s*false\s*,\s*true\s*\)\s*\)\s*\{(?P<body>.{0,600})",
        src, re.DOTALL,
    )
    assert on_scan_region, "未找到 compareAndSet 抢占后的回调体"
    body = on_scan_region.group("body")
    assert "onDismiss()" not in body, (
        "扫码成功回调里仍然调用 onDismiss() —— 这正是要移除的旧行为（扫一码关一次相机）"
    )


# ---------------------------------------------------------------------------
# T4. 节流窗口取值合理
# ---------------------------------------------------------------------------
def test_t4_throttle_window_is_sane():
    src = _read(SCANNER)
    m = re.search(r"CONTINUOUS_SCAN_THROTTLE_MS\s*=\s*(\d+)L?", src)
    assert m, "缺少 CONTINUOUS_SCAN_THROTTLE_MS 节流窗口常量"
    ms = int(m.group(1))
    assert 300 < ms < 2000, (
        f"节流窗口 {ms}ms 取值不合理："
        "≤300ms 挡不住同一码在 1~3 帧内的反复命中（30fps 约 33~100ms），"
        "≥2000ms 会拖慢人手换件的节奏"
    )
    # 必须在主线程 Handler 上延迟复位（分析线程不可直接改 UI 相关状态）
    assert re.search(r"postDelayed\s*\(", src), "节流复位必须用 postDelayed 延迟执行"
    assert "Looper.getMainLooper()" in src, "节流复位应切回主线程 Handler"


# ---------------------------------------------------------------------------
# T5 + T6. 不得破坏 BUG-2026-08-09-001 / H4 的既有保护
# ---------------------------------------------------------------------------
def test_t5_only_arm_on_non_empty_barcode():
    src = _no_comments(_read(SCANNER))
    # 只在 rawValue 非空时抢占
    assert re.search(r"rawValue\.isNullOrEmpty\s*\(\s*\)", src), (
        "缺少 rawValue 非空判断 —— BUG-2026-08-09-001：ML Kit 对未识别到条码的帧"
        "同样回调成功（barcodes 为空），若无条件置位，相机首帧（几乎必为空结果）"
        "会永久关闭后续所有帧的分析，表现为「扫码无法识别条码」"
    )
    m = re.search(
        r"if\s*\(\s*!rawValue\.isNullOrEmpty\s*\(\s*\)\s*&&\s*scannedFlag\.compareAndSet",
        src,
    )
    assert m, "置位条件必须同时满足「条码非空」与「compareAndSet 抢占」"


def test_t6_uses_atomic_compare_and_set():
    src = _no_comments(_read(SCANNER))
    assert "AtomicBoolean" in src, "scannedFlag 必须是 AtomicBoolean（相机分析在子线程）"
    assert re.search(r"compareAndSet\s*\(\s*false\s*,\s*true\s*\)", src), (
        "必须用 compareAndSet 原子抢占，不得退化成非原子的 if (!flag) { flag = true }"
    )
    # 负面：不得出现非原子写法
    assert not re.search(r"if\s*\(\s*!\s*scannedFlag\.get\s*\(\s*\)\s*\)\s*\{\s*scannedFlag\.set\s*\(\s*true\s*\)", src), (
        "检测到非原子置位写法，多帧并发时会重复回调"
    )


# ---------------------------------------------------------------------------
# T7. UI 反馈：计数字样 + 完成/继续扫
# ---------------------------------------------------------------------------
def test_t7_ui_feedback_present():
    src = _read(SCANNER)
    assert re.search(r"已扫\s*\$?\{?\s*scannedCount", src) or re.search(
        r'"已扫\s*\$scannedCount', src
    ), "顶部缺少「已扫 N 件」计数回显"
    assert "完成" in src, "缺少「完成」按钮（连续模式下用户需要明确的退出动作）"
    assert "继续扫" in src, "缺少「继续扫」手动放行按钮（手速快于节流窗口时不用干等）"
    # 回显刚扫到的条码：确认这一件确实进去了，否则用户会怀疑漏扫而重复扫
    assert re.search(r"lastScannedCode", src), "缺少 lastScannedCode 回显"
    # 最后一条码为空时不应渲染"已加入：null"
    assert re.search(r"lastScannedCode\s*!=\s*null", src), (
        "回显区必须判空，否则首次打开会渲染「已加入：null」"
    )


# ---------------------------------------------------------------------------
# T8. 三种场景接线
# ---------------------------------------------------------------------------
def test_t8_wiring_for_all_scan_scenarios():
    base = _no_comments(_read(SCAN_BASE))
    opening = _no_comments(_read(OPENING))
    screens = _no_comments(_read(SCAN_SCREENS))

    # 入库/出库/盘点共用 ScanScreenBase → 应启用连续
    assert re.search(r"continuous\s*=\s*true", base), (
        "ScanScreenBase（入库/出库/盘点共用）未启用连续扫描"
    )
    assert re.search(r"continuous\s*=\s*true", opening), "期初库存页未启用连续扫描"

    # 查库存是"扫一个看一个" → 必须显式关闭
    assert re.search(r"continuous\s*=\s*false", screens), (
        "查库存页应显式 continuous = false —— 该场景是扫码查单个物料，"
        "连续模式会让弹窗不退出，用户看不到查询结果"
    )

    # 查库存页的 onBarcodeScanned 仍需关闭弹窗（否则查询结果不可见）
    m = re.search(
        r"continuous\s*=\s*false\s*,\s*onBarcodeScanned\s*=\s*\{\s*barcode\s*->\s*\n?\s*showScannerDialog\s*=\s*false",
        screens,
    )
    assert m, "查库存页在 continuous = false 时仍应关闭弹窗以展示查询结果"


# ---------------------------------------------------------------------------
# T9. 计数职责与复位
# ---------------------------------------------------------------------------
def test_t9_count_owned_by_caller_and_reset_on_open():
    base = _no_comments(_read(SCAN_BASE))
    opening = _no_comments(_read(OPENING))

    for name, src in (("ScanScreenBase", base), ("OpeningStockScreen", opening)):
        # 计数变量由调用方持有
        assert re.search(r"continuousScanCount\s+by\s+remember", src), (
            f"{name} 未在调用方持有 continuousScanCount"
        )
        # 扫中时累加
        assert re.search(r"continuousScanCount\s*\+=\s*1", src), (
            f"{name} 扫码回调未累加计数"
        )
        # 打开相机时复位（否则上一轮的 N 串到本轮）
        m = re.search(
            r"continuousScanCount\s*=\s*0[^}]{0,200}showCameraScanner\s*=\s*true"
            r"|showCameraScanner\s*=\s*true",
            src, re.DOTALL,
        )
        assert m, f"{name} 未在打开相机时复位计数"
        reset_region = re.search(
            r"continuousScanCount\s*=\s*0(?P<gap>.{0,300}?)showCameraScanner\s*=\s*true",
            src, re.DOTALL,
        )
        assert reset_region, (
            f"{name} 的计数复位必须与「打开相机」在同一处，"
            "否则上一轮的已扫数会串到本轮，与清单行数对不上"
        )

    # 弹窗不得自己维护计数
    scanner = _no_comments(_read(SCANNER))
    assert not re.search(r"scannedCount\s*\+=", scanner), (
        "计数必须由调用方持有（弹窗只负责报告「扫到了」）—— "
        "弹窗内自增会让「已扫 N 件」与清单行数脱钩"
    )
