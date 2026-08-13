# -*- coding: utf-8 -*-
"""INV-AUDIT-004 回归测试：旧物料模糊查询接口必须按仓库隔离返回库存。

修复前的 BUG：
- POST /api/query/search 不校验仓库参数，未传 warehouse 时直接返回
  全局 Material.stock，跨仓库存可见，违反 AGENTS.md "库存查询仓库必填"。

修复后：
- 仓库必填：未传 warehouse 时回退默认仓库；无默认仓库则 400。
- stock 字段返回仓库级库存（get_warehouse_stock_quantities），
  不再回退全局 Material.stock。
- 跨仓查询：A 仓库物料不会被 B 仓库的库存覆盖。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    from app import User
    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    db.session.commit()


def _seed_warehouse(code, name, is_default=False):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active", is_default=is_default)
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material(code, name, stock=0):
    from app import Material, Unit
    unit = Unit.query.first()
    if not unit:
        unit = Unit(code="U1", name="个")
        db.session.add(unit)
        db.session.commit()
    m = Material(code=code, name=name, stock=stock, unit=unit)
    db.session.add(m)
    db.session.commit()
    return m


def _enable_location_management():
    from app import set_system_setting
    set_system_setting("location_management_enabled", "1")
    db.session.commit()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
    c = app_module.app.test_client()
    _login(c)
    yield c


class TestApiQuerySearchWarehouseRequired:
    """INV-AUDIT-004：仓库必填（无默认仓库时 400）。"""

    def test_search_without_warehouse_and_no_default_returns_400(self, client):
        with app_module.app.app_context():
            _seed_material("M001", "测试物料", stock=100)
        resp = client.post("/api/query/search", data={"keyword": "M001"})
        assert resp.status_code == 400, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "仓库" in body["msg"]

    def test_search_falls_back_to_default_warehouse(self, client):
        with app_module.app.app_context():
            _seed_warehouse("W001", "默认仓", is_default=True)
            _seed_material("M001", "测试物料", stock=100)
        resp = client.post("/api/query/search", data={"keyword": "M001"})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "success", body
        assert len(body["data"]) == 1


class TestApiQuerySearchWarehouseLevelStock:
    """INV-AUDIT-004：stock 字段返回仓库级库存而非全局 Material.stock。"""

    def test_stock_returns_warehouse_level_not_global(self, client):
        """全局 stock=100，但仓库A 只有 8，必须返回 8。"""
        with app_module.app.app_context():
            w = _seed_warehouse("W001", "仓库A")
            m = _seed_material("M001", "测试物料", stock=100)
            _enable_location_management()
            from app import LocationInventory
            db.session.add(LocationInventory(
                material_id=m.id, warehouse_id=w.id, location="A1", quantity=8,
            ))
            db.session.commit()

        resp = client.post("/api/query/search", data={"keyword": "M001", "warehouse": "仓库A"})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "success", body
        assert len(body["data"]) == 1
        assert body["data"][0]["stock"] == 8.0, body["data"][0]

    def test_cross_warehouse_stock_not_leaked(self, client):
        """A 仓库 8 + B 仓库 3，查 A 时只能看到 A 的 8。"""
        with app_module.app.app_context():
            w1 = _seed_warehouse("W001", "仓库A")
            w2 = _seed_warehouse("W002", "仓库B")
            m = _seed_material("M001", "测试物料", stock=100)
            _enable_location_management()
            from app import LocationInventory
            db.session.add_all([
                LocationInventory(material_id=m.id, warehouse_id=w1.id, location="A1", quantity=8),
                LocationInventory(material_id=m.id, warehouse_id=w2.id, location="B1", quantity=3),
            ])
            db.session.commit()

        # 查仓库A：只能看到 8
        resp_a = client.post("/api/query/search", data={"keyword": "M001", "warehouse": "仓库A"})
        assert resp_a.status_code == 200
        body_a = resp_a.get_json()
        assert body_a["data"][0]["stock"] == 8.0, body_a["data"]

        # 查仓库B：只能看到 3
        resp_b = client.post("/api/query/search", data={"keyword": "M001", "warehouse": "仓库B"})
        assert resp_b.status_code == 200
        body_b = resp_b.get_json()
        assert body_b["data"][0]["stock"] == 3.0, body_b["data"]

    def test_warehouse_with_no_inventory_returns_zero_stock(self, client):
        """A 仓库有 8，B 仓库没有，查 B 必须返回 0（而非全局 100）。"""
        with app_module.app.app_context():
            w1 = _seed_warehouse("W001", "仓库A")
            w2 = _seed_warehouse("W002", "仓库B")
            m = _seed_material("M001", "测试物料", stock=100)
            _enable_location_management()
            from app import LocationInventory
            db.session.add(LocationInventory(
                material_id=m.id, warehouse_id=w1.id, location="A1", quantity=8,
            ))
            db.session.commit()

        resp = client.post("/api/query/search", data={"keyword": "M001", "warehouse": "仓库B"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"][0]["stock"] == 0.0, body["data"]


class TestApiQuerySearchWarehouseExistenceValidation:
    """INV-AUDIT-004：仓库不存在或已停用时拒绝查询。"""

    def test_nonexistent_warehouse_returns_400(self, client):
        with app_module.app.app_context():
            _seed_material("M001", "测试物料", stock=100)
        resp = client.post("/api/query/search", data={"keyword": "M001", "warehouse": "不存在的仓库"})
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["status"] == "error"
        assert "仓库不存在" in body["msg"]

    def test_inactive_warehouse_returns_400(self, client):
        with app_module.app.app_context():
            from app import Warehouse
            db.session.add(Warehouse(code="W001", name="停用仓", status="inactive", is_default=False))
            db.session.commit()
            _seed_material("M001", "测试物料", stock=100)
        resp = client.post("/api/query/search", data={"keyword": "M001", "warehouse": "停用仓"})
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["status"] == "error"
        assert "停用" in body["msg"]
