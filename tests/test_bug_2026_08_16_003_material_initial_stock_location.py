# -*- coding: utf-8 -*-
"""BUG-2026-08-16-003 回归：新增物料初始库存单事务化 + 同步库位账。

审计发现（AUDIT-2026-08-16 F3/P0-3）：
- 新增物料带初始库存走 Material(stock=initial_stock) ORM 直改，
  不写 LocationInventory（开库位管理时总账与库位账分叉）；
- 物料 commit 与流水 commit 两次独立提交，中间失败留下
  "库存已涨、流水缺失"的不一致状态。

修复后要求：
- 开启库位管理且有默认仓库时，初始库存同步写库位账（仓库占位行）；
- 未开启库位管理时不写库位账（向后兼容）；
- 库位账写入失败时整体回滚（物料不落库，保证原子性）；
- 审计流水与物料同事务。
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
    LocationInventory, Material, MaterialCategory, StockTransaction, Unit,
    User, Warehouse, db, set_system_setting,
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
            Warehouse(code="WH01", name="主仓", is_default=True),
        ])
        db.session.commit()
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
    c = app_module.app.test_client()
    token = _login(c)
    c.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})
    yield c


def _add_material(client, code, stock):
    return client.post("/material/add", data={
        "code": code, "name": f"料{code}", "spec": "S",
        "brand": "", "price": "10", "stock": stock,
    })


def test_initial_stock_writes_location_inventory_when_enabled(client):
    """开启库位管理 + 默认仓库：初始库存同步写库位账（仓库占位行）。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    resp = _add_material(client, "M-INIT-1", "100")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json().get("status") == "success", resp.get_json()
    with app_module.app.app_context():
        material = Material.query.filter_by(code="M-INIT-1").first()
        wh = Warehouse.query.filter_by(name="主仓").first()
        assert abs((material.stock or 0) - 100) < 1e-6
        rows = LocationInventory.query.filter_by(
            material_id=material.id, warehouse_id=wh.id, location="主仓").all()
        assert len(rows) == 1, "初始库存未写库位账"
        assert abs((rows[0].quantity or 0) - 100) < 1e-6
        txn = StockTransaction.query.filter_by(material_id=material.id).first()
        assert txn is not None
        assert txn.location == "主仓"


def test_initial_stock_skips_location_inventory_when_disabled(client):
    """未开启库位管理：不写库位账（向后兼容），流水仍记录。"""
    resp = _add_material(client, "M-INIT-2", "50")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    with app_module.app.app_context():
        material = Material.query.filter_by(code="M-INIT-2").first()
        assert LocationInventory.query.filter_by(material_id=material.id).count() == 0
        assert StockTransaction.query.filter_by(material_id=material.id).count() == 1


def test_initial_stock_without_default_warehouse_still_succeeds(client):
    """无默认仓库：不写库位账、流水 location 为空，但建料成功（兼容旧行为）。"""
    with app_module.app.app_context():
        Warehouse.query.filter_by(name="主仓").update({"is_default": False})
        db.session.commit()
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    resp = _add_material(client, "M-INIT-3", "30")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    with app_module.app.app_context():
        material = Material.query.filter_by(code="M-INIT-3").first()
        assert material is not None
        assert abs((material.stock or 0) - 30) < 1e-6
        assert LocationInventory.query.filter_by(material_id=material.id).count() == 0


def test_location_inventory_failure_rolls_back_material(client, monkeypatch):
    """库位账写入失败：物料整体回滚，不落库（单事务原子性）。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()

    def _fail(material, location, delta, warehouse=None):
        return False, "库位账写入失败(测试注入)"

    monkeypatch.setattr(app_module, "update_location_inventory", _fail)
    resp = _add_material(client, "M-INIT-4", "80")
    data = resp.get_json()
    assert data.get("status") == "error", data
    with app_module.app.app_context():
        assert Material.query.filter_by(code="M-INIT-4").first() is None, \
            "库位账失败后物料不得落库"
        assert StockTransaction.query.filter(
            StockTransaction.remark == "新增物料初始库存").count() == 0
