# -*- coding: utf-8 -*-
"""
移动端期初库存 API 回归测试（AI-OS-APP-001）。

覆盖：
S1. GET /api/warehouses 返回启用的仓库列表。
S2. GET /api/opening_stock 期初库存列表（可按仓库筛选）。
S3. POST /api/opening_stock 期初建账：选择日期+仓库，扫码物料行，库存随之增加。
S4. POST 校验：缺仓库、物料不存在、数量为负均返回 4xx。
S5. 同物料同仓库二次提交按差额调整，不产生 500。
S6. 移动端提交的明细行必须归入 QSLEGACY 兼容单，且 PC 单据列表可见（BUG-2026-09-16-009）。
S7. 历史 doc_id=NULL 悬空行在移动端再次提交时被收养进兼容单。
S8. 静态契约：提交链路必须向入账函数传 doc_id。
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

    def test_submit_lines_attached_to_doc(self):
        """S6（BUG-2026-09-16-009）：移动端提交的明细行必须归入单据——

        此前漏传 doc_id，行 doc_id=NULL，PC 单据列表/首上下末导航永远
        找不到（跨端黑洞）。现与 batch_save 兼容分支同口径归 QSLEGACY 单。
        """
        client = self._setup()
        headers = _bearer(client)
        r = client.post("/api/opening_stock", json={
            "date": "2026-09-16",
            "warehouse_code": "MC",
            "lines": [{"material_code": "M001", "quantity": 100}],
        }, headers=headers)
        assert r.status_code == 200, r.get_data(as_text=True)
        with app_module.app.app_context():
            from app import OpeningStock, OpeningStockDoc
            line = OpeningStock.query.first()
            assert line is not None
            assert line.doc_id is not None, "移动端提交的明细行 doc_id 仍为 NULL"
            doc = OpeningStockDoc.query.get(line.doc_id)
            assert doc is not None
            assert doc.doc_no.startswith("QSLEGACY"), doc.doc_no
        # PC 端单据列表必须能看到这张兼容单（跨端可见性闭环）
        _login(client)
        r2 = client.get("/opening_stock")
        assert r2.status_code == 200
        assert "QSLEGACY" in r2.get_data(as_text=True)

    def test_submit_adopts_legacy_null_doc_lines(self):
        """S7（BUG-2026-09-16-009）：历史 doc_id=NULL 直连行在移动端再次
        提交同 (物料,仓库) 时被收养进兼容单（_apply_opening_stock_balance
        既有归单逻辑），不留悬空行。"""
        client = self._setup()
        with app_module.app.app_context():
            from app import Material, OpeningStock, Warehouse
            m = Material.query.filter_by(code="M001").first()
            w = Warehouse.query.filter_by(code="MC").first()
            db.session.add(OpeningStock(
                doc_id=None, material_id=m.id, warehouse_id=w.id,
                quantity=10, price=1, amount=10))
            db.session.commit()
        headers = _bearer(client)
        r = client.post("/api/opening_stock", json={
            "warehouse_code": "MC",
            "lines": [{"material_code": "M001", "quantity": 20}],
        }, headers=headers)
        assert r.status_code == 200, r.get_data(as_text=True)
        with app_module.app.app_context():
            from app import OpeningStock
            line = OpeningStock.query.first()
            assert line.doc_id is not None, "历史悬空行未被收养进单据"
            assert line.quantity == 20

    def test_static_submit_passes_doc_id(self):
        """S8（静态契约）：native_api 期初提交必须向 _apply_opening_stock_balance
        传 doc_id——防止后续重构再次漏参退回跨端黑洞。"""
        src = (ROOT / "app" / "routes" / "native_api.py").read_text(encoding="utf-8")
        assert "_opening_stock_compat_doc(" in src, "移动端提交未取兼容单"
        assert "doc_id=compat_doc.id" in src, "移动端提交未把兼容单 id 传给入账函数"


def main():
    import traceback
    t = TestMobileOpeningStockApi()
    methods = [
        "test_endpoints_registered",
        "test_get_warehouses",
        "test_submit_opening_stock",
        "test_submit_validation",
        "test_submit_adjust_delta",
        "test_submit_lines_attached_to_doc",
        "test_submit_adopts_legacy_null_doc_lines",
        "test_static_submit_passes_doc_id",
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