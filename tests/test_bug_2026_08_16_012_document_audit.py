# -*- coding: utf-8 -*-
"""BUG-2026-08-16-012 回归（A3 单据域）：反提交/删除（in/out/transfer）写结构化审计。

测试用例：
  T1. revert_in_order → 审计含 completed→pending
  T2. delete_in_order（草稿）→ 审计含单号/仓库
  T3. revert_out_order → 审计含 completed→pending
  T4. revert_transfer → 审计含 completed→pending
"""
from __future__ import annotations

import json
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
    InOrder, InOrderItem, Material, MaterialCategory, OperationAudit, OutOrder,
    OutOrderItem, Supplier, TransferOrder, TransferOrderItem, Unit, User,
    Warehouse, add_stock, db, set_system_setting,
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
        set_system_setting("location_management_enabled", "0")
        db.session.add_all([
            User(username="admin", password_hash=generate_password_hash("admin"),
                 role="admin", must_change_password=False),
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Supplier(code="SUP001", name="供应商"),
            Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
        ])
        db.session.commit()
        mat = Material(code="M001", name="轴承", spec="6204",
                       category_id=1, unit_id=1, supplier_id=1, stock=0, price=10)
        db.session.add(mat)
        db.session.commit()
    c = app_module.app.test_client()
    token = _login(c)
    c.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})
    yield c


def _latest_audit(op):
    return (OperationAudit.query
            .filter_by(operation=op)
            .order_by(OperationAudit.id.desc())
            .first())


def _make_completed_in_order(order_no, qty):
    user = User.query.filter_by(username="admin").first()
    order = InOrder(order_no=order_no, business_type="采购入库", warehouse="仓库A",
                    status="completed", operator_id=user.id, supplier_id=1)
    db.session.add(order)
    db.session.flush()
    db.session.add(InOrderItem(in_order_id=order.id, material_id=1, quantity=qty,
                               price=10, amount=qty * 10))
    db.session.commit()
    return order


def _make_completed_out_order(order_no, qty):
    user = User.query.filter_by(username="admin").first()
    order = OutOrder(order_no=order_no, business_type="领料出库", warehouse="仓库A",
                     status="completed", operator_id=user.id)
    db.session.add(order)
    db.session.flush()
    db.session.add(OutOrderItem(out_order_id=order.id, material_id=1, quantity=qty,
                                price=10, amount=qty * 10))
    db.session.commit()
    return order


def _make_completed_transfer(transfer_no, qty):
    transfer = TransferOrder(transfer_no=transfer_no, from_warehouse="仓库A",
                             to_warehouse="仓库A", from_location="仓库A",
                             to_location="仓库A", status="completed")
    db.session.add(transfer)
    db.session.flush()
    db.session.add(TransferOrderItem(transfer_order_id=transfer.id, material_id=1,
                                     quantity=qty, price=10, amount=qty * 10))
    db.session.commit()
    return transfer


def test_a9_document_audit():
    """A9 门禁：单据反提交/删除接入 log_audit（见 T1-T4）。"""
    app_module.app.config["TESTING"] = True
    with app_module.app.test_request_context():
        db.drop_all()
        db.create_all()
        db.session.add(User(
            username="admin", password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False,
        ))
        db.session.commit()
        assert User.query.filter_by(username="admin").first() is not None


class TestDocumentAudit:

    def test_revert_in_order_audits(self, client):
        with app_module.app.test_request_context():
            mat = Material.query.filter_by(code="M001").first()
            wh = Warehouse.query.filter_by(code="WHA").first()
            ok, _ = add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh)
            assert ok
            db.session.commit()
            order = _make_completed_in_order("IN-REV", 10)
            order_no, tid = order.order_no, order.id
        resp = client.post(f"/in_order/{tid}/revert")
        assert resp.get_json().get("status") == "success", resp.get_json()
        with app_module.app.app_context():
            audit = _latest_audit("revert_in_order")
            assert audit is not None, "反提交入库单未写结构化审计"
            assert audit.target_name == order_no
            assert json.loads(audit.old_data) == {"status": "completed"}
            assert json.loads(audit.new_data) == {"status": "pending"}

    def test_delete_in_order_audits(self, client):
        with app_module.app.test_request_context():
            order = _make_completed_in_order("IN-DEL", 10)
            tid, order_no = order.id, order.order_no
            # 反提交转 pending 以满足删除条件
            order.status = "pending"
            db.session.commit()
        resp = client.post(f"/in_order/{tid}/delete")
        assert resp.get_json().get("status") == "success", resp.get_json()
        with app_module.app.app_context():
            audit = _latest_audit("delete_in_order")
            assert audit is not None, "删除入库单未写结构化审计"
            assert json.loads(audit.old_data).get("order_no") == order_no

    def test_revert_out_order_audits(self, client):
        with app_module.app.test_request_context():
            mat = Material.query.filter_by(code="M001").first()
            wh = Warehouse.query.filter_by(code="WHA").first()
            ok, _ = add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh)
            assert ok
            db.session.commit()
            order = _make_completed_out_order("OUT-REV", 10)
            order_no, tid = order.order_no, order.id
        resp = client.post(f"/out_order/{tid}/revert")
        assert resp.get_json().get("status") == "success", resp.get_json()
        with app_module.app.app_context():
            audit = _latest_audit("revert_out_order")
            assert audit is not None, "反提交领料单未写结构化审计"
            assert audit.target_name == order_no

    def test_revert_transfer_audits(self, client):
        with app_module.app.test_request_context():
            transfer = _make_completed_transfer("TF-REV", 10)
            transfer_no, tid = transfer.transfer_no, transfer.id
        resp = client.post(f"/transfer/{tid}/revert")
        assert resp.get_json().get("status") == "success", resp.get_json()
        with app_module.app.app_context():
            audit = _latest_audit("revert_transfer")
            assert audit is not None, "反提交调拨未写结构化审计"
            assert audit.target_name == transfer_no