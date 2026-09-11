# -*- coding: utf-8 -*-
"""P2-9 采购在途口径收口回归。

根因：在途（quantity − received_quantity）聚合散落在 ≥6 处消费点，且截断
层次不一致——todo_summary 完全不截断（超收负数直接进汇总）、补货候选/
缺料分析"聚合后截断"（一行超收 -5 + 一行未收 +10 被算成 5）、供应商
履约行级截断。同数据不同值，补货建议置信度受损。

修复：统一入口 get_purchase_in_transit / get_purchase_in_transit_by_material
（行级 max(0)，case 表达式跨库），全部消费点改走统一函数。

数值 diff 验证（替换前后同数据集）：
- 有超收数据的物料新旧有差异（差异 = 超收负数被修正），人工判真通过；
- 无超收数据的物料新旧完全相等（行为不变）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (Material, PurchaseOrder, PurchaseOrderItem, Supplier,  # noqa: E402
                 Unit, User, Warehouse, db)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_po(order_no, supplier, status, rows):
    """rows: [(material, quantity, received_quantity), ...]"""
    order = PurchaseOrder(order_no=order_no, supplier_id=supplier.id, status=status)
    db.session.add(order)
    db.session.flush()
    for material, qty, rec in rows:
        db.session.add(PurchaseOrderItem(
            purchase_order_id=order.id, material_id=material.id,
            quantity=qty, received_quantity=rec, price=1, amount=qty))
    return order


@pytest.fixture(scope="module")
def seeded():
    """种子：覆盖 pending/partial/completed/closed × 正常/超收/NULL received。"""
    with app_module.app.app_context():
        _reset_db()
        db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                            role="admin", must_change_password=False))
        db.session.add(Warehouse(name="主仓", code="WHA", status="active", is_default=True))
        unit = Unit(code="GE", name="个")
        s1 = Supplier(code="S001", name="供应商一")
        s2 = Supplier(code="S002", name="供应商二")
        db.session.add_all([unit, s1, s2])
        db.session.flush()
        mats = {key: Material(code=f"TRANS-{key}", name=f"物料{key}", stock=0, unit_id=unit.id)
                for key in ("A", "B", "C", "D")}
        db.session.add_all(mats.values())
        db.session.flush()

        _make_po("PO-T1", s1, "pending",   [(mats["A"], 100, 0)])
        _make_po("PO-T2", s1, "partial",   [(mats["A"], 50, 80)])    # 超收行：行级差 -30
        _make_po("PO-T3", s1, "completed", [(mats["B"], 60, 50)])    # completed 尾差 +10
        _make_po("PO-T4", s2, "pending",   [(mats["B"], 200, 0)])
        _make_po("PO-T5", s2, "closed",    [(mats["C"], 500, 0)])    # closed 排除
        _make_po("PO-T6", s1, "partial",
                 [(mats["D"], 100, 30), (mats["D"], 40, 40)])        # +70 / 0
        db.session.commit()

        # NULL received（历史数据防御）：ORM default=0 挡 None，须 raw SQL
        db.session.add(PurchaseOrderItem(
            purchase_order_id=db.session.query(PurchaseOrder).filter_by(order_no="PO-T6").first().id,
            material_id=mats["D"].id, quantity=20, received_quantity=0, price=1, amount=20))
        db.session.commit()
        db.session.execute(db.text(
            "UPDATE purchase_order_item SET received_quantity = NULL "
            "WHERE quantity = 20 AND material_id = :mid"), {"mid": mats["D"].id})
        db.session.commit()

        yield {
            "s1": s1, "s2": s2, "mats": mats,
            "all_ids": [m.id for m in mats.values()],
        }


def test_get_purchase_in_transit(seeded):
    """A9-T1 核心口径：pending/partial 计入、completed/closed 排除、行级 max(0)。"""
    mats = seeded["mats"]
    # A 物料：pending +100 与 partial 超收行（-30 → 行级 0）= 100
    assert app_module.get_purchase_in_transit(material_id=mats["A"].id) == 100.0
    # C 物料：仅 closed 单 → 0（不在结果字典，get 缺省）
    assert app_module.get_purchase_in_transit_by_material([mats["C"].id]).get(mats["C"].id, 0) == 0.0
    # 全局（pending/partial）：A=100 + B(partial/partial 之外 completed 排除)=200 + D=90
    assert app_module.get_purchase_in_transit() == 390.0


def test_get_purchase_in_transit_row_level_no_negative_offset(seeded):
    """A9-T2 超收行不得以负数抵消其他行的在途（行级 vs 聚合后截断的分界）。"""
    mats = seeded["mats"]
    # 旧"聚合后截断"口径会把 A 算成 max(100-30, 0)=70；行级口径应为 100
    assert app_module.get_purchase_in_transit(material_id=mats["A"].id) == 100.0
    # D 物料：+70 / 0 / -15(超收) / +20(NULL received) → 旧 75，行级 90
    assert app_module.get_purchase_in_transit(material_id=mats["D"].id) == 90.0


def test_get_purchase_in_transit_null_received_defense(seeded):
    """A9-T3 NULL received 行按 0 已收处理（coalesce），不得丢行。"""
    mats = seeded["mats"]
    # D 的 NULL 行 qty=20 → 计入在途 20（旧 SQL sum 忽略 NULL 行）
    by_material = app_module.get_purchase_in_transit_by_material([mats["D"].id])
    assert by_material[mats["D"].id] == 90.0


def test_get_purchase_in_transit_filters(seeded):
    """A9-T4 material/supplier 过滤与仓库无关性（在途是单据口径非库存口径）。"""
    s1, s2, mats = seeded["s1"], seeded["s2"], seeded["mats"]
    assert app_module.get_purchase_in_transit(supplier_id=s1.id) == 190.0   # A100+D90
    assert app_module.get_purchase_in_transit(supplier_id=s2.id) == 200.0   # B200（closed 排除）
    assert app_module.get_purchase_in_transit(supplier_id=s1.id, material_id=mats["A"].id) == 100.0
    assert app_module.get_purchase_in_transit(material_id=999999) == 0.0


def test_get_purchase_in_transit_statuses_semantics(seeded):
    """A9-T5 默认口径排除 completed；显式含 completed 时尾差计入（档案卡语义）。"""
    s1 = seeded["s1"]
    default_value = app_module.get_purchase_in_transit(supplier_id=s1.id)
    with_completed = app_module.get_purchase_in_transit(
        supplier_id=s1.id, statuses=("pending", "partial", "completed"))
    assert default_value == 190.0
    assert with_completed == 200.0  # P3 completed 尾差 +10


def test_get_purchase_in_transit_by_material(seeded):
    """A9-T6 批量版：与单量版口径一致、空列表返回 {}、缺键物料不出现。"""
    all_ids = seeded["all_ids"]
    by_material = app_module.get_purchase_in_transit_by_material(all_ids)
    assert app_module.get_purchase_in_transit_by_material([]) == {}
    for mid in all_ids:
        single = app_module.get_purchase_in_transit(material_id=mid)
        assert by_material.get(mid, 0) == single, f"material {mid}: 批量 {by_material.get(mid, 0)} != 单量 {single}"
    assert set(by_material) == {seeded["mats"][k].id for k in ("A", "B", "D")}  # C(closed) 无键


def test_todo_summary_remaining_qty_uses_unified_transit(seeded):
    """A9-T7 消费点接线：采购待办 remaining_qty 走统一口径（超收不进汇总）。"""
    summary = app_module.build_purchase_order_todo_summary()
    assert summary["remaining_qty"] == 390.0  # 行级口径；旧实现会算出 325


def test_replenishment_and_shortage_consumers(seeded):
    """A9-T8 消费点接线：补货候选/补货 open_qty/缺料分析均走统一口径。"""
    mats = seeded["mats"]
    # _ai_replenishment_open_qty（补货报告共用）
    on_order, _pending = app_module._ai_replenishment_open_qty(seeded["all_ids"])
    assert on_order.get(mats["A"].id, 0) == 100.0
    assert on_order.get(mats["D"].id, 0) == 90.0
    assert on_order.get(mats["C"].id, 0) == 0.0  # closed 单不计


def test_no_inline_in_transit_aggregation_left():
    """A9-T9 防再膨胀：app.py 不得再出现内联在途聚合（func.sum(quantity - received)）。

    采购执行表字段字典的行级 remaining 表达式（非聚合）不受限。
    """
    src = (APP_DIR / "app.py").read_text(encoding="utf-8", errors="ignore")
    assert "func.sum(PurchaseOrderItem.quantity - PurchaseOrderItem.received_quantity)" not in src
    # 统一函数存在且被主要消费点调用
    assert "def get_purchase_in_transit(" in src
    for caller in ("build_purchase_order_todo_summary", "_ai_stage4_shortage_report",
                   "_ai_purchase_replenishment_candidates", "_ai_replenishment_open_qty"):
        m = src.index(f"def {caller}(")
        nxt = src.find("\ndef ", m + 1)
        body = src[m:nxt if nxt > 0 else len(src)]
        assert "get_purchase_in_transit" in body, f"{caller} 未接线统一在途函数"
