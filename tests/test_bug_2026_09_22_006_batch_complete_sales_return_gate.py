# -*- coding: utf-8 -*-
"""BUG-2026-09-22-006 回归：批量完成销售退货入库单必须补防超退闸。

根因：单据版 complete_in_order 在 P1-5 已挂 sales_return_remaining_check
真闸（加锁后整单校验，有来源明细逐行 退货量 ≤ 原销售订单行 shipped_quantity
− 已退量聚合），但 batch_complete_in_order 的校验序列只对采购入库挂了
validate_purchase_in_order_source / validate_purchase_receive_quantity，
'销售退货入库' 漏配——草稿改大后经批量完成即超量退货入库：库存凭空
虚增，且原销售单的退货量被穿透（后续合法退货全被拒），账实分叉。

覆盖：
- T1 超退草稿在批量完成中被跳过（保持 pending、msg 带"可退数量"），
     同批合法草稿正常完成且库存只增合法单；
- T2 无来源行不受闸门误伤（与单据版语义一致）。
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
os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")

import datetime  # noqa: E402

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import Customer, InOrder, InOrderItem, Material, MaterialCategory, \
    SalesOrder, SalesOrderItem, Unit, User, Warehouse, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base():
    """仓库（默认）+ 客户 + 物料。仓库置默认以便批量完成取默认仓。"""
    db.session.add(User(username="warehouse", password_hash=generate_password_hash("admin"),
                        role="warehouse", must_change_password=False))
    wh = Warehouse(name="退货入库仓", code="WSRI", status="active", is_default=True)
    customer = Customer(code="C01", name="退货客户")
    unit = Unit(code="GE", name="个")
    cat = MaterialCategory(code="WJ", name="五金")
    db.session.add_all([wh, customer, unit, cat])
    db.session.flush()
    material = Material(code="M-SRBC", name="销售退货批量测试件", spec="T1", stock=0,
                        min_stock=0, price=2.0, unit_id=unit.id, category_id=cat.id)
    db.session.add(material)
    db.session.commit()
    return {"wh": wh, "customer": customer, "material": material}


def _make_sales_order(material, warehouse, quantity, shipped):
    """已发货销售订单一行，返回 (sales_order_id, sales_order_item_id)。"""
    order = SalesOrder(order_no="SO-SRBC-1", customer_id=1,
                       warehouse=warehouse.name, warehouse_id=warehouse.id,
                       status="confirmed", shipment_status="shipped")
    db.session.add(order)
    db.session.flush()
    si = SalesOrderItem(sales_order_id=order.id, material_id=material.id,
                        quantity=quantity, shipped_quantity=shipped, price=2.0)
    db.session.add(si)
    db.session.commit()
    return order.id, si.id


def _make_return_draft(order_no, material, warehouse, customer_id, so_id, si_id,
                       quantity):
    """DB 直造销售退货入库草稿（绕过保存校验，模拟改大后的草稿）。

    注：入库单无 customer 字符串字段（只有 customer_id），异常检测的
    「重复单据」按 同日+同物料+同 supplier_id 匹配——本用例两张草稿都不带
    供应商，天然不会误触重复告警。
    """
    order = InOrder(order_no=order_no, date=datetime.date.today(),
                    business_type="销售退货入库", customer_id=customer_id,
                    warehouse=warehouse.name, status="pending",
                    source_sales_order_id=so_id, purpose="客户退货")
    db.session.add(order)
    db.session.flush()
    db.session.add(InOrderItem(
        in_order_id=order.id, material_id=material.id,
        source_sales_order_item_id=si_id if si_id else None,
        quantity=quantity, price=2.0, amount=quantity * 2.0))
    db.session.commit()
    return order.id


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


def test_t1_batch_complete_blocks_over_return():
    """T1（核心）：超退草稿批量完成被跳过，同批合法草稿正常完成。

    场景：发货 10，草稿 A 退 6（合法）、草稿 B 退 11（直造绕过保存校验）。
    批量完成必须只放行 A；B 保持 pending 且 msg 指明可退数量，库存只增 6。
    """
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        so_id, si_id = _make_sales_order(seed["material"], seed["wh"], 10, 10)
        good_id = _make_return_draft("SR-BC-GOOD", seed["material"], seed["wh"],
                                     seed["customer"].id, so_id, si_id, 6)
        bad_id = _make_return_draft("SR-BC-BAD", seed["material"], seed["wh"],
                                    seed["customer"].id, so_id, si_id, 11)
        seed_data.update(material_id=seed["material"].id, good_id=good_id, bad_id=bad_id)

    client = _make_client()
    resp = client.post("/in_order/batch_complete",
                       json={"ids": [seed_data["good_id"], seed_data["bad_id"]]})
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
    data = resp.get_json()
    assert data["status"] == "success", data
    assert data["completed"] == 1, f"只应完成 1 张合法草稿，实际 {data}"
    assert "SR-BC-BAD" in data["msg"], f"超退草稿必须出现在跳过名单：{data['msg']}"
    assert "可退数量" in data["msg"], f"跳过原因必须是防超退闸：{data['msg']}"

    with app_module.app.app_context():
        good = db.session.get(InOrder, seed_data["good_id"])
        bad = db.session.get(InOrder, seed_data["bad_id"])
        assert good.status == "completed", "合法草稿必须正常完成"
        assert bad.status == "pending", "超退草稿必须保持待审核"
        stock = db.session.get(Material, seed_data["material_id"]).stock
        assert stock == 6, f"库存只应增合法单 6，实际 {stock}"


def test_t2_batch_complete_no_source_rows_not_blocked():
    """T2：无来源行不受闸门误伤（与单据版 sales_return_remaining_check
    语义一致：无来源行跳过校验，兼容历史退货单）。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        order = InOrder(order_no="SR-BC-NOSRC", date=datetime.date.today(),
                        business_type="销售退货入库", customer_id=seed["customer"].id,
                        warehouse=seed["wh"].name, status="pending",
                        purpose="客户退货")
        db.session.add(order)
        db.session.flush()
        db.session.add(InOrderItem(in_order_id=order.id,
                                   material_id=seed["material"].id,
                                   quantity=2, price=2.0, amount=4.0))
        db.session.commit()
        seed_data.update(order_id=order.id, material_id=seed["material"].id)

    client = _make_client()
    resp = client.post("/in_order/batch_complete",
                       json={"ids": [seed_data["order_id"]]})
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
    data = resp.get_json()
    assert data["status"] == "success", data
    assert data["completed"] == 1, f"无来源行草稿不应被防超退闸误伤：{data}"

    with app_module.app.app_context():
        order = db.session.get(InOrder, seed_data["order_id"])
        assert order.status == "completed", "无来源草稿应正常完成"
        stock = db.session.get(Material, seed_data["material_id"]).stock
        assert stock == 2, f"库存应增 2，实际 {stock}"
