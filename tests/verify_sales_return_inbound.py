# -*- coding: utf-8 -*-
"""P1-5 回归：销售退货入库单（business_type='销售退货入库'）。

根因：客户退回的货无处落账——走"其他入库"丢失与原销售单的关联
（退货率无法统计），或不入账（账实分叉的最大来源）。

方案（D2 决策：独立单据类型）：
- 复用 InOrder + business_type='销售退货入库' + customer_id 归属退货客户；
- InOrder.source_sales_order_id / InOrderItem.source_sales_order_item_id 关联原单；
- 防超退：退货量 ≤ 原行 shipped_quantity − 已退量聚合；
  **已退量是聚合查询不是状态字段**（不加 returned_quantity，防第四套口径，
  与 STOCK-TRUTH-P16 占用账同一决策哲学，见 INVENTORY_TRUTH.md §2.1.1）；
- 库存写入复用 complete_in_order 管道（add_stock + update_location_inventory
  成对），不新增总账写入口——三账一致由既有管道保证。
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

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (Customer, LocationInventory, Material, MaterialCategory,  # noqa: E402
                 SalesOrder, SalesOrderItem, StockTransaction, Unit, User,
                 Warehouse, db)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base():
    """仓库 + 客户 + 物料。"""
    db.session.add(User(username="warehouse", password_hash=generate_password_hash("admin"),
                        role="warehouse", must_change_password=False))
    wh = Warehouse(name="退货仓", code="WHR", status="active")
    customer = Customer(code="C01", name="退货客户")
    unit = Unit(code="GE", name="个")
    cat = MaterialCategory(code="WJ", name="五金")
    db.session.add_all([wh, customer, unit, cat])
    db.session.flush()
    material = Material(code="M-RETURN", name="退货测试件", spec="T1", stock=0,
                        min_stock=0, price=2.0, unit_id=unit.id, category_id=cat.id)
    db.session.add(material)
    db.session.commit()
    return {"wh": wh, "customer": customer, "material": material}


def _make_sales_order(material, warehouse, rows, status="confirmed"):
    """已发货的销售订单：rows = [(quantity, shipped), ...]（同一订单多行）。"""
    order = SalesOrder(
        order_no=f"SO-RET-{order_no_seq()}", customer_id=1,
        warehouse=warehouse.name, warehouse_id=warehouse.id,
        status=status, shipment_status="shipped" if all(
            s >= q for q, s in rows) else "partial",
    )
    db.session.add(order)
    db.session.flush()
    items = []
    for i, (quantity, shipped) in enumerate(rows, 1):
        si = SalesOrderItem(sales_order_id=order.id, material_id=material.id,
                            quantity=quantity, shipped_quantity=shipped, price=2.0)
        db.session.add(si)
        items.append(si)
    db.session.commit()
    return order, items


_seq = [0]


def order_no_seq():
    _seq[0] += 1
    return f"{_seq[0]:03d}"


def _return_payload(customer_id, warehouse_name, items, location=""):
    """items = [(material_code, quantity, source_sales_order_item_id|None)]"""
    return {
        "order_no": f"SR-RET-{order_no_seq()}",
        "business_type": "销售退货入库",
        "customer_id": customer_id,
        "date": "2026-09-11",
        "warehouse": warehouse_name,
        "location": location,
        "purpose": "客户退货",
        "items": [
            {"code": code, "quantity": qty, "price": 2.0,
             **({"source_sales_order_item_id": sid} if sid else {})}
            for code, qty, sid in items
        ],
    }


def _make_client(role="warehouse"):
    with app_module.app.app_context():
        if not User.query.filter_by(username=role).first():
            db.session.add(User(username=role, password_hash=generate_password_hash("admin"),
                                role=role, must_change_password=False))
            db.session.commit()
    client = app_module.app.test_client()
    client.post("/login", data={"username": role, "password": "admin"},
                content_type="application/x-www-form-urlencoded")
    return client


def test_validate_sales_return_quantity():
    """A9 同名：行级限额 = shipped_quantity − 已退聚合；超退拒绝。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _, items = _make_sales_order(seed["material"], seed["wh"], [(10, 10)])
        si = items[0]
        # 无已退：可退 10
        ok, _ = app_module.validate_sales_return_quantity(si, 10)
        assert ok
        ok, msg = app_module.validate_sales_return_quantity(si, 10.01)
        assert not ok and "可退数量 10.00" in msg
        # 造一张已完成退货单（回填 4），可退变 6
        order = app_module.InOrder(order_no="SR-SEED-1", date=__import__("datetime").date.today(),
                                   business_type="销售退货入库", customer_id=seed["customer"].id,
                                   warehouse=seed["wh"].name, status="completed",
                                   source_sales_order_id=si.sales_order_id)
        db.session.add(order)
        db.session.flush()
        db.session.add(app_module.InOrderItem(
            in_order_id=order.id, material_id=seed["material"].id,
            source_sales_order_item_id=si.id, quantity=4, price=2.0, amount=8.0))
        db.session.commit()
        ok, _ = app_module.validate_sales_return_quantity(si, 6)
        assert ok, "已退 4 后应可退 6"
        ok, msg = app_module.validate_sales_return_quantity(si, 6.01)
        assert not ok and "可退数量 6.00" in msg


def test_sales_return_remaining_check():
    """A9 同名：整单校验——多行独立计限、无来源行跳过。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _, items = _make_sales_order(seed["material"], seed["wh"], [(10, 10), (5, 5)])
        order = app_module.InOrder(order_no="SR-SEED-2", date=__import__("datetime").date.today(),
                                   business_type="销售退货入库", customer_id=seed["customer"].id,
                                   warehouse=seed["wh"].name, status="pending")
        db.session.add(order)
        db.session.flush()
        db.session.add_all([
            app_module.InOrderItem(in_order_id=order.id, material_id=seed["material"].id,
                                   source_sales_order_item_id=items[0].id,
                                   quantity=10, price=2.0, amount=20.0),
            app_module.InOrderItem(in_order_id=order.id, material_id=seed["material"].id,
                                   quantity=3, price=2.0, amount=6.0),  # 无来源
        ])
        db.session.commit()
        ok, msg = app_module.sales_return_remaining_check(order)
        assert ok, f"行1 退 10（=发货量）+ 无来源行 3 都应放行：{msg}"
        # 行1 超 1 → 整单拒绝
        order.items[0].quantity = 11
        db.session.commit()
        ok, msg = app_module.sales_return_remaining_check(order)
        assert not ok and "可退数量 10.00" in msg


def test_t1_three_ledgers_consistent():
    """T1（核心）：退货完成走 complete_in_order 管道 → 三账增量一致。

    开启库位管理（location_management_enabled='1'）以覆盖库位账写入口：
    关闭时库位账不写是设计行为（INVENTORY_TRUTH §2.1 ③→① 兜底口径）。
    """
    from app import SystemSetting
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        db.session.add(SystemSetting(key="location_management_enabled", value="1"))
        seed = _seed_base()
        _, items = _make_sales_order(seed["material"], seed["wh"], [(8, 8)])
        seed_data.update(material_id=seed["material"].id, wh_id=seed["wh"].id,
                         wh_name=seed["wh"].name, customer_id=seed["customer"].id,
                         si_id=items[0].id)

    client = _make_client()
    payload = _return_payload(seed_data["customer_id"], seed_data["wh_name"],
                              [("M-RETURN", 8, seed_data["si_id"])], location="RET-01")
    resp = client.post("/in_order/add", json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
    data = resp.get_json()
    assert data["status"] == "success", data
    order_id = data["id"]

    resp = client.post(f"/in_order/{order_id}/complete")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]

    with app_module.app.app_context():
        material = db.session.get(Material, seed_data["material_id"])
        stock_after = material.stock
        txn_qty = db.session.query(
            db.func.coalesce(db.func.sum(StockTransaction.quantity), 0)
        ).filter_by(material_id=material.id, transaction_type="in",
                    reference_type="in_order", reference_id=order_id).scalar()
        loc_qty = db.session.query(
            db.func.coalesce(db.func.sum(LocationInventory.quantity), 0)
        ).filter_by(material_id=material.id, warehouse_id=seed_data["wh_id"]).scalar()
        # 三账：总账、流水、库位账增量同为 +8
        assert stock_after == 8, f"总账应为 8，实际 {stock_after}"
        assert float(txn_qty) == 8, f"流水应为 8，实际 {txn_qty}"
        assert float(loc_qty) == 8, f"库位账应为 8，实际 {loc_qty}"
        order = db.session.get(app_module.InOrder, order_id)
        assert order.source_sales_order_id is not None, "单头必须聚合来源销售订单"
        assert order.source_sales_order_no.startswith("SO-RET-"), "冗余单号必须回填"


def test_t2_stock_txn_warehouse_id():
    """T2：退货流水 warehouse_id 必须正确归属（INVENTORY_TRUTH §3 铁律）。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _, items = _make_sales_order(seed["material"], seed["wh"], [(5, 5)])
        seed_data.update(material_id=seed["material"].id, wh_id=seed["wh"].id,
                         wh_name=seed["wh"].name, customer_id=seed["customer"].id,
                         si_id=items[0].id)

    client = _make_client()
    payload = _return_payload(seed_data["customer_id"], seed_data["wh_name"],
                              [("M-RETURN", 5, seed_data["si_id"])])
    resp = client.post("/in_order/add", json=payload)
    order_id = resp.get_json()["id"]
    client.post(f"/in_order/{order_id}/complete")

    with app_module.app.app_context():
        txn = StockTransaction.query.filter_by(
            material_id=seed_data["material_id"], reference_type="in_order",
            reference_id=order_id).first()
        assert txn is not None, "退货必须产生库存流水"
        assert txn.warehouse_id == seed_data["wh_id"], \
            f"流水必须归属退货仓库，实际 warehouse_id={txn.warehouse_id}"


def test_t3_over_return_rejected_on_complete():
    """T3：完成时超退 → 400 拒绝（加锁后真闸）。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _, items = _make_sales_order(seed["material"], seed["wh"], [(5, 5)])
        seed_data.update(wh_name=seed["wh"].name, customer_id=seed["customer"].id,
                         si_id=items[0].id)

    client = _make_client()
    payload = _return_payload(seed_data["customer_id"], seed_data["wh_name"],
                              [("M-RETURN", 6, seed_data["si_id"])])
    # 保存阶段就应拦截（validate_sales_return_quantity 行级校验）
    resp = client.post("/in_order/add", json=payload)
    data = resp.get_json()
    assert data["status"] == "error", "保存阶段必须拦超退"
    assert "可退数量 5.00" in data.get("msg", ""), data


def test_t4_multi_row_independent():
    """T4：一张销售订单多行退货，各行独立计限。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _, items = _make_sales_order(seed["material"], seed["wh"], [(10, 10), (4, 4)])
        order = app_module.InOrder(order_no="SR-SEED-3", date=__import__("datetime").date.today(),
                                   business_type="销售退货入库", customer_id=seed["customer"].id,
                                   warehouse=seed["wh"].name, status="pending")
        db.session.add(order)
        db.session.flush()
        db.session.add_all([
            app_module.InOrderItem(in_order_id=order.id, material_id=seed["material"].id,
                                   source_sales_order_item_id=items[0].id,
                                   quantity=10, price=2.0, amount=20.0),
            app_module.InOrderItem(in_order_id=order.id, material_id=seed["material"].id,
                                   source_sales_order_item_id=items[1].id,
                                   quantity=4, price=2.0, amount=8.0),
        ])
        db.session.commit()
        ok, msg = app_module.sales_return_remaining_check(order)
        assert ok, f"行1 退满 10、行2 退满 4 各自独立，应放行：{msg}"
        # 行2 超 1 → 只报行2
        order.items[1].quantity = 5
        db.session.commit()
        ok, msg = app_module.sales_return_remaining_check(order)
        assert not ok and "可退数量 4.00" in msg


def test_t5_no_ai_capability_registered():
    """T5：退货是高敏动作，AI 不参与——能力键台账不得含销售退货。"""
    ledger = (ROOT / "app" / "ai" / "policies.py").read_text(encoding="utf-8", errors="ignore")
    assert "销售退货" not in ledger, "AI 能力键不得覆盖销售退货（高敏动作人工执行）"


def test_t6_duplicate_complete_idempotent():
    """T6：重复提交完成 → 第二次被幂等锁拒绝（不重复加库存）。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _, items = _make_sales_order(seed["material"], seed["wh"], [(3, 3)])
        seed_data.update(material_id=seed["material"].id, wh_name=seed["wh"].name,
                         customer_id=seed["customer"].id, si_id=items[0].id)

    client = _make_client()
    payload = _return_payload(seed_data["customer_id"], seed_data["wh_name"],
                              [("M-RETURN", 3, seed_data["si_id"])])
    resp = client.post("/in_order/add", json=payload)
    order_id = resp.get_json()["id"]
    r1 = client.post(f"/in_order/{order_id}/complete")
    assert r1.status_code == 200, r1.get_data(as_text=True)[:200]
    r2 = client.post(f"/in_order/{order_id}/complete")
    data2 = r2.get_json()
    assert data2["status"] == "error", "第二次完成必须被拒"

    with app_module.app.app_context():
        stock = db.session.get(Material, seed_data["material_id"]).stock
        assert stock == 3, f"重复提交不得重复加库存，总账应为 3，实际 {stock}"


def test_t7_return_without_source_allowed():
    """T7：无来源行的历史退货允许保存（有来源才校验限额）——但必须选客户。"""
    seed_data = {}
    client = _make_client()

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        seed_data.update(customer_id=seed["customer"].id, wh_name=seed["wh"].name)

    payload = _return_payload(seed_data["customer_id"], seed_data["wh_name"],
                              [("M-RETURN", 2, None)])
    resp = client.post("/in_order/add", json=payload)
    data = resp.get_json()
    assert data["status"] == "success", data
    order_id = data["id"]

    with app_module.app.app_context():
        order = db.session.get(app_module.InOrder, order_id)
        assert order.business_type == "销售退货入库"
        assert order.source_sales_order_id is None, "无来源行不得猜归属"


def test_t8_customer_required():
    """T8：销售退货入库必须选择退货客户。"""
    seed_data = {}
    client = _make_client()

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        seed_data.update(wh_name=seed["wh"].name)

    payload = _return_payload(None, seed_data["wh_name"], [("M-RETURN", 2, None)])
    resp = client.post("/in_order/add", json=payload)
    data = resp.get_json()
    assert data["status"] == "error" and "退货客户" in data.get("msg", ""), data
