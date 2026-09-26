# -*- coding: utf-8 -*-
"""期初建账扫码数量合并语义 + 点行改数量 —— 静态契约测试（BUG-2026-09-16-010）。

需求背景（仓库库存管理专家评审 2026-09-16，用户拍板"先做 P0"）：

改造前两个硬伤
--------------------------------------------------------------------
1. `OpeningStockViewModel.addLine` 对同编码物料行做**覆盖**
   （`existing.copy(quantity = quantity)`）——连续扫描场景同一件货
   扫 N 次，数量恒为 manualQty（默认 1）。仓管扫 100 个轴承，提交
   数量是 1，"连续扫描"（AI-MOB-CONTINUOUS-SCAN-01）在期初场景
   名存实亡。
2. 已录入行**不能改数量**——行卡片只有删除按钮，数量错了只能删行
   重扫/重加。

改造后契约（任何一条被改坏都要红）
--------------------------------------------------------------------
T1. addLine 同编码合并必须是**累加**（existing.quantity + quantity），
    不得退回覆盖语义（copy(quantity = quantity) 出现在 addLine 内即红）。
T2. ViewModel 必须声明 updateLineQuantity（点行改数量的确切值入口），
    且其对数量做非负校验。
T3. OpeningStockScreen 的行卡片可点击（clickable）且点击打开编辑弹窗
    （editLineIndex 状态），弹窗确认接线 viewModel.updateLineQuantity。
T4. 连续扫描回调仍逐件加行（累加链路接线未断）。
    2026-09-26 修订（BUG-2026-09-26-007 / AI-APP-FIX-108）：扫码加行数量固定为 1.0，
    与手动弹窗的 manualQty **解耦**——原写法复用 manualQty，弹窗里输了 5 又取消时
    残留值会让接下来每扫一件加 5（静默错账）。故断言从「传入 manualQty」改为
    「固定传 1.0」，累加由 addLine 的 existing.quantity + quantity 保证。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"

VIEWMODEL = SRC / "ui" / "viewmodel" / "opening" / "OpeningStockViewModel.kt"
SCREEN = SRC / "ui" / "screens" / "OpeningStockScreen.kt"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _no_comments(src: str) -> str:
    """去掉 Kotlin 注释（与 verify_android_continuous_scan.py 同款加固）。"""
    no_block = re.sub(r"(?<!\S)/\*.*?\*/", "", src, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", no_block)


def _addline_body(src: str) -> str:
    """截取 addLine 函数体（到下一个 fun 声明为止）。"""
    m = re.search(r"fun\s+addLine\s*\(.*?(?=\n    fun\s|\n})", src, flags=re.DOTALL)
    assert m, "OpeningStockViewModel.addLine 声明丢失"
    return m.group(0)


# ---------------------------------------------------------------------------
# T1. 合并语义：累加，禁止覆盖
# ---------------------------------------------------------------------------
def test_t1_addline_merges_by_accumulation():
    src = _no_comments(_read(VIEWMODEL))
    body = _addline_body(src)
    assert "existing.quantity + quantity" in body, (
        "addLine 同编码合并必须累加（existing.quantity + quantity）——"
        "连续扫描同一件货扫 N 次应得 N，覆盖语义会让扫码数量恒为 1"
    )
    assert "copy(quantity = quantity)" not in body, (
        "addLine 退回覆盖语义（copy(quantity = quantity)）——"
        "扫码数量会被压成 manualQty，BUG-2026-09-16-010 复发"
    )


# ---------------------------------------------------------------------------
# T2. ViewModel 提供点行改数量入口
# ---------------------------------------------------------------------------
def test_t2_viewmodel_declares_update_line_quantity():
    src = _no_comments(_read(VIEWMODEL))
    assert re.search(r"fun\s+updateLineQuantity\s*\(\s*index\s*:\s*Int\s*,\s*quantity\s*:\s*Double\s*\)", src), (
        "OpeningStockViewModel 缺少 updateLineQuantity(index, quantity)——"
        "点行改数量没有数据层入口"
    )
    m = re.search(r"fun\s+updateLineQuantity\s*\(.*?(?=\n    fun\s|\n})", src, flags=re.DOTALL)
    body = m.group(0)
    assert "quantity < 0" in body, "updateLineQuantity 必须对负数数量做校验"


# ---------------------------------------------------------------------------
# T3. 行卡片可点击 + 编辑弹窗接线
# ---------------------------------------------------------------------------
def test_t3_screen_line_click_opens_edit_dialog():
    src = _no_comments(_read(SCREEN))
    assert "editLineIndex" in src, "Screen 缺少 editLineIndex 状态（点行编辑）"
    # 行卡片接收 onClick 且内部 clickable
    assert re.search(r"fun\s+OpeningStockLineCard\s*\([^)]*onClick\s*:\s*\(\)\s*->\s*Unit", src, flags=re.DOTALL), (
        "OpeningStockLineCard 缺少 onClick 参数"
    )
    card = re.search(r"fun\s+OpeningStockLineCard\s*\(.*?(?=\n@Composable|\nprivate fun|\Z)", src, flags=re.DOTALL)
    assert card and ".clickable(onClick = onClick)" in card.group(0), (
        "行卡片未接 clickable——点击无响应"
    )
    # 弹窗确认接线 ViewModel
    assert "viewModel.updateLineQuantity(" in src, (
        "编辑弹窗未接线 viewModel.updateLineQuantity"
    )


# ---------------------------------------------------------------------------
# T4. 连续扫描累加链路未断
# ---------------------------------------------------------------------------
def test_t4_continuous_scan_still_feeds_addline():
    src = _no_comments(_read(SCREEN))
    m = re.search(r"onBarcodeScanned\s*=\s*\{\s*barcode\s*->(.*?)\n        \}", src, flags=re.DOTALL)
    assert m, "ScannerDialog.onBarcodeScanned 回调丢失"
    cb = m.group(1)
    assert "viewModel.addLine(barcode" in cb, (
        "扫码回调不再调 addLine——连续扫描加行链路断了"
    )
    # BUG-2026-09-26-007：扫码通道固定逐件加 1，与 manualQty 解耦（防残留值错账）
    assert "viewModel.addLine(barcode, 1.0)" in cb, (
        "扫码加行必须固定为 1.0（逐件计数）——复用 manualQty 会让取消手动弹窗后的"
        "残留数量乘到每一次扫码上（静默错账）"
    )
