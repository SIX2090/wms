# -*- coding: utf-8 -*-
"""F3.9 仓库删除 blocker：ID 匹配 + stock_transaction.warehouse_id 补检（审计 §3.4）。

根因：_warehouse_delete_blockers 全部按仓库名/编码字符串匹配——
  1. 漏检 stock_transaction.warehouse_id（有流水的仓库可被删，历史报表悬空）；
  2. LocationInventory.warehouse_id 外键存在却没走 ID 判据；
  3. 名称与编码撞车的两个仓库（A.name == B.code）在字符串口径下互误伤。

修复：有外键的表一律 ID 精确匹配；历史未归属行（warehouse_id IS NULL）
用 location 字符串兜底；字符串列单据保持全等匹配。

用例：
  T1. 有归属流水（warehouse_id == id）→ 阻断含「库存流水」
  T2. 历史未归属流水（warehouse_id NULL + location=仓库名）→ 阻断含「历史未归属」
  T3. 归属库位库存（warehouse_id == id）→ 阻断含「库位库存」
  T4. 名称/编码撞车：B 的销售订单（warehouse_id=B.id）不误伤 A（A.name == B.code）
  T5. 名称/编码撞车：B 的归属流水不误伤 A
  T6. 空名称空编码仓库：ID 检查仍然生效（不再提前 return []）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    db, Customer, LocationInventory, Material, SalesOrder, StockTransaction,
    Warehouse, _warehouse_delete_blockers,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


import pytest  # noqa: E402


@pytest.fixture()
def app_ctx():
    with app_module.app.app_context():
        yield


def _mk_warehouse(code, name):
    wh = Warehouse(code=code, name=name)
    db.session.add(wh)
    db.session.flush()
    return wh


def _mk_material(code="M-F39"):
    m = Material(code=code, name="F3.9物料")
    db.session.add(m)
    db.session.flush()
    return m


def _labels(blockers):
    return [label for label, _count in blockers]


def test_t1_owned_stock_transaction_blocks(app_ctx):
    _reset_db()
    wh = _mk_warehouse("W1", "材料仓")
    m = _mk_material()
    db.session.add(StockTransaction(
        material_id=m.id, transaction_type="in", quantity=1,
        location="材料仓", warehouse_id=wh.id))
    db.session.commit()
    assert "库存流水" in _labels(_warehouse_delete_blockers(wh))


def test_t2_legacy_unowned_transaction_blocks(app_ctx):
    _reset_db()
    wh = _mk_warehouse("W1", "材料仓")
    m = _mk_material()
    db.session.add(StockTransaction(
        material_id=m.id, transaction_type="in", quantity=1,
        location="材料仓", warehouse_id=None))
    db.session.commit()
    assert "库存流水(历史未归属)" in _labels(_warehouse_delete_blockers(wh))


def test_t3_owned_location_inventory_blocks(app_ctx):
    _reset_db()
    wh = _mk_warehouse("W1", "材料仓")
    m = _mk_material()
    db.session.add(LocationInventory(
        material_id=m.id, warehouse_id=wh.id, location="A-01", quantity=5))
    db.session.commit()
    assert "库位库存" in _labels(_warehouse_delete_blockers(wh))


def test_t4_name_code_collision_no_friendly_fire_sales(app_ctx):
    """A.name == B.code：B 的 ID 归属单据不得阻断 A 的删除。"""
    _reset_db()
    a = _mk_warehouse("WA", "ZC")   # A 的名称 == B 的编码
    b = _mk_warehouse("ZC", "主仓")
    c = Customer(code="C1", name="客户1")
    db.session.add(c)
    db.session.flush()
    db.session.add(SalesOrder(order_no="SO-F39-1", customer_id=c.id,
                              warehouse="主仓", warehouse_id=b.id))
    db.session.commit()
    assert _warehouse_delete_blockers(a) == []
    assert "销售订单" in _labels(_warehouse_delete_blockers(b))


def test_t5_name_code_collision_no_friendly_fire_txn(app_ctx):
    _reset_db()
    a = _mk_warehouse("WA", "ZC")
    b = _mk_warehouse("ZC", "主仓")
    m = _mk_material()
    db.session.add(StockTransaction(
        material_id=m.id, transaction_type="in", quantity=1,
        location="主仓", warehouse_id=b.id))
    db.session.commit()
    assert _warehouse_delete_blockers(a) == []


def test_t6_blank_name_code_still_checks_id(app_ctx):
    """名称/编码皆空的仓库：ID 检查不得被跳过（修复前提前 return []）。"""
    _reset_db()
    wh = _mk_warehouse("W9", "临时仓")
    m = _mk_material()
    db.session.add(StockTransaction(
        material_id=m.id, transaction_type="in", quantity=1,
        location="", warehouse_id=wh.id))
    db.session.commit()
    wh.name, wh.code = "", ""  # 构造极端：名称编码皆空（绕过 unique 仅内存态）
    assert "库存流水" in _labels(_warehouse_delete_blockers(wh))
