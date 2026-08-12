# -*- coding: utf-8 -*-
"""P1 回归：库存调整单行级库位必填（AGENTS.md 规则二）。

S11 修复：location_management_enabled 时，
- add_adjustment 保存明细时每条 item.location 必填
- complete_adjustment 加同样校验防绕过（存量草稿或直改库清空 item.location）
- loc_key 优先 item.location，未开库位退回 adjustment.warehouse
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
    AdjustmentOrder, AdjustmentOrderItem, LocationInventory, Material,
    Unit, User, Warehouse, db, generate_order_no, set_system_setting,
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
    wh = Warehouse(code="WHA", name="仓库A", status="active", is_default=True)
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
        _seed_basics()
    c = app_module.app.test_client()
    _login(c)
    yield c


def _create_adjustment(client, *, items, adjustment_type="surplus"):
    """通过 /adjustment/add 创建一张草稿调整单，返回 id。"""
    with app_module.app.app_context():
        adj_no = generate_order_no("ADJ")
    payload = {
        "adjustment_no": adj_no,
        "adjustment_type": adjustment_type,
        "warehouse": "仓库A",
        "items": items,
    }
    resp = client.post("/adjustment/add", json=payload)
    return resp


def test_add_adjustment_rejects_missing_item_location_when_enabled(client):
    """开启库位管理时，item.location 留空必须拒绝保存。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    resp = _create_adjustment(client, items=[
        {"code": "M001", "quantity": 5, "location": "", "reason": "测试"},
    ])
    assert resp.status_code in (200, 400)
    data = resp.get_json()
    assert data.get("status") == "error", data
    assert "库位" in (data.get("msg") or ""), data


def test_add_adjustment_succeeds_with_item_location_when_enabled(client):
    """开启库位管理且 item.location 填写时，保存应成功。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    resp = _create_adjustment(client, items=[
        {"code": "M001", "quantity": 5, "location": "仓库A-L1", "reason": "测试"},
    ])
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data


def test_add_adjustment_allows_empty_item_location_when_disabled(client):
    """未开启库位管理时，item.location 留空也能保存（向后兼容）。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
    resp = _create_adjustment(client, items=[
        {"code": "M001", "quantity": 5, "location": "", "reason": "测试"},
    ])
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data


def test_complete_adjustment_rejects_missing_item_location_when_enabled(client):
    """开启库位管理时，complete_adjustment 必须拒绝 item.location 为空的草稿
    （防绕过：先保存带库位草稿，再直改库清空 item.location 后完成）。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    resp = _create_adjustment(client, items=[
        {"code": "M001", "quantity": 5, "location": "仓库A-L1", "reason": "测试"},
    ])
    data = resp.get_json()
    aid = data.get("id") or data.get("order_id")
    # 模拟绕过：直改库清空 item.location
    with app_module.app.app_context():
        AdjustmentOrderItem.query.filter_by(adjustment_order_id=aid).update({"location": None})
        db.session.commit()
    resp = client.post(f"/adjustment/{aid}/complete")
    assert resp.status_code in (200, 400)
    data = resp.get_json()
    assert data.get("status") == "error", data
    assert "库位" in (data.get("msg") or ""), data


def test_complete_adjustment_succeeds_with_item_location_when_enabled(client):
    """开启库位管理且 item.location 填写时，complete 应成功。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        m = Material.query.filter_by(code="M001").first()
        db.session.add(LocationInventory(material_id=m.id, location="仓库A-L1", quantity=10))
        db.session.commit()
    resp = _create_adjustment(client, items=[
        {"code": "M001", "quantity": 5, "location": "仓库A-L1", "reason": "测试"},
    ])
    data = resp.get_json()
    aid = data.get("id") or data.get("order_id")
    resp = client.post(f"/adjustment/{aid}/complete")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        adj = db.session.get(AdjustmentOrder, aid)
        assert adj.status == "completed"
