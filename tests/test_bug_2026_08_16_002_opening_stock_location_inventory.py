# -*- coding: utf-8 -*-
"""BUG-2026-08-16-002 回归：期初库存必须同步写 LocationInventory 库位账。

审计发现（AUDIT-2026-08-16 F2/P0-2）：_apply_opening_stock_balance 只改
Material.stock + 写一条 opening 流水，从不写 LocationInventory。开启库位
管理后期初建账即错账：库存查询显示 0、出库被库位余额不足拦截。

修复后要求：
- OpeningStock 模型含 location 列；
- 开启库位管理时，新增/编辑/批量保存期初都同步写库位账
  （未填库位以仓库名作占位行）；
- 编辑下调时正确扣减库位账；历史缺行时按旧数量回填基线再扣差额；
- get_warehouse_stock_quantities 与 Material.stock 口径一致；
- 未开启库位管理时不写库位账（向后兼容）。
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
    LocationInventory, Material, MaterialCategory, OpeningStock, Supplier,
    Unit, User, Warehouse, db, get_warehouse_stock_quantities,
    set_system_setting,
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
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False,
            ))
        db.session.add_all([
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Supplier(code="SUP001", name="供应商"),
            Warehouse(code="WH01", name="主仓", is_default=True),
        ])
        db.session.commit()
        db.session.add(Material(
            code="M-OPEN", name="期初料", spec="S",
            category_id=1, unit_id=1, supplier_id=1, stock=0, price=1,
        ))
        db.session.commit()
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
    c = app_module.app.test_client()
    token = _login(c)
    c.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})
    yield c


def _ids():
    with app_module.app.app_context():
        return (
            Material.query.filter_by(code="M-OPEN").first().id,
            Warehouse.query.filter_by(name="主仓").first().id,
            Warehouse.query.filter_by(name="主仓").first(),
        )


def _location_rows(material_id, warehouse_id, location):
    with app_module.app.app_context():
        return LocationInventory.query.filter_by(
            material_id=material_id, warehouse_id=warehouse_id, location=location
        ).all()


def test_opening_stock_model_has_location_column():
    """BUG-2026-08-16-002：OpeningStock 必须含 location 列。"""
    with app_module.app.app_context():
        col = OpeningStock.__table__.columns.get("location")
        assert col is not None, "OpeningStock 缺少 location 列"


def test_add_opening_stock_writes_location_inventory_when_enabled(client):
    """开启库位管理：新增期初必须写库位账，仓库级聚合可见。"""
    material_id, warehouse_id, wh = _ids()
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    resp = client.post("/opening_stock/add", data={
        "material_id": material_id, "warehouse_id": warehouse_id,
        "quantity": "10", "price": "1", "location": "主仓-A1",
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json().get("status") == "success", resp.get_json()
    rows = _location_rows(material_id, warehouse_id, "主仓-A1")
    assert len(rows) == 1
    assert abs((rows[0].quantity or 0) - 10) < 1e-6
    with app_module.app.app_context():
        material = db.session.get(Material, material_id)
        assert abs((material.stock or 0) - 10) < 1e-6
        qty_map = get_warehouse_stock_quantities(wh)
        assert abs(qty_map.get(material_id, 0) - 10) < 1e-6


def test_add_opening_stock_blank_location_uses_warehouse_placeholder(client):
    """未填库位：以仓库名作占位行落库位账，保证仓库级聚合可见。"""
    material_id, warehouse_id, wh = _ids()
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    resp = client.post("/opening_stock/add", data={
        "material_id": material_id, "warehouse_id": warehouse_id,
        "quantity": "5", "price": "1",
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    rows = _location_rows(material_id, warehouse_id, "主仓")
    assert len(rows) == 1
    assert abs((rows[0].quantity or 0) - 5) < 1e-6
    with app_module.app.app_context():
        qty_map = get_warehouse_stock_quantities(wh)
        assert abs(qty_map.get(material_id, 0) - 5) < 1e-6


def test_edit_opening_stock_adjusts_location_inventory(client):
    """编辑下调数量：总账与库位账同步按差额扣减。"""
    material_id, warehouse_id, _wh = _ids()
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    client.post("/opening_stock/add", data={
        "material_id": material_id, "warehouse_id": warehouse_id,
        "quantity": "10", "price": "1", "location": "主仓-A1",
    })
    with app_module.app.app_context():
        opening = OpeningStock.query.filter_by(material_id=material_id).first()
        opening_id = opening.id
    resp = client.post(f"/opening_stock/edit/{opening_id}", data={
        "material_id": material_id, "warehouse_id": warehouse_id,
        "quantity": "4", "price": "1", "location": "主仓-A1",
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json().get("status") == "success", resp.get_json()
    rows = _location_rows(material_id, warehouse_id, "主仓-A1")
    assert len(rows) == 1
    assert abs((rows[0].quantity or 0) - 4) < 1e-6
    with app_module.app.app_context():
        material = db.session.get(Material, material_id)
        assert abs((material.stock or 0) - 4) < 1e-6


def test_edit_backfills_legacy_missing_location_row(client):
    """历史数据：库位管理关闭时建的期初（无库位行），开启后编辑下调，
    应按旧数量回填基线再扣差额，行值 == 新数量。"""
    material_id, warehouse_id, _wh = _ids()
    # 关闭库位管理建期初（旧行为：不写库位账）
    client.post("/opening_stock/add", data={
        "material_id": material_id, "warehouse_id": warehouse_id,
        "quantity": "10", "price": "1",
    })
    assert _location_rows(material_id, warehouse_id, "主仓") == []
    # 开启库位管理后编辑下调到 3
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
        opening = OpeningStock.query.filter_by(material_id=material_id).first()
        opening_id = opening.id
    resp = client.post(f"/opening_stock/edit/{opening_id}", data={
        "material_id": material_id, "warehouse_id": warehouse_id,
        "quantity": "3", "price": "1",
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    rows = _location_rows(material_id, warehouse_id, "主仓")
    assert len(rows) == 1
    assert abs((rows[0].quantity or 0) - 3) < 1e-6


def test_disabled_location_management_skips_location_inventory(client):
    """未开启库位管理：不写库位账（向后兼容旧行为）。"""
    material_id, warehouse_id, _wh = _ids()
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
    resp = client.post("/opening_stock/add", data={
        "material_id": material_id, "warehouse_id": warehouse_id,
        "quantity": "8", "price": "1", "location": "主仓-A1",
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    with app_module.app.app_context():
        assert LocationInventory.query.filter_by(material_id=material_id).count() == 0


def test_batch_save_writes_location_inventory(client):
    """批量保存期初也必须同步库位账。"""
    material_id, warehouse_id, wh = _ids()
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    resp = client.post("/opening_stock/batch_save", json={
        "items": [{
            "material_id": material_id, "warehouse_id": warehouse_id,
            "quantity": 6, "price": 1, "location": "主仓-B2",
        }],
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json().get("status") == "success", resp.get_json()
    rows = _location_rows(material_id, warehouse_id, "主仓-B2")
    assert len(rows) == 1
    assert abs((rows[0].quantity or 0) - 6) < 1e-6
    with app_module.app.app_context():
        qty_map = get_warehouse_stock_quantities(wh)
        assert abs(qty_map.get(material_id, 0) - 6) < 1e-6
