# -*- coding: utf-8 -*-
"""
BUG-2026-08-08-002 回归测试：报表页 客户/部门 输入框自动补全

历史背景：
  最初修复为 report_view.html 的 customer 输入框增加了页面级自写下拉
  （customerDropdown / customerList + /api/customers 加载）。
  但该实现与全局 quick-select 组件（data-ks="customer"）并存，
  形成双下拉互相遮挡、Enter 键行为冲突（2026-08-30 报表输入问题）。

当前口径（2026-08-30 起）：
  报表页 物料/供应商/客户 筛选输入框统一由全局 quick-select 组件接管
  （data-ks 属性声明式绑定，支持键盘导航与拼音匹配），
  页面不再维护自写下拉 DOM 与加载逻辑。

具体断言：
  T1. customer 输入框带 data-ks="customer"，且选中回填名称（data-ks-put="name"）
  T2. customer 输入框带 autocomplete="off"
  T3. 页面不再包含自写下拉容器与 /api/customers 加载逻辑（双下拉已消除）
  T4. 物料输入框带 data-ks="material"（台账等报表的物料搜索同口径）

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
    def test_T1_customer_input_uses_quick_select(self):
        text = _get_out_detail_page()
        seg = text.split('id="customer"', 1)[1][:400]
        assert 'data-ks="customer"' in seg, "customer 输入框未接入 quick-select（data-ks=customer）"
        assert 'data-ks-put="name"' in seg, "customer 选中应回填名称（后端按名称文本模糊匹配）"

    def test_T2_customer_input_autocomplete_off(self):
        text = _get_out_detail_page()
        seg = text.split('id="customer"', 1)[1][:400]
        assert 'autocomplete="off"' in seg, "customer 输入框缺少 autocomplete=off"

    def test_T3_legacy_dropdown_removed(self):
        text = _get_out_detail_page()
        assert 'id="customerDropdown"' not in text, "旧版客户自写下拉容器应已移除（避免双下拉冲突）"
        assert 'id="customerList"' not in text, "旧版客户下拉列表容器应已移除"
        assert "loadCustomersForSearch" not in text, "旧版 /api/customers 加载逻辑应已移除"

    def test_T4_material_input_uses_quick_select(self):
        text = _get_out_detail_page()
        seg = text.split('id="material_code"', 1)[1][:400]
        assert 'data-ks="material"' in seg, "物料搜索输入框未接入 quick-select（data-ks=material）"
        assert 'id="materialDropdown"' not in text, "旧版物料自写下拉容器应已移除"
