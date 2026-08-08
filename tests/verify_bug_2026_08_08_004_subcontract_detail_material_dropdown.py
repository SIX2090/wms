# -*- coding: utf-8 -*-
"""
BUG-2026-08-08-004 回归测试：委外单详情页三处编码输入关键词下拉

测试目标：
  - subcontract_detail.html 的 productCode / issueCode / receiveCode 三个模态框输入框
    由纯盲打（无任何绑定，搜索按钮无 JS）升级为基于 subcontractMaterials 的客户端
    关键词下拉（编码/名称/规格），支持点选、键盘导航、选中回填关联字段。

具体断言：
  T1. 三个下拉容器 productCodeDropdown / issueCodeDropdown / receiveCodeDropdown 渲染存在
  T2. 三个输入框带 autocomplete="off"
  T3. JS 包含 filterSubcontractMaterials / bindScMaterialInput
  T4. 选中回填逻辑存在（issueName / receiveName）
  T5. 搜索按钮 openSearchBtn / openReceiveSearchBtn 已有 JS 绑定（show()）

使用方法：
  cd /workspace && python -m pytest tests/verify_bug_2026_08_08_004_subcontract_detail_material_dropdown.py -xvs
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
from app import SubcontractOrder, User, db  # noqa: E402

app_module.app.config["TESTING"] = True


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_common():
    from werkzeug.security import generate_password_hash
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    order = SubcontractOrder(order_no="SC-TEST-001", status="pending")
    db.session.add_all([user, order])
    db.session.commit()
    return order


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


def _get_detail_page():
    with app_module.app.app_context():
        _reset_db()
        order = _seed_common()
        client = _make_client()
        resp = client.get(f"/subcontract/{order.id}", follow_redirects=True)
        assert resp.status_code == 200
        return resp.get_data(as_text=True)


class TestBug20260808004:
    def test_T1_three_dropdowns_rendered(self):
        text = _get_detail_page()
        for did in ("productCodeDropdown", "issueCodeDropdown", "receiveCodeDropdown"):
            assert f'id="{did}"' in text, f"下拉容器 {did} 缺失"

    def test_T2_inputs_autocomplete_off(self):
        text = _get_detail_page()
        for iid in ("productCode", "issueCode", "receiveCode"):
            seg = text.split(f'id="{iid}"', 1)[1][:200]
            assert 'autocomplete="off"' in seg, f"{iid} 缺少 autocomplete=off"

    def test_T3_filter_and_bind_functions_present(self):
        text = _get_detail_page()
        assert "filterSubcontractMaterials" in text, "缺少关键词过滤函数"
        assert "bindScMaterialInput" in text, "缺少通用绑定函数"

    def test_T4_select_fill_logic_present(self):
        text = _get_detail_page()
        assert "issueName" in text and "getElementById('issueName').value" in text, "发料选中回填缺失"
        assert "getElementById('receiveName').value" in text, "收货选中回填缺失"

    def test_T5_search_buttons_bound(self):
        text = _get_detail_page()
        assert "issueSearch.show" in text, "发料搜索按钮未绑定下拉展示"
        assert "receiveSearch.show" in text, "收货搜索按钮未绑定下拉展示"
