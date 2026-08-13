# -*- coding: utf-8 -*-
"""
BUG-2026-08-13-001 回归测试：移动端物料图片上传/删除强制仓库角色。

旧实现移动端 /mobile/api/material_archive/<id>/images (POST/DELETE)
仅用 @_web_or_api_required 校验登录，不限业务角色；普通用户可修改任意
物料图片。要求与 Web 端 material_image_upload/delete 保持一致，强制
admin 或 warehouse 角色。

覆盖：
T1. warehouse Bearer Token 上传图片 201。
T2. warehouse Bearer Token 删除图片 200。
T3. user Bearer Token 上传图片 403（权限不足）。
T4. user Bearer Token 删除图片 403。
T5. 无 Authorization 上传 401 / 删除 401。
T6. admin Web 会话（cookie）上传+删除回归 PASS。
T7. 源码静态：POST/DELETE 路由使用 @_web_or_api_role_required('warehouse')。
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import ApiToken, Material, MaterialImage, User, db  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _seed_user(role: str) -> User:
    u = User(username=f"imgrole_{role}", role=role,
             password_hash=generate_password_hash("x"),
             status="normal", must_change_password=False)
    db.session.add(u)
    db.session.commit()
    return u


def _seed_token(user: User) -> ApiToken:
    t = ApiToken(
        token=f"tok_{user.id}_{os.urandom(4).hex()}",
        user_id=user.id,
        expires_at=datetime.now() + app_module.timedelta(days=7),
        revoked=False,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _seed_material() -> Material:
    m = Material(code=f"MIMG{os.urandom(2).hex()}", name="测试物料",
                 spec="规格1", stock=0, price=0)
    db.session.add(m)
    db.session.commit()
    return m


class TestMobileImageRole(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()

    def setUp(self):
        with app_module.app.app_context():
            ApiToken.query.delete()
            MaterialImage.query.delete()
            Material.query.delete()
            User.query.filter(User.username.like("imgrole_%")).delete(synchronize_session=False)
            db.session.commit()

    def test_warehouse_bearer_upload_ok(self):
        """T1：warehouse Bearer 上传图片 201/200（success=true）。"""
        with app_module.app.app_context():
            wh = _seed_user("warehouse")
            tok = _seed_token(wh)
            mat = _seed_material()
            mat_id = mat.id
            tok_val = tok.token

        from io import BytesIO
        with patch.object(app_module, "save_upload_image", return_value=("path/to/img.png", None)):
            with app_module.app.test_client() as c:
                rv = c.post(f"/mobile/api/material_archive/{mat_id}/images",
                            data={"image": (BytesIO(b"fakebytes"), "a.png")},
                            headers={"Authorization": f"Bearer {tok_val}"},
                            content_type="multipart/form-data")
        # 允许 200 或 201
        self.assertIn(rv.status_code, (200, 201), rv.get_json())
        body = rv.get_json()
        self.assertTrue(body.get("success"), body)

    def test_warehouse_bearer_delete_ok(self):
        """T2：warehouse Bearer 删除图片 200。"""
        with app_module.app.app_context():
            wh = _seed_user("warehouse")
            tok = _seed_token(wh)
            mat = _seed_material()
            img = MaterialImage(material_id=mat.id, image="p/x.png", sort_order=0)
            db.session.add(img)
            db.session.commit()
            img_id = img.id
            tok_val = tok.token

        with app_module.app.test_client() as c:
            rv = c.delete(f"/mobile/api/material_archive/images/{img_id}",
                          headers={"Authorization": f"Bearer {tok_val}"})
        self.assertEqual(rv.status_code, 200, rv.get_json())

    def test_user_bearer_upload_403(self):
        """T3：普通 user Bearer 上传 403。"""
        with app_module.app.app_context():
            u = _seed_user("user")
            tok = _seed_token(u)
            mat = _seed_material()
            mat_id = mat.id
            tok_val = tok.token

        with app_module.app.test_client() as c:
            rv = c.post(f"/mobile/api/material_archive/{mat_id}/images",
                        data={"image": (b"fake", "a.png")},
                        headers={"Authorization": f"Bearer {tok_val}"},
                        content_type="multipart/form-data")
        self.assertEqual(rv.status_code, 403, rv.get_json())

    def test_user_bearer_delete_403(self):
        """T4：普通 user Bearer 删除 403。"""
        with app_module.app.app_context():
            u = _seed_user("user")
            tok = _seed_token(u)
            mat = _seed_material()
            img = MaterialImage(material_id=mat.id, image="p/x.png", sort_order=0)
            db.session.add(img)
            db.session.commit()
            img_id = img.id
            tok_val = tok.token

        with app_module.app.test_client() as c:
            rv = c.delete(f"/mobile/api/material_archive/images/{img_id}",
                          headers={"Authorization": f"Bearer {tok_val}"})
        self.assertEqual(rv.status_code, 403, rv.get_json())

    def test_no_auth_401(self):
        """T5：无 Authorization，上传 401、删除 401。"""
        with app_module.app.app_context():
            mat = _seed_material()
            img = MaterialImage(material_id=mat.id, image="p/x.png", sort_order=0)
            db.session.add(img)
            db.session.commit()
            mat_id = mat.id
            img_id = img.id

        from io import BytesIO
        with app_module.app.test_client() as c:
            rv_post = c.post(f"/mobile/api/material_archive/{mat_id}/images",
                             data={"image": (BytesIO(b"fake"), "a.png")},
                             content_type="multipart/form-data")
            rv_del = c.delete(f"/mobile/api/material_archive/images/{img_id}")
        self.assertEqual(rv_post.status_code, 401)
        self.assertEqual(rv_del.status_code, 401)

    def test_admin_web_session(self):
        """T6：admin Web 会话（cookie）上传+删除回归 PASS。"""
        with app_module.app.app_context():
            admin = _seed_user("admin")
            admin_id = admin.id
            mat = _seed_material()
            mat_id = mat.id

        from io import BytesIO
        with app_module.app.test_client() as c:
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_id)
            # 上传
            with patch.object(app_module, "save_upload_image", return_value=("path/b.png", None)):
                rv_post = c.post(f"/mobile/api/material_archive/{mat_id}/images",
                                 data={"image": (BytesIO(b"fake"), "b.png")},
                                 content_type="multipart/form-data")
            self.assertIn(rv_post.status_code, (200, 201), rv_post.get_json())
            self.assertTrue(rv_post.get_json().get("success"))
            img_id = None
            with app_module.app.app_context():
                row = MaterialImage.query.filter_by(material_id=mat_id).first()
                if row:
                    img_id = row.id
            self.assertIsNotNone(img_id)
            # 删除
            with c.session_transaction() as sess:
                sess["_user_id"] = str(admin_id)
            rv_del = c.delete(f"/mobile/api/material_archive/images/{img_id}")
            self.assertEqual(rv_del.status_code, 200, rv_del.get_json())

    def test_source_role_decorator(self):
        """T7：源码静态——POST/DELETE 路由使用 @_web_or_api_role_required('warehouse')。"""
        with open(APP_DIR / "routes" / "mobile.py", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("_web_or_api_role_required('warehouse')", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
