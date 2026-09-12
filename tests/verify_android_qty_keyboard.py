# -*- coding: utf-8 -*-
"""数量输入框键盘优化 —— 静态契约测试（AI-MOB-SCAN-UX-01）。

需求背景（用户原话：「wms手机端app怎么把它打造一个很好用很实用的app?」→「按你的思路来做」）

诊断结论
--------------------------------------------------------------------
全项目有 3 个数量输入框，**一个都没声明 keyboardOptions**：
  - `ScanScreenBase.kt`        扫码页数量框（入库/出库/盘点共用）
  - `OpeningStockScreen.kt`    期初库存手动添加弹窗
  - `AiScreens.kt`             识物盘点实盘数量

弹的是**全键盘**。用户输数量要先切到符号页，现场戴手套误触率高。

而这个 API 团队是知道的 —— `VoiceOutDraftDialogs.kt:290` 用了 `KeyboardType.Decimal`，
`LoginScreen.kt` 用了 `Uri`/`Password`。所以这是**遗漏**，不是能力缺口。

本测试锁定的契约
--------------------------------------------------------------------
T1. `ScanScreenBase` 数量框必须声明 `KeyboardType.Decimal`（允许小数点，
    WMS 存在 0.5kg 这类计量单位）与 `ImeAction.Done`。
T2. `ScanScreenBase` 数量框的 onDone 必须触发加行（`onManualAdd`），
    扫完码输完数量敲回车即完成，不用挪手点按钮。
T3. `OpeningStockScreen` / `AiScreens` 数量框必须声明数字键盘。
T4. `OpeningStockScreen` 的 onDone **不得**绑加行 —— 该弹窗"添加"按钮有
    `enabled = 编码非空` 前置校验，回车直接提交会绕过它。
T5. 相关 import 齐全（曾因漏 import 导致编译失败）。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"

SCAN_BASE = SRC / "ui" / "screens" / "ScanScreenBase.kt"
OPENING = SRC / "ui" / "screens" / "OpeningStockScreen.kt"
AI = SRC / "ui" / "screens" / "AiScreens.kt"

# 每个文件需要 import 的符号
KEYBOARD_IMPORTS = [
    "androidx.compose.foundation.text.KeyboardOptions",
    "androidx.compose.ui.text.input.KeyboardType",
    "androidx.compose.ui.text.input.ImeAction",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _no_comments(src: str) -> str:
    """去掉 Kotlin 注释，避免说明文本本身触发误判。

    块注释必须用 `(?<!\\S)/\\*` 约束 —— 否则会把字符串里的 `image/*"` 当成注释起点，
    一路匹配到后面某个 `*/`，**吞掉大半个文件**（本测试最初就踩了这个坑：
    AiScreens.kt 77KB 被削到 14KB，导致字段提取全部失败）。
    同一处理见 tests/verify_bug_2026_08_09_003_takepicture_permission_and_path.py。
    """
    no_block = re.sub(r"(?<!\S)/\*.*?\*/", "", src, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", no_block)


def _field_block(src: str, value_var: str) -> str:
    """取出以 `value = <var>,` 开头的那个 OutlinedTextField 调用文本。

    注意：不能用「匹配到第一个 \\n) 」这种偷懒写法 —— 字段体内部有大量嵌套括号
    （`label = { Text("数量") }`、`KeyboardOptions(...)`），会把块在中间截断。
    这里按括号配平扫描，取到真正闭合的那一个 `)` 为止。
    """
    m = re.search(rf"OutlinedTextField\s*\(\s*value\s*=\s*{re.escape(value_var)}\s*,", src)
    assert m, f"未找到 value = {value_var} 的 OutlinedTextField"
    start = m.start()
    # 从 OutlinedTextField 的左括号开始配平
    i = src.index("(", start)
    depth = 0
    for j in range(i, len(src)):
        ch = src[j]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return src[i : j + 1]
    raise AssertionError(f"value = {value_var} 的 OutlinedTextField 括号不配平")


# ---------------------------------------------------------------------------
# T1 + T2. 扫码页数量框（最高频）
# ---------------------------------------------------------------------------
def test_t1_scan_screen_qty_uses_decimal_keyboard():
    body = _field_block(_no_comments(_read(SCAN_BASE)), "manualQty")
    assert "KeyboardType.Decimal" in body, (
        "扫码页数量框未声明 KeyboardType.Decimal —— 会弹全键盘，"
        "输数量要先切符号页（WMS 有 0.5 这类小数计量，故用 Decimal 而非 Number）"
    )
    assert "ImeAction.Done" in body, "扫码页数量框未声明 ImeAction.Done"


def test_t2_scan_screen_qty_done_adds_line():
    body = _field_block(_no_comments(_read(SCAN_BASE)), "manualQty")
    assert re.search(r"onDone\s*=\s*\{\s*onManualAdd\s*\(\s*\)\s*\}", body), (
        "扫码页数量框的 onDone 必须触发 onManualAdd —— "
        "扫完码输完数量敲回车即完成，避免挪手去点「添加」按钮"
    )
    assert "KeyboardActions" in body, "声明了 onDone 但缺少 KeyboardActions 包装"


# ---------------------------------------------------------------------------
# T3. 另外两个数量框
# ---------------------------------------------------------------------------
def test_t3_other_qty_fields_use_numeric_keyboard():
    opening = _field_block(_no_comments(_read(OPENING)), "manualQty")
    assert "KeyboardType.Decimal" in opening, "期初库存数量框未声明数字键盘"

    ai = _field_block(_no_comments(_read(AI)), "countQty")
    assert "KeyboardType.Decimal" in ai, "识物盘点数量框未声明数字键盘"


# ---------------------------------------------------------------------------
# T4. 期初库存不得用 onDone 绕过校验
# ---------------------------------------------------------------------------
def test_t4_opening_stock_done_does_not_bypass_enabled_check():
    raw = _read(OPENING)
    body = _field_block(_no_comments(raw), "manualQty")
    assert "onDone" not in body, (
        "期初库存数量框不得绑 onDone 提交：该弹窗「添加」按钮有 "
        "enabled = manualCode.isNotBlank() 前置校验，回车提交会绕过它而落下空编码行"
    )
    # 同时确认那个前置校验确实还在（契约的前提）
    assert re.search(r"enabled\s*=\s*manualCode\.isNotBlank\s*\(\s*\)", _no_comments(raw)), (
        "期初库存「添加」按钮的 enabled = manualCode.isNotBlank() 校验被移除，"
        "此时 T4 的约束前提已变，需重新评估是否需要 onDone"
    )


# ---------------------------------------------------------------------------
# T5. import 完整性（曾因漏 import 编译失败）
# ---------------------------------------------------------------------------
def test_t5_required_imports_present():
    for path in (SCAN_BASE, OPENING, AI):
        src = _read(path)
        for imp in KEYBOARD_IMPORTS:
            assert f"import {imp}" in src, f"{path.name} 缺少 import {imp}"
        # 用到 KeyboardActions 就必须 import
        if "KeyboardActions" in _no_comments(src):
            assert "import androidx.compose.foundation.text.KeyboardActions" in src, (
                f"{path.name} 使用了 KeyboardActions 但未 import"
            )
