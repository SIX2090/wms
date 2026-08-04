# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：合同（contract）域路由迁移到 routes/contract.py。

采用 register-on-app 模式（register_contract_routes(app)），endpoint 名保持不变
（如 contract_list、api_contracts_search），URL 路径不变，因此模板/导航中的
url_for('contract_list') 等引用无需改动。

验收点：
S1. 11 个 endpoint（contract_list/add_contract/get_contract/edit_contract/
    delete_contract/batch_delete_contract_master/contract_api_list/
    api_contracts_search/download_contract_template/export_contract/import_contract）
    已注册，且仍是未加前缀的原始 endpoint 名，不存在 contract.xxx 带前缀的重复 endpoint。
S2. URL 路径保持不变（/contract、/contract/add、/contract/<id>、
    /contract/<id>/edit、/contract/<id>/delete、/contract/delete、
    /contract/api/list、/api/contracts、/contract/download_template、
    /contract/export、/contract/import）。
S3. 合同列表页可渲染（200，含"合同"字样）。
S4. 新增合同成功；合同编号/工程名称必填、合同编号重复被拒绝。
S5. 读取合同详情成功。
S6. 行级编辑成功；合同编号改为另一合同占用的编号被拒绝。
S7. 删除合同成功（无业务引用时）。
S8. 合同搜索 API 返回标准信封 {status, data:{contracts}}。
S9. 导入合同：合法行新增，已存在合同编号更新。
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
from app import db, Contract  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

CONTRACT_ENDPOINTS = [
    "contract_list",
    "add_contract",
    "get_contract",
    "edit_contract",
    "delete_contract",
    "batch_delete_contract_master",
    "contract_api_list",
    "api_contracts_search",
    "download_contract_template",
    "export_contract",
    "import_contract",
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


def _add_contract(client, contract_no="HT001", project_name="工程甲", **extra):
    data = {"contract_no": contract_no, "project_name": project_name}
    data.update(extra)
    return client.post("/contract/add", data=data)


class TestContractRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_endpoints_and_urls(self):
        """S1/S2：11 个 endpoint 注册、URL 不变、无前缀重复。"""
        with app_module.app.app_context():
            for ep in CONTRACT_ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            for ep in CONTRACT_ENDPOINTS:
                assert f"contract.{ep}" not in app_module.app.view_functions, f"contract.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("contract_list") == "/contract"
                assert url_for("add_contract") == "/contract/add"
                assert url_for("get_contract", id=1) == "/contract/1"
                assert url_for("edit_contract", id=1) == "/contract/1/edit"
                assert url_for("delete_contract", id=1) == "/contract/1/delete"
                assert url_for("batch_delete_contract_master") == "/contract/delete"
                assert url_for("contract_api_list") == "/contract/api/list"
                assert url_for("api_contracts_search") == "/api/contracts"
                assert url_for("download_contract_template") == "/contract/download_template"
                assert url_for("export_contract") == "/contract/export"
                assert url_for("import_contract") == "/contract/import"

    def test_contract_list(self):
        """S3：列表页可渲染。"""
        client = self._setup()
        _login(client)
        resp = client.get("/contract")
        assert resp.status_code == 200
        assert "合同" in resp.get_data(as_text=True)

    def test_add_contract(self):
        """S4：新增成功、合同编号/工程名称必填、合同编号重复被拒绝。"""
        client = self._setup()
        _login(client)
        resp = _add_contract(client, contract_no="HT001", project_name="工程甲")
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            assert Contract.query.filter_by(contract_no="HT001").first() is not None
        # 合同编号必填
        r1 = _add_contract(client, contract_no="", project_name="工程乙")
        assert r1.get_json()["status"] == "error"
        # 工程名称必填
        r2 = _add_contract(client, contract_no="HT002", project_name="")
        assert r2.get_json()["status"] == "error"
        # 合同编号重复
        r3 = _add_contract(client, contract_no="HT001", project_name="工程丙")
        assert r3.get_json()["status"] == "error"

    def test_get_contract(self):
        """S5：读取合同详情。"""
        client = self._setup()
        _login(client)
        _add_contract(client, contract_no="HT001", project_name="工程甲")
        with app_module.app.app_context():
            cid = Contract.query.filter_by(contract_no="HT001").first().id
        g = client.get(f"/contract/{cid}")
        data = g.get_json()
        assert data["status"] == "success"
        assert data["contract"]["contract_no"] == "HT001"

    def test_edit_contract(self):
        """S6：行级编辑成功；合同编号改为另一合同占用的编号被拒绝。"""
        client = self._setup()
        _login(client)
        _add_contract(client, contract_no="HT001", project_name="工程甲")
        _add_contract(client, contract_no="HT002", project_name="工程乙")
        with app_module.app.app_context():
            c1 = Contract.query.filter_by(contract_no="HT001").first().id
            c2 = Contract.query.filter_by(contract_no="HT002").first().id
        resp = client.post(f"/contract/{c1}/edit", data={"contract_no": "HT001", "project_name": "工程甲改"})
        assert resp.get_json()["status"] == "success", resp.get_json()
        with app_module.app.app_context():
            assert db.session.get(Contract, c1).project_name == "工程甲改"
        # 合同编号改为另一合同已占用的编号
        r = client.post(f"/contract/{c1}/edit", data={"contract_no": "HT002", "project_name": "工程甲改"})
        assert r.get_json()["status"] == "error"

    def test_delete_contract(self):
        """S7：无业务引用时删除成功。"""
        client = self._setup()
        _login(client)
        _add_contract(client, contract_no="HT001", project_name="工程甲")
        with app_module.app.app_context():
            cid = Contract.query.filter_by(contract_no="HT001").first().id
        resp = client.post(f"/contract/{cid}/delete")
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            assert db.session.get(Contract, cid) is None

    def test_api_contracts_search(self):
        """S8：合同搜索 API 返回标准信封 {status, data:{contracts}}。"""
        client = self._setup()
        _login(client)
        _add_contract(client, contract_no="HT001", project_name="厚街医院工程")
        resp = client.get("/api/contracts?keyword=厚街")
        data = resp.get_json()
        assert data["status"] == "success", data
        assert "contracts" in data["data"], data
        assert any(c["contract_no"] == "HT001" for c in data["data"]["contracts"])

    def test_import_contract(self):
        """S9：合法行新增，已存在合同编号更新。"""
        client = self._setup()
        _login(client)
        _add_contract(client, contract_no="HT001", project_name="工程甲")
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "合同档案导入模板"
        ws.append(["合同编号", "工程名称", "状态", "备注"])
        ws.append(["HT002", "导入工程乙", "active", ""])
        ws.append(["HT001", "工程甲更新", "active", "更新备注"])  # 已存在，应更新
        ws.append(["", "", "", ""])  # 空行，应跳过
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        resp = client.post(
            "/contract/import",
            data={"file": (buf, "contracts.xlsx")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        data = resp.get_json()
        assert data["status"] == "success", data
        assert "新增 1 条" in data["msg"], data
        assert "更新 1 条" in data["msg"], data
        with app_module.app.app_context():
            assert Contract.query.filter_by(contract_no="HT002").first() is not None
            assert db.session.get(Contract, Contract.query.filter_by(contract_no="HT001").first().id).project_name == "工程甲更新"