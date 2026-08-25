# -*- coding: utf-8 -*-
"""BUG-2026-08-25-001 回归测试：其他入库单先开单后建客户，客户选不中。

根因（双重）：
  1. `in_order_add.html` 的主数据广播监听只处理 `supplier_updated`，
     客户页新建客户广播的是 `customer_updated`，其他入库单页（客户模式）
     收到后不做刷新，页面级 `suppliers` 数组停留在开单时的旧数据，
     新客户永远不进下拉框。
  2. `refreshSuppliers()` 固定请求 `/api/suppliers`（供应商接口）。
     客户模式下一旦触发刷新，客户列表会被供应商数据整体覆盖，
     既选不到新客户、也可能误选同编号供应商。

修复：
  - 广播监听按 `partyField` 分流：客户模式（partyField === 'customer_id'）
    响应 `customer_updated`，供应商模式响应 `supplier_updated`。
  - `refreshSuppliers()` 按 `partyField` 选择 `/api/customers` 或
    `/api/suppliers`，提示语用 `partyLabel`。

测试用例：
  T1. 其他入库单新增页（客户模式）渲染结果包含 customer_updated 监听分支
  T2. 其他入库单新增页 refreshSuppliers 含 /api/customers 端点选择逻辑
  T3. 采购入库单新增页（供应商模式）仍为 supplier_id 且保留 supplier_updated 分支
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
from app import db, User, Warehouse  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


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


def _get_other_in_add_page():
    with app_module.app.app_context():
        _reset_db()
        _seed()
    client = _make_client()
    resp = client.get("/other_in_order/add")
    assert resp.status_code == 200, f"其他入库单新增页返回 {resp.status_code}，应为 200"
    return resp.data.decode("utf-8", errors="replace")


def test_T1_other_in_page_listens_customer_updated():
    """客户模式页必须监听 customer_updated 广播，否则跨页新建客户不刷新。"""
    body = _get_other_in_add_page()
    assert 'const partyField = "customer_id"' in body, "其他入库单新增页应为客户模式（partyField=customer_id）"
    assert "customer_updated" in body, "页面缺少 customer_updated 广播监听，新建客户后下拉列表不会刷新"


def test_T2_refresh_suppliers_uses_customers_api_in_customer_mode():
    """refreshSuppliers 在客户模式必须请求 /api/customers，避免客户列表被供应商覆盖。"""
    body = _get_other_in_add_page()
    assert "/api/customers" in body, "refreshSuppliers 缺少 /api/customers 端点，客户模式刷新会拉到供应商数据"
    assert "partyField === 'customer_id'" in body, "refreshSuppliers 缺少按 partyField 分流端点的逻辑"


def test_T3_purchase_in_page_keeps_supplier_mode():
    """采购入库单（供应商模式）保持 supplier_id 与 supplier_updated 分支不回退。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()
    client = _make_client()
    resp = client.get("/in_order/add")
    assert resp.status_code == 200, f"采购入库单新增页返回 {resp.status_code}，应为 200"
    body = resp.data.decode("utf-8", errors="replace")
    assert 'const partyField = "supplier_id"' in body, "采购入库单新增页应为供应商模式（partyField=supplier_id）"
    assert "supplier_updated" in body, "采购入库单页供应商广播监听不应回退"
