# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：物料分类（category）域路由迁移到 routes/category.py。

采用 register-on-app 模式（register_category_routes(app)），endpoint 名保持不变
（如 category_list），URL 路径不变，因此模板/导航中的 url_for('category_list')
等引用无需改动。

验收点：
S1. 8 个 endpoint（category_list/add_category/get_category/edit_category/
    delete_category/download_category_template/export_category/import_category）
    已注册，且仍是未加前缀的原始 endpoint 名（与 app.py 原实现一致）。
S2. URL 路径保持不变（/category、/category/add、/category/<id>、
    /category/edit/<id>、/category/delete、/category/download_template、
    /category/export、/category/import）。
S3. 新增分类成功；重复编码/名称被拒绝；上级分类不存在被拒绝。
S4. 行级编辑成功；上级分类不能选择自己/自己的下级。
S5. 删除分类：被物料引用时禁止删除；无引用时删除成功。
S6. 导入分类：合法行导入成功，重复/无父分类行跳过。
"""
from __future__ import annotations

import io
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
from app import db, MaterialCategory  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


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
    u = User(username="admin", password_hash=generate_password_hash("admin"), role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


class TestCategoryRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_category_list(self):
        """S1/S2：endpoint 注册、URL 不变、列表页可渲染。"""
        with app_module.app.app_context():
            for ep in ("category_list", "add_category", "get_category", "edit_category",
                       "delete_category", "download_category_template", "export_category",
                       "import_category"):
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            # 不应出现带前缀的重复 endpoint
            assert "category.category_list" not in app_module.app.view_functions
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("category_list") == "/category"
                assert url_for("add_category") == "/category/add"
                assert url_for("get_category", id=1) == "/category/1"
                assert url_for("edit_category", id=1) == "/category/edit/1"
                assert url_for("delete_category") == "/category/delete"
                assert url_for("download_category_template") == "/category/download_template"
                assert url_for("export_category") == "/category/export"
                assert url_for("import_category") == "/category/import"
        client = self._setup()
        _login(client)
        resp = client.get("/category")
        assert resp.status_code == 200
        assert "分类" in resp.get_data(as_text=True)

    def test_add_category(self):
        """S3：新增成功、重复编码/名称拒绝、上级分类不存在拒绝。"""
        client = self._setup()
        _login(client)
        resp = client.post("/category/add", data={"code": "C1", "name": "原材料"})
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            assert MaterialCategory.query.filter_by(code="C1").first() is not None
        # 重复编码
        r1 = client.post("/category/add", data={"code": "C1", "name": "另一个"})
        assert r1.get_json()["status"] == "error"
        # 重复名称
        r2 = client.post("/category/add", data={"code": "C2", "name": "原材料"})
        assert r2.get_json()["status"] == "error"
        # 上级分类不存在
        r3 = client.post("/category/add", data={"code": "C3", "name": "子类", "parent_id": 9999})
        assert r3.get_json()["status"] == "error"

    def test_get_category(self):
        """S4：读取分类详情。"""
        client = self._setup()
        _login(client)
        client.post("/category/add", data={"code": "C1", "name": "原材料"})
        with app_module.app.app_context():
            cid = MaterialCategory.query.filter_by(code="C1").first().id
        g = client.get(f"/category/{cid}")
        assert g.get_json()["status"] == "success"
        assert g.get_json()["category"]["code"] == "C1"

    def test_edit_category(self):
        """S4：行级编辑成功；上级分类不能选择自己。"""
        client = self._setup()
        _login(client)
        client.post("/category/add", data={"code": "C1", "name": "原材料"})
        with app_module.app.app_context():
            cid = MaterialCategory.query.filter_by(code="C1").first().id
        resp = client.post(f"/category/edit/{cid}", data={"code": "C2", "name": "半成品"})
        assert resp.get_json()["status"] == "success", resp.get_json()
        with app_module.app.app_context():
            assert MaterialCategory.query.get(cid).code == "C2"
        # 上级分类不能选择自己
        r = client.post(f"/category/edit/{cid}", data={"code": "C2", "name": "半成品", "parent_id": cid})
        assert r.get_json()["status"] == "error"

    def test_delete_category(self):
        """S5：被物料引用时禁止删除；无引用时删除成功。"""
        client = self._setup()
        _login(client)
        client.post("/category/add", data={"code": "C1", "name": "原材料"})
        with app_module.app.app_context():
            cid = MaterialCategory.query.filter_by(code="C1").first().id
        # 被物料引用不能删除
        from app import Material, Unit
        from app import Supplier
        with app_module.app.app_context():
            cat = MaterialCategory.query.get(cid)
            unit = Unit(name="个", code="PCS")
            sup = Supplier(code="S1", name="供应商甲")
            db.session.add_all([unit, sup])
            db.session.flush()
            mat = Material(code="M1", name="物料", unit_id=unit.id, category_id=cat.id, supplier_id=sup.id)
            db.session.add(mat)
            db.session.commit()
        resp = client.post("/category/delete", json={"ids": [cid]})
        assert resp.get_json()["status"] == "error", resp.get_json()
        assert "引用" in resp.get_json()["msg"]
        # 解除引用后删除成功
        with app_module.app.app_context():
            db.session.query(Material).filter(Material.code == "M1").delete()
            db.session.commit()
        resp = client.post("/category/delete", json={"ids": [cid]})
        assert resp.get_json()["status"] == "success", resp.get_json()
        with app_module.app.app_context():
            assert MaterialCategory.query.get(cid) is None

    def test_import_category(self):
        """S6：合法行导入成功，重复/无父分类行跳过。"""
        client = self._setup()
        _login(client)
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "分类导入"
        ws.append(["分类编码", "分类名称", "上级分类编码"])
        ws.append(["100", "原材料", ""])
        ws.append(["101", "金属材料", "100"])
        ws.append(["102", "重复", "100"])
        ws.append(["102", "重复", "100"])  # 重复行，应跳过
        ws.append(["103", "无父分类", "999"])  # 父分类不存在，应跳过
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        resp = client.post(
            "/category/import",
            data={"file": (buf, "cats.xlsx")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert data["status"] == "success", data
        assert "共导入 3 条" in data["msg"], data
        with app_module.app.app_context():
            assert MaterialCategory.query.filter_by(code="100").first() is not None
            assert MaterialCategory.query.filter_by(code="101").first() is not None
            assert MaterialCategory.query.filter_by(code="102").first() is not None
            assert MaterialCategory.query.filter_by(code="103").first() is None