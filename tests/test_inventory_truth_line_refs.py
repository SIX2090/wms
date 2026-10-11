# -*- coding: utf-8 -*-
"""P1-8 防腐：INVENTORY_TRUTH.md 里的「函数 ↔ 行号」引用不许再烂掉。

背景：文档里的行号已烂过两轮（deduct_stock_atomic 标 3464 → 4741 → 实际
4751，一路漂移）——app.py 一路长胖，没人回头改文档。更离谱的一处连文件都
写错了：StockTransaction.warehouse_id 的列定义曾标着 app/app.py，
实际在 app/models/inventory.py。

行号本身就是易腐信息，光修一次没用。本文件用「符号名动态定位」双向钉住：

  1. 代码侧：每个引用的符号必须真实存在于代码中（找不到即红）；
  2. 文档侧：INVENTORY_TRUTH.md 里写的行号必须等于该符号**当前实际行号**
     （代码漂移 → 实际行号变化 → 文档旧行号对不上 → 红，提醒更新文档）。

与旧版的区别：REFS 不再自带行号清单——两份行号迟早分叉，行号的唯一
事实来源就是代码本身。符号在文件中多处出现时用 anchor（所属函数/类）
限定搜索起点消歧。
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# (符号文本, 文件, 锚点) —— 与 INVENTORY_TRUTH.md 逐条对应。
# 行号不在此维护；anchor 用于符号多处出现时限定搜索起点（锚点所在行之后）。
REFS = [
    ("def deduct_stock_atomic(", "app/app.py", None),
    ("def add_stock(", "app/app.py", None),
    ("def _apply_opening_stock_balance(", "app/app.py", None),
    ("def add_stock_transaction(", "app/app.py", None),
    ("def add_location_inventory_atomic(", "app/app.py", None),
    ("def deduct_location_inventory_atomic(", "app/app.py", None),
    ("def update_location_inventory(", "app/app.py", None),
    ("def backfill_stock_txn_warehouse_id(", "app/app.py", None),
    ("def _material_stock_unattributed(", "app/app.py", None),
    # 单仓库短路（文档 §3.3 (a)，在 get_warehouse_stock_quantities 内部）。
    # 该 if 在 app.py 出现 2 次（get_warehouse_stock_quantities 与
    # backfill_stock_txn_warehouse_id 各一），必须锚定到前者体内那次。
    ("if Warehouse.query.count() == 1:", "app/app.py",
     "def get_warehouse_stock_quantities("),
    # 列定义：注意不在 app.py，在模型文件里（锚定 StockTransaction 类）。
    ("warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))",
     "app/models/inventory.py", "class StockTransaction"),
]


def _locate(rel: str, needle: str, anchor: str | None = None) -> int:
    """返回 needle 在 rel 中首次出现的 1-based 行号；提供 anchor 时从锚点行之后开始找。"""
    lines = (ROOT / rel).read_text(encoding="utf-8").splitlines()
    start = 0
    if anchor is not None:
        for i, line in enumerate(lines):
            if anchor in line:
                start = i
                break
        else:
            raise AssertionError(f"{rel} 中找不到锚点 {anchor!r}")
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i + 1
    raise AssertionError(
        f"{rel} 中找不到 {needle!r}（锚点 {anchor!r} 之后）——"
        f"符号被改名/删除，请更新 INVENTORY_TRUTH.md 与本文件的 REFS 清单。"
    )


@pytest.mark.parametrize("needle,rel,anchor", REFS)
def test_symbol_locatable_in_code(needle, rel, anchor):
    """引用的符号必须真实存在（找不到即说明代码重构了，清单要更新）。"""
    _locate(rel, needle, anchor)


@pytest.mark.parametrize("needle,rel,anchor", REFS)
def test_doc_cites_current_line(needle, rel, anchor):
    """INVENTORY_TRUTH.md 里写的行号必须等于符号当前实际行号。"""
    actual = _locate(rel, needle, anchor)
    doc = (ROOT / "INVENTORY_TRUTH.md").read_text(encoding="utf-8")
    assert f"{rel}:{actual}" in doc, (
        f"INVENTORY_TRUTH.md 里没有 {rel}:{actual}——代码行数漂移了，"
        f"请把文档中的引用更新为当前实际行号。"
    )
