# -*- coding: utf-8 -*-
"""
app.py 拆分试点回归测试：单位（unit）域路由迁移到 routes/unit.py Blueprint。

背景：app.py 是单体巨石文件（约 4.8 万行）。试点将「单位」域 5 个 CRUD 路由
（unit_list / add_unit / delete_unit / get_unit / edit_unit）迁移到
app/routes/unit.py 的 unit_bp Blueprint。

验收点：
U1. 5 个 endpoint 已注册在 unit_bp 下（unit.unit_list / unit.add_unit / ...），
    URL 路径保持不变（/unit、/unit/add、/unit/delete、/unit/<id>、/unit/<id>/edit）。
U2. 新增单位成功。
U3. 重复单位编号/名称被拒绝。
U4. 行级编辑成功。
U5. 删除单位成功。
U6. 被物料引用的单位不能删除。
U7. url_for 解析（与模板/导航/AI 目录所用 endpoint 一致）。
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
from app import db, Unit, MaterialCategory  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _login(client):
    resp = client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )
    return resp


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"), role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


class TestUnitBlueprint:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_unit_list(self):
        """U1/U7：单位列表 endpoint 注册、URL 不变、列表页可渲染。"""
        with app_module.app.app_context():
            # endpoint 已迁移到 unit_bp
            assert "unit.unit_list" in app_module.app.view_functions
            assert "unit.add_unit" in app_module.app.view_functions
            assert "unit.delete_unit" in app_module.app.view_functions
            assert "unit.get_unit" in app_module.app.view_functions
            assert "unit.edit_unit" in app_module.app.view_functions
            # 旧 endpoint 不应再存在（防止重复注册）
            assert "unit_list" not in app_module.app.view_functions
            assert "add_unit" not in app_module.app.view_functions
            # URL 路径保持不变（需 request context 才能 url_for 生成路径）
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("unit.unit_list") == "/unit"
                assert url_for("unit.add_unit") == "/unit/add"
                assert url_for("unit.delete_unit") == "/unit/delete"
                assert url_for("unit.get_unit", unit_id=1) == "/unit/1"
                assert url_for("unit.edit_unit", unit_id=1) == "/unit/1/edit"
        # 列表页可渲染
        client = self._setup()
        _login(client)
        resp = client.get("/unit")
        assert resp.status_code == 200
        assert "单位" in resp.get_data(as_text=True)

    def test_add_unit(self):
        """U2/U3：新增单位成功、重复编码/名称被拒绝。"""
        client = self._setup()
        _login(client)
        resp = client.post("/unit/add", data={"code": "PCS", "name": "个"})
        data = resp.get_json()
        assert data["status"] == "success", data
        assert "id" in data
        with app_module.app.app_context():
            assert Unit.query.filter_by(code="PCS", name="个").first() is not None
        # 重复
        r1 = client.post("/unit/add", data={"code": "PCS", "name": "个2"})
        assert r1.get_json()["status"] == "error"
        r2 = client.post("/unit/add", data={"code": "PCS2", "name": "个"})
        assert r2.get_json()["status"] == "error"

    def test_get_unit(self):
        """U4：读取单位详情。"""
        client = self._setup()
        _login(client)
        client.post("/unit/add", data={"code": "PCS", "name": "个"})
        with app_module.app.app_context():
            uid = Unit.query.filter_by(code="PCS").first().id
        g = client.get(f"/unit/{uid}")
        assert g.get_json()["status"] == "success"
        assert g.get_json()["unit"]["code"] == "PCS"
        assert g.get_json()["unit"]["name"] == "个"

    def test_edit_unit(self):
        """U4：单位行级编辑。"""
        client = self._setup()
        _login(client)
        client.post("/unit/add", data={"code": "PCS", "name": "个"})
        with app_module.app.app_context():
            uid = Unit.query.filter_by(code="PCS").first().id
        resp = client.post(f"/unit/{uid}/edit", data={"code": "PCS2", "name": "个件"})
        assert resp.get_json()["status"] == "success", resp.get_json()
        with app_module.app.app_context():
            assert Unit.query.get(uid).code == "PCS2"
            assert Unit.query.get(uid).name == "个件"

    def test_delete_unit(self):
        """U5/U6：删除单位成功；被物料引用的单位禁止删除。"""
        client = self._setup()
        _login(client)
        client.post("/unit/add", data={"code": "PCS", "name": "个"})
        with app_module.app.app_context():
            uid = Unit.query.filter_by(code="PCS").first().id
        # 被物料引用不能删除
        from app import Material, Supplier
        with app_module.app.app_context():
            unit = Unit.query.get(uid)
            cat = MaterialCategory(name="分类", code="C1")
            sup = Supplier(code="S1", name="供应商")
            db.session.add_all([cat, sup])
            db.session.flush()
            mat = Material(code="M1", name="物料", unit_id=unit.id, category_id=cat.id, supplier_id=sup.id)
            db.session.add(mat)
            db.session.commit()
        resp = client.post("/unit/delete", json={"ids": [uid]})
        assert resp.get_json()["status"] == "error", resp.get_json()
        assert "已关联物料" in resp.get_json()["msg"]
        # 解除引用后删除成功
        with app_module.app.app_context():
            db.session.query(Material).filter(Material.code == "M1").delete()
            db.session.commit()
        resp = client.post("/unit/delete", json={"ids": [uid]})
        assert resp.get_json()["status"] == "success", resp.get_json()
        with app_module.app.app_context():
            assert Unit.query.get(uid) is None