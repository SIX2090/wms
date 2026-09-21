# -*- coding: utf-8 -*-
"""BUG-2026-09-21-001 回归闸门：采购入库单新增页明细表「表头/表尾/行模板」列序必须一致。

事故经过：d0c53730（2026-09-19，入库明细新增批次号/有效期捕获，P0 可追溯性）
在 ``app/templates/in_order_add.html`` 的 ``<thead>`` 里把 ``batch_no`` /
``expiry_date`` 两个 ``<th>`` 各写了**两次**（数量后一对 + 当前库存后一对），
而两个行模板（``addNewRow`` / ``copyPreviousRow`` 的 ``innerHTML``）只在当前
库存后有一对，``<tfoot>`` 合计行又只在数量后有一对 —— 表头 18 列、表体 16 列、
表尾 17 列，三种列序互不一致。页面上批次号/有效期出现两次，其后所有列整体
错位（2026-09-21 用户截图实证：单位列下渲染出「批次」「年-月-日」）。

同时重复的 ``data-column-key`` 还会击穿 app.js 的字段设置/列宽/排序机制
（``ths.find(key)`` 只命中第一个表头），属同根因次生灾害。

本测试是防复发闸门（纯静态解析，无需 app context，符合 A12/R7）：

1. **表头不允许重复列键** —— 任何列键在 ``<thead>`` 出现两次立即变红；
2. **三处列序完全一致** —— ``<thead>`` / ``<tfoot>`` / 每个行模板的
   ``data-column-key`` 序列必须逐一相等（含顺序）。新增/删除/调整明细列时
   必须三处同改，否则本测试立即变红。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "app" / "templates" / "in_order_add.html"

KEY_RE = re.compile(r'data-column-key="([a-z_]+)"')


def _thead_keys(src: str) -> list[str]:
    m = re.search(r"<thead>.*?</thead>", src, re.S)
    assert m, "in_order_add.html 未找到 <thead>"
    return KEY_RE.findall(m.group(0))


def _tfoot_keys(src: str) -> list[str]:
    m = re.search(r"<tfoot>.*?</tfoot>", src, re.S)
    assert m, "in_order_add.html 未找到 <tfoot>"
    return KEY_RE.findall(m.group(0))


def _row_template_keys(src: str) -> list[list[str]]:
    """抽取行模板的列键序列：行模板是 JS 中 ``row.innerHTML = `...`;`` 的模板字符串，
    以含 ``data-column-key="row_no"`` 作为行模板判别（下拉框等其它 innerHTML 不算）。
    文件中现有两个行模板：addNewRow 与 copyPreviousRow，二者都必须与表头一致。"""
    tpls = re.findall(r"\.innerHTML = `(.*?)`;", src, re.S)
    rows = [KEY_RE.findall(t) for t in tpls if 'data-column-key="row_no"' in t]
    assert rows, "in_order_add.html 未找到任何含 row_no 列的行模板"
    return rows


def test_thead_has_no_duplicate_column_keys() -> None:
    keys = _thead_keys(TPL.read_text(encoding="utf-8"))
    dups = sorted({k for k in keys if keys.count(k) > 1})
    assert not dups, f"表头存在重复列键（BUG-2026-09-21-001 复发）: {dups}"


def test_header_footer_and_row_templates_share_same_column_order() -> None:
    src = TPL.read_text(encoding="utf-8")
    thead = _thead_keys(src)
    tfoot = _tfoot_keys(src)
    assert thead == tfoot, (
        "表头与表尾列序不一致：\n"
        f"  thead={thead}\n  tfoot={tfoot}"
    )
    for i, row in enumerate(_row_template_keys(src)):
        assert row == thead, (
            f"行模板#{i} 与表头列序不一致：\n"
            f"  row={row}\n  thead={thead}"
        )
