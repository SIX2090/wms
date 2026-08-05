# -*- coding: utf-8 -*-
"""
BUG-2026-08-05-002 回归测试：complete_in_order / update_completed_in_order /
update_in_order 不再因漏导入 InOrder 抛 NameError。

原 Bug：路由拆分迁移到 app/routes/in_order.py 时，complete_in_order 等函数
的延迟导入 `from app import (...)` 漏了 InOrder，点击"完成入库"即抛
NameError，单据停在草稿、下推按钮（需 completed 状态）不出现。

修复：在三个函数的导入中补入 InOrder。

测试策略：
  T1. 采购入库单（手工明细、无采购订单来源）完成入库成功：status->completed，
      库存增加，_in_order_push_source_type 返回 purchase_in_order（下推可用）
  T2. 已完成入库单编辑明细（update_completed）不再抛 NameError
  T3. 草稿入库单编辑表头（update_in_order）不再抛 NameError
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

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    db, Warehouse, User, Material, MaterialCategory, Unit, Supplier,
    InOrder, InOrderItem, _in_order_push_source_type,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    from werkzeug.security import generate_password_hash
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    sup = Supplier(code="SUP001", name="测试供应商")
    wh = Warehouse(code="XMC", name="项目仓", is_default=True, status="active")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    mat = Material(
        code="206140", name="测试物料", spec="S1",
        category=cat, unit=unit, supplier=sup,
        stock=0, price=10, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup, wh, user, mat])
    db.session.commit()
    return {"mat": mat, "wh": wh, "user": user}


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


def _make_pending_purchase_in_order(mat, qty=25):
    """创建一张草稿（pending）采购入库单，手工明细、无采购订单来源。"""
    order = InOrder(
        order_no="IN-REPRO-002",
        business_type="采购入库",
        status="pending",
        warehouse="项目仓",
        total_amount=qty * 10,
    )
    db.session.add(order)
    db.session.flush()
    item = InOrderItem(
        in_order_id=order.id,
        material_id=mat.id,
        quantity=qty,
        price=10,
        amount=qty * 10,
    )
    db.session.add(item)
    db.session.commit()
    return order, item


class TestBug20260805002CompleteInOrderImports:
    """完成入库 / 编辑已完成 / 编辑草稿 不再因漏导入 InOrder 抛 NameError。"""

    def test_T1_complete_purchase_in_order_succeeds_and_can_push(self):
        """完成入库成功：status->completed、库存增加、可下推。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, item = _make_pending_purchase_in_order(seeds["mat"], qty=25)
            resp = client.post(f"/in_order/{order.id}/complete")
            assert resp.status_code == 200, f"应 200: {resp.status_code}"
            data = resp.get_json()
            assert data["status"] == "success", f"应成功: {data}"
            # 状态已变为 completed
            db.session.expire(order, ["status"])
            assert order.status == "completed"
            # 库存增加 25
            db.session.expire(seeds["mat"], ["stock"])
            assert seeds["mat"].stock == 25
            # 下推可用
            assert _in_order_push_source_type(order) == "purchase_in_order"

    def test_T2_update_completed_in_order_no_nameerror(self):
        """已完成入库编辑明细不再抛 NameError。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, item = _make_pending_purchase_in_order(seeds["mat"], qty=25)
            # 先完成
            client.post(f"/in_order/{order.id}/complete")
            db.session.expire(order, ["status"])
            assert order.status == "completed"
            # 编辑已完成明细数量 25 -> 30（+5）
            resp = client.post(f"/in_order/{order.id}/update_completed", json={
                "items": [{"id": item.id, "quantity": 30, "price": 10}],
                "deleted_items": [],
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "success", f"应成功: {data}"
            db.session.expire(seeds["mat"], ["stock"])
            assert seeds["mat"].stock == 30

    def test_T3_update_in_order_no_nameerror(self):
        """草稿入库单编辑表头不再抛 NameError。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, item = _make_pending_purchase_in_order(seeds["mat"], qty=25)
            resp = client.post(f"/in_order/{order.id}/update", json={
                "date": "2026-08-05",
                "status": "pending",
            })
            assert resp.status_code in (200, 400)
            # 只要不抛 NameError（500）即通过；400 是字段校验，非常规错误
            assert resp.status_code != 500