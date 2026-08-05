# -*- coding: utf-8 -*-
# app.py 拆分回归测试：报表（report）域路由迁移到 routes/report.py。
#
# register-on-app 模式（register_report_routes(app)），endpoint 名与 URL 不变。
#
# 验收点：
# A1. 核心 endpoint 已注册，且无 report.xxx 前缀重复。
# A2. URL 路径保持不变。
# A3. 报表列表页可渲染（200）。
# A4. 拆分模块 routes/report.py 可正常导入并暴露 register_report_routes。
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
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINTS = [
    "report", "purchase_report", "report_dashboard", "report_dashboard_ai_insights",
    "report_view", "report_api_query", "report_inout_print", "report_inout_export",
    "report_stock_print", "report_print_not_implemented",
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


class TestReportRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_endpoints_and_urls(self):
        with app_module.app.app_context():
            for ep in ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
                assert f"report.{ep}" not in app_module.app.view_functions, f"report.{ep} 重复注册"
        from flask import url_for
        with app_module.app.test_request_context():
            assert url_for("report") == "/report"
            assert url_for("purchase_report") == "/purchase_report"
            assert url_for("report_dashboard") == "/report/dashboard"
            assert url_for("report_dashboard_ai_insights") == "/report/dashboard/ai_insights"
            assert url_for("report_view", report_type="abc") == "/report/view/abc"
            assert url_for("report_api_query") == "/report/api/query"
            assert url_for("report_inout_print") == "/report/inout/print"
            assert url_for("report_inout_export") == "/report/inout/export"
            assert url_for("report_stock_print") == "/report/stock/print"
            assert url_for("report_print_not_implemented") == "/report/print"

    def test_module_importable(self):
        # 拆分模块可正常导入且暴露注册入口（不注册到 app，避免与内联路由重复）
        import routes.report as report_module
        assert hasattr(report_module, "register_report_routes")
        assert callable(report_module.register_report_routes)

    def test_report_page(self):
        client = self._setup()
        _login(client)
        resp = client.get("/report")
        assert resp.status_code == 200
        assert "report" in resp.get_data(as_text=True).lower()

    def test_purchase_report_page(self):
        client = self._setup()
        _login(client)
        resp = client.get("/purchase_report")
        assert resp.status_code == 200

    def test_report_print_not_implemented(self):
        client = self._setup()
        _login(client)
        resp = client.get("/report/print")
        assert resp.status_code == 404