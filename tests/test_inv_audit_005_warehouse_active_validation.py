# -*- coding: utf-8 -*-
"""INV-AUDIT-005 回归测试：调拨/盘点/调整/普通出库/stocktake 仓库存在性 + active 校验。

修复前的 BUG：
- /transfer/save_table、/transfer/add、/check/save_table、/check/add、
  /adjustment/add、/out_order/add（领料单/其他出库）、/api/stocktake
  只校验仓库非空，不校验仓库存在与 active 状态，导致可选用已删除/已停用
  仓库创建库存单据。

修复后：
- 新增 resolve_active_inventory_warehouse / validate_inventory_warehouse
  统一仓库解析（与销售出库对称）。
- 各库存单据保存接口在仓库非空校验后追加存在性 + active 校验。
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


def _seed_warehouse(code, name, is_default=False, status="active"):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status=status, is_default=is_default)
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material(code="M001", name="测试物料", stock=100):
    from app import Material, Unit
    unit = Unit.query.first()
    if not unit:
        unit = Unit(code="U1", name="个")
        db.session.add(unit)
        db.session.commit()
    m = Material(code=code, name=name, stock=stock, price=5, unit=unit)
    db.session.add(m)
    db.session.commit()
    return m


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
        # 默认存在一个 active 仓库
        _seed_warehouse("W001", "默认仓", is_default=True)
        _seed_material("M001", "测试物料", stock=100)
    c = app_module.app.test_client()
    _login(c)
    yield c


class TestValidateInventoryWarehouseHelper:
    """INV-AUDIT-005：resolve_active_inventory_warehouse / validate_inventory_warehouse
    辅助函数行为。"""

    def test_resolve_active_inventory_warehouse(self):
        """A9 入口：覆盖 resolve_active_inventory_warehouse 主路径（按名/编码/ID 解析 + active 过滤）。"""
        from app import resolve_active_inventory_warehouse
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w = _seed_warehouse("W001", "材料仓")
            # 按名解析
            assert resolve_active_inventory_warehouse("材料仓").id == w.id
            # 按编码解析
            assert resolve_active_inventory_warehouse("W001").id == w.id
            # 按 ID 解析
            assert resolve_active_inventory_warehouse(warehouse_id=w.id).id == w.id
            # 不存在 / 停用 / 空值
            assert resolve_active_inventory_warehouse("不存在的仓") is None
            assert resolve_active_inventory_warehouse(None) is None
            _seed_warehouse("W002", "停用仓", status="inactive")
            assert resolve_active_inventory_warehouse("停用仓") is None

    def test_validate_inventory_warehouse(self):
        """A9 入口：覆盖 validate_inventory_warehouse 主路径（成功/不存在/停用）。"""
        from app import validate_inventory_warehouse
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w = _seed_warehouse("W001", "材料仓")
            # active 仓库：返回对象 + None 错误
            wh, err = validate_inventory_warehouse("材料仓")
            assert err is None
            assert wh.id == w.id
            # 不存在：返回 (None, 错误信息)
            wh, err = validate_inventory_warehouse("不存在的仓")
            assert wh is None
            assert "不存在" in err
            # 停用：返回 (None, 错误信息)
            _seed_warehouse("W002", "停用仓", status="inactive")
            wh, err = validate_inventory_warehouse("停用仓")
            assert wh is None
            assert "停用" in err

    def test_resolve_active_inventory_warehouse_by_name(self):
        from app import resolve_active_inventory_warehouse
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w = _seed_warehouse("W001", "材料仓")
            result = resolve_active_inventory_warehouse("材料仓")
            assert result is not None
            assert result.id == w.id

    def test_resolve_active_inventory_warehouse_by_code(self):
        from app import resolve_active_inventory_warehouse
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w = _seed_warehouse("W001", "材料仓")
            result = resolve_active_inventory_warehouse("W001")
            assert result is not None
            assert result.id == w.id

    def test_resolve_active_inventory_warehouse_by_id(self):
        from app import resolve_active_inventory_warehouse
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w = _seed_warehouse("W001", "材料仓")
            result = resolve_active_inventory_warehouse(warehouse_id=w.id)
            assert result is not None
            assert result.id == w.id

    def test_resolve_active_inventory_warehouse_inactive_returns_none(self):
        from app import resolve_active_inventory_warehouse
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_warehouse("W001", "停用仓", status="inactive")
            assert resolve_active_inventory_warehouse("停用仓") is None

    def test_resolve_active_inventory_warehouse_nonexistent_returns_none(self):
        from app import resolve_active_inventory_warehouse
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            assert resolve_active_inventory_warehouse("不存在的仓") is None

    def test_validate_inventory_warehouse_returns_error_for_inactive(self):
        from app import validate_inventory_warehouse
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_warehouse("W001", "停用仓", status="inactive")
            wh, err = validate_inventory_warehouse("停用仓")
            assert wh is None
            assert err is not None
            assert "停用" in err

    def test_validate_inventory_warehouse_returns_error_for_nonexistent(self):
        from app import validate_inventory_warehouse
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            wh, err = validate_inventory_warehouse("不存在的仓")
            assert wh is None
            assert err is not None
            assert "不存在" in err

    def test_validate_inventory_warehouse_returns_obj_for_active(self):
        from app import validate_inventory_warehouse
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w = _seed_warehouse("W001", "材料仓")
            wh, err = validate_inventory_warehouse("材料仓")
            assert err is None
            assert wh is not None
            assert wh.id == w.id


class TestTransferWarehouseActiveValidation:
    """INV-AUDIT-005：/transfer/save_table 与 /transfer/add 必须拒绝不存在的仓库。"""

    def test_save_table_rejects_nonexistent_from_warehouse(self, client):
        resp = client.post("/transfer/save_table", json={
            "order_no": "TF001",
            "header": {"from_warehouse": "不存在的仓", "to_warehouse": "默认仓"},
            "items": [{"code": "M001", "quantity": 1, "unit_id": 1}],
        })
        assert resp.status_code in (200, 400)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "不存在" in body["msg"] or "停用" in body["msg"]

    def test_save_table_rejects_nonexistent_to_warehouse(self, client):
        resp = client.post("/transfer/save_table", json={
            "order_no": "TF001",
            "header": {"from_warehouse": "默认仓", "to_warehouse": "不存在的仓"},
            "items": [{"code": "M001", "quantity": 1, "unit_id": 1}],
        })
        assert resp.status_code in (200, 400)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "不存在" in body["msg"] or "停用" in body["msg"]

    def test_save_table_rejects_inactive_warehouse(self, client):
        with app_module.app.app_context():
            _seed_warehouse("W002", "停用仓", status="inactive")
        resp = client.post("/transfer/save_table", json={
            "order_no": "TF001",
            "header": {"from_warehouse": "停用仓", "to_warehouse": "默认仓"},
            "items": [{"code": "M001", "quantity": 1, "unit_id": 1}],
        })
        assert resp.status_code in (200, 400)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "停用" in body["msg"]

    def test_add_rejects_nonexistent_warehouse(self, client):
        resp = client.post("/transfer/add", data={
            "from_warehouse": "不存在的仓",
            "to_warehouse": "默认仓",
        })
        assert resp.status_code in (200, 400)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "不存在" in body["msg"] or "停用" in body["msg"]


class TestCheckWarehouseActiveValidation:
    """INV-AUDIT-005：/check/save_table 与 /check/add 必须拒绝不存在的仓库。"""

    def test_save_table_rejects_nonexistent_warehouse(self, client):
        resp = client.post("/check/save_table", json={
            "order_no": "CK001",
            "header": {"warehouse": "不存在的仓"},
            "items": [{"code": "M001", "system_stock": 100, "actual_stock": 100, "unit_id": 1}],
        })
        assert resp.status_code in (200, 400)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "不存在" in body["msg"] or "停用" in body["msg"]

    def test_save_table_rejects_inactive_warehouse(self, client):
        with app_module.app.app_context():
            _seed_warehouse("W002", "停用仓", status="inactive")
        resp = client.post("/check/save_table", json={
            "order_no": "CK001",
            "header": {"warehouse": "停用仓"},
            "items": [{"code": "M001", "system_stock": 100, "actual_stock": 100, "unit_id": 1}],
        })
        assert resp.status_code in (200, 400)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "停用" in body["msg"]

    def test_add_rejects_nonexistent_warehouse(self, client):
        resp = client.post("/check/add", data={"warehouse": "不存在的仓"})
        assert resp.status_code in (200, 400)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "不存在" in body["msg"] or "停用" in body["msg"]


class TestAdjustmentWarehouseActiveValidation:
    """INV-AUDIT-005：/adjustment/add 必须拒绝不存在的仓库。"""

    def test_add_rejects_nonexistent_warehouse(self, client):
        resp = client.post("/adjustment/add", json={
            "adjustment_type": "surplus",
            "warehouse": "不存在的仓",
            "items": [{"code": "M001", "quantity": 1, "unit_id": 1}],
        })
        assert resp.status_code in (200, 400)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "不存在" in body["msg"] or "停用" in body["msg"]

    def test_add_rejects_inactive_warehouse(self, client):
        with app_module.app.app_context():
            _seed_warehouse("W002", "停用仓", status="inactive")
        resp = client.post("/adjustment/add", json={
            "adjustment_type": "surplus",
            "warehouse": "停用仓",
            "items": [{"code": "M001", "quantity": 1, "unit_id": 1}],
        })
        assert resp.status_code in (200, 400)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "停用" in body["msg"]


class TestOutOrderWarehouseActiveValidation:
    """INV-AUDIT-005：/out_order/add 领料单/其他出库必须拒绝不存在的仓库。"""

    def test_add_rejects_nonexistent_warehouse(self, client):
        resp = client.post("/out_order/add", json={
            "warehouse": "不存在的仓",
            "business_type": "领料单",
            "items": [{"code": "M001", "quantity": 1, "unit_id": 1}],
        })
        assert resp.status_code in (200, 400)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "不存在" in body["msg"] or "停用" in body["msg"]

    def test_add_rejects_inactive_warehouse(self, client):
        with app_module.app.app_context():
            _seed_warehouse("W002", "停用仓", status="inactive")
        resp = client.post("/out_order/add", json={
            "warehouse": "停用仓",
            "business_type": "领料单",
            "items": [{"code": "M001", "quantity": 1, "unit_id": 1}],
        })
        assert resp.status_code in (200, 400)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "停用" in body["msg"]


class TestApiStocktakeWarehouseActiveValidation:
    """INV-AUDIT-005：/api/stocktake 必须拒绝不存在的仓库。"""

    def _make_token(self):
        from datetime import datetime
        from app import ApiToken
        with app_module.app.app_context():
            token = ApiToken(
                token="test-token-005",
                user_id=1,
                expires_at=datetime.now() + app_module.timedelta(days=7),
                revoked=False,
            )
            db.session.add(token)
            db.session.commit()
        return "test-token-005"

    def test_stocktake_rejects_nonexistent_warehouse(self, client):
        token = self._make_token()
        resp = client.post(
            "/api/stocktake",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "warehouse": "不存在的仓",
                "lines": [{"material_code": "M001", "actual_stock": 100}],
            },
        )
        assert resp.status_code in (200, 400)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "不存在" in body["msg"] or "停用" in body["msg"]

    def test_stocktake_rejects_inactive_warehouse(self, client):
        with app_module.app.app_context():
            _seed_warehouse("W002", "停用仓", status="inactive")
        token = self._make_token()
        resp = client.post(
            "/api/stocktake",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "warehouse": "停用仓",
                "lines": [{"material_code": "M001", "actual_stock": 100}],
            },
        )
        assert resp.status_code in (200, 400)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "停用" in body["msg"]
