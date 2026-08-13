# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：部门（department）域路由迁移到 routes/department.py。

采用 register-on-app 模式（register_department_routes(app)），endpoint 名保持不变
（如 department_list），URL 路径不变，因此模板/导航中的 url_for('department_list')
等引用无需改动。

验收点：
S1. 10 个 endpoint（department_list/add_department/get_department/edit_department/
    delete_department/batch_delete_department_master/department_api_list/
    download_department_template/export_department/import_department）
    已注册，且仍是未加前缀的原始 endpoint 名，不存在 department.xxx 带前缀的重复 endpoint。
S2. URL 路径保持不变（/department、/department/add、/department/<id>、
    /department/<id>/edit、/department/<id>/delete、/department/delete、
    /department/api/list、/department/download_template、/department/export、
    /department/import）。
S3. 部门列表页可渲染（200，含"部门"字样）。
S4. 新增部门成功；编码/名称必填、编码/名称重复被拒绝。
S5. 读取部门详情成功。
S6. 行级编辑成功；编码改为另一部门占用的编码被拒绝。
S7. 删除部门成功（无业务引用时）。
S8. 导入部门：合法行新增，重复编码跳过。
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
from app import db, Department  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

DEPARTMENT_ENDPOINTS = [
    "department_list",
    "add_department",
    "get_department",
    "edit_department",
    "delete_department",
    "batch_delete_department_master",
    "department_api_list",
    "download_department_template",
    "export_department",
    "import_department",
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


def _add_department(client, code="D001", name="生产部", **extra):
    data = {"code": code, "name": name}
    data.update(extra)
    return client.post("/department/add", data=data)


class TestDepartmentRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_endpoints_and_urls(self):
        """S1/S2：10 个 endpoint 注册、URL 不变、无前缀重复。"""
        with app_module.app.app_context():
            for ep in DEPARTMENT_ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            for ep in DEPARTMENT_ENDPOINTS:
                assert f"department.{ep}" not in app_module.app.view_functions, f"department.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("department_list") == "/department"
                assert url_for("add_department") == "/department/add"
                assert url_for("get_department", id=1) == "/department/1"
                assert url_for("edit_department", id=1) == "/department/1/edit"
                assert url_for("delete_department", id=1) == "/department/1/delete"
                assert url_for("batch_delete_department_master") == "/department/delete"
                assert url_for("department_api_list") == "/department/api/list"
                assert url_for("download_department_template") == "/department/download_template"
                assert url_for("export_department") == "/department/export"
                assert url_for("import_department") == "/department/import"

    def test_department_list(self):
        """S3：列表页可渲染。"""
        client = self._setup()
        _login(client)
        resp = client.get("/department")
        assert resp.status_code == 200
        assert "部门" in resp.get_data(as_text=True)

    def test_add_department(self):
        """S4：新增成功、编码/名称必填、重复被拒绝。"""
        client = self._setup()
        _login(client)
        resp = _add_department(client, code="D001", name="生产部")
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            assert Department.query.filter_by(code="D001").first() is not None
        # 编码必填
        r1 = _add_department(client, code="", name="生产部2")
        assert r1.get_json()["status"] == "error"
        # 名称必填
        r2 = _add_department(client, code="D002", name="")
        assert r2.get_json()["status"] == "error"
        # 编码重复
        r3 = _add_department(client, code="D001", name="生产部3")
        assert r3.get_json()["status"] == "error"

    def test_get_department(self):
        """S5：读取部门详情。"""
        client = self._setup()
        _login(client)
        _add_department(client, code="D001", name="生产部")
        with app_module.app.app_context():
            did = Department.query.filter_by(code="D001").first().id
        g = client.get(f"/department/{did}")
        data = g.get_json()
        assert data["status"] == "success"
        assert data["department"]["code"] == "D001"

    def test_edit_department(self):
        """S6：行级编辑成功；编码改为另一部门占用的编码被拒绝。"""
        client = self._setup()
        _login(client)
        _add_department(client, code="D001", name="生产部")
        _add_department(client, code="D002", name="质检部")
        with app_module.app.app_context():
            d1 = Department.query.filter_by(code="D001").first().id
            d2 = Department.query.filter_by(code="D002").first().id
        resp = client.post(f"/department/{d1}/edit", data={"code": "D001", "name": "生产部改"})
        assert resp.get_json()["status"] == "success", resp.get_json()
        with app_module.app.app_context():
            assert db.session.get(Department, d1).name == "生产部改"
        # 编码改为另一部门已占用的编码
        r = client.post(f"/department/{d1}/edit", data={"code": "D002", "name": "生产部改"})
        assert r.get_json()["status"] == "error"

    def test_delete_department(self):
        """S7：无业务引用时删除成功。"""
        client = self._setup()
        _login(client)
        _add_department(client, code="D001", name="生产部")
        with app_module.app.app_context():
            did = Department.query.filter_by(code="D001").first().id
        resp = client.post(f"/department/{did}/delete")
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            assert db.session.get(Department, did) is None

    def test_import_department(self):
        """S8：合法行新增、重复编码跳过、空行跳过。"""
        client = self._setup()
        _login(client)
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "部门导入模板"
        ws.append(["部门编码", "部门名称", "状态", "备注"])
        ws.append(["ID001", "导入生产部", "active", ""])
        ws.append(["ID002", "导入质检部", "active", ""])
        ws.append(["", "", "", ""])  # 空行，应跳过
        ws.append(["ID001", "重复部门", "", ""])  # 重复编码，应跳过
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        resp = client.post(
            "/department/import",
            data={"file": (buf, "departments.xlsx")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        data = resp.get_json()
        assert data["status"] == "success", data
        assert "共导入 2 条" in data["msg"], data
        with app_module.app.app_context():
            assert Department.query.filter_by(code="ID001").first() is not None
            assert Department.query.filter_by(code="ID002").first() is not None

    def test_delete_department_blocks_employee_reference(self):
        """部门删除时应检查员工档案引用，有员工时拒绝删除。"""
        client = self._setup()
        _login(client)
        _add_department(client, code="D001", name="生产部")
        with app_module.app.app_context():
            department = Department.query.filter_by(code="D001").first()
            assert department is not None
            from app import Employee
            db.session.add(Employee(name="张三", department_id=department.id))
            db.session.commit()
            department_id = department.id
        response = client.post(f"/department/{department_id}/delete")
        data = response.get_json()
        assert response.status_code == 400, data
        assert data["status"] == "error", data
        assert "员工档案" in data["msg"], data
        with app_module.app.app_context():
            assert db.session.get(Department, department_id) is not None

    def test_batch_delete_department_blocks_employee_reference(self):
        """批量删除部门时应检查员工档案引用，有员工的部门拒绝删除。"""
        client = self._setup()
        _login(client)
        _add_department(client, code="D001", name="生产部")
        _add_department(client, code="D002", name="销售部")
        with app_module.app.app_context():
            dept1 = Department.query.filter_by(code="D001").first()
            dept2 = Department.query.filter_by(code="D002").first()
            assert dept1 is not None and dept2 is not None
            from app import Employee
            db.session.add(Employee(name="张三", department_id=dept1.id))
            db.session.commit()
            dept1_id = dept1.id
            dept2_id = dept2.id
        response = client.post("/department/delete", json={"ids": [dept1_id, dept2_id]})
        data = response.get_json()
        assert response.status_code == 200, data
        assert data["status"] == "success", data
        assert "已删除 1 个部门" in data["msg"], data
        assert "员工档案" in data["msg"], data
        with app_module.app.app_context():
            assert db.session.get(Department, dept1_id) is not None
            assert db.session.get(Department, dept2_id) is None