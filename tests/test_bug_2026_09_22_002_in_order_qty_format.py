# -*- coding: utf-8 -*-
"""BUG-2026-09-22-002 回归：采购入库「数量」字段两处体验缺陷。

用户反馈（采购入库新增/编辑草稿共用模板 ``in_order_add.html``）：

  1. 数量输入框是 ``<input type="number">``，浏览器自带上下箭头（spinner），
     点击/滚动极易误增减（误操作）；
  2. 数量为整数时被 ``toFixed(2)`` 补成两位小数——``1`` 显示成 ``1.00``。

修复（仅 ``in_order_add.html``，不动后端、不动单价/金额口径）：

  * 加 CSS 隐藏 ``.material-qty`` 的 spinner（webkit ``appearance:none`` +
    Firefox ``-moz-appearance: textfield``），保留 ``type="number"`` 的
    数字键盘与校验；
  * 新增 ``formatQtyTrim``：整数不补小数位（1→"1"），小数最多 2 位并去尾零
    （0.5→"0.5"、1.50→"1.5"、0.1+0.2→"0.3" 收敛浮点误差），替换数量字段的
    5 个 ``toFixed(2)`` 赋值点（两处 blur、加载草稿、粘贴导入、采购单下推）。

**刻意边界**：单价/金额是货币，仍恒保留 2 位小数（``toFixed(2)``），不得被误改。

测试用例（纯源码门禁，无需 app context，符合 A12/R7）：
  T1. formatQtyTrim 存在且实现为「toFixed(2) 收敛 + parseFloat 去尾零」；
  T2. 数量 blur 处理器全部改用 formatQtyTrim（不再 toFixed(2) 补小数）；
  T3. 数量字段所有 ``.value =`` 赋值不得再出现 toFixed(2)；
  T4. 去箭头 CSS 同时覆盖 webkit 与 Firefox；
  T5. 数量输入框仍为 type="number"（未退回 text，数字键盘/校验保留）；
  T6. 单价 blur 仍用 toFixed(2)（货币口径未被误伤）。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "app" / "templates" / "in_order_add.html"


def _src() -> str:
    return TPL.read_text(encoding="utf-8")


def _listener_bodies(src: str, selector: str, event: str) -> list[str]:
    """提取 ``querySelector('<selector>').addEventListener('<event>', function(){...})`` 的函数体。"""
    bodies = []
    for m in re.finditer(
        re.escape("querySelector('" + selector + "').addEventListener('" + event + "', function() {")
        + r"(.*?)\n    \}\);",
        src,
        re.S,
    ):
        bodies.append(m.group(1))
    return bodies


def test_T1_format_qty_trim_defined_and_trims():
    src = _src()
    m = re.search(r"function formatQtyTrim\(value\) \{(.*?)\n\}", src, re.S)
    assert m, "缺少 formatQtyTrim 函数"
    body = m.group(1)
    # 必须先 toFixed(2) 收敛浮点，再 parseFloat 去尾零（整数才不补 .00）
    assert "String(parseFloat(num.toFixed(2)))" in body, (
        "formatQtyTrim 实现应为 String(parseFloat(num.toFixed(2)))（整数去尾零）"
    )


def test_T2_qty_blur_uses_format_qty_trim():
    src = _src()
    bodies = _listener_bodies(src, ".material-qty", "blur")
    assert len(bodies) >= 2, f"应至少有两个数量 blur 处理器（主行/插入行），实际 {len(bodies)}"
    for i, b in enumerate(bodies):
        assert "formatQtyTrim(this.value)" in b, (
            f"第 {i+1} 个数量 blur 处理器未用 formatQtyTrim（整数仍会被补成两位小数）"
        )
        assert "toFixed(2)" not in b, f"第 {i+1} 个数量 blur 处理器仍残留 toFixed(2)"


def test_T3_no_qty_assignment_uses_tofixed2():
    src = _src()
    # 数量字段所有 .value 赋值（加载草稿/粘贴导入/采购单下推等）都不得再用 toFixed(2)
    offenders = re.findall(r"material-qty'\)\.value\s*=\s*[^;]*toFixed\(2\)", src)
    assert not offenders, f"数量字段仍有 toFixed(2) 赋值：{offenders}"
    # 且确实改用了 formatQtyTrim（回填路径覆盖）
    assert "querySelector('.material-qty').value = formatQtyTrim(" in src, (
        "数量字段回填未改用 formatQtyTrim"
    )


def test_T4_spinner_hidden_css_covers_webkit_and_firefox():
    src = _src()
    assert "material-qty::-webkit-inner-spin-button" in src, "缺 webkit 去箭头 CSS"
    assert "material-qty::-webkit-outer-spin-button" in src, "缺 webkit 去箭头 CSS（outer）"
    assert '-webkit-appearance: none' in src, "缺 -webkit-appearance: none"
    assert re.search(r"material-qty\[type=\"number\"\][\s\S]*?-moz-appearance:\s*textfield", src), (
        "缺 Firefox -moz-appearance: textfield（数量箭头在火狐仍会显示）"
    )


def test_T5_qty_input_stays_type_number():
    src = _src()
    qty_inputs = re.findall(r'<input[^>]*class="form-control material-qty"[^>]*>', src)
    assert qty_inputs, "未找到数量输入框"
    for tag in qty_inputs:
        assert 'type="number"' in tag, f"数量输入框不应退回 type=text（失去数字键盘）：{tag}"


def test_T6_price_blur_keeps_two_decimals():
    src = _src()
    bodies = _listener_bodies(src, ".material-price", "blur")
    assert bodies, "未找到单价 blur 处理器"
    for i, b in enumerate(bodies):
        assert "toFixed(2)" in b, (
            f"第 {i+1} 个单价 blur 处理器被误改——货币口径必须恒保留 2 位小数"
        )
