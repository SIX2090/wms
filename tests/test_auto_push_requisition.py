# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module
from app import DocumentPushLine, InOrder, Material, OutOrder, Supplier, Unit, User, Warehouse, db
from werkzeug.security import generate_password_hash

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    unit = Unit(code="PCS", name="个")
    warehouse = Warehouse(code="AUTO_WH", name="自动领料仓", status="active", is_default=True)
    supplier = Supplier(code="AUTO_SUP", name="自动领料供应商")
    user = User(
        username="auto_push_admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        status="normal",
        must_change_password=False,
    )
    material = Material(code="AUTO_MAT", name="自动领料物料", unit=unit, stock=0, price=12)
    db.session.add_all([unit, warehouse, supplier, user, material])
    db.session.commit()
    return supplier.id


def _login(client):
    response = client.post(
        "/login",
        data={"username": "auto_push_admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )
    assert response.status_code in (200, 302)


def _create_purchase_in_order(client, supplier_id, auto_push_requisition):
    response = client.post(
        "/in_order/add",
        json={
            "business_type": "采购入库",
            "supplier_id": supplier_id,
            "warehouse": "自动领料仓",
            "auto_push_requisition": auto_push_requisition,
            "items": [{"code": "AUTO_MAT", "quantity": 5, "price": 12}],
        },
    )
    body = response.get_json()
    assert body["status"] == "success", body
    return body["id"]


class TestAutoPushRequisition:
    def setup_method(self):
        with app_module.app.app_context():
            _reset_db()
            self.supplier_id = _seed()
        self.client = app_module.app.test_client()
        _login(self.client)

    def test_default_is_disabled_and_completion_does_not_create_requisition(self):
        html = self.client.get("/in_order/add").get_data(as_text=True)
        assert 'id="autoPushRequisition"' in html
        assert 'name="auto_push_requisition"' in html
        assert 'id="autoPushRequisition" value="1" checked' not in html

        order_id = _create_purchase_in_order(self.client, self.supplier_id, False)
        response = self.client.post(f"/in_order/{order_id}/complete?force=1")
        body = response.get_json()
        assert body["status"] == "success", body
        assert body["auto_requisition_id"] is None

        with app_module.app.app_context():
            order = db.session.get(InOrder, order_id)
            assert order.auto_push_requisition is False
            assert OutOrder.query.count() == 0
            assert DocumentPushLine.query.count() == 0
            assert db.session.query(Material.stock).filter_by(code="AUTO_MAT").scalar() == 5

    def test_enabled_completion_creates_completed_requisition_and_traceability(self):
        order_id = _create_purchase_in_order(self.client, self.supplier_id, True)
        response = self.client.post(f"/in_order/{order_id}/complete?force=1")
        body = response.get_json()
        assert body["status"] == "success", body
        assert body["auto_requisition_id"]

        with app_module.app.app_context():
            order = db.session.get(InOrder, order_id)
            requisition = db.session.get(OutOrder, body["auto_requisition_id"])
            material = Material.query.filter_by(code="AUTO_MAT").first()
            push_lines = DocumentPushLine.query.filter_by(
                source_document_type="purchase_in_order",
                source_document_id=order_id,
                target_document_type="requisition",
                target_document_id=requisition.id,
            ).all()
            assert order.status == "completed"
            assert order.auto_push_requisition is True
            assert requisition.status == "completed"
            assert requisition.business_type == "领料单"
            assert requisition.warehouse == order.warehouse
            assert requisition.purpose == "自动下推领料单"
            assert len(requisition.items) == 1
            assert requisition.items[0].material_id == order.items[0].material_id
            assert requisition.items[0].quantity == order.items[0].quantity
            assert len(push_lines) == 1
            assert push_lines[0].pushed_quantity == order.items[0].quantity
            assert material.stock == 0
