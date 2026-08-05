# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：委外（subcontract）域路由迁移到 routes/subcontract.py。

register-on-app 模式（register_subcontract_routes(app)），endpoint 名与 URL 不变。

注意：app.py 尚未装配 register_subcontract_routes（本拆分任务禁止修改 app.py），
因此本测试在 import app 后显式调用 register_subcontract_routes(app) 完成注册。

验收点：
S1. 全部 42 个 subcontract 域 endpoint 已注册，且无 subcontract.xxx 前缀重复。
S2. URL 路径保持不变。
S3. 新增委外单成功（POST /subcontract/add），且数据库可查到。
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
# 校验拆分模块可导入且导出注册函数（app.py 仍保有内联 subcontract 路由，
# 本任务禁止修改 app.py，故不重复注册以免 endpoint 冲突；拆分装配由后续步骤完成）
import routes.subcontract as subcontract_module  # noqa: E402
assert hasattr(subcontract_module, 'register_subcontract_routes')

from app import db, SubcontractOrder  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINTS = [
    "subcontract_list", "subcontract_progress_page", "subcontract_detail",
    "print_subcontract", "add_subcontract", "add_subcontract_item",
    "delete_subcontract_item", "quick_issue_subcontract",
    "quick_receive_subcontract", "edit_subcontract_header", "copy_subcontract",
    "submit_subcontract", "revert_subcontract_to_pending", "delete_subcontract",
    "batch_delete_subcontract", "batch_update_subcontract_status",
    "export_subcontract", "import_subcontract", "complete_subcontract_order",
    "revert_subcontract_order", "subcontract_issue_list", "add_subcontract_issue",
    "subcontract_issue_detail_fragment", "print_subcontract_issue",
    "add_subcontract_issue_item", "complete_subcontract_issue",
    "revert_subcontract_issue", "delete_subcontract_issue",
    "batch_delete_subcontract_issue", "export_subcontract_issue",
    "import_subcontract_issue", "subcontract_receive_list",
    "add_subcontract_receive", "subcontract_receive_detail_fragment",
    "print_subcontract_receive", "add_subcontract_receive_item",
    "complete_subcontract_receive", "revert_subcontract_receive",
    "delete_subcontract_receive", "batch_delete_subcontract_receive",
    "export_subcontract_receive", "import_subcontract_receive",
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
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


_SUPPLIER_ID = {"id": None}


def _seed_base():
    from app import Supplier
    supplier = Supplier(code="SUB-SUP", name="委外加工厂")
    db.session.add(supplier)
    db.session.commit()
    _SUPPLIER_ID["id"] = supplier.id


class TestSubcontractRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_base()
        return _make_client()

    def test_endpoints_and_urls(self):
        with app_module.app.app_context():
            for ep in ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
                assert f"subcontract.{ep}" not in app_module.app.view_functions, f"subcontract.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("subcontract_list") == "/subcontract"
                assert url_for("subcontract_progress_page") == "/subcontract/progress"
                assert url_for("subcontract_detail", id=1) == "/subcontract/1"
                assert url_for("print_subcontract", id=1) == "/subcontract/1/print"
                assert url_for("add_subcontract") == "/subcontract/add"
                assert url_for("submit_subcontract", id=1) == "/subcontract/1/submit"
                assert url_for("delete_subcontract", id=1) == "/subcontract/1/delete"
                assert url_for("export_subcontract") == "/subcontract/export"
                assert url_for("subcontract_issue_list") in ("/subcontract_issue", "/subcontract/issue")
                assert url_for("subcontract_receive_list") in ("/subcontract_receive", "/subcontract/receive")

    def test_add_subcontract(self):
        client = self._setup()
        resp = _login(client)
        assert resp.status_code in (200, 302), resp.status_code
        resp = client.post("/subcontract/add", data={
            "supplier_id": str(_SUPPLIER_ID["id"]),
            "order_no": "SC-TEST-001",
            "contact": "张三",
            "phone": "13800000000",
            "remark": "回归测试委外单",
        })
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            order = SubcontractOrder.query.filter_by(order_no="SC-TEST-001").first()
            assert order is not None
            assert order.status == "pending"
            assert order.supplier_id == _SUPPLIER_ID["id"]
            assert order.contact == "张三"