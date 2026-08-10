# -*- coding: utf-8 -*-
"""
手机端物料档案（多图归档）API 回归测试（AI-MOB-ARCH-F01）。

覆盖：
T1. 端点注册：search / images / upload / delete。
T2. 搜索物料：按编码/名称/规格/品牌模糊匹配，返回 image_count。
T3. 上传图片：成功保存并返回图片记录。
T4. 数量上限：每个物料最多 5 张，第 6 张被拒。
T5. 列出图片：返回物料信息 + 全部图片。
T6. 删除图片：删除后列表不再包含该图。
T7. 认证：无 Web 会话且无 Bearer Token -> 401。
T8. Bearer Token 鉴权可访问。
T12. material_image 表不存在时搜索不 500（WMS_SKIP_STARTUP_DB_UPGRADE 回归）。
"""
from __future__ import annotations

import io
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

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

API_ENDPOINTS = [
    "mobile_material_archive_search",
    "mobile_material_archive_images",
    "mobile_material_archive_upload",
    "mobile_material_archive_delete_image",
]
MAX = 5

def _make_png():
    """用 Pillow 生成一张真实有效的 PNG，供上传接口通过内容校验。"""
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 200, 200)).save(buf, format="PNG")
    return buf.getvalue()


_PNG = _make_png()


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _login(client):
    r = client.post("/login", data={
        "username": "admin",
        "password": "admin",
        "login_mode": "user",
        "usage_consent": "1",
    })
    assert r.status_code in (200, 302), r.get_data(as_text=True)
    return {}


def _bearer_headers(client):
    from datetime import datetime, timedelta
    import secrets
    from app import ApiToken, User
    with app_module.app.app_context():
        user = User.query.filter_by(username="admin").first()
        token = ApiToken(
            token=secrets.token_urlsafe(48),
            user_id=user.id,
            expires_at=datetime.now() + timedelta(days=7),
        )
        db.session.add(token)
        db.session.commit()
        return {"Authorization": f"Bearer {token.token}"}


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _seed_material(code, name, spec="", brand=""):
    from app import Material
    with app_module.app.app_context():
        m = Material(code=code, name=name, spec=spec, brand=brand)
        db.session.add(m)
        db.session.commit()
        return m.id


def _upload(client, headers, mid, filename="material.png"):
    data = {"image": (io.BytesIO(_PNG), filename)}
    return client.post(f"/mobile/api/material_archive/{mid}/images", data=data,
                       content_type="multipart/form-data", headers=headers)


class TestMobileMaterialArchiveApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()

    def setUp(self):
        from app import Material, MaterialImage
        with app_module.app.app_context():
            Material.query.delete()
            MaterialImage.query.delete()
            db.session.commit()
        self.client = _make_client()
        self.headers = _login(self.client)

    def test_endpoints_registered(self):
        """T1：四个物料档案端点均已注册。"""
        from app import app
        rules = [str(r.rule) for r in app.url_map.iter_rules()]
        self.assertIn("/mobile/api/material_archive/search", rules)
        self.assertIn("/mobile/api/material_archive/<int:id>/images", rules)
        self.assertIn("/mobile/api/material_archive/images/<int:image_id>", rules)

    def test_search_material(self):
        """T2：按编码/名称/规格/品牌模糊搜索，返回 image_count。"""
        mid = _seed_material("6204", "深沟球轴承", "6204", "SKF")
        _seed_material("M8-100", "六角螺母", "M8", "国标")
        r = self.client.get("/mobile/api/material_archive/search?keyword=6204",
                            headers=self.headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        body = r.get_json()
        self.assertEqual(body["status"], "success", body)
        self.assertEqual(len(body["data"]), 1)
        self.assertEqual(body["data"][0]["id"], mid)
        self.assertEqual(body["data"][0]["image_count"], 0)
        # 空关键字返回全部（上限 50）
        r2 = self.client.get("/mobile/api/material_archive/search",
                             headers=self.headers)
        self.assertEqual(len(r2.get_json()["data"]), 2)

    def test_upload_image(self):
        """T3：上传图片成功，返回图片记录。"""
        mid = _seed_material("6204", "深沟球轴承", "6204")
        r = _upload(self.client, self.headers, mid)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        body = r.get_json()
        self.assertEqual(body["status"], "success", body)
        self.assertTrue(body["data"]["id"])
        self.assertTrue(body["data"]["image"].startswith("uploads/material_images"))
        self.assertTrue(body["data"]["url"])

    def test_max_five_images(self):
        """T4：第 6 张图片被拒。"""
        mid = _seed_material("6204", "深沟球轴承", "6204")
        for i in range(MAX):
            r = _upload(self.client, self.headers, mid, filename=f"m{i}.png")
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        r6 = _upload(self.client, self.headers, mid, filename="m6.png")
        self.assertEqual(r6.status_code, 400, r6.get_data(as_text=True))
        self.assertIn("最多", r6.get_json()["msg"])

    def test_list_images(self):
        """T5：列出某物料全部图片。"""
        mid = _seed_material("6204", "深沟球轴承", "6204")
        _upload(self.client, self.headers, mid, filename="a.png")
        _upload(self.client, self.headers, mid, filename="b.png")
        r = self.client.get(f"/mobile/api/material_archive/{mid}/images",
                            headers=self.headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        body = r.get_json()
        self.assertEqual(body["status"], "success", body)
        self.assertEqual(body["data"]["material"]["id"], mid)
        self.assertEqual(len(body["data"]["images"]), 2)

    def test_delete_image(self):
        """T6：删除后列表不再包含该图。"""
        mid = _seed_material("6204", "深沟球轴承", "6204")
        up = _upload(self.client, self.headers, mid).get_json()["data"]
        img_id = up["id"]
        r = self.client.delete(f"/mobile/api/material_archive/images/{img_id}",
                               headers=self.headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        lst = self.client.get(f"/mobile/api/material_archive/{mid}/images",
                              headers=self.headers).get_json()
        self.assertEqual(lst["data"]["images"], [])

    def test_no_auth_returns_401(self):
        """T7：无会话无 Token -> 401。"""
        r = _make_client().get("/mobile/api/material_archive/search")
        self.assertEqual(r.status_code, 401, r.get_data(as_text=True))

    def test_bearer_token_auth(self):
        """T8：Bearer Token 可搜索与上传。"""
        mid = _seed_material("6204", "深沟球轴承", "6204")
        headers = _bearer_headers(self.client)
        r = self.client.get("/mobile/api/material_archive/search?keyword=6204",
                            headers=headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        up = _upload(self.client, headers, mid)
        self.assertEqual(up.status_code, 200, up.get_data(as_text=True))

    def test_upload_syncs_primary_image(self):
        """T9：上传图片后 Material.image 同步为该图（主图）。"""
        from app import Material
        mid = _seed_material("6204", "深沟球轴承", "6204")
        up = _upload(self.client, self.headers, mid).get_json()["data"]
        with app_module.app.app_context():
            m = db.session.get(Material, mid)
            self.assertEqual(m.image, up["image"])

    def test_delete_syncs_primary_image(self):
        """T10：删除图片后 Material.image 回退为下一张，删空则置空。"""
        from app import Material
        mid = _seed_material("6204", "深沟球轴承", "6204")
        img1 = _upload(self.client, self.headers, mid, filename="a.png").get_json()["data"]
        img2 = _upload(self.client, self.headers, mid, filename="b.png").get_json()["data"]
        # 删掉首图 -> 主图回退为第二张
        self.client.delete(f"/mobile/api/material_archive/images/{img1['id']}",
                           headers=self.headers)
        with app_module.app.app_context():
            m = db.session.get(Material, mid)
            self.assertEqual(m.image, img2["image"])
        # 再删掉剩下的 -> 主图置空
        self.client.delete(f"/mobile/api/material_archive/images/{img2['id']}",
                           headers=self.headers)
        with app_module.app.app_context():
            m = db.session.get(Material, mid)
            self.assertIsNone(m.image)


def test_search_when_material_image_table_missing():
    """T12（回归）：material_image 表不存在时搜索不 500，image_count 返回 0。

    模拟 WMS_SKIP_STARTUP_DB_UPGRADE 场景：db.create_all() 被跳过，
    material_image 表缺失，搜索接口必须容错返回 0 而非 500。
    """
    from app import Material
    with app_module.app.app_context():
        # 临时删除 material_image 表模拟缺失场景
        db.session.execute(db.text("DROP TABLE IF EXISTS material_image"))
        db.session.commit()
        # 确认表已删除
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        assert not inspector.has_table("material_image"), "前置条件：material_image 表应已删除"

        mid = _seed_material("M8-NO-TABLE", "无表回归测试", "M8")
        client = _make_client()
        headers = _login(client)
        r = client.get("/mobile/api/material_archive/search?keyword=M8", headers=headers)
        assert r.status_code == 200, f"表缺失时搜索不应 500，实际 {r.status_code}: {r.get_data(as_text=True)}"
        body = r.get_json()
        assert body["status"] == "success"
        assert body["data"][0]["image_count"] == 0

        # 恢复表，避免影响后续测试
        db.create_all()


def test_sync_material_primary_image():
    """T11：sync_material_primary_image 直接单元测试。"""
    from app import Material, MaterialImage
    from utils import sync_material_primary_image
    with app_module.app.app_context():
        m = Material(code="SP-01", name="同步测试")
        db.session.add(m)
        db.session.commit()
        assert m.image is None  # 无图时主图置空
        db.session.add(MaterialImage(material_id=m.id, image="uploads/material_images/a.png", sort_order=0))
        db.session.add(MaterialImage(material_id=m.id, image="uploads/material_images/b.png", sort_order=1))
        db.session.commit()
        sync_material_primary_image(m)
        assert m.image == "uploads/material_images/a.png"  # 首图为主图
        db.session.commit()
        # 删空后主图置空
        MaterialImage.query.filter_by(material_id=m.id).delete()
        db.session.commit()
        sync_material_primary_image(m)
        assert m.image is None


if __name__ == "__main__":
    unittest.main(verbosity=2)
