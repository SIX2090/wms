# -*- coding: utf-8 -*-
"""BUG-2026-09-22-003 回归：采购申请单物料编码输入框死引用 selectBtn 致一连串功能失效。

事故：``purchase_request_add.html`` 的 ``bindMaterialInput(row)`` 中部引用了
**本函数内从未声明、物料单元格 DOM 里也根本不存在**的 ``selectBtn``——物料格只有
``<input class="material-code">`` 和 ``.material-dropdown``，并没有供应商格那样的
``.supplier-select-btn`` 按钮。这段是从 ``bindSupplierInput``（那里有真正的
``const selectBtn``）误抄来的死代码。

非 strict 模式下读取未声明标识符 ``selectBtn`` 会抛 ``ReferenceError``，而
``addNewRow`` 的调用顺序是::

    bindMaterialInput(row)   // 在 selectBtn 处抛错
    bindSupplierInput(row)   // ↑ 抛错导致不执行 → 供应商补全失效
    fillRowData / updateRowAmount / renumberRows   // 全部不执行

且 ``bindMaterialInput`` 内部抛错点之后的两个绑定也随之失效：

  * ``dropdown.addEventListener('click', ...)`` → **下拉项鼠标点选失效**；
  * ``.quantity`` / ``.estimated-price`` 的 input 监听 → **预估金额不自动计算**。

用户可见症状：行号跳号（renumberRows 没跑）、下拉点不动、预估金额空、合计 ¥0.00。

修复：删除 ``bindMaterialInput`` 里这段死 ``selectBtn`` 代码块，让其后的绑定恢复。

测试用例（纯源码门禁，无需 app context，符合 A12/R7）：
  T1. bindMaterialInput 函数体内不再出现 selectBtn（死引用已除）；
  T2. bindMaterialInput 仍绑定物料下拉 click（.material-dropdown-item 点选）；
  T3. bindMaterialInput 仍绑定 .quantity / .estimated-price 的 input（金额联动）；
  T4. addNewRow 仍依次调用 bindMaterialInput → bindSupplierInput（顺序未乱）；
  T5. bindSupplierInput 自己的 const selectBtn（供应商▼按钮）未被误删。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "app" / "templates" / "purchase_request_add.html"


def _src() -> str:
    return TPL.read_text(encoding="utf-8")


def _fn_body(src: str, name: str, next_name: str) -> str:
    m = re.search(
        r"function " + re.escape(name) + r"\(.*?\{(.*?)\nfunction " + re.escape(next_name),
        src,
        re.S,
    )
    assert m, f"未找到函数 {name}"
    return m.group(1)


def test_T1_bind_material_has_no_selectbtn():
    body = _fn_body(_src(), "bindMaterialInput", "showDropdown")
    assert "selectBtn" not in body, (
        "bindMaterialInput 仍引用未声明的 selectBtn（会抛 ReferenceError，"
        "打断其后的下拉点选/金额联动/供应商绑定）"
    )


def test_T2_material_dropdown_click_still_bound():
    body = _fn_body(_src(), "bindMaterialInput", "showDropdown")
    assert "dropdown.addEventListener('click'" in body, "物料下拉 click 监听缺失（点选失效）"
    assert ".material-dropdown-item" in body, "物料下拉项选择逻辑缺失"


def test_T3_qty_price_amount_listeners_bound():
    body = _fn_body(_src(), "bindMaterialInput", "showDropdown")
    assert "row.querySelector('.quantity').addEventListener('input'" in body, "数量 input 监听缺失"
    assert "row.querySelector('.estimated-price').addEventListener('input'" in body, "单价 input 监听缺失"


def test_T4_add_new_row_calls_both_binders_in_order():
    src = _src()
    m = re.search(r"bindMaterialInput\(row\);(\s*)bindSupplierInput\(row\);", src)
    assert m, "addNewRow 应先 bindMaterialInput 再 bindSupplierInput（顺序被打乱或缺其一）"


def test_T5_supplier_selectbtn_intact():
    body = _fn_body(_src(), "bindSupplierInput", "showSupplierDropdown")
    assert "const selectBtn = row.querySelector('.supplier-select-btn')" in body, (
        "bindSupplierInput 自己的 selectBtn（供应商▼按钮）被误删——它才是合法的那个"
    )
