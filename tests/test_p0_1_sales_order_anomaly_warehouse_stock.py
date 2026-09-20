# -*- coding: utf-8 -*-
"""P0-1 回归：销售订单 AI 异常分析「缺货风险」按订单仓库口径判定。

修复前：api_ai_sales_order_anomaly_analysis 缺货风险用全局 Material.stock
判定，A 仓订单会被 B 仓库存掩护而漏报缺货（只读提示场景，A11/R2 同根因）。

修复后：
1. 双仓场景：库存全部归属副仓时，主仓订单必须报缺货风险（含仓库名口径）；
2. 正常场景：库存归属本仓时不报缺货；
3. 兼容场景：库存全部来自无法归属仓库的历史遗留流水时回退全局口径，
   避免"有库存却误报缺货"（与 deduct_stock_atomic BUG-2026-09-19-001 同判据）；
4. 数据兼容：订单无仓库时回退全局口径（保持旧行为），文案不含仓库名。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    Customer, Material, MaterialCategory, SalesOrder, SalesOrderItem,
    StockTransaction, Supplier, Unit, User, Warehouse, db, set_system_setting,
)


def _login(client):
    page = client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    return token.group(1) if token else ""


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False,
        ))
        db.session.add_all([
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Supplier(code="SUP001", name="供应商"),
            Customer(code="CUS001", name="测试客户"),
            Warehouse(code="WH01", name="主仓", is_default=True),
            Warehouse(code="WH02", name="副仓", is_default=False),
        ])
        db.session.commit()
        db.session.add(Material(
            code="M-SO", name="销售料", spec="S",
            category_id=1, unit_id=1, supplier_id=1, stock=10, price=1,
        ))
        db.session.commit()
        # 双仓隔离判定需要关闭库位管理（走流水净额口径）
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
    c = app_module.app.test_client()
    token = _login(c)
    c.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})
    yield c


def _create_order(warehouse="主仓", qty=5, material_stock=None):
    """直接建一张 confirmed 未发货销售订单（含 1 行明细），返回 id。"""
    with app_module.app.app_context():
        if material_stock is not None:
            m = Material.query.filter_by(code="M-SO").first()
            m.stock = material_stock
        order = SalesOrder(
            order_no=f"SO-{warehouse or 'NOWH'}-001",
            customer_id=1,
            warehouse=warehouse,
            status="confirmed",
            shipment_status="pending",
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(SalesOrderItem(
            sales_order_id=order.id, material_id=1,
            quantity=qty, shipped_quantity=0, price=1,
        ))
        db.session.commit()
        return order.id


def _anomaly(client, order_id):
    resp = client.get(f"/api/ai/sales_order/{order_id}/anomaly_analysis")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    return data["data"]


def _shortage_messages(payload):
    return [a["message"] for a in payload["anomalies"] if a["kind"] == "缺货风险"]


def _add_inbound_tx(warehouse_name, qty=10):
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M-SO").first()
        wh = Warehouse.query.filter_by(name=warehouse_name).first()
        db.session.add(StockTransaction(
            material_id=m.id, transaction_type="in", quantity=qty,
            warehouse_id=wh.id, location=None, remark=f"{warehouse_name}入库",
        ))
        db.session.commit()


def test_shortage_detected_when_stock_only_in_other_warehouse(client):
    """库存全部归属副仓时，主仓订单必须报缺货风险（双仓隔离，不再被掩护）。"""
    _add_inbound_tx("副仓")
    oid = _create_order(warehouse="主仓")
    payload = _anomaly(client, oid)
    msgs = _shortage_messages(payload)
    assert msgs, f"应报缺货风险，实际 anomalies={payload['anomalies']}"
    assert "主仓库存" in msgs[0], msgs
    assert "M-SO" in msgs[0], msgs


def test_no_shortage_when_stock_in_same_warehouse(client):
    """库存归属本仓时不报缺货（控制组）。"""
    _add_inbound_tx("主仓")
    oid = _create_order(warehouse="主仓")
    payload = _anomaly(client, oid)
    assert _shortage_messages(payload) == [], payload["anomalies"]


def test_no_shortage_when_stock_unattributed(client):
    """库存全部来自无归属历史遗留流水时回退全局口径，不误报缺货。"""
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M-SO").first()
        db.session.add(StockTransaction(
            material_id=m.id, transaction_type="in", quantity=10,
            warehouse_id=None, location=None, remark="历史遗留",
        ))
        db.session.commit()
    oid = _create_order(warehouse="主仓")
    payload = _anomaly(client, oid)
    assert _shortage_messages(payload) == [], payload["anomalies"]


def test_shortage_fallback_global_when_no_warehouse(client):
    """订单无仓库时回退全局口径：全局不足仍报缺货，且文案不含仓库名。"""
    oid = _create_order(warehouse="", material_stock=3)
    payload = _anomaly(client, oid)
    msgs = _shortage_messages(payload)
    assert msgs, f"应报缺货风险，实际 anomalies={payload['anomalies']}"
    assert " vs 库存 " in msgs[0], msgs
    assert "仓库存" not in msgs[0], msgs
