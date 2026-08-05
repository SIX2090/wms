# -*- coding: utf-8 -*-
"""
移动端期初库存 API 回归测试（AI-OS-APP-001）。

覆盖：
S1. GET /api/warehouses 返回启用的仓库列表。
S2. GET /api/opening_stock 期初库存列表（可按仓库筛选）。
S3. POST /api/opening_stock 期初建账：选择日期+仓库，扫码物料行，库存随之增加。
S4. POST 校验：缺仓库、物料不存在、数量为负均返回 4xx。
S5. 同物料同仓库二次提交按差额调整，不产生 500。
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

API_ENDPOINTS = [
    "native_api_warehouses",
    "native_api_opening_stock_list",
    "native_api_opening_stock_submit",
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


def _bearer(client):
    """通过 /api/login 获取 Bearer Token，返回 Authorization 头。"""
    r = client.post("/api/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, r.get_data(as_text=True)
    token = r.get_json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _seed_warehouse(code, name):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active")
    db.session.add(w)
    db.session.commit()
    return w.id


def _seed_material(code, name, stock=0, price=5):
    from app import Material
    m = Material(code=code, name=name, stock=stock, price=price)
    db.session.add(m)
    db.session.commit()
    return m.id


class TestMobileOpeningStockApi:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_warehouse("MC", "材料仓")
            _seed_warehouse("CP", "成品仓")
            _seed_material("M001", "6204轴承", price=12.5)
            _seed_material("M002", "M8螺母", price=0.5)
        return _make_client()

    def test_endpoints_registered(self):
        for ep in API_ENDPOINTS:
            assert ep in app_module.app.view_functions, f"{ep} 未注册"

    def test_get_warehouses(self):
        """S1：GET /api/warehouses 返回启用仓库。"""
        client = self._setup()
        _login(client)
        r = client.get("/api/warehouses")
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]["items"]
        codes = {w["code"] for w in data}
        assert "MC" in codes and "CP" in codes

    def test_submit_opening_stock(self):
        """S3：POST /api/opening_stock 建账成功，库存增加。"""
        client = self._setup()
        headers = _bearer(client)
        payload = {
            "date": "2023-01-01",
            "warehouse_code": "MC",
            "lines": [
                {"material_code": "M001", "quantity": 100, "price": 12.5},
                {"material_code": "M002", "quantity": 500},
            ],
        }
        r = client.post("/api/opening_stock", json=payload, headers=headers)
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert body["status"] == "success", body
        assert body["data"]["count"] == 2

        # 库存增加
        with app_module.app.app_context():
            from app import Material
            m1 = Material.query.filter_by(code="M001").first()
            m2 = Material.query.filter_by(code="M002").first()
            assert m1.stock == 100, m1.stock
            assert m2.stock == 500, m2.stock

        # 列表返回（带 Bearer 头）
        r2 = client.get("/api/opening_stock?warehouse_id=1", headers=headers)
        assert r2.status_code == 200
        items = r2.get_json()["data"]["items"]
        assert len(items) == 2
        assert any(i["material_code"] == "M001" and i["date"] == "2023-01-01" for i in items)

    def test_submit_validation(self):
        """S4：缺仓库 / 物料不存在 / 数量为负均返回 4xx。"""
        client = self._setup()
        headers = _bearer(client)
        # 缺仓库
        r = client.post("/api/opening_stock", json={"lines": [{"material_code": "M001", "quantity": 1}]}, headers=headers)
        assert r.status_code == 400
        # 物料不存在
        r = client.post("/api/opening_stock", json={
            "warehouse_code": "MC",
            "lines": [{"material_code": "NOPE", "quantity": 1}],
        }, headers=headers)
        assert r.status_code == 400
        # 数量为负
        r = client.post("/api/opening_stock", json={
            "warehouse_code": "MC",
            "lines": [{"material_code": "M001", "quantity": -5}],
        }, headers=headers)
        assert r.status_code == 400

    def test_submit_adjust_delta(self):
        """S5：同物料同仓库二次提交按差额调整。"""
        client = self._setup()
        headers = _bearer(client)
        base = {"warehouse_code": "MC", "lines": [{"material_code": "M001", "quantity": 100}]}
        r1 = client.post("/api/opening_stock", json=base, headers=headers)
        assert r1.status_code == 200
        # 第二次改为 150，应为差额 +50
        r2 = client.post("/api/opening_stock", json={
            "warehouse_code": "MC",
            "lines": [{"material_code": "M001", "quantity": 150}],
        }, headers=headers)
        assert r2.status_code == 200, r2.get_data(as_text=True)
        with app_module.app.app_context():
            from app import Material
            m1 = Material.query.filter_by(code="M001").first()
            assert m1.stock == 150, m1.stock


def main():
    import traceback
    t = TestMobileOpeningStockApi()
    methods = [
        "test_endpoints_registered",
        "test_get_warehouses",
        "test_submit_opening_stock",
        "test_submit_validation",
        "test_submit_adjust_delta",
    ]
    failed = 0
    for name in methods:
        print(f"[RUN] {name}")
        try:
            getattr(t, name)()
            print("  OK")
        except Exception:
            failed += 1
            traceback.print_exc()
    print(f"\n{len(methods) - failed}/{len(methods)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())