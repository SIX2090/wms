# -*- coding: utf-8 -*-
"""P1 回归：工单领料单库位必填（AGENTS.md 规则二）。

S9 修复：ProductionRequisition 模型新增 location 列，
开启库位管理后 complete_requisition 必须拒绝未填 location 的草稿；
未开启库位管理时不得误报（向后兼容）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    LocationInventory, Material, ProductionRequisition,
    ProductionRequisitionItem, Unit, User, Warehouse, db,
    generate_order_no, set_system_setting,
)


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    db.session.add(User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin", must_change_password=False,
    ))
    db.session.commit()


def _seed_basics():
    wh = Warehouse(code="RWH0", name="默认仓", status="active", is_default=True)
    unit = Unit(code="U1", name="个")
    db.session.add_all([wh, unit])
    db.session.flush()
    mat = Material(code="M001", name="测试物料", spec="S1", unit=unit, stock=100)
    db.session.add(mat)
    db.session.commit()
    return wh, mat


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        wh, mat = _seed_basics()
    c = app_module.app.test_client()
    _login(c)
    yield c


def _create_pending_requisition(client, *, location=""):
    """通过 /requisition/save_table 创建一条带明细的 pending 领料单，返回 id。"""
    with app_module.app.app_context():
        req_no = generate_order_no("REQ")
    payload = {
        "order_no": req_no,
        "header": {
            "warehouse": "默认仓",
            "location": location,
            "purpose": "测试领料",
            "picker": "张三",
        },
        "items": [
            {"code": "M001", "quantity": 1, "unit_id": 1}
        ],
    }
    resp = client.post("/requisition/save_table", json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        order = ProductionRequisition.query.filter_by(req_no=req_no).first()
        return order.id


def test_requisition_location_field_exists():
    """模型必须含 location 列（S9 模型变更）。"""
    with app_module.app.app_context():
        col = ProductionRequisition.__table__.columns.get("location")
        assert col is not None, "ProductionRequisition 缺少 location 列"


def test_save_table_persists_location(client):
    """save_table 必须把 location 持久化到数据库。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    rid = _create_pending_requisition(client, location="默认仓-A1")
    with app_module.app.app_context():
        order = db.session.get(ProductionRequisition, rid)
        assert (order.location or "") == "默认仓-A1"


def test_complete_requisition_rejects_missing_location_when_enabled(client):
    """开启库位管理时，未填 location 的草稿不得被完成。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    rid = _create_pending_requisition(client, location="")
    resp = client.post(f"/requisition/{rid}/complete")
    assert resp.status_code in (200, 400)
    data = resp.get_json()
    assert data.get("status") == "error", data
    assert "库位" in (data.get("msg") or ""), data
    with app_module.app.app_context():
        order = db.session.get(ProductionRequisition, rid)
        assert order.status == "pending"


def test_complete_requisition_succeeds_with_location_when_enabled(client):
    """开启库位管理且填写 location 时，完成应成功。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        m = Material.query.filter_by(code="M001").first()
        db.session.add(LocationInventory(material_id=m.id, location="默认仓-A1", quantity=10))
        db.session.commit()
    rid = _create_pending_requisition(client, location="默认仓-A1")
    resp = client.post(f"/requisition/{rid}/complete")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        order = db.session.get(ProductionRequisition, rid)
        assert order.status == "completed"


def test_complete_requisition_allows_empty_location_when_disabled(client):
    """未开启库位管理时，location 留空也能完成（向后兼容）。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
    rid = _create_pending_requisition(client, location="")
    resp = client.post(f"/requisition/{rid}/complete")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
