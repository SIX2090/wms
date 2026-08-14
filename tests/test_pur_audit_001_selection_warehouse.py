# -*- coding: utf-8 -*-
"""
PUR-AUDIT-001 回归测试：多采购订单选单生成采购入库时，
assert_warehouse_active 返回值被误用导致合法仓库被错误拒绝。

修复前：wh_err = assert_warehouse_active(warehouse) 将 (True, '') 元组赋给
wh_err，非空元组恒为真，选单下推功能完全不可用。
修复后：正确解构 (ok, msg)，仅在 not ok 时返回 msg。

测试用例：
  T1. 两张同供应商 pending 订单，选单下推成功生成一张 pending 入库草稿，
      明细来源完整，source_purchase_order_id=None（多来源）
  T2. 不存在仓库名返回业务错误
  T3. 停用仓库返回业务错误
  T4. 不同供应商明细被拒绝
  T5. 新草稿 source_purchase_order_id 为 None，各明细来源正确
"""
from __future__ import annotations

import os
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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
    db, Warehouse, User, Material, MaterialCategory, Unit, Supplier,
    PurchaseOrder, PurchaseOrderItem, InOrder, InOrderItem,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base():
    from werkzeug.security import generate_password_hash
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    sup1 = Supplier(code="SUP001", name="供应商甲")
    sup2 = Supplier(code="SUP002", name="供应商乙")
    wh_active = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    wh_inactive = Warehouse(code="WHB", name="仓库B", status="inactive")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    mat = Material(
        code="M001", name="测试物料", spec="S1",
        category=cat, unit=unit, supplier=sup1,
        stock=0, price=10, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup1, sup2, wh_active, wh_inactive, user, mat])
    db.session.commit()
    return {"mat": mat, "wh_active": wh_active, "wh_inactive": wh_inactive,
            "sup1": sup1, "sup2": sup2, "user": user}


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


def _make_purchase_order(sup, mat, qty, order_no, status="pending"):
    po = PurchaseOrder(order_no=order_no, supplier_id=sup.id, status=status)
    db.session.add(po)
    db.session.flush()
    po_item = PurchaseOrderItem(
        purchase_order_id=po.id,
        material_id=mat.id,
        quantity=qty,
        received_quantity=0,
        price=10,
        amount=qty * 10,
    )
    db.session.add(po_item)
    db.session.commit()
    db.session.refresh(po)
    return po, po_item


class TestSelectionWarehouseValid:
    """T1+T5：合法仓库选单下推成功，明细来源完整。"""

    def test_two_orders_same_supplier_selection_success(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po1, pi1 = _make_purchase_order(seed["sup1"], seed["mat"], 100, "PO-001")
            po2, pi2 = _make_purchase_order(seed["sup1"], seed["mat"], 50, "PO-002")
            client = _make_client()

            resp = client.post(
                "/purchase_order/create_in_order_from_selection",
                json={
                    "items": [
                        {"purchase_order_item_id": pi1.id, "quantity": 30},
                        {"purchase_order_item_id": pi2.id, "quantity": 20},
                    ],
                    "warehouse": "仓库A",
                },
            )

            assert resp.status_code == 200, resp.get_data(as_text=True)
            body = resp.get_json()
            assert body["status"] == "success", body

            in_order = InOrder.query.filter_by(order_no=body["order_no"]).first()
            assert in_order is not None
            assert in_order.status == "pending"
            assert in_order.business_type == "采购入库"
            # 多来源：表头 source_purchase_order_id 为 None
            assert in_order.source_purchase_order_id is None
            # 明细来源完整
            items = InOrderItem.query.filter_by(in_order_id=in_order.id).all()
            assert len(items) == 2
            source_ids = {item.source_purchase_order_item_id for item in items}
            assert source_ids == {pi1.id, pi2.id}
            # 数量正确
            qty_by_source = {item.source_purchase_order_item_id: item.quantity for item in items}
            assert qty_by_source[pi1.id] == 30
            assert qty_by_source[pi2.id] == 20


class TestSelectionWarehouseInvalid:
    """T2+T3：不存在/停用仓库被拒绝。"""

    def test_nonexistent_warehouse_rejected(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po1, pi1 = _make_purchase_order(seed["sup1"], seed["mat"], 100, "PO-001")
            client = _make_client()

            resp = client.post(
                "/purchase_order/create_in_order_from_selection",
                json={
                    "items": [{"purchase_order_item_id": pi1.id, "quantity": 30}],
                    "warehouse": "不存在的仓库",
                },
            )
            assert resp.status_code in (200, 400)
            body = resp.get_json()
            assert body["status"] == "error"
            assert "不存在" in body.get("msg", "") or "仓库" in body.get("msg", "")

    def test_inactive_warehouse_rejected(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po1, pi1 = _make_purchase_order(seed["sup1"], seed["mat"], 100, "PO-001")
            client = _make_client()

            resp = client.post(
                "/purchase_order/create_in_order_from_selection",
                json={
                    "items": [{"purchase_order_item_id": pi1.id, "quantity": 30}],
                    "warehouse": "仓库B",
                },
            )
            assert resp.status_code in (200, 400)
            body = resp.get_json()
            assert body["status"] == "error"
            assert "停用" in body.get("msg", "") or "仓库" in body.get("msg", "")


class TestSelectionDifferentSupplier:
    """T4：不同供应商明细被拒绝。"""

    def test_different_suppliers_rejected(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po1, pi1 = _make_purchase_order(seed["sup1"], seed["mat"], 100, "PO-001")
            po2, pi2 = _make_purchase_order(seed["sup2"], seed["mat"], 50, "PO-002")
            client = _make_client()

            resp = client.post(
                "/purchase_order/create_in_order_from_selection",
                json={
                    "items": [
                        {"purchase_order_item_id": pi1.id, "quantity": 30},
                        {"purchase_order_item_id": pi2.id, "quantity": 20},
                    ],
                    "warehouse": "仓库A",
                },
            )
            body = resp.get_json()
            assert body["status"] == "error"
            assert "同一供应商" in body.get("msg", "") or "供应商" in body.get("msg", "")
