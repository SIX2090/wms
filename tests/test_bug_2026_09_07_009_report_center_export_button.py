# -*- coding: utf-8 -*-
"""BUG-2026-09-07-009 回归：报表中心卡片「导出」按钮修复。

背景：卡片导出链接裸调 /report/api/<type>?export=excel 不带 warehouse_id——
有默认仓库时用户无感知地导出"默认仓库全量"；无默认仓库时后端按仓库必填
规则返回 400 JSON，浏览器直接下载一个错误页。

修复：导出显式带默认仓库 warehouse_id（title 注明口径）；无默认仓库时
按钮禁用并提示进预览页选仓。

断言：
  T1. 有默认仓库：/report 页面导出链接含 warehouse_id=<默认仓 id>，title 注明口径。
  T2. 无默认仓库：导出为 disabled 按钮并提示，无裸 warehouse_id 链接。
  T3. 后端路由把 default_warehouse 传入模板上下文（源码锚点）。
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
from app import User, Warehouse, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _login_client():
    client = app_module.app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"})
    return client


class TestBug20260907009:
    def setup_method(self):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            from werkzeug.security import generate_password_hash
            db.session.add(User(username="admin",
                                password_hash=generate_password_hash("admin"),
                                role="admin", must_change_password=False))
            db.session.commit()

    def test_T1_export_link_has_default_warehouse(self):
        with app_module.app.app_context():
            wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
            db.session.add(wh)
            db.session.commit()
            wh_id = wh.id
        client = _login_client()
        r = client.get("/report")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert f"warehouse_id={wh_id}" in html, "导出链接必须显式带默认仓库 id"
        assert "按默认仓库" in html, "导出按钮必须注明口径"
        assert "disabled" not in html.split('导出')[0][-400:], "有默认仓库时按钮不得禁用"

    def test_T2_no_default_warehouse_disables_export(self):
        with app_module.app.app_context():
            wh = Warehouse(code="WHB", name="仓库B", is_default=False, status="active")
            db.session.add(wh)
            db.session.commit()
        client = _login_client()
        r = client.get("/report")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert "未配置默认仓库" in html, "无默认仓库时必须提示"
        assert "disabled" in html, "无默认仓库时导出按钮必须禁用"
        assert "export=excel&" not in html and "export=excel\"" not in html, \
            "无默认仓库时不得渲染裸导出链接"

    def test_T3_route_passes_default_warehouse(self):
        src = (APP_DIR / "routes" / "report.py").read_text(encoding="utf-8")
        assert "default_warehouse=get_default_warehouse()" in src, \
            "/report 路由必须把 default_warehouse 传入模板"
