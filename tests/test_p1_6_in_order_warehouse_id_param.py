# -*- coding: utf-8 -*-
"""P1-6 回归：单据保存路由统一接受 warehouse_id（ID 优先，名称兜底）。

背景（审计 3.2）：13 个页面用「名称模式」——`<select name="warehouse">` 的
option value 是 `{{ warehouse.name }}`，仓库改名后历史筛选/草稿回填全部失配。

修复策略（零风险向后兼容）：后端校验函数 `validate_inventory_warehouse(value, warehouse_id)`
本身已支持 ID 优先解析，但路由层从未把表单里的 `warehouse_id` 传进去。
本次改动让路由同时接受两种参数：
  - 传 warehouse_id → 按 ID 解析（新前端，改名不失配）
  - 传 warehouse(名称) → 按名称解析（旧客户端/脚本，行为完全不变）
  - 两者都传 → ID 优先
  - 两者都不传 → 回退默认仓库（AGENTS.md 规则一），无默认则 400

测试用例：
  T1. 传 warehouse_id 能正确落库仓库名（新前端路径）
  T2. 传 warehouse 名称仍然正确落库（旧客户端路径，防回归）
  T3. 两者都传时 ID 优先
  T4. 两者都不传且有默认仓库 → 回退默认仓库
  T5. 传无效 warehouse_id → 400 报错（不静默落库空/错值）
  T6. 停用仓库的 ID → 400 拒绝
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    InOrder, Material, Supplier, Unit, User, Warehouse, db,
)
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed(default=True):
    """建两个仓库：默认仓 + 非默认仓。返回 (supplier_id, wh_a, wh_b)。"""
    unit = Unit(code="PCS", name="个")
    wh_a = Warehouse(code="WHA", name="仓库甲", status="active", is_default=default)
    wh_b = Warehouse(code="WHB", name="仓库乙", status="active", is_default=False)
    supplier = Supplier(code="SUP", name="测试供应商")
    user = User(
        username="p16_admin",
        password_hash=generate_password_hash("admin"),
        role="admin", status="normal", must_change_password=False,
    )
    material = Material(code="P16MAT", name="测试物料", unit=unit, stock=0, price=10)
    db.session.add_all([unit, wh_a, wh_b, supplier, user, material])
    db.session.commit()
    return supplier.id, wh_a, wh_b


def _login(client):
    resp = client.post(
        "/login",
        data={"username": "p16_admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code in (200, 302)


def _post_in_order(client, supplier_id, **extra):
    payload = {
        "business_type": "采购入库",
        "supplier_id": supplier_id,
        "items": [{"code": "P16MAT", "quantity": 5, "price": 10}],
    }
    payload.update(extra)
    return client.post("/in_order/add", json=payload)


class TestInOrderAddFormUsesWarehouseId:
    """前端迁移：in_order_add.html 的仓库选择器必须传 ID 而非名称。"""

    def test_form_field_is_warehouse_id(self):
        """T7：页面渲染 name="warehouse_id"，且不再有 name="warehouse"。"""
        with app_module.app.app_context():
            _reset_db()
            supplier_id, wh_a, wh_b = _seed()
            client = app_module.app.test_client()
            _login(client)
            html = client.get("/in_order/add").get_data(as_text=True)
            assert 'name="warehouse_id"' in html, html
            assert 'name="warehouse"' not in html, "仍存在旧的名称模式字段"

    def test_option_values_are_ids(self):
        """T8：option 的 value 是仓库 ID，显示文本仍是名称。"""
        with app_module.app.app_context():
            _reset_db()
            supplier_id, wh_a, wh_b = _seed()
            client = app_module.app.test_client()
            _login(client)
            html = client.get("/in_order/add").get_data(as_text=True)
            # value 为数字 ID，> 号后为名称
            assert f'value="{wh_a.id}"' in html, html
            assert f'value="{wh_b.id}"' in html, html
            # 名称仍作为显示文本出现，但不应作为 value
            assert f'value="仓库甲"' not in html, "option value 仍是仓库名称（未迁移）"

    def test_default_warehouse_preselected_by_id(self):
        """T9：默认仓库按 ID 预选。"""
        with app_module.app.app_context():
            _reset_db()
            supplier_id, wh_a, wh_b = _seed(default=True)
            client = app_module.app.test_client()
            _login(client)
            html = client.get("/in_order/add").get_data(as_text=True)
            assert f'value="{wh_a.id}" selected' in html, html


class TestInOrderWarehouseIdParam:

    def test_warehouse_id_resolves_to_name(self):
        """T1：传 warehouse_id → 正确落库该仓库的名称。"""
        with app_module.app.app_context():
            _reset_db()
            supplier_id, wh_a, wh_b = _seed()
            client = app_module.app.test_client()
            _login(client)
            resp = _post_in_order(client, supplier_id, warehouse_id=wh_b.id)
            body = resp.get_json()
            assert body["status"] == "success", body
            order = InOrder.query.get(body["id"])
            assert order.warehouse == "仓库乙", order.warehouse

    def test_legacy_name_still_works(self):
        """T2：传 warehouse 名称仍正确（旧客户端路径，防回归）。"""
        with app_module.app.app_context():
            _reset_db()
            supplier_id, wh_a, wh_b = _seed()
            client = app_module.app.test_client()
            _login(client)
            resp = _post_in_order(client, supplier_id, warehouse="仓库乙")
            body = resp.get_json()
            assert body["status"] == "success", body
            order = InOrder.query.get(body["id"])
            assert order.warehouse == "仓库乙", order.warehouse

    def test_id_takes_precedence_over_name(self):
        """T3：两者都传时 ID 优先（名称是干扰值）。"""
        with app_module.app.app_context():
            _reset_db()
            supplier_id, wh_a, wh_b = _seed()
            client = app_module.app.test_client()
            _login(client)
            resp = _post_in_order(
                client, supplier_id, warehouse_id=wh_b.id, warehouse="仓库甲")
            body = resp.get_json()
            assert body["status"] == "success", body
            order = InOrder.query.get(body["id"])
            assert order.warehouse == "仓库乙", order.warehouse

    def test_fallback_to_default_warehouse(self):
        """T4：两者都不传且有默认仓库 → 回退默认仓。"""
        with app_module.app.app_context():
            _reset_db()
            supplier_id, wh_a, wh_b = _seed(default=True)
            client = app_module.app.test_client()
            _login(client)
            resp = _post_in_order(client, supplier_id)
            body = resp.get_json()
            assert body["status"] == "success", body
            order = InOrder.query.get(body["id"])
            assert order.warehouse == "仓库甲", order.warehouse

    def test_invalid_warehouse_id_rejected(self):
        """T5：无效 warehouse_id → 400，不静默落库。"""
        with app_module.app.app_context():
            _reset_db()
            supplier_id, wh_a, wh_b = _seed()
            client = app_module.app.test_client()
            _login(client)
            resp = _post_in_order(client, supplier_id, warehouse_id=99999)
            assert resp.status_code == 400
            body = resp.get_json()
            assert body["status"] == "error", body

    def test_inactive_warehouse_id_rejected(self):
        """T6：停用仓库的 ID → 400 拒绝。"""
        with app_module.app.app_context():
            _reset_db()
            supplier_id, wh_a, wh_b = _seed()
            wh_b.status = "inactive"
            db.session.commit()
            client = app_module.app.test_client()
            _login(client)
            resp = _post_in_order(client, supplier_id, warehouse_id=wh_b.id)
            assert resp.status_code == 400
            body = resp.get_json()
            assert body["status"] == "error", body
