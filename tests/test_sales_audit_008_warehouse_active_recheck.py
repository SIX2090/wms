# -*- coding: utf-8 -*-
"""SALES-AUDIT-008 回归测试：销售出库完成 active 复核。

根因（P1）：
  complete_out_order 在草稿保存后才校验仓库，草稿创建时仓库可能仍 active，
  但保存后仓库被停用（status='inactive'），完成流程此前不再复核，
  导致已停用仓库仍可完成出库，违反 AGENTS.md「仓库始终必填且必须有效」规则。

修复：
  complete_out_order 加锁后、扣库存前，对 business_type=='销售出库' 的单据
  调用 validate_sales_outbound_warehouse(order) 复核 active 状态，
  不通过则 rollback 并返回错误。

测试用例：
  T1. 正常 active 仓库完成成功
  T2. 仓库被停用后完成被拒绝
  T3. 非销售出库类型不触发 active 复核（其他出库）
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


class TestCompleteSalesOutboundWarehouseActiveRecheck:
    """SALES-AUDIT-008：销售出库完成 active 复核。"""

    def test_active_warehouse_complete_succeeds(self):
        """T1：正常 active 仓库完成成功。"""
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-ACTIVE-001")
            outbound = _make_pending_outbound(order, sales_item, seed["mat"], 5, "OUT-ACTIVE-001")
            client = _make_client()
            resp = client.post(f"/out_order/{outbound.id}/complete?force=true")
            assert resp.status_code == 200, resp.get_data(as_text=True)
            body = resp.get_json()
            assert body["status"] == "success", body
            db.session.refresh(outbound)
            assert outbound.status == "completed"

    def test_inactive_warehouse_blocks_complete(self):
        """T2：仓库被停用后完成被拒绝。"""
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-ACTIVE-002")
            outbound = _make_pending_outbound(order, sales_item, seed["mat"], 5, "OUT-ACTIVE-002")
            # 停用仓库
            wh = Warehouse.query.filter_by(name="仓库A").first()
            wh.status = "inactive"
            db.session.commit()
            client = _make_client()
            resp = client.post(f"/out_order/{outbound.id}/complete?force=true")
            assert resp.status_code == 400, resp.get_data(as_text=True)
            body = resp.get_json()
            assert body["status"] == "error"
            msg = body.get("msg", "")
            assert "仓库" in msg or "启用" in msg or "停用" in msg
            # 出库单状态保持 pending
            db.session.refresh(outbound)
            assert outbound.status == "pending"

    def test_non_sales_outbound_not_affected_by_active_recheck(self):
        """T3：非销售出库（其他出库）不触发 active 复核。

        其他出库应通过 validate_sales_warehouse 流程（in_order.py 已覆盖），
        这里验证其他出库单即使在仓库停用状态下也能进入完成流程
        （不会被 SALES-AUDIT-008 的销售专属校验拦截）。
        """
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            # 其他出库单（无销售来源）
            outbound = OutOrder(
                order_no="OUT-OTHER-001", warehouse="仓库A",
                business_type="其他出库", status="pending", date=date.today(),
            )
            db.session.add(outbound)
            db.session.flush()
            item = OutOrderItem(
                out_order_id=outbound.id, material_id=seed["mat"].id,
                quantity=5, price=10, amount=50,
            )
            db.session.add(item)
            db.session.commit()
            # 停用仓库
            wh = Warehouse.query.filter_by(name="仓库A").first()
            wh.status = "inactive"
            db.session.commit()
            client = _make_client()
            resp = client.post(f"/out_order/{outbound.id}/complete?force=true")
            # 销售专属校验不应触发；其他出库走自己的仓库校验逻辑
            # 此处仅断言不被 SALES-AUDIT-008 的"销售出库"分支拦截
            body = resp.get_json() if resp.is_json else {}
            msg = body.get("msg", "") if isinstance(body, dict) else ""
            # 关键：错误消息不应是销售专属消息"请选择有效且启用的发货仓库"
            # 其他出库可能有其他仓库校验失败消息，但不应该是销售出库分支抛出的
            assert "发货仓库" not in msg, "其他出库不应触发销售出库 active 复核分支"
