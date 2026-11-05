# -*- coding: utf-8 -*-
"""新增采购入库单工具栏移除「最近使用 / 存为模板 / 选择模板」——渲染冒烟 + 回归。

背景：按用户需求下线明细工具栏中体验较差/易误解的两个功能：
  * 最近使用（showRecentMaterials）
  * 存为模板 + 选择模板（saveAsTemplate / loadTemplate / loadTemplateOptions / templateSelect）
两者均仅存浏览器 localStorage、不跨设备/账号共享。本次把 UI 按钮与专属 JS 函数
（含 recordRecentMaterial 在 selectMaterial / setupScanAutoFill 的两处调用）整块移除。

测试用例：
  T1. GET /in_order/add 渲染 200（模板无 Jinja/JS 结构性破坏）
  T2. 保留的按钮仍在（添加物料/选采购单/复制上一行/粘贴导入/刷新物料/批量修改/字段设置）
  T3. 被删的按钮与函数不再出现（最近使用/存为模板/选择模板/templateSelect/
      showRecentMaterials/saveAsTemplate/loadTemplate/recordRecentMaterial）
"""
from __future__ import annotations

import os
import re
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
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import db, Warehouse, User  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

KEPT = ["添加物料", "选采购单", "复制上一行", "粘贴导入", "刷新物料", "批量修改", "字段设置"]
REMOVED = [
    "最近使用", "存为模板", "选择模板", "templateSelect",
    "showRecentMaterials", "saveAsTemplate", "loadTemplate", "recordRecentMaterial",
]


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
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
    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post(
        "/login",
        data={"username": "admin", "password": "admin", "csrf_token": token},
    )
    return client


def _get_add_page() -> str:
    client = _make_client()
    resp = client.get("/in_order/add")
    assert resp.status_code == 200, f"新增入库单页返回 {resp.status_code}，应为 200"
    return resp.data.decode("utf-8", errors="replace")


def test_T1_add_page_renders_200():
    with app_module.app.app_context():
        _reset_db()
        _seed()
    body = _get_add_page()
    assert "materialTableBody" in body, "新增入库单页应包含明细表格"


def test_T2_kept_buttons_present():
    with app_module.app.app_context():
        _reset_db()
        _seed()
    body = _get_add_page()
    for label in KEPT:
        assert label in body, f"保留按钮[{label}]应出现在工具栏"


def test_T3_removed_buttons_and_functions_absent():
    with app_module.app.app_context():
        _reset_db()
        _seed()
    body = _get_add_page()
    for token in REMOVED:
        assert token not in body, f"被删元素[{token}]不应再出现在页面"
