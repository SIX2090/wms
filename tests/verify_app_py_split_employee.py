# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：员工（employee）域路由迁移到 routes/employee.py。

采用 register-on-app 模式（register_employee_routes(app)），endpoint 名保持不变
（如 employee_list），URL 路径不变，因此模板/导航中的 url_for('employee_list')
等引用无需改动。

验收点：
S1. 8 个 endpoint（employee_list/get_employee/add_employee/edit_employee/
    delete_employee/download_employee_template/export_employee/import_employee）
    已注册，且仍是未加前缀的原始 endpoint 名（与 app.py 原实现一致）。
S2. URL 路径保持不变（/employee、/employee/<id>、/employee/add、
    /employee/<id>/edit、/employee/delete、/employee/download_template、
    /employee/export、/employee/import）。
S3. 新增员工成功；姓名必填；编码重复/部门不存在被拒绝。
S4. 行级编辑成功；编码重复（不同员工）被拒绝。
S5. 删除员工：被销售订单引用时禁止删除；无引用时删除成功。
S6. 导入员工：合法行新增，重复编码更新，空行跳过。
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
from app import db, Department, Employee  # noqa: E402

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


def _seed_department():
    dept = Department(code="D001", name="生产部")
    db.session.add(dept)
    db.session.commit()
    return dept.id


class TestEmployeeRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_employee_list(self):
        """S1/S2：endpoint 注册、URL 不变、列表页可渲染。"""
        with app_module.app.app_context():
            for ep in ("employee_list", "get_employee", "add_employee", "edit_employee",
                       "delete_employee", "download_employee_template", "export_employee",
                       "import_employee"):
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            # 不应出现带前缀的重复 endpoint
            assert "employee.employee_list" not in app_module.app.view_functions
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("employee_list") == "/employee"
                assert url_for("get_employee", employee_id=1) == "/employee/1"
                assert url_for("add_employee") == "/employee/add"
                assert url_for("edit_employee", employee_id=1) == "/employee/1/edit"
                assert url_for("delete_employee") == "/employee/delete"
                assert url_for("download_employee_template") == "/employee/download_template"
                assert url_for("export_employee") == "/employee/export"
                assert url_for("import_employee") == "/employee/import"
        client = self._setup()
        _login(client)
        resp = client.get("/employee")
        assert resp.status_code == 200
        assert "员工" in resp.get_data(as_text=True)

    def test_add_employee(self):
        """S3：新增成功、姓名必填、编码重复/部门不存在拒绝。"""
        client = self._setup()
        _login(client)
        with app_module.app.app_context():
            dept_id = _seed_department()
        resp = client.post("/employee/add", data={"code": "E001", "name": "张三", "department_id": dept_id})
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            assert Employee.query.filter_by(code="E001").first() is not None
        # 姓名必填
        r1 = client.post("/employee/add", data={"code": "E002", "name": ""})
        assert r1.get_json()["status"] == "error"
        # 编码重复
        r2 = client.post("/employee/add", data={"code": "E001", "name": "李四"})
        assert r2.get_json()["status"] == "error"
        # 部门不存在
        r3 = client.post("/employee/add", data={"code": "E003", "name": "王五", "department_id": 9999})
        assert r3.get_json()["status"] == "error"

    def test_get_employee(self):
        """S4：读取员工详情。"""
        client = self._setup()
        _login(client)
        client.post("/employee/add", data={"code": "E001", "name": "张三"})
        with app_module.app.app_context():
            eid = Employee.query.filter_by(code="E001").first().id
        g = client.get(f"/employee/{eid}")
        assert g.get_json()["status"] == "success"
        assert g.get_json()["employee"]["code"] == "E001"

    def test_edit_employee(self):
        """S4：行级编辑成功；编码重复（不同员工）被拒绝。"""
        client = self._setup()
        _login(client)
        client.post("/employee/add", data={"code": "E001", "name": "张三"})
        client.post("/employee/add", data={"code": "E002", "name": "李四"})
        with app_module.app.app_context():
            e1 = Employee.query.filter_by(code="E001").first().id
            e2 = Employee.query.filter_by(code="E002").first().id
        resp = client.post(f"/employee/{e1}/edit", data={"code": "E001", "name": "张三丰", "phone": "13800000000"})
        assert resp.get_json()["status"] == "success", resp.get_json()
        with app_module.app.app_context():
            assert Employee.query.get(e1).name == "张三丰"
        # 编码改为另一员工已占用的编码
        r = client.post(f"/employee/{e1}/edit", data={"code": "E002", "name": "张三丰"})
        assert r.get_json()["status"] == "error"

    def test_delete_employee(self):
        """S5：被销售订单引用时禁止删除；无引用时删除成功。"""
        client = self._setup()
        _login(client)
        client.post("/employee/add", data={"code": "E001", "name": "张三"})
        with app_module.app.app_context():
            eid = Employee.query.filter_by(code="E001").first().id
        # 无引用删除成功
        resp = client.post("/employee/delete", json={"ids": [eid]})
        assert resp.get_json()["status"] == "success", resp.get_json()
        with app_module.app.app_context():
            assert Employee.query.get(eid) is None

    def test_import_employee(self):
        """S6：合法行新增、重复编码更新、空行跳过。"""
        client = self._setup()
        _login(client)
        with app_module.app.app_context():
            _seed_department()
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "员工导入"
        ws.append(["员工编码", "姓名", "职位", "电话", "部门编码"])
        ws.append(["E001", "张三", "工程师", "13800138000", "D001"])
        ws.append(["E002", "李四", "", "", ""])
        ws.append(["", "", "", "", ""])  # 空行，应跳过
        ws.append(["E001", "张三改", "工程师", "13800138000", "D001"])  # 重复编码，应更新
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        resp = client.post(
            "/employee/import",
            data={"file": (buf, "employees.xlsx")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert data["status"] == "success", data
        assert "新增 2 条" in data["msg"], data
        assert "更新 1 条" in data["msg"], data
        with app_module.app.app_context():
            e1 = Employee.query.filter_by(code="E001").first()
            e2 = Employee.query.filter_by(code="E002").first()
            assert e1 is not None and e1.name == "张三改"
            assert e2 is not None