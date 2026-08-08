# -*- coding: utf-8 -*-
"""
移动端识别单据确认生成入库草稿 API 回归测试（AI-MOB-OCR-F01）。

覆盖：
T1. POST /api/mobile/inbound_draft 端点注册。
T2. 有效匹配物料 + 仓库 -> 生成 pending 入库草稿，不直接加库存。
T3. 未匹配到建档物料的识别行 -> 拦截并返回 400。
T4. 未传仓库且无默认仓库 -> 返回 400。
T5. 空明细 / 数量非法(pydantic 校验) -> 返回 400。
T6. 未传仓库但有默认仓库 -> 自动带入默认仓库生成草稿。
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

API_ENDPOINTS = ["native_api_inbound_draft"]


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _bearer(client):
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


def _seed_warehouse(code, name, is_default=False):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active", is_default=is_default)
    db.session.add(w)
    db.session.commit()
    return w.id


def _seed_material(code, name, stock=0, price=5):
    from app import Material
    m = Material(code=code, name=name, stock=stock, price=price)
    db.session.add(m)
    db.session.commit()
    return m.id


class TestMobileInboundDraftApi:
    def _setup(self, default_warehouse=False):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_warehouse("MC", "材料仓", is_default=default_warehouse)
            _seed_warehouse("CP", "成品仓")
            _seed_material("M001", "6204轴承", stock=0, price=12.5)
            _seed_material("M002", "M8螺母", stock=0, price=0.5)
        return _make_client()

    def test_endpoints_registered(self):
        for ep in API_ENDPOINTS:
            assert ep in app_module.app.view_functions, f"{ep} 未注册"

    def test_create_draft(self):
        """T2：有效物料+仓库 -> pending 草稿，不直接加库存。"""
        client = self._setup()
        headers = _bearer(client)
        payload = {
            "business_type": "采购入库",
            "warehouse_code": "MC",
            "lines": [
                {"material_code": "M001", "quantity": 100, "price": 12.5},
                {"material_code": "M002", "quantity": 500},
            ],
        }
        r = client.post("/api/mobile/inbound_draft", json=payload, headers=headers)
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert body["status"] == "success", body
        assert body["data"]["status"] == "pending"
        assert body["data"]["order_no"].startswith("IN")
        assert len(body["data"]["items"]) == 2

        # 草稿不直接加库存
        with app_module.app.app_context():
            from app import InOrder, InOrderItem, Material
            order = InOrder.query.filter_by(order_no=body["data"]["order_no"]).first()
            assert order is not None
            assert order.status == "pending", order.status
            assert order.warehouse == "材料仓"
            assert InOrderItem.query.filter_by(in_order_id=order.id).count() == 2
            m1 = Material.query.filter_by(code="M001").first()
            assert m1.stock == 0, m1.stock

    def test_unmatched_blocked(self):
        """T3：未匹配物料 -> 拦截并返回 400。"""
        client = self._setup()
        headers = _bearer(client)
        payload = {
            "warehouse_code": "MC",
            "lines": [
                {"material_code": "M001", "quantity": 10},
                {"material_code": "NOPE", "quantity": 5},
            ],
        }
        r = client.post("/api/mobile/inbound_draft", json=payload, headers=headers)
        assert r.status_code == 400, r.get_data(as_text=True)
        assert "未建档" in r.get_json()["msg"]

    def test_missing_warehouse(self):
        """T4：未传仓库且无默认仓库 -> 400。"""
        client = self._setup(default_warehouse=False)
        headers = _bearer(client)
        payload = {"lines": [{"material_code": "M001", "quantity": 10}]}
        r = client.post("/api/mobile/inbound_draft", json=payload, headers=headers)
        assert r.status_code == 400, r.get_data(as_text=True)

    def test_default_warehouse(self):
        """T6：未传仓库但有默认仓库 -> 自动带入。"""
        client = self._setup(default_warehouse=True)
        headers = _bearer(client)
        payload = {"lines": [{"material_code": "M001", "quantity": 10}]}
        r = client.post("/api/mobile/inbound_draft", json=payload, headers=headers)
        assert r.status_code == 200, r.get_data(as_text=True)
        with app_module.app.app_context():
            from app import InOrder
            order = InOrder.query.filter_by(order_no=r.get_json()["data"]["order_no"]).first()
            assert order.warehouse == "材料仓"

    def test_validation(self):
        """T5：pydantic 校验（空明细/非法数量）-> 400。"""
        client = self._setup()
        headers = _bearer(client)
        # 空明细
        r = client.post("/api/mobile/inbound_draft", json={"lines": []}, headers=headers)
        assert r.status_code == 400
        # 数量为 0 或负
        r = client.post("/api/mobile/inbound_draft", json={
            "warehouse_code": "MC",
            "lines": [{"material_code": "M001", "quantity": 0}],
        }, headers=headers)
        assert r.status_code == 400


def main():
    import traceback
    t = TestMobileInboundDraftApi()
    methods = [
        "test_endpoints_registered",
        "test_create_draft",
        "test_unmatched_blocked",
        "test_missing_warehouse",
        "test_default_warehouse",
        "test_validation",
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