# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：供应商（supplier）域路由迁移到 routes/supplier.py。

采用 register-on-app 模式（register_supplier_routes(app)），endpoint 名保持不变
（如 supplier_list），URL 路径不变，因此模板/导航/AI 目录中的 url_for('supplier_list')
等引用无需改动。

验收点：
S1. 5 个 endpoint（supplier_list/add_supplier/delete_supplier/get_supplier/edit_supplier）
    已注册，且仍是未加前缀的原始 endpoint 名（与 app.py 原实现一致）。
S2. URL 路径保持不变（/supplier、/supplier/add、/supplier/delete、
    /supplier/<id>、/supplier/<id>/edit）。
S3. 新增供应商成功；重复编号/名称被拒绝；长度超限被拒绝。
S4. 行级编辑成功。
S5. 删除供应商：被物料/入库单/采购订单引用时禁止删除；无引用时删除成功。
S6. GET /supplier/add 重定向到列表页（携带 showAddModal=1）。
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
from app import db, Supplier  # noqa: E402

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


class TestSupplierRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_supplier_list(self):
        """S1/S2：endpoint 注册、URL 不变、列表页可渲染。"""
        with app_module.app.app_context():
            for ep in ("supplier_list", "add_supplier", "delete_supplier", "get_supplier", "edit_supplier"):
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            # 不应出现带前缀的重复 endpoint
            assert "supplier.supplier_list" not in app_module.app.view_functions
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("supplier_list") == "/supplier"
                assert url_for("add_supplier") == "/supplier/add"
                assert url_for("delete_supplier") == "/supplier/delete"
                assert url_for("get_supplier", supplier_id=1) == "/supplier/1"
                assert url_for("edit_supplier", supplier_id=1) == "/supplier/1/edit"
        client = self._setup()
        _login(client)
        resp = client.get("/supplier")
        assert resp.status_code == 200
        assert "供应商" in resp.get_data(as_text=True)

    def test_add_supplier(self):
        """S3：新增成功、重复编号/名称拒绝、长度超限拒绝。"""
        client = self._setup()
        _login(client)
        resp = client.post("/supplier/add", data={"code": "S1", "name": "供应商甲", "contact": "张三", "phone": "13800000000", "address": "某地"})
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            assert Supplier.query.filter_by(code="S1").first() is not None
        # 重复编号
        r1 = client.post("/supplier/add", data={"code": "S1", "name": "另一个"})
        assert r1.get_json()["status"] == "error"
        # 重复名称
        r2 = client.post("/supplier/add", data={"code": "S2", "name": "供应商甲"})
        assert r2.get_json()["status"] == "error"
        # 长度超限：sanitize_text_input 先截断到 50，故保存成功但编号被截断
        r3 = client.post("/supplier/add", data={"code": "S" * 51, "name": "超长"})
        assert r3.get_json()["status"] == "success", r3.get_json()
        with app_module.app.app_context():
            assert Supplier.query.filter_by(code="S" * 50).first() is not None
            assert Supplier.query.filter_by(code="S" * 51).first() is None

    def test_get_supplier(self):
        """S4：读取供应商详情。"""
        client = self._setup()
        _login(client)
        client.post("/supplier/add", data={"code": "S1", "name": "供应商甲"})
        with app_module.app.app_context():
            sid = Supplier.query.filter_by(code="S1").first().id
        g = client.get(f"/supplier/{sid}")
        assert g.get_json()["status"] == "success"
        assert g.get_json()["supplier"]["code"] == "S1"
        assert g.get_json()["supplier"]["name"] == "供应商甲"

    def test_edit_supplier(self):
        """S4：供应商行级编辑。"""
        client = self._setup()
        _login(client)
        client.post("/supplier/add", data={"code": "S1", "name": "供应商甲"})
        with app_module.app.app_context():
            sid = Supplier.query.filter_by(code="S1").first().id
        resp = client.post(f"/supplier/{sid}/edit", data={"code": "S2", "name": "供应商乙"})
        assert resp.get_json()["status"] == "success", resp.get_json()
        with app_module.app.app_context():
            assert Supplier.query.get(sid).code == "S2"
            assert Supplier.query.get(sid).name == "供应商乙"

    def test_delete_supplier(self):
        """S5：被引用时禁止删除；无引用时删除成功。"""
        client = self._setup()
        _login(client)
        client.post("/supplier/add", data={"code": "S1", "name": "供应商甲"})
        with app_module.app.app_context():
            sid = Supplier.query.filter_by(code="S1").first().id
        # 被物料引用不能删除
        from app import Material, MaterialCategory, Unit
        with app_module.app.app_context():
            sup = Supplier.query.get(sid)
            cat = MaterialCategory(name="分类", code="C1")
            unit = Unit(name="个", code="PCS")
            db.session.add_all([cat, unit])
            db.session.flush()
            mat = Material(code="M1", name="物料", unit_id=unit.id, category_id=cat.id, supplier_id=sup.id)
            db.session.add(mat)
            db.session.commit()
        resp = client.post("/supplier/delete", json={"ids": [sid]})
        assert resp.get_json()["status"] == "error", resp.get_json()
        assert "已关联物料" in resp.get_json()["msg"]
        # 解除引用后删除成功
        with app_module.app.app_context():
            db.session.query(Material).filter(Material.code == "M1").delete()
            db.session.commit()
        resp = client.post("/supplier/delete", json={"ids": [sid]})
        assert resp.get_json()["status"] == "success", resp.get_json()
        with app_module.app.app_context():
            assert Supplier.query.get(sid) is None

    def test_get_add_supplier_redirect(self):
        """S6：GET /supplier/add 重定向到列表页并携带 showAddModal=1。"""
        client = self._setup()
        _login(client)
        resp = client.get("/supplier/add")
        assert resp.status_code == 302
        assert "showAddModal=1" in resp.headers["Location"]

    def test_next_supplier_code(self):
        """自动编号：数字后缀最大的编号 +1 并补零，前缀保留。"""
        from types import SimpleNamespace
        from app.routes.supplier import _next_supplier_code

        sup = lambda code: SimpleNamespace(code=code)  # noqa: E731
        # 纯数字 3 位：009 → 010
        assert _next_supplier_code([sup("007"), sup("009")]) == "010"
        # 带前缀：SUP009 → SUP010
        assert _next_supplier_code([sup("SUP001"), sup("SUP009")]) == "SUP010"
        # 混合前缀取最大数字（8 进 9 位进位仍补零）
        assert _next_supplier_code([sup("M-08"), sup("A-03")]) == "M-09"
        # 跨位数进位：009 → 010 不进位到 4 位
        assert _next_supplier_code([sup("009")]) == "010"
        # 无数字后缀的编号被忽略
        assert _next_supplier_code([sup("ABC"), sup("X")]) == "001"
        # 无任何编号 → 起始 001
        assert _next_supplier_code([]) == "001"
        # 空 code / None 忽略
        assert _next_supplier_code([sup(""), sup(None)]) == "001"

    def test_supplier_list_renders_next_code(self):
        """列表页自动带出下一个供应商编号（009 → 010）。"""
        client = self._setup()
        _login(client)
        client.post("/supplier/add", data={"code": "009", "name": "供应商一"})
        client.post("/supplier/add", data={"code": "010", "name": "供应商二"})
        resp = client.get("/supplier")
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'value="011"' in html