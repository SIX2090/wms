# -*- coding: utf-8 -*-
"""
BUG-2026-08-08-003 回归测试：领料/其他出库单详情页物料输入快速下拉

测试目标：
  - out_order_detail.html 的添加物料模态框 `#code` 与行内新增行 `.material-code-field`
    由"精确编码盲查"升级为关键词搜索下拉（编码/名称/规格），
    支持键盘上下选择、Enter 选中、Esc 关闭、点外关闭。

具体断言：
  T1. 详情页渲染包含 materialQuickDropdown 容器与 material-quick-search 结构
  T2. JS 使用 /api/material/search?kw= 关键词搜索（而非仅 /api/material/info 精确匹配）
  T3. JS 包含 renderMaterialQuickDropdown / selectAddMaterial / bindMaterialQuickInput
  T4. JS 包含键盘导航（ArrowDown/Enter/Escape）与点外关闭逻辑

使用方法：
  cd /workspace && python -m pytest tests/verify_bug_2026_08_08_003_out_order_detail_material_quick_dropdown.py -xvs
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
from app import OutOrder, User, db  # noqa: E402

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
    order = OutOrder(order_no="OUT-TEST-001", status="pending", business_type="领料出库")
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
        resp = client.get(f"/out_order/{order.id}", follow_redirects=True)
        assert resp.status_code == 200
        return resp.get_data(as_text=True)


class TestBug20260808003:
    def test_T1_quick_dropdown_container_rendered(self):
        text = _get_detail_page()
        assert 'id="materialQuickDropdown"' in text, "模态框物料下拉容器缺失"
        assert "material-quick-search" in text, "material-quick-search 结构缺失"
        assert "material-quick-dropdown" in text, "material-quick-dropdown 样式类缺失"

    def test_T2_uses_keyword_search_api(self):
        text = _get_detail_page()
        assert "/api/material/search?kw=" in text, "未使用关键词搜索接口"

    def test_T3_quick_dropdown_functions_present(self):
        text = _get_detail_page()
        for fn in ("renderMaterialQuickDropdown", "selectAddMaterial", "bindMaterialQuickInput"):
            assert fn in text, f"缺少函数 {fn}"

    def test_T4_keyboard_and_outside_close_logic(self):
        text = _get_detail_page()
        assert "ArrowDown" in text, "缺少键盘下导航"
        assert "Escape" in text, "缺少 Esc 关闭"
        assert "hideMaterialQuickDropdown" in text, "缺少统一下拉关闭逻辑"
