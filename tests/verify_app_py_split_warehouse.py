# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：仓库（warehouse）域路由迁移到 routes/warehouse.py。

采用 register-on-app 模式（register_warehouse_routes(app)），endpoint 名保持不变
（如 warehouse_list），URL 路径不变，因此模板/导航中的 url_for('warehouse_list')
等引用无需改动。

验收点：
S1. 11 个 endpoint（warehouse_list/add_warehouse/get_warehouse/edit_warehouse/
    delete_warehouse/batch_delete_warehouse_master/warehouse_set_default/
    warehouse_api_list/download_warehouse_template/export_warehouse/import_warehouse）
    已注册，且仍是未加前缀的原始 endpoint 名，不存在 warehouse.xxx 带前缀的重复 endpoint。
S2. URL 路径保持不变（/warehouse、/warehouse/add、/warehouse/<id>、
    /warehouse/<id>/edit、/warehouse/<id>/delete、/warehouse/delete、
    /warehouse/<id>/set_default、/warehouse/api/list、/warehouse/download_template、
    /warehouse/export、/warehouse/import）。
S3. 仓库列表页可渲染（200，含"仓库"字样）。
S4. 新增仓库成功；编码/名称必填、编码/名称重复被拒绝。
S5. 读取仓库详情成功。
S6. 行级编辑成功；编码改为另一仓库占用的编码被拒绝。
S7. 删除仓库成功（无业务引用时）。
S8. 设为默认仓成功。
S9. 导入仓库：合法行新增，重复编码跳过。
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
from app import db, Warehouse  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

WAREHOUSE_ENDPOINTS = [
    "warehouse_list",
    "add_warehouse",
    "get_warehouse",
    "edit_warehouse",
    "delete_warehouse",
    "batch_delete_warehouse_master",
    "warehouse_set_default",
    "warehouse_api_list",
    "download_warehouse_template",
    "export_warehouse",
    "import_warehouse",
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


def _add_warehouse(client, code="WH001", name="材料仓", **extra):
    data = {"code": code, "name": name}
    data.update(extra)
    return client.post("/warehouse/add", data=data)


class TestWarehouseRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_endpoints_and_urls(self):
        """S1/S2：11 个 endpoint 注册、URL 不变、无前缀重复。"""
        with app_module.app.app_context():
            for ep in WAREHOUSE_ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            for ep in WAREHOUSE_ENDPOINTS:
                assert f"warehouse.{ep}" not in app_module.app.view_functions, f"warehouse.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("warehouse_list") == "/warehouse"
                assert url_for("add_warehouse") == "/warehouse/add"
                assert url_for("get_warehouse", id=1) == "/warehouse/1"
                assert url_for("edit_warehouse", id=1) == "/warehouse/1/edit"
                assert url_for("delete_warehouse", id=1) == "/warehouse/1/delete"
                assert url_for("batch_delete_warehouse_master") == "/warehouse/delete"
                assert url_for("warehouse_set_default", warehouse_id=1) == "/warehouse/1/set_default"
                assert url_for("warehouse_api_list") == "/warehouse/api/list"
                assert url_for("download_warehouse_template") == "/warehouse/download_template"
                assert url_for("export_warehouse") == "/warehouse/export"
                assert url_for("import_warehouse") == "/warehouse/import"

    def test_warehouse_list(self):
        """S3：列表页可渲染。"""
        client = self._setup()
        _login(client)
        resp = client.get("/warehouse")
        assert resp.status_code == 200
        assert "仓库" in resp.get_data(as_text=True)

    def test_add_warehouse(self):
        """S4：新增成功、编码/名称必填、重复被拒绝。"""
        client = self._setup()
        _login(client)
        resp = _add_warehouse(client, code="WH001", name="材料仓")
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            assert Warehouse.query.filter_by(code="WH001").first() is not None
        # 编码必填
        r1 = _add_warehouse(client, code="", name="材料仓2")
        assert r1.get_json()["status"] == "error"
        # 名称必填
        r2 = _add_warehouse(client, code="WH002", name="")
        assert r2.get_json()["status"] == "error"
        # 编码重复
        r3 = _add_warehouse(client, code="WH001", name="材料仓3")
        assert r3.get_json()["status"] == "error"

    def test_get_warehouse(self):
        """S5：读取仓库详情。"""
        client = self._setup()
        _login(client)
        _add_warehouse(client, code="WH001", name="材料仓")
        with app_module.app.app_context():
            wid = Warehouse.query.filter_by(code="WH001").first().id
        g = client.get(f"/warehouse/{wid}")
        data = g.get_json()
        assert data["status"] == "success"
        assert data["warehouse"]["code"] == "WH001"

    def test_edit_warehouse(self):
        """S6：行级编辑成功；编码改为另一仓库占用的编码被拒绝。"""
        client = self._setup()
        _login(client)
        _add_warehouse(client, code="WH001", name="材料仓")
        _add_warehouse(client, code="WH002", name="成品仓")
        with app_module.app.app_context():
            w1 = Warehouse.query.filter_by(code="WH001").first().id
            w2 = Warehouse.query.filter_by(code="WH002").first().id
        resp = client.post(f"/warehouse/{w1}/edit", data={"code": "WH001", "name": "材料仓改"})
        assert resp.get_json()["status"] == "success", resp.get_json()
        with app_module.app.app_context():
            assert db.session.get(Warehouse, w1).name == "材料仓改"
        # 编码改为另一仓库已占用的编码
        r = client.post(f"/warehouse/{w1}/edit", data={"code": "WH002", "name": "材料仓改"})
        assert r.get_json()["status"] == "error"

    def test_delete_warehouse(self):
        """S7：无业务引用时删除成功。"""
        client = self._setup()
        _login(client)
        _add_warehouse(client, code="WH001", name="材料仓")
        with app_module.app.app_context():
            wid = Warehouse.query.filter_by(code="WH001").first().id
        resp = client.post(f"/warehouse/{wid}/delete")
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            assert db.session.get(Warehouse, wid) is None

    def test_warehouse_set_default(self):
        """S8：设为默认仓成功（仅 active 状态）。"""
        client = self._setup()
        _login(client)
        _add_warehouse(client, code="WH001", name="材料仓")
        with app_module.app.app_context():
            wid = Warehouse.query.filter_by(code="WH001").first().id
        resp = client.post(f"/warehouse/{wid}/set_default")
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            assert db.session.get(Warehouse, wid).is_default is True

    def test_import_warehouse(self):
        """S9：合法行新增、重复编码跳过、空行跳过。"""
        client = self._setup()
        _login(client)
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "仓库导入模板"
        ws.append(["仓库编码", "仓库名称", "仓库类型", "仓库位置", "状态", "备注"])
        ws.append(["IW001", "导入材料仓", "原料仓", "一楼", "active", ""])
        ws.append(["IW002", "导入成品仓", "成品仓", "二楼", "active", ""])
        ws.append(["", "", "", "", "", ""])  # 空行，应跳过
        ws.append(["IW001", "重复仓库", "", "", "", ""])  # 重复编码，应跳过
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        resp = client.post(
            "/warehouse/import",
            data={"file": (buf, "warehouses.xlsx")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        data = resp.get_json()
        assert data["status"] == "success", data
        assert "共导入 2 条" in data["msg"], data
        with app_module.app.app_context():
            assert Warehouse.query.filter_by(code="IW001").first() is not None
            assert Warehouse.query.filter_by(code="IW002").first() is not None