# -*- coding: utf-8 -*-
"""BUG-2026-08-17-006 回归：删除已反提交的采购入库单不得留下库存台账流水。"""
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
    InOrder,
    InOrderItem,
    Material,
    MaterialCategory,
    StockTransaction,
    Unit,
    User,
    Warehouse,
    _collect_ledger_rows,
    db,
    set_system_setting,
)


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        set_system_setting("location_management_enabled", "0")
        warehouse = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
        db.session.add_all([
            User(username="admin", password_hash=generate_password_hash("admin"),
                 role="admin", must_change_password=False),
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT"),
            warehouse,
        ])
        db.session.commit()
        db.session.add(Material(code="M001", name="测试物料", category_id=1, unit_id=1, stock=0))
        db.session.commit()

    test_client = app_module.app.test_client()
    login_page = test_client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page).group(1)
    response = test_client.post("/login", data={
        "username": "admin", "password": "admin", "csrf_token": token,
    })
    assert response.status_code in (302, 303)
    return test_client


def test_delete_in_order_cleans_stock_transactions_and_ledger(client):
    with app_module.app.app_context():
        material = Material.query.filter_by(code="M001").first()
        warehouse = Warehouse.query.filter_by(code="WHA").first()
        user = User.query.filter_by(username="admin").first()
        order = InOrder(
            order_no="IN-DELETE-LEDGER", business_type="采购入库", warehouse=warehouse.name,
            status="completed", operator_id=user.id,
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(InOrderItem(
            in_order_id=order.id, material_id=material.id, quantity=10, price=1, amount=10,
        ))
        db.session.add(StockTransaction(
            material_id=material.id,
            transaction_type="in",
            quantity=10,
            location=warehouse.name,
            reference_type="in_order",
            reference_id=order.id,
            operator_id=user.id,
        ))
        material.stock = 10
        db.session.commit()
        order_id = order.id
        warehouse_id = warehouse.id
        warehouse_name = warehouse.name
        warehouse_code = warehouse.code

    reverted = client.post(f"/in_order/{order_id}/revert")
    assert reverted.get_json()["status"] == "success", reverted.get_json()

    deleted = client.post(f"/in_order/{order_id}/delete")
    assert deleted.get_json()["status"] == "success", deleted.get_json()

    with app_module.app.app_context():
        assert InOrder.query.get(order_id) is None
        assert StockTransaction.query.filter_by(reference_type="in_order", reference_id=order_id).count() == 0
        ledger_rows = _collect_ledger_rows({
            "warehouse_id": warehouse_id,
            "warehouse": warehouse_name,
            "warehouse_code": warehouse_code,
        })
        assert ledger_rows == []
