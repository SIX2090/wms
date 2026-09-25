# -*- coding: utf-8 -*-
"""P1-8 防腐：INVENTORY_TRUTH.md 里的「函数 ↔ 行号」引用不许再烂掉。

背景：文档里的行号全线过期（deduct_stock_atomic 标 3464，实际 4510，
差 1000 行上下）——app.py 一路长胖，没人回头改文档。更离谱的一处连文件都
写错了：StockTransaction.warehouse_id 的列定义标着 app/app.py:6286，
实际在 app/models/inventory.py:73。

行号本身就是易腐信息，光修一次没用。本文件双向钉住：
  1. 代码侧：文档标的行号处，确实能找到那个符号（±2 行容错）；
  2. 文档侧：下面这份清单里的行号，文档里确实写着（防止只改代码清单、
     文档继续骗人）。

app.py 一改行数导致漂移 → 测试 1 红 → 顺手更新清单与文档即可。
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# (符号/文本片段, 文件, 行号) —— 与 INVENTORY_TRUTH.md 逐条对应
REFS = [
    ("def deduct_stock_atomic(", "app/app.py", 4510),
    ("def add_stock(", "app/app.py", 4578),
    ("def _apply_opening_stock_balance(", "app/app.py", 8030),
    ("def add_stock_transaction(", "app/app.py", 4852),
    ("def add_location_inventory_atomic(", "app/app.py", 4709),
    ("def deduct_location_inventory_atomic(", "app/app.py", 4794),
    ("def update_location_inventory(", "app/app.py", 4647),
    ("def backfill_stock_txn_warehouse_id(", "app/app.py", 27729),
    ("def _material_stock_unattributed(", "app/app.py", 5320),
    # 单仓库短路（文档 §3.3 (a)，在 get_warehouse_stock_quantities 内部）
    ("if Warehouse.query.count() == 1:", "app/app.py", 5137),
    # 列定义：注意不在 app.py，在模型文件里
    ("warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))",
     "app/models/inventory.py", 73),
]


def _window(rel: str, line: int, span: int = 2) -> str:
    lines = (ROOT / rel).read_text(encoding="utf-8").splitlines()
    start = max(0, line - 1 - span)
    end = min(len(lines), line + span)
    return "\n".join(lines[start:end])


@pytest.mark.parametrize("symbol,rel,line", REFS)
def test_code_still_matches_documented_line(symbol, rel, line):
    """文档标的行号处，必须还能找到那个符号。"""
    assert symbol in _window(rel, line), (
        f"{rel}:{line} 处找不到 {symbol!r}——app.py 行数漂移了，"
        f"请更新 INVENTORY_TRUTH.md 与本文件的 REFS 清单。"
    )


@pytest.mark.parametrize("symbol,rel,line", REFS)
def test_doc_mentions_the_same_line_number(symbol, rel, line):
    """文档里必须真的写着这个行号（防止只改清单、文档继续骗人）。"""
    doc = (ROOT / "INVENTORY_TRUTH.md").read_text(encoding="utf-8")
    assert f"{rel}:{line}" in doc, (
        f"INVENTORY_TRUTH.md 里没有 {rel}:{line}——代码清单与文档不同步。"
    )
