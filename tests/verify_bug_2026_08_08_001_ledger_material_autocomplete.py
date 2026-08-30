# -*- coding: utf-8 -*-
"""
BUG-2026-08-08-001 回归测试：库存台账物料搜索框关键词自动补全

历史背景：
  最初修复为 report_view.html 物料搜索框增加了页面级自写下拉
  （materialDropdown / materialList + 分页加载 /material/api/all）。
  该实现无键盘导航、大数据量时需循环拉全表，且与客户/供应商筛选的
  交互不一致（2026-08-30 报表输入问题）。

当前口径（2026-08-30 起）：
  物料搜索框统一由全局 quick-select 组件接管（data-ks="material"），
  支持键盘 ↑↓/Enter/Esc、拼音/首字母匹配，大数据量自动切换远程搜索；
  页面不再维护自写下拉 DOM 与全量加载逻辑。台账必填校验（ledger 需先
  选物料）保持不变。

具体断言：
  T1. /report/view/ledger 物料输入框带 data-ks="material" 且选中回填编码
  T2. material_code 输入框带 autocomplete="off"
  T3. 页面不再包含自写下拉容器与 /material/api/all 全量加载逻辑
  T4. 台账保留物料必填前端校验（ledger 空物料不发起查询）

使用方法：
  cd /workspace && python -m pytest tests/verify_bug_2026_08_08_001_ledger_material_autocomplete.py -xvs
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


def _get_ledger_page():
    with app_module.app.app_context():
        _reset_db()
        _seed_common()
        client = _make_client()
        resp = client.get("/report/view/ledger", follow_redirects=True)
        assert resp.status_code == 200
        return resp.get_data(as_text=True)


class TestBug20260808001:
    def test_T1_material_input_uses_quick_select(self):
        text = _get_ledger_page()
        seg = text.split('id="material_code"', 1)[1][:400]
        assert 'data-ks="material"' in seg, "物料搜索框未接入 quick-select（data-ks=material）"
        assert 'data-ks-put="code"' in seg, "物料选中应回填编码（后端按编码/名称/规格匹配）"

    def test_T2_material_input_autocomplete_off(self):
        text = _get_ledger_page()
        seg = text.split('id="material_code"', 1)[1][:400]
        assert 'autocomplete="off"' in seg, "material_code 输入框缺少 autocomplete=off"

    def test_T3_legacy_dropdown_removed(self):
        text = _get_ledger_page()
        assert 'id="materialDropdown"' not in text, "旧版物料自写下拉容器应已移除"
        assert 'id="materialList"' not in text, "旧版物料下拉列表容器应已移除"
        assert "/material/api/all?page=" not in text, "旧版全量物料加载逻辑应已移除"

    def test_T4_ledger_material_required_guard_kept(self):
        text = _get_ledger_page()
        assert "reportType === 'ledger'" in text, "台账物料必填前端校验缺失"
