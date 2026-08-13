# -*- coding: utf-8 -*-
"""
BUG-2026-08-13-002 回归测试：scan_submit 支持 Bearer Token。

旧实现 scan_submit 用 @require_role('warehouse')+@login_required，两者只
认 Flask-Login current_user，原生 App 使用 Bearer Token 一律 401，功能阻断。

覆盖：
T1. warehouse Bearer + mode=in 成功落库，operator_id 正确。
T2. warehouse Bearer + mode=out 成功。
T3. warehouse Bearer + mode=check 成功。
T4. warehouse Bearer + mode=query 成功（无操作人权限判定）。
T5. user Bearer -> 403。
T6. 无 Auth -> 401。
T7. admin Web 会话 mode=in 回归 PASS。
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, date
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
from app import (  # noqa: E402
    ApiToken, InOrder, Material, OutOrder, InventoryCheckScan,
    User, Warehouse, db,
)
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False
app_module.app.config["DISABLE_STOCK_SAVE_REQUIRED_WAREHOUSE"] = True


def _seed_user(role: str) -> User:
    u = User(username=f"scan_{role}", role=role,
             password_hash=generate_password_hash("x"),
             status="normal", must_change_password=False)
    db.session.add(u)
    db.session.commit()
    return u


def _seed_token(user: User) -> ApiToken:
    t = ApiToken(
        token=f"stok_{user.id}_{os.urandom(4).hex()}",
        user_id=user.id,
        expires_at=datetime.now() + app_module.timedelta(days=7),
        revoked=False,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _ensure_warehouse():
    w = Warehouse.query.filter_by(code="TEST_WH").first()
    if not w:
        w = Warehouse(code="TEST_WH", name="测试仓", status="active",
                      is_default=True)
        db.session.add(w)
        db.session.commit()
    return w


def _seed_material(code: str, stock: float = 100.0) -> Material:
    m = Material(code=code, name=f"扫码测试物料{code}",
                 spec="规格1", stock=stock, price=10.0)
    db.session.add(m)
    db.session.commit()
    return m


class TestScanSubmitBearer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()

    def setUp(self):
        with app_module.app.app_context():
            ApiToken.query.delete()
            InOrder.query.delete()
            OutOrder.query.delete()
            InventoryCheckScan.query.delete()
            Material.query.filter(Material.code.like("SC%")).delete(synchronize_session=False)
            User.query.filter(User.username.like("scan_%")).delete(synchronize_session=False)
            db.session.commit()
            _ensure_warehouse()

    def test_warehouse_bearer_in_success(self):
        """T1：warehouse Bearer + mode=in 成功，operator_id 落库。"""
        with app_module.app.app_context():
            wh_user = _seed_user("warehouse")
            tok = _seed_token(wh_user)
            _seed_material("SC1", stock=0.0)
            tok_val, wh_id = tok.token, wh_user.id

        with app_module.app.test_client() as c:
            rv = c.post("/mobile/api/scan_submit",
                        json={"mode": "in", "code": "SC1", "quantity": "5",
                              "warehouse": "TEST_WH"},
                        headers={"Authorization": f"Bearer {tok_val}"})
        self.assertEqual(rv.status_code, 200, rv.get_json())
        self.assertTrue(rv.get_json().get("success"), rv.get_json())
        with app_module.app.app_context():
            order = InOrder.query.order_by(InOrder.id.desc()).first()
            self.assertIsNotNone(order)
            self.assertEqual(order.operator_id, wh_id)
            self.assertAlmostEqual(order.total_amount, 50.0, places=2)

    def test_warehouse_bearer_out_success(self):
        """T2：warehouse Bearer + mode=out 成功。"""
        with app_module.app.app_context():
            wh_user = _seed_user("warehouse")
            tok = _seed_token(wh_user)
            _seed_material("SC2", stock=20.0)
            tok_val, wh_id = tok.token, wh_user.id

        with app_module.app.test_client() as c:
            rv = c.post("/mobile/api/scan_submit",
                        json={"mode": "out", "code": "SC2", "quantity": "3",
                              "warehouse": "TEST_WH"},
                        headers={"Authorization": f"Bearer {tok_val}"})
        self.assertEqual(rv.status_code, 200, rv.get_json())
        self.assertTrue(rv.get_json().get("success"))
        with app_module.app.app_context():
            o = OutOrder.query.order_by(OutOrder.id.desc()).first()
            self.assertIsNotNone(o)
            self.assertEqual(o.operator_id, wh_id)

    def test_warehouse_bearer_check_success(self):
        """T3：warehouse Bearer + mode=check 成功。"""
        with app_module.app.app_context():
            wh_user = _seed_user("warehouse")
            tok = _seed_token(wh_user)
            _seed_material("SC3", stock=10.0)
            tok_val, wh_id = tok.token, wh_user.id

        with app_module.app.test_client() as c:
            rv = c.post("/mobile/api/scan_submit",
                        json={"mode": "check", "code": "SC3",
                              "actual_stock": "20", "warehouse": "TEST_WH"},
                        headers={"Authorization": f"Bearer {tok_val}"})
        self.assertEqual(rv.status_code, 200, rv.get_json())
        self.assertTrue(rv.get_json().get("success"))
        with app_module.app.app_context():
            chk = InventoryCheckScan.query.order_by(InventoryCheckScan.id.desc()).first()
            self.assertIsNotNone(chk)
            self.assertEqual(chk.operator_id, wh_id)

    def test_warehouse_bearer_query_success(self):
        """T4：warehouse Bearer + mode=query 成功。"""
        with app_module.app.app_context():
            wh_user = _seed_user("warehouse")
            tok = _seed_token(wh_user)
            _seed_material("SC4", stock=8.0)
            tok_val = tok.token

        with app_module.app.test_client() as c:
            rv = c.post("/mobile/api/scan_submit",
                        json={"mode": "query", "code": "SC4"},
                        headers={"Authorization": f"Bearer {tok_val}"})
        self.assertEqual(rv.status_code, 200)
        self.assertTrue(rv.get_json().get("success"))

    def test_user_bearer_403(self):
        """T5：普通 user Bearer -> 403。"""
        with app_module.app.app_context():
            u = _seed_user("user")
            tok = _seed_token(u)
            _seed_material("SC5", stock=1.0)
            tok_val = tok.token

        with app_module.app.test_client() as c:
            rv = c.post("/mobile/api/scan_submit",
                        json={"mode": "in", "code": "SC5", "quantity": "1",
                              "warehouse": "TEST_WH"},
                        headers={"Authorization": f"Bearer {tok_val}"})
        self.assertEqual(rv.status_code, 403, rv.get_json())

    def test_no_auth_401(self):
        """T6：无 Auth -> 401。"""
        with app_module.app.test_client() as c:
            rv = c.post("/mobile/api/scan_submit",
                        json={"mode": "in", "code": "NOSUCH", "quantity": "1"})
        self.assertEqual(rv.status_code, 401)

    def test_admin_web_session_in(self):
        """T7：admin Web 会话 mode=in 回归 PASS。"""
        with app_module.app.app_context():
            admin = _seed_user("admin")
            admin_id = admin.id
            _seed_material("SC7", stock=0.0)

        with app_module.app.test_client() as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_id)
            rv = c.post("/mobile/api/scan_submit",
                        json={"mode": "in", "code": "SC7", "quantity": "2",
                              "warehouse": "TEST_WH"})
        self.assertEqual(rv.status_code, 200, rv.get_json())
        self.assertTrue(rv.get_json().get("success"))
        with app_module.app.app_context():
            order = InOrder.query.order_by(InOrder.id.desc()).first()
            self.assertIsNotNone(order)
            self.assertEqual(order.operator_id, admin_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
