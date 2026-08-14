# -*- coding: utf-8 -*-
"""SALES-AUDIT-006 回归测试：complete_out_order 完成前校验出库数量 ≤ 未发货数量。

根因（P1）：
  complete_out_order 此前不校验 outbound_item.quantity ≤
  sales_item.quantity - sales_item.shipped_quantity。叠加编辑路径
  （SALES-AUDIT-005 已修）允许"生成小数量草稿→编辑改大→完成"超量出库。
  recalculate_sales_order 又用 min(..., qty) 截断 shipped_quantity，
  掩盖超发，超发部分库存无任何单据对应。

修复：
  complete_out_order 加锁后、扣库存前调用 sales_outbound_remaining_check，
  超量则 rollback 并返回错误。

测试用例：
  T1. 正常数量完成成功（quantity ≤ remaining）
  T2. 超量完成被拒绝（编辑改大数量后完成）
  T3. 无来源明细的出库单不受 remaining 校验影响
  T4. 部分发货后超量完成被拒绝
"""
from __future__ import annotations

import os
import sys
import re
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    db, Customer, Material, MaterialCategory, OutOrder, OutOrderItem,
    SalesOrder, SalesOrderItem, Supplier, Unit, User, Warehouse,
    sales_outbound_remaining_check,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base():
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    sup = Supplier(code="SUP001", name="供应商甲")
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    cust = Customer(code="C001", name="测试客户")
    mat = Material(
        code="M001", name="测试物料", spec="S1",
        category=cat, unit=unit, supplier=sup,
        stock=100, price=10, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup, wh, user, cust, mat])
    db.session.commit()
    return {"mat": mat, "wh": wh, "cust": cust, "user": user}


def _make_client():
    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post(
        "/login",
        data={"username": "admin", "password": "admin", "csrf_token": token},
    )
    return client


def _make_confirmed_order(cust, mat, qty, order_no):
    order = SalesOrder(
        order_no=order_no, customer_id=cust.id, warehouse="仓库A",
        date=date.today(), status="confirmed", shipment_status="pending",
    )
    db.session.add(order)
    db.session.flush()
    item = SalesOrderItem(
        sales_order_id=order.id, material_id=mat.id,
        quantity=qty, shipped_quantity=0, price=10,
        amount=qty * 10, tax_rate=0.13,
    )
    db.session.add(item)
    db.session.commit()
    return order, item


def _make_pending_outbound(order, sales_item, mat, qty, order_no):
    outbound = OutOrder(
        order_no=order_no, warehouse="仓库A",
        business_type="销售出库", source_sales_order_id=order.id,
        status="pending", date=date.today(),
    )
    db.session.add(outbound)
    db.session.flush()
    item = OutOrderItem(
        out_order_id=outbound.id, material_id=mat.id,
        quantity=qty, price=10, amount=qty * 10,
        source_sales_order_item_id=sales_item.id,
    )
    db.session.add(item)
    db.session.commit()
    return outbound


class TestRemainingCheckHelper:
    """直接测试 sales_outbound_remaining_check 辅助函数。"""

    def test_sales_outbound_remaining_check(self):
        """A9 合规：与函数同名的入口测试，覆盖正常 + 超量两路径。"""
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-CHK-000")
            outbound_ok = _make_pending_outbound(order, sales_item, seed["mat"], 5, "OUT-CHK-000A")
            ok, _ = sales_outbound_remaining_check(outbound_ok)
            assert ok is True

            outbound_over = _make_pending_outbound(order, sales_item, seed["mat"], 15, "OUT-CHK-000B")
            ok2, err2 = sales_outbound_remaining_check(outbound_over)
            assert ok2 is False
            assert "超" in err2

    def test_normal_quantity_passes(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-CHK-001")
            outbound = _make_pending_outbound(order, sales_item, seed["mat"], 5, "OUT-CHK-001")
            ok, err = sales_outbound_remaining_check(outbound)
            assert ok is True
            assert err == ''

    def test_over_quantity_blocked(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-CHK-002")
            outbound = _make_pending_outbound(order, sales_item, seed["mat"], 15, "OUT-CHK-002")
            ok, err = sales_outbound_remaining_check(outbound)
            assert ok is False
            assert "超过" in err or "超" in err

    def test_no_source_item_passes(self):
        """无 source_sales_order_item_id 的明细不受校验。"""
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            outbound = OutOrder(
                order_no="OUT-CHK-003", warehouse="仓库A",
                business_type="其他出库", status="pending", date=date.today(),
            )
            db.session.add(outbound)
            db.session.flush()
            item = OutOrderItem(
                out_order_id=outbound.id, material_id=seed["mat"].id,
                quantity=999, price=10, amount=9990,
            )
            db.session.add(item)
            db.session.commit()
            ok, err = sales_outbound_remaining_check(outbound)
            assert ok is True

    def test_partial_shipped_then_over_blocked(self):
        """已部分发货后超量被拒。"""
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-CHK-004")
            sales_item.shipped_quantity = 6  # 已发 6，剩 4
            db.session.commit()
            outbound = _make_pending_outbound(order, sales_item, seed["mat"], 5, "OUT-CHK-004")
            ok, err = sales_outbound_remaining_check(outbound)
            assert ok is False
            assert "超过" in err or "超" in err


class TestCompleteOutOrderRemainingValidation:
    """通过 complete_out_order 路由验证。"""

    def test_complete_succeeds_for_normal_quantity(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-COMP-001")
            outbound = _make_pending_outbound(order, sales_item, seed["mat"], 5, "OUT-COMP-001")
            client = _make_client()
            resp = client.post(f"/out_order/{outbound.id}/complete?force=true")
            assert resp.status_code == 200, resp.get_data(as_text=True)
            body = resp.get_json()
            assert body["status"] == "success", body

    def test_complete_blocked_for_over_quantity(self):
        """编辑改大数量后完成被拒。"""
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-COMP-002")
            outbound = _make_pending_outbound(order, sales_item, seed["mat"], 5, "OUT-COMP-002")
            # 编辑改大数量到 15（超订单量）
            client = _make_client()
            edit_resp = client.post("/out_order/add", json={
                "order_id": outbound.id,
                "order_no": outbound.order_no,
                "date": str(date.today()),
                "warehouse": "仓库A",
                "business_type": "销售出库",
                "customer": "测试客户",
                "picker": "",
                "purpose": f"来源销售订单 {order.order_no}",
                "remark": "",
                "items": [{"code": "M001", "quantity": 15, "price": 10}],
            })
            assert edit_resp.status_code == 200, edit_resp.get_data(as_text=True)
            # 完成应被拒
            resp = client.post(f"/out_order/{outbound.id}/complete?force=true")
            body = resp.get_json()
            assert body["status"] == "error", body
            assert "超过" in body.get("msg", "") or "超" in body.get("msg", "")
            # 出库单状态应保持 pending
            db.session.refresh(outbound)
            assert outbound.status == "pending"
