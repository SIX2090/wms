# -*- coding: utf-8 -*-
"""BUG-2026-09-03-002 回归：手机端物料接口"系统库存"展示按仓库级口径。

修复前：mobile_material_payload（mobile.py）的 stock 字段固定返回全局
Material.stock，locations 不过滤仓库。手机盘点/查询/扫码结果页显示的
"当前库存"是全仓合计——A 仓盘点时页面显示 A+B 总和（全局 100 而 A 仓
只有 10），误导盘点员以为实盘短缺，且与后端实际使用的仓库级账面
（INV-AUDIT-003-FIX-01 / BUG-2026-09-02-001）不一致。

修复后：mobile_material_payload 支持 warehouse 参数（对象或仓库名/编码）：
- 传入仓库 → stock 取 get_warehouse_stock_quantities(该仓)；开启库位管理时
  locations 只返回该仓库位（含历史 NULL warehouse_id 兼容行）。
- 未传仓库（未选仓库的查询/识物场景）→ 保持全局库存展示，向后兼容。
已接入：/mobile/api/material_lookup 可选 warehouse 查询参数；/mobile/api/
scan_submit mode=query（请求带仓库时）与 in/out/check 成功响应。

覆盖：
T1. lookup?warehouse=A仓 → stock=10（全局 100）
T2. lookup 不带 warehouse → stock=100（全局展示兼容）
T3. lookup warehouse=仓库编码 WA → 解析为 A 仓库存 10
T4. scan_submit mode=query + warehouse → 仓库级
T5. scan_submit in 成功响应 material.stock=A 仓加库后数量，非全局口径
T6. 开启库位管理双仓：lookup A 仓 locations 只含 A 仓库位、stock 按 A 仓
T7. 传入无效仓库 → 忽略并回退全局（不报错）
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
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


def _login_web(client):
    r = client.post("/login", data={"username": "admin", "password": "admin"})
    assert r.status_code in (302, 303), f"Web 登录失败：{r.status_code}"


def _seed_admin():
    from app import User
    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    db.session.commit()


def _seed_warehouse(code, name):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active")
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material(code="M001", global_stock=100.0):
    from app import Material, Unit
    unit = Unit.query.first()
    if not unit:
        unit = Unit(code="U1", name="个")
        db.session.add(unit)
        db.session.commit()
    m = Material(code=code, name=f"物料{code}", stock=global_stock, price=5, unit=unit)
    db.session.add(m)
    db.session.commit()
    return m


def _seed_txn_stock(material, warehouse, qty):
    """关库位管理：按 warehouse_id 归属的库存流水。"""
    from app import StockTransaction
    db.session.add(StockTransaction(
        material_id=material.id, transaction_type="in", quantity=qty,
        location=warehouse.name, warehouse_id=warehouse.id, created_at=datetime.now()))
    db.session.commit()


def _seed_location_stock(material, warehouse, location, qty):
    """开库位管理：LocationInventory 行。"""
    from app import LocationInventory
    db.session.add(LocationInventory(
        material_id=material.id, warehouse_id=warehouse.id,
        location=location, quantity=qty))
    db.session.commit()


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
    c = app_module.app.test_client()
    _login_web(c)
    yield c


def _scene_non_location():
    """关库位管理：M001 全局 100，A仓 10、B仓 40。"""
    with app_module.app.app_context():
        m = _seed_material("M001", 100.0)
        wa = _seed_warehouse("WA", "A仓")
        wb = _seed_warehouse("WB", "B仓")
        _seed_txn_stock(m, wa, 10)
        _seed_txn_stock(m, wb, 40)
    return m, wa


class TestLookupDisplayWarehouseStock:
    def test_t1_lookup_with_warehouse_returns_warehouse_stock(self, client):
        _scene_non_location()
        r = client.get("/mobile/api/material_lookup?code=M001&warehouse=A仓")
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert data["stock"] == 10.0, "带仓库查询必须返回 A 仓账面 10，而非全局 100"
        assert data["code"] == "M001"

    def test_t2_lookup_without_warehouse_keeps_global(self, client):
        _scene_non_location()
        r = client.get("/mobile/api/material_lookup?code=M001")
        assert r.status_code == 200
        assert r.get_json()["data"]["stock"] == 100.0, "未传仓库时保持全局展示（向后兼容）"

    def test_t3_lookup_with_warehouse_code_alias(self, client):
        _scene_non_location()
        r = client.get("/mobile/api/material_lookup?code=M001&warehouse=WA")
        assert r.status_code == 200
        assert r.get_json()["data"]["stock"] == 10.0, "仓库编码也应解析为 A 仓账面"

    def test_t7_invalid_warehouse_falls_back(self, client):
        _scene_non_location()
        r = client.get("/mobile/api/material_lookup?code=M001&warehouse=不存在的仓")
        assert r.status_code == 200
        assert r.get_json()["data"]["stock"] == 100.0, "无效仓库应忽略并回退全局，不报错"


class TestScanSubmitDisplayWarehouseStock:
    def test_t4_query_mode_with_warehouse(self, client):
        _scene_non_location()
        r = client.post("/mobile/api/scan_submit",
                        json={"mode": "query", "code": "M001", "warehouse": "A仓"})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json()["data"]["material"]["stock"] == 10.0

    def test_t5_in_response_stock_is_warehouse_scoped(self, client):
        _scene_non_location()
        # A 仓账面 10；入库 5 后 A 仓账面应为 15，而全局是 105
        r = client.post("/mobile/api/scan_submit",
                        json={"mode": "in", "code": "M001", "quantity": 5, "warehouse": "A仓", "location": "A仓"})
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert body["status"] == "success", body
        stock = body["data"]["material"]["stock"]
        assert stock == 15.0, f"入库成功响应的库存应为 A 仓仓库级 15，实际 {stock}"
        assert stock != 105.0, "不得返回全局口径 105"

    def test_t6_locations_filtered_by_warehouse(self, client):
        """开启库位管理：lookup A 仓只返回 A 仓库位，stock 按 A 仓汇总。"""
        with app_module.app.app_context():
            from app import set_system_setting
            m = _seed_material("M001", 100.0)
            wa = _seed_warehouse("WA", "A仓")
            wb = _seed_warehouse("WB", "B仓")
            _seed_location_stock(m, wa, "A1", 6)
            _seed_location_stock(m, wa, "A2", 4)
            _seed_location_stock(m, wb, "B1", 40)
            set_system_setting("location_management_enabled", "1")
            set_system_setting("location_required_on_save", "1")
            db.session.commit()
        r = client.get("/mobile/api/material_lookup?code=M001&warehouse=A仓")
        assert r.status_code == 200
        data = r.get_json()["data"]
        assert data["stock"] == 10.0, "A 仓库位合计 10，而非全局 100"
        locs = {loc["location"]: loc["quantity"] for loc in data["locations"]}
        assert locs == {"A1": 6.0, "A2": 4.0}, f"locations 必须只含 A 仓库位：{locs}"
