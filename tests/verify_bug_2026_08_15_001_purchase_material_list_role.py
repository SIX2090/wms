# -*- coding: utf-8 -*-
"""
BUG-2026-08-15-001 回归测试：采购订单列表 /material 列表的服务端角色门禁。

旧实现 /purchase_order 与 /material 列表路由仅 @login_required，任何已登录
用户（production / viewer 等受限角色）都能用直链访问，虽然侧边栏按角色隐藏了
菜单，但 URL 直访形成越权。要求与侧边栏可见性一致：admin 与 warehouse 可访问，
production / viewer 不得访问。

修复：两个列表路由加 @require_role('warehouse')（require_role 内置放行 admin）。

覆盖：
T1. production @ /purchase_order -> 302 跳回首页（拒绝）。
T2. production @ /material        -> 302 跳回首页（拒绝）。
T3. viewer     @ /material        -> 302 跳回首页（拒绝）。
T4. viewer     @ /purchase_order  -> 302 跳回首页（拒绝）。
T5. warehouse  @ /purchase_order  -> 200（允许）。
T6. warehouse  @ /material        -> 200（允许）。
T7. admin      @ /purchase_order / /material -> 200（允许）。
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import User, db  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

PASSWORD = "x"


def _seed_user(role: str) -> User:
    u = User(username=f"rolelst_{role}", role=role,
             password_hash=generate_password_hash(PASSWORD),
             status="normal", must_change_password=False)
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, role: str):
    return client.post("/login", data={"username": f"rolelst_{role}",
                                       "password": PASSWORD})


class TestPurchaseMaterialListRole(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()

    def setUp(self):
        with app_module.app.app_context():
            User.query.filter(User.username.like("rolelst_%")).delete(synchronize_session=False)
            db.session.commit()

    def _assert_denied(self, role, path):
        with app_module.app.app_context():
            _seed_user(role)
        with app_module.app.test_client() as c:
            rv = _login(c, role)
            self.assertEqual(rv.status_code, 302, rv.status_code)
            rv2 = c.get(path)
            self.assertEqual(rv2.status_code, 302, f"{role}@{path} 应被拒绝")
            self.assertTrue(rv2.headers.get("Location", "").endswith("/"),
                            f"{role}@{path} 应跳回首页，got {rv2.headers.get('Location')}")

    def _assert_allowed(self, role, path):
        with app_module.app.app_context():
            _seed_user(role)
        with app_module.app.test_client() as c:
            rv = _login(c, role)
            self.assertEqual(rv.status_code, 302, rv.status_code)
            rv2 = c.get(path)
            self.assertEqual(rv2.status_code, 200, f"{role}@{path} 应被允许")

    def test_production_purchase_order_denied(self):
        self._assert_denied("production", "/purchase_order")

    def test_production_material_denied(self):
        self._assert_denied("production", "/material")

    def test_viewer_material_denied(self):
        self._assert_denied("viewer", "/material")

    def test_viewer_purchase_order_denied(self):
        self._assert_denied("viewer", "/purchase_order")

    def test_warehouse_purchase_order_allowed(self):
        self._assert_allowed("warehouse", "/purchase_order")

    def test_warehouse_material_allowed(self):
        self._assert_allowed("warehouse", "/material")

    def test_admin_allowed(self):
        with app_module.app.app_context():
            _seed_user("admin")
        with app_module.app.test_client() as c:
            rv = _login(c, "admin")
            self.assertEqual(rv.status_code, 302, rv.status_code)
            self.assertEqual(c.get("/purchase_order").status_code, 200)
            self.assertEqual(c.get("/material").status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)