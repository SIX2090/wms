# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：客户（customer）域路由迁移到 routes/customer.py。

采用 register-on-app 模式（register_customer_routes(app)），endpoint 名保持不变
（如 customer_list），URL 路径不变，因此模板/导航中的 url_for('customer_list')
等引用无需改动。

验收点：
S1. 8 个 endpoint（customer_list/add_customer/delete_customer/get_customer/
    edit_customer/download_customer_template/export_customer/import_customer）
    已注册，且仍是未加前缀的原始 endpoint 名，不存在 customer.xxx 带前缀的重复 endpoint。
S2. URL 路径保持不变（/customer、/customer/add、/customer/delete、
    /customer/<id>、/customer/<id>/edit、/customer/download_template、
    /customer/export、/customer/import）。
S3. 客户列表页可渲染（200，含"客户"字样）。
S4. 新增客户成功；编号/名称必填、编号/名称重复被拒绝。
S5. 读取客户详情成功。
S6. 行级编辑成功；编号改为另一客户占用的编号被拒绝。
S7. 删除客户成功。
S8. 导入客户：合法行新增，重复编码跳过。
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
from app import db, Customer  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

CUSTOMER_ENDPOINTS = [
    "customer_list",
    "add_customer",
    "delete_customer",
    "get_customer",
    "edit_customer",
    "download_customer_template",
    "export_customer",
    "import_customer",
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


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"), role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _add_customer(client, code="CUS-001", name="客户甲", **extra):
    data = {"code": code, "name": name}
    data.update(extra)
    return client.post("/customer/add", data=data)


class TestCustomerRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_endpoints_and_urls(self):
        """S1/S2：8 个 endpoint 注册、URL 不变、无前缀重复。"""
        with app_module.app.app_context():
            for ep in CUSTOMER_ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            for ep in CUSTOMER_ENDPOINTS:
                assert f"customer.{ep}" not in app_module.app.view_functions, f"customer.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("customer_list") == "/customer"
                assert url_for("add_customer") == "/customer/add"
                assert url_for("delete_customer") == "/customer/delete"
                assert url_for("get_customer", customer_id=1) == "/customer/1"
                assert url_for("edit_customer", customer_id=1) == "/customer/1/edit"
                assert url_for("download_customer_template") == "/customer/download_template"
                assert url_for("export_customer") == "/customer/export"
                assert url_for("import_customer") == "/customer/import"

    def test_customer_list(self):
        """S3：列表页可渲染。"""
        client = self._setup()
        _login(client)
        resp = client.get("/customer")
        assert resp.status_code == 200
        assert "客户" in resp.get_data(as_text=True)

    def test_add_customer(self):
        """S4：新增成功、编号/名称必填、重复被拒绝。"""
        client = self._setup()
        _login(client)
        resp = _add_customer(client, code="CUS-001", name="客户甲")
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            assert Customer.query.filter_by(code="CUS-001").first() is not None
        # 编号必填
        r1 = _add_customer(client, code="", name="客户乙")
        assert r1.get_json()["status"] == "error"
        # 名称必填
        r2 = _add_customer(client, code="CUS-002", name="")
        assert r2.get_json()["status"] == "error"
        # 编号重复
        r3 = _add_customer(client, code="CUS-001", name="客户丙")
        assert r3.get_json()["status"] == "error"

    def test_get_customer(self):
        """S5：读取客户详情。"""
        client = self._setup()
        _login(client)
        _add_customer(client, code="CUS-001", name="客户甲")
        with app_module.app.app_context():
            cid = Customer.query.filter_by(code="CUS-001").first().id
        g = client.get(f"/customer/{cid}")
        data = g.get_json()
        assert data["status"] == "success"
        assert data["customer"]["code"] == "CUS-001"

    def test_edit_customer(self):
        """S6：行级编辑成功；编号改为另一客户占用的编号被拒绝。"""
        client = self._setup()
        _login(client)
        _add_customer(client, code="CUS-001", name="客户甲")
        _add_customer(client, code="CUS-002", name="客户乙")
        with app_module.app.app_context():
            c1 = Customer.query.filter_by(code="CUS-001").first().id
            c2 = Customer.query.filter_by(code="CUS-002").first().id
        resp = client.post(f"/customer/{c1}/edit", data={"code": "CUS-001", "name": "客户甲改"})
        assert resp.get_json()["status"] == "success", resp.get_json()
        with app_module.app.app_context():
            assert Customer.query.get(c1).name == "客户甲改"
        # 编号改为另一客户已占用的编号
        r = client.post(f"/customer/{c1}/edit", data={"code": "CUS-002", "name": "客户甲改"})
        assert r.get_json()["status"] == "error"

    def test_delete_customer(self):
        """S7：无业务引用时删除成功。"""
        client = self._setup()
        _login(client)
        _add_customer(client, code="CUS-001", name="客户甲")
        with app_module.app.app_context():
            cid = Customer.query.filter_by(code="CUS-001").first().id
        resp = client.post("/customer/delete", json={"ids": [cid]})
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            assert Customer.query.get(cid) is None

    def test_import_customer(self):
        """S8：合法行新增、重复编码跳过、空行跳过。"""
        client = self._setup()
        _login(client)
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "客户导入模板"
        ws.append(["客户编号", "客户名称", "联系人", "电话", "地址"])
        ws.append(["IC001", "导入客户甲", "张三", "13800138000", "广州市"])
        ws.append(["IC002", "导入客户乙", "李四", "13800138001", "深圳市"])
        ws.append(["", "", "", "", ""])  # 空行，应跳过
        ws.append(["IC001", "重复客户", "", "", ""])  # 重复编码，应跳过
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        resp = client.post(
            "/customer/import",
            data={"file": (buf, "customers.xlsx")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        data = resp.get_json()
        assert data["status"] == "success", data
        assert "共导入 2 条" in data["msg"], data
        with app_module.app.app_context():
            assert Customer.query.filter_by(code="IC001").first() is not None
            assert Customer.query.filter_by(code="IC002").first() is not None