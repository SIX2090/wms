# -*- coding: utf-8 -*-
"""SALES-AUDIT-005 回归测试：编辑出库草稿重建明细时保留 source_sales_order_item_id。

根因（P1）：
  out_order.py 编辑分支先 db.session.delete 全部旧明细，再从 submitted_items
  重建 OutOrderItem，重建字段不含 source_sales_order_item_id。重建后
  sync_sales_order_shipment 里 outbound_item.source_sales_order_item_id 为 None，
  退化为按 material_id 模糊匹配，同订单多条同物料时跳过回写，
  shipped_quantity 漏更新。

修复：
  编辑重建前按 material_id 构建旧 source_sales_order_item_id 映射，
  重建时优先用前端回传的来源，其次按 material_id 恢复。

测试用例：
  T1. 编辑后 source_sales_order_item_id 保留（按 material_id 恢复）
  T2. 编辑后改数量仍保留来源，sync 回写正确
  T3. 前端回传 source_sales_order_item_id 时优先使用前端值
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
    sync_sales_order_shipment,
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


class TestEditPreservesSourceItemId:
    """T1：编辑后 source_sales_order_item_id 通过 material_id 映射保留。"""

    def test_edit_preserves_source_by_material_id(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-EDIT-001")
            outbound = _make_pending_outbound(order, sales_item, seed["mat"], 5, "OUT-EDIT-001")
            client = _make_client()

            # 编辑：改数量从 5 到 3，不传 source_sales_order_item_id
            # 路由是 /out_order/add（带 order_id 为编辑模式）
            resp = client.post("/out_order/add", json={
                "order_id": outbound.id,
                "order_no": outbound.order_no,
                "date": str(date.today()),
                "warehouse": "仓库A",
                "business_type": "销售出库",
                "customer": "测试客户",
                "picker": "",
                "purpose": f"来源销售订单 {order.order_no}",
                "remark": "",
                "items": [
                    {"code": "M001", "quantity": 3, "price": 10}
                ],
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)
            body = resp.get_json()
            assert body["status"] == "success", body

            # 验证重建后 source_sales_order_item_id 保留
            db.session.refresh(outbound)
            new_item = OutOrderItem.query.filter_by(out_order_id=outbound.id).first()
            assert new_item is not None
            assert new_item.source_sales_order_item_id == sales_item.id, \
                "编辑重建后 source_sales_order_item_id 丢失"
            assert new_item.quantity == 3

    def test_edit_then_sync_writes_correct_shipped(self):
        """T2：编辑后改数量，sync 回写正确的 shipped_quantity。"""
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-EDIT-002")
            outbound = _make_pending_outbound(order, sales_item, seed["mat"], 5, "OUT-EDIT-002")
            client = _make_client()

            # 编辑：改数量从 5 到 7
            resp = client.post("/out_order/add", json={
                "order_id": outbound.id,
                "order_no": outbound.order_no,
                "date": str(date.today()),
                "warehouse": "仓库A",
                "business_type": "销售出库",
                "customer": "测试客户",
                "picker": "",
                "purpose": f"来源销售订单 {order.order_no}",
                "remark": "",
                "items": [
                    {"code": "M001", "quantity": 7, "price": 10}
                ],
            })
            assert resp.status_code == 200

            # sync 应回写 7（而不是原来的 5）
            db.session.refresh(outbound)
            sync_sales_order_shipment(outbound, quantity_sign=1)
            db.session.commit()
            db.session.refresh(sales_item)
            assert sales_item.shipped_quantity == 7, \
                f"sync 回写错误，期望 7，实际 {sales_item.shipped_quantity}"

    def test_edit_uses_frontend_source_id_when_provided(self):
        """T3：前端回传 source_sales_order_item_id 时优先使用。"""
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-EDIT-003")
            outbound = _make_pending_outbound(order, sales_item, seed["mat"], 5, "OUT-EDIT-003")
            # 创建第二张销售订单明细（同物料）用于测试前端覆盖
            sales_item2 = SalesOrderItem(
                sales_order_id=order.id, material_id=seed["mat"].id,
                quantity=20, shipped_quantity=0, price=10,
                amount=20 * 10, tax_rate=0.13,
            )
            db.session.add(sales_item2)
            db.session.commit()
            client = _make_client()

            # 编辑：前端回传 source_sales_order_item_id=sales_item2.id
            resp = client.post("/out_order/add", json={
                "order_id": outbound.id,
                "order_no": outbound.order_no,
                "date": str(date.today()),
                "warehouse": "仓库A",
                "business_type": "销售出库",
                "customer": "测试客户",
                "picker": "",
                "purpose": f"来源销售订单 {order.order_no}",
                "remark": "",
                "items": [
                    {
                        "code": "M001",
                        "quantity": 5,
                        "price": 10,
                        "source_sales_order_item_id": sales_item2.id,
                    }
                ],
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)

            # 验证优先使用前端回传的 source_sales_order_item_id
            new_item = OutOrderItem.query.filter_by(out_order_id=outbound.id).first()
            assert new_item.source_sales_order_item_id == sales_item2.id, \
                "未优先使用前端回传的 source_sales_order_item_id"
