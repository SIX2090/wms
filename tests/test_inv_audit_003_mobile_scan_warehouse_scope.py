# -*- coding: utf-8 -*-
"""INV-AUDIT-003 回归测试：移动扫码入库/出库/盘点必须执行仓库必填
和仓库级库存规则（AGENTS.md 规则一/规则二）。

修复前的 BUG：
1. /mobile/api/scan_submit 未强制仓库必填，前端不传 warehouse 时直接用
   全局 Material.stock 完成出入库。
2. 出库库存校验使用全局 Material.stock，跨仓库存可见。
3. 盘点 system_stock 使用全局 Material.stock，跨仓差异会被错误归零。
4. update_location_inventory 调用未传 warehouse，导致库位库存写入无
   warehouse_id 维度，跨仓同名库位被合并。

修复后：
- 仓库始终必填，未提供时回退默认仓库；无默认仓库则拒绝。
- 出库库存校验改用 get_warehouse_stock_quantities(warehouse)。
- 盘点 system_stock 改用 get_warehouse_stock_quantities(warehouse)。
- update_location_inventory 调用传入 warehouse 对象，写入 warehouse_id。
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


def _seed_material(code, name, stock=0, price=5):
    from app import Material, Unit
    unit = Unit.query.first()
    if not unit:
        unit = Unit(code="U1", name="个")
        db.session.add(unit)
        db.session.commit()
    m = Material(code=code, name=name, stock=stock, price=price, unit=unit)
    db.session.add(m)
    db.session.commit()
    return m


def _enable_location_management():
    from app import set_system_setting
    set_system_setting("location_management_enabled", "1")
    set_system_setting("location_required_on_save", "1")
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


class TestMobileScanSubmitWarehouseRequired:
    """INV-AUDIT-003：仓库始终必填（无默认仓库时拒绝保存）。"""

    def test_in_without_warehouse_and_no_default_rejected(self, client):
        """无仓库参数且无默认仓库时，in 模式必须 400。"""
        with app_module.app.app_context():
            _seed_material("M001", "测试物料", stock=10)
        resp = client.post(
            "/mobile/api/scan_submit",
            json={"mode": "in", "code": "M001", "quantity": 3},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["status"] == "error"
        assert "仓库" in body["msg"]

    def test_out_without_warehouse_and_no_default_rejected(self, client):
        """无仓库参数且无默认仓库时，out 模式必须 400。"""
        with app_module.app.app_context():
            _seed_material("M001", "测试物料", stock=10)
        resp = client.post(
            "/mobile/api/scan_submit",
            json={"mode": "out", "code": "M001", "quantity": 1},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["status"] == "error"
        assert "仓库" in body["msg"]

    def test_in_falls_back_to_default_warehouse(self, client):
        """未传 warehouse 时自动带入默认仓库。"""
        with app_module.app.app_context():
            _seed_warehouse("W001", "默认仓", is_default=True)
            _seed_material("M001", "测试物料", stock=10)
        resp = client.post(
            "/mobile/api/scan_submit",
            json={"mode": "in", "code": "M001", "quantity": 3},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "success", body
        from app import InOrder
        with app_module.app.app_context():
            order = InOrder.query.first()
            assert order is not None
            assert order.warehouse == "默认仓"


class TestMobileScanSubmitWarehouseLevelStock:
    """INV-AUDIT-003：出库/盘点使用仓库级库存而非全局 Material.stock。"""

    def test_out_uses_warehouse_level_stock(self, client):
        """物料全局库存充足但目标仓库库存为 0 时，出库必须拒绝。"""
        with app_module.app.app_context():
            w1 = _seed_warehouse("W001", "仓库A")
            w2 = _seed_warehouse("W002", "仓库B")
            m = _seed_material("M001", "测试物料", stock=100)
            # 库存只在仓库A，仓库B 没有
            from app import LocationInventory, set_system_setting
            set_system_setting("location_management_enabled", "1")
            db.session.commit()
            db.session.add(LocationInventory(
                material_id=m.id, warehouse_id=w1.id, location="仓库A", quantity=100,
            ))
            db.session.commit()

        resp = client.post(
            "/mobile/api/scan_submit",
            json={
                "mode": "out", "code": "M001", "quantity": 5,
                "warehouse": "仓库B", "location": "仓库B-A1",
            },
        )
        # 仓库B 库存为 0，必须拒绝
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["status"] == "error"
        assert "仓库B" in body["msg"] or "库存不足" in body["msg"]

    def test_check_uses_warehouse_level_system_stock(self, client):
        """盘点 system_stock 来自仓库级库存，差异按仓库级计算。"""
        with app_module.app.app_context():
            w1 = _seed_warehouse("W001", "仓库A")
            w2 = _seed_warehouse("W002", "仓库B")
            m = _seed_material("M001", "测试物料", stock=100)
            from app import LocationInventory, set_system_setting
            set_system_setting("location_management_enabled", "1")
            db.session.commit()
            # 仓库A 有 8，仓库B 有 3，全局 stock=100（旧值）
            db.session.add_all([
                LocationInventory(material_id=m.id, warehouse_id=w1.id, location="A1", quantity=8),
                LocationInventory(material_id=m.id, warehouse_id=w2.id, location="B1", quantity=3),
            ])
            # INV-BATCH-001-E：预置仓库B 进行中盘点单供选单
            from app import InventoryCheck
            chk = InventoryCheck(check_no="CK-MOB-AUDIT3", warehouse="仓库B", status="pending")
            db.session.add(chk)
            db.session.commit()
            batch_id = chk.id

        # 盘点仓库B 实际 3，应该无差异（system_stock=3, actual=3）
        resp = client.post(
            "/mobile/api/scan_submit",
            json={
                "mode": "check", "code": "M001", "actual_stock": 3,
                "warehouse": "仓库B", "location": "B1", "check_id": batch_id,
            },
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "success", body
        from app import InventoryCheckScanItem
        with app_module.app.app_context():
            item = InventoryCheckScanItem.query.first()
            assert item is not None
            # 仓库级 system_stock 应为 3，而非全局 100
            assert item.system_stock == 3.0
            assert item.difference == 0.0


class TestMobileScanSubmitLocationWarehouseIdPropagation:
    """INV-AUDIT-003：扫码出入库写 LocationInventory 时必须带 warehouse_id。"""

    def test_in_writes_warehouse_id_to_location_inventory(self, client):
        with app_module.app.app_context():
            w = _seed_warehouse("W001", "仓库A")
            warehouse_id = w.id
            _seed_material("M001", "测试物料", stock=0)
            _enable_location_management()

        resp = client.post(
            "/mobile/api/scan_submit",
            json={
                "mode": "in", "code": "M001", "quantity": 5,
                "warehouse": "仓库A", "location": "A1",
            },
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "success", body

        from app import LocationInventory
        with app_module.app.app_context():
            rows = LocationInventory.query.all()
            assert len(rows) == 1
            assert rows[0].warehouse_id == warehouse_id
            assert rows[0].location == "A1"
            assert rows[0].quantity == 5.0

    def test_out_writes_warehouse_id_to_location_inventory(self, client):
        with app_module.app.app_context():
            w = _seed_warehouse("W001", "仓库A")
            warehouse_id = w.id
            m = _seed_material("M001", "测试物料", stock=10)
            _enable_location_management()
            from app import LocationInventory
            db.session.add(LocationInventory(
                material_id=m.id, warehouse_id=warehouse_id, location="A1", quantity=10,
            ))
            db.session.commit()

        resp = client.post(
            "/mobile/api/scan_submit",
            json={
                "mode": "out", "code": "M001", "quantity": 4,
                "warehouse": "仓库A", "location": "A1",
            },
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "success", body

        from app import LocationInventory
        with app_module.app.app_context():
            rows = LocationInventory.query.all()
            assert len(rows) == 1
            assert rows[0].warehouse_id == warehouse_id
            assert rows[0].location == "A1"
            assert rows[0].quantity == 6.0
