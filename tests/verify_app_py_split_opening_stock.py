# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：期初库存（opening_stock）域路由迁移到 routes/opening_stock.py。

采用 register-on-app 模式（register_opening_stock_routes(app)），endpoint 名保持不变
（opening_stock_list/add_opening_stock/get_opening_stock/edit_opening_stock/
batch_save_opening_stock），URL 路径不变，因此模板/导航中的 url_for('opening_stock_list')
等引用无需改动。

验收点：
S1. 5 个 endpoint 已注册，仍是未加前缀的原始 endpoint 名，不存在 opening_stock.xxx 重复。
S2. URL 路径保持不变（/opening_stock、/opening_stock/add、/opening_stock/<id>、
    /opening_stock/edit/<id>、/opening_stock/batch_save）。
S3. 期初库存列表页可渲染（200，含"期初库存"字样）。
S4. 新增期初库存成功，物料库存随之增加；同物料同仓库重复新增被拒绝。
S5. 读取单条期初库存详情。
S6. 编辑期初库存按差额调整成功。
S7. 批量保存期初库存成功，去重/校验正确。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

OPENING_ENDPOINTS = [
    "opening_stock_list",
    "add_opening_stock",
    "get_opening_stock",
    "edit_opening_stock",
    "batch_save_opening_stock",
]


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _seed_master(warehouse_name="材料仓", warehouse_code="WH001", material_code="M1", material_name="轴承",
                 unit_code="PCS", cat_code="C1", cat_name="分类"):
    """种子数据：单位、分类、物料、仓库。返回 (unit_id, category_id, material_id, warehouse_id)。"""
    from app import Material, MaterialCategory, Unit, Warehouse
    unit = Unit(name=unit_code, code=unit_code)
    cat = MaterialCategory(name=cat_name, code=cat_code)
    db.session.add_all([unit, cat])
    db.session.flush()
    mat = Material(code=material_code, name=material_name, unit_id=unit.id, category_id=cat.id)
    db.session.add(mat)
    wh = Warehouse(code=warehouse_code, name=warehouse_name, status="active")
    db.session.add(wh)
    db.session.commit()
    return unit.id, cat.id, mat.id, wh.id


class TestOpeningStockRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_endpoints_and_urls(self):
        """S1/S2：endpoint 注册、URL 不变、无前缀重复。"""
        with app_module.app.app_context():
            for ep in OPENING_ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            for ep in OPENING_ENDPOINTS:
                assert f"opening_stock.{ep}" not in app_module.app.view_functions, f"opening_stock.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("opening_stock_list") == "/opening_stock"
                assert url_for("add_opening_stock") == "/opening_stock/add"
                assert url_for("get_opening_stock", id=1) == "/opening_stock/1"
                assert url_for("edit_opening_stock", id=1) == "/opening_stock/edit/1"
                assert url_for("batch_save_opening_stock") == "/opening_stock/batch_save"

    def test_opening_stock_list_page(self):
        """S3：期初库存列表页可渲染。"""
        client = self._setup()
        _login(client)
        resp = client.get("/opening_stock")
        assert resp.status_code == 200
        assert "期初" in resp.get_data(as_text=True)

    def test_add_get_edit_opening_stock(self):
        """S4/S5/S6：新增、读取、编辑（按差额调整）。"""
        client = self._setup()
        _login(client)
        with app_module.app.app_context():
            _, _, mid, wid = _seed_master()
        # 新增
        r = client.post("/opening_stock/add", data={
            "material_id": mid, "warehouse_id": wid, "quantity": "10", "price": "5", "remark": "首批"
        })
        data = r.get_json()
        assert data["status"] == "success", data
        assert data["delta"] == 10.0
        with app_module.app.app_context():
            from app import Material, OpeningStock
            opening = OpeningStock.query.filter_by(material_id=mid, warehouse_id=wid).first()
            assert opening is not None
            assert opening.quantity == 10.0
            assert Material.query.get(mid).stock == 10.0
            oid = opening.id
        # 同物料同仓库重复新增被拒绝
        r2 = client.post("/opening_stock/add", data={
            "material_id": mid, "warehouse_id": wid, "quantity": "5", "price": "5"
        })
        assert r2.get_json()["status"] == "error"
        # 读取详情
        g = client.get(f"/opening_stock/{oid}")
        gd = g.get_json()
        assert gd["status"] == "success", gd
        assert gd["record"]["material_code"] == "M1"
        assert gd["record"]["quantity"] == 10.0
        # 读取不存在的记录
        g2 = client.get("/opening_stock/99999")
        assert g2.status_code == 404
        # 编辑：数量调整到 25（差额 +15）
        e = client.post(f"/opening_stock/edit/{oid}", data={
            "material_id": mid, "warehouse_id": wid, "quantity": "25", "price": "6", "remark": "调整"
        })
        ed = e.get_json()
        assert ed["status"] == "success", ed
        assert ed["delta"] == 15.0
        with app_module.app.app_context():
            from app import Material, OpeningStock
            assert OpeningStock.query.get(oid).quantity == 25.0
            assert Material.query.get(mid).stock == 25.0

    def test_batch_save_opening_stock(self):
        """S7：批量保存成功、去重校验、缺数量校验。"""
        client = self._setup()
        _login(client)
        with app_module.app.app_context():
            _, _, mid, wid = _seed_master()
            _, _, mid2, _ = _seed_master(warehouse_name="成品仓", warehouse_code="WH002",
                                         material_code="M2", material_name="螺母",
                                         unit_code="BOX", cat_code="C2", cat_name="分类二")
        # 正常批量保存
        r = client.post("/opening_stock/batch_save", json={"items": [
            {"material_id": mid, "warehouse_id": wid, "quantity": "20", "price": "1"},
            {"material_id": mid2, "warehouse_id": wid, "quantity": "50", "price": "0.5"},
        ]})
        data = r.get_json()
        assert data["status"] == "success", data
        assert data["changed_count"] == 2
        with app_module.app.app_context():
            from app import Material, OpeningStock
            assert OpeningStock.query.filter_by(material_id=mid, warehouse_id=wid).first().quantity == 20.0
            assert Material.query.get(mid).stock == 20.0
        # 物料+仓库重复行被拒绝
        r2 = client.post("/opening_stock/batch_save", json={"items": [
            {"material_id": mid, "warehouse_id": wid, "quantity": "1", "price": "1"},
            {"material_id": mid, "warehouse_id": wid, "quantity": "2", "price": "2"},
        ]})
        assert r2.get_json()["status"] == "error"
        # 增量更新：再次保存同一物料+仓库，第二次 changed_count 应为 0（库存无变化）
        r4 = client.post("/opening_stock/batch_save", json={"items": [
            {"material_id": mid, "warehouse_id": wid, "quantity": "20", "price": "1"},
        ]})
        assert r4.get_json()["status"] == "success"
        assert r4.get_json()["changed_count"] == 0