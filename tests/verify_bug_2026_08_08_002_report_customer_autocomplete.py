# -*- coding: utf-8 -*-
"""
BUG-2026-08-08-002 回归测试：报表页 客户/部门 输入框自动补全

测试目标：
  - report_view.html 的 customer 输入框新增 client 端自动补全下拉：
    加载 /api/customers，按 名称/编码 关键词过滤（escapeHtml 转义防 XSS），
    点选后回填客户名称并关闭下拉；加载失败时静默降级为普通输入框。

具体断言：
  T1. /report/view/out_detail 渲染包含 customerDropdown / customerList 容器
  T2. customer 输入框带 autocomplete="off"
  T3. JS 包含 /api/customers 加载逻辑
  T4. JS 包含 loadCustomersForSearch 过滤逻辑

使用方法：
  cd /workspace && python -m pytest tests/verify_bug_2026_08_08_002_report_customer_autocomplete.py -xvs
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
from app import Warehouse, User, db  # noqa: E402

app_module.app.config["TESTING"] = True


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_common():
    from werkzeug.security import generate_password_hash
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    db.session.add_all([wh, user])
    db.session.commit()


def _make_client():
    import re
    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post(
        "/login",
        data={"username": "admin", "password": "admin", "csrf_token": token},
    )
    return client


def _get_out_detail_page():
    with app_module.app.app_context():
        _reset_db()
        _seed_common()
        client = _make_client()
        resp = client.get("/report/view/out_detail", follow_redirects=True)
        assert resp.status_code == 200
        return resp.get_data(as_text=True)


class TestBug20260808002:
    def test_T1_customer_dropdown_container_rendered(self):
        text = _get_out_detail_page()
        assert 'id="customerDropdown"' in text, "客户下拉容器缺失"
        assert 'id="customerList"' in text, "客户下拉列表容器缺失"

    def test_T2_customer_input_autocomplete_off(self):
        text = _get_out_detail_page()
        seg = text.split('id="customer"', 1)[1][:300]
        assert 'autocomplete="off"' in seg, "customer 输入框缺少 autocomplete=off"

    def test_T3_js_loads_customers_api(self):
        text = _get_out_detail_page()
        assert "/api/customers" in text, "缺少 /api/customers 加载逻辑"

    def test_T4_js_has_customer_filter_logic(self):
        text = _get_out_detail_page()
        assert "loadCustomersForSearch" in text, "缺少客户加载函数"
        assert "customerSearchTimeout" in text, "缺少客户搜索防抖逻辑"
