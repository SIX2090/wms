# -*- coding: utf-8 -*-
"""BUG-2026-09-21-004 回归闸门：单据页表尾（合计行）/空态行必须与表头列数对齐。

背景：「表头加列、表尾忘改」是反复出现的同类事故（R6）——

  * sales_order_add / sales_order_edit：08 月行级合同/工程列上线时 thead 与
    行模板加了 contract_no / project_name，tfoot 合计行没加 → 表尾 15 列对
    表头 17 列，「备注/操作」两列下方悬空、合计行右端整体错位；
  * purchase_order_add：tfoot colspan=7 + 金额 + 2 空列 = 10 列对表头 12 列；
  * after_sale_out_add：tfoot colspan=9 + 金额 + 1 空列 = 11 列对表头 12 列；
  * in_order_detail：空态行 colspan 写死 22/20，未计入「其他入库」客供列
    （应为 pending 23 / 非 pending 21，其他入库再 +1）。

本测试是防复发闸门（纯静态解析，无 app context，符合 A12/R7）：
  T1/T2. 销售单两页：tfoot 的 data-column-key 序列必须与 thead 完全一致；
  T3/T4. 采购单/售后出库两页：tfoot 有效列宽（colspan 求和）必须等于表头 th 数；
  T5. in_order_detail 空态 colspan 表达式必须计入 business_type 条件列。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TPL_DIR = ROOT / "app" / "templates"

KEY_RE = re.compile(r'data-column-key="([a-zA-Z_]+)"')


def _block(src: str, tag: str) -> str:
    m = re.search(rf"<{tag}>.*?</{tag}>", src, re.S)
    assert m, f"未找到 <{tag}>"
    return m.group(0)


def _thead_keys(src: str) -> list[str]:
    return KEY_RE.findall(_block(src, "thead"))


def _tfoot_keys(src: str) -> list[str]:
    return KEY_RE.findall(_block(src, "tfoot"))


def _thead_th_count(src: str) -> int:
    return len(re.findall(r"<th[\s>]", _block(src, "thead")))


def _tfoot_effective_width(src: str) -> int:
    width = 0
    for td in re.findall(r"<td\b[^>]*>", _block(src, "tfoot")):
        m = re.search(r'colspan="(\d+)"', td)
        width += int(m.group(1)) if m else 1
    return width


def _read(name: str) -> str:
    return (TPL_DIR / name).read_text(encoding="utf-8")


def test_T1_sales_order_add_tfoot_matches_thead() -> None:
    src = _read("sales_order_add.html")
    assert _tfoot_keys(src) == _thead_keys(src), (
        f"销售单新增页表尾列与表头不一致：\n thead={_thead_keys(src)}\n tfoot={_tfoot_keys(src)}"
    )


def test_T2_sales_order_edit_tfoot_matches_thead() -> None:
    src = _read("sales_order_edit.html")
    assert _tfoot_keys(src) == _thead_keys(src), (
        f"销售单编辑页表尾列与表头不一致：\n thead={_thead_keys(src)}\n tfoot={_tfoot_keys(src)}"
    )


def test_T3_purchase_order_add_tfoot_width_matches_thead() -> None:
    src = _read("purchase_order_add.html")
    assert _tfoot_effective_width(src) == _thead_th_count(src), (
        f"采购单新增页表尾有效列宽({_tfoot_effective_width(src)}) != 表头列数({_thead_th_count(src)})"
    )


def test_T4_after_sale_out_add_tfoot_width_matches_thead() -> None:
    src = _read("after_sale_out_add.html")
    assert _tfoot_effective_width(src) == _thead_th_count(src), (
        f"售后出库新增页表尾有效列宽({_tfoot_effective_width(src)}) != 表头列数({_thead_th_count(src)})"
    )


def test_T5_in_order_detail_empty_state_colspan_covers_conditional_columns() -> None:
    src = _read("in_order_detail.html")
    m = re.search(r'class="empty-state"', src)
    assert m, "未找到空态行"
    line = src[src.rfind("<td", 0, m.start()):m.end()]
    assert "其他入库" in line, "空态 colspan 未计入「其他入库」客供条件列"
    assert "23" in line and "21" in line, (
        "空态 colspan 基准值应为 pending=23 / 非 pending=21（seq+chk+action+20 基列）"
    )
