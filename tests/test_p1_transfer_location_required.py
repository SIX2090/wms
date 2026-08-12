# -*- coding: utf-8 -*-
"""P1 回归：调拨单开启库位管理时 from/to_location 必填（AGENTS.md 规则二）。

S10 修复：location_management_enabled 时，
save_transfer_table / add_transfer 必须拒绝未填 from_location 或 to_location 的请求；
complete_transfer 加同样校验防绕过。
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
    LocationInventory, Material, TransferOrder, TransferOrderItem,
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
    wh_a = Warehouse(code="WHA", name="仓库A", status="active")
    wh_b = Warehouse(code="WHB", name="仓库B", status="active", is_default=True)
    unit = Unit(code="U1", name="个")
    db.session.add_all([wh_a, wh_b, unit])
    db.session.flush()
    mat = Material(code="M001", name="测试物料", spec="S1", unit=unit, stock=100)
    db.session.add(mat)
    db.session.commit()
    return wh_a, wh_b, mat


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


def test_save_transfer_table_rejects_missing_from_location_when_enabled(client):
    """开启库位管理时，save_transfer_table 未填 from_location 必须拒绝。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    with app_module.app.app_context():
        transfer_no = generate_order_no("TF")
    payload = {
        "order_no": transfer_no,
        "header": {
            "from_warehouse": "仓库A",
            "to_warehouse": "仓库B",
            "to_location": "仓库B-L1",
            # 故意不传 from_location
        },
        "items": [{"code": "M001", "quantity": 1, "unit_id": 1}],
    }
    resp = client.post("/transfer/save_table", json=payload)
    assert resp.status_code in (200, 400)
    data = resp.get_json()
    assert data.get("status") == "error", data
    assert "调出库位" in (data.get("msg") or ""), data


def test_save_transfer_table_rejects_missing_to_location_when_enabled(client):
    """开启库位管理时，save_transfer_table 未填 to_location 必须拒绝。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    with app_module.app.app_context():
        transfer_no = generate_order_no("TF")
    payload = {
        "order_no": transfer_no,
        "header": {
            "from_warehouse": "仓库A",
            "to_warehouse": "仓库B",
            "from_location": "仓库A-L1",
            # 故意不传 to_location
        },
        "items": [{"code": "M001", "quantity": 1, "unit_id": 1}],
    }
    resp = client.post("/transfer/save_table", json=payload)
    assert resp.status_code in (200, 400)
    data = resp.get_json()
    assert data.get("status") == "error", data
    assert "调入库位" in (data.get("msg") or ""), data


def test_save_transfer_table_succeeds_with_both_locations_when_enabled(client):
    """开启库位管理且填写双向库位时，save_transfer_table 应成功。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    with app_module.app.app_context():
        transfer_no = generate_order_no("TF")
    payload = {
        "order_no": transfer_no,
        "header": {
            "from_warehouse": "仓库A",
            "to_warehouse": "仓库B",
            "from_location": "仓库A-L1",
            "to_location": "仓库B-L1",
        },
        "items": [{"code": "M001", "quantity": 1, "unit_id": 1}],
    }
    resp = client.post("/transfer/save_table", json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data


def test_save_transfer_table_allows_empty_locations_when_disabled(client):
    """未开启库位管理时，from_location/to_location 留空也能保存（向后兼容）。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
    with app_module.app.app_context():
        transfer_no = generate_order_no("TF")
    payload = {
        "order_no": transfer_no,
        "header": {
            "from_warehouse": "仓库A",
            "to_warehouse": "仓库B",
        },
        "items": [{"code": "M001", "quantity": 1, "unit_id": 1}],
    }
    resp = client.post("/transfer/save_table", json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data


def test_complete_transfer_rejects_missing_location_when_enabled(client):
    """开启库位管理时，complete_transfer 必须拒绝 from_location 为空的草稿
    （防绕过：直接改库把 from_location 清空再完成）。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    # 先正常保存一张带库位的草稿
    with app_module.app.app_context():
        transfer_no = generate_order_no("TF")
    payload = {
        "order_no": transfer_no,
        "header": {
            "from_warehouse": "仓库A",
            "to_warehouse": "仓库B",
            "from_location": "仓库A-L1",
            "to_location": "仓库B-L1",
        },
        "items": [{"code": "M001", "quantity": 1, "unit_id": 1}],
    }
    resp = client.post("/transfer/save_table", json=payload)
    data = resp.get_json()
    tid = data.get("id") or data.get("order_id")
    # 模拟绕过：直接清空 from_location
    with app_module.app.app_context():
        t = db.session.get(TransferOrder, tid)
        t.from_location = ""
        db.session.commit()
    resp = client.post(f"/transfer/{tid}/complete")
    assert resp.status_code in (200, 400)
    data = resp.get_json()
    assert data.get("status") == "error", data
    assert "调出库位" in (data.get("msg") or ""), data
