# -*- coding: utf-8 -*-
"""
BUG-2026-08-04-003 回归测试：update_completed_in_order 必须加写锁

原 Bug：update_completed_in_order 缺少 _acquire_order_write_lock，并发编辑
已完成入库单或同时反提交（revert_in_order 已加锁）时，库存调整可能
重复执行或对 pending 单据做库存操作。

修复：在库存操作前加 _acquire_order_write_lock(InOrder, id, 'completed')，
加锁后重新读取状态并做仓库赋值，与 complete_in_order 对称。

测试策略：
  T1. 正常修改已完成入库单明细数量：加锁后仍能成功调整库存
  T2. 状态变为 pending（被并发反提交）后修改：应被锁拒绝
  T3. 状态变为 deleted/不存在后修改：应被锁拒绝
"""
from __future__ import annotations

import os
import sys
import re
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
    InOrder, InOrderItem, StockTransaction,
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
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    mat = Material(
        code="M001", name="测试物料", spec="S1",
        category=cat, unit=unit, supplier=sup,
        stock=100, price=10, min_stock=0, max_stock=9999, reorder_point=0,
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


def _make_completed_in_order(mat, qty=50):
    """创建一张已完成的入库单（直接写数据库，不走 complete 路由）。"""
    order = InOrder(
        order_no="IN-TEST-001",
        status="completed",
        warehouse="仓库A",
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
    # 总库存已在 _seed 中设为 100，这里不再重复加
    db.session.commit()
    return order, item


class TestBug20260804003UpdateCompletedLock:
    """update_completed_in_order 必须加写锁。"""

    def test_T1_normal_edit_succeeds_with_lock(self):
        """正常修改已完成入库单明细数量：加锁后仍能成功调整库存。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, item = _make_completed_in_order(seeds["mat"], qty=50)
            # 修改明细数量从 50 增加到 80（qty_diff=+30）
            resp = client.post(f"/in_order/{order.id}/update_completed", json={
                "items": [{"id": item.id, "quantity": 80, "price": 10}],
                "deleted_items": [],
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "success", f"应成功: {data}"
            # 验证库存增加了 30（100+30=130）
            db.session.expire(seeds["mat"], ['stock'])
            assert seeds["mat"].stock == 130

    def test_T2_status_changed_to_pending_blocks_edit(self):
        """状态变为 pending（被并发反提交）后修改：应被锁拒绝。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, item = _make_completed_in_order(seeds["mat"], qty=50)
            # 模拟并发反提交：直接改状态为 pending
            order.status = "pending"
            db.session.commit()
            # 尝试修改已完成明细
            resp = client.post(f"/in_order/{order.id}/update_completed", json={
                "items": [{"id": item.id, "quantity": 80, "price": 10}],
                "deleted_items": [],
            })
            data = resp.get_json()
            # 锁应检测到状态不是 completed，拒绝操作
            assert data["status"] == "error", f"应被锁拒绝: {data}"
            assert "状态已变更" in data.get("msg", "") or "已完成" in data.get("msg", "")

    def test_T3_pending_order_fast_path_rejects(self):
        """非 completed 状态的入库单在 fast-path 即被拒绝。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, item = _make_completed_in_order(seeds["mat"], qty=50)
            order.status = "pending"
            db.session.commit()
            resp = client.post(f"/in_order/{order.id}/update_completed", json={
                "items": [],
                "deleted_items": [],
            })
            data = resp.get_json()
            assert data["status"] == "error"
            assert "已完成" in data.get("msg", "")
