# -*- coding: utf-8 -*-
"""BUG-2026-09-22-011 回归测试：采购单下推入库两条路径对重复明细的口径必须一致。

问题（R6 同模式收口）：
  采购单下推入库有两条入口，对「同一采购明细 id 在请求体里出现多次」的处理不同：
    - create_in_order_from_purchase_order（按单下推）：`d[id] = qty`  **赋值**
      → `[{id:1,qty:60},{id:1,qty:60}]` 只记 60，静默少入库（用户以为入了 120），
        且超量校验失去输入依据，超量提交不会被拦。
    - create_in_order_from_selection（选单下推）：`d[id] = d.get(id,0)+qty`  **累加**
      → 得 120，被 validate_purchase_receive_quantity 正常拦下。

修复：两条路径统一收敛为**累加**，共用 _aggregate_submitted_qty_by_item_id。

测试用例：
  T1. 按单下推：同一明细重复提交 60+60、采购量 100 → 必须被超量校验拒绝
      （修复前：赋值只记 60，直接成功 → 静默少入库）
  T2. 按单下推：同一明细重复提交 30+30、采购量 100 → 累加 60 成功且入库明细为 60
  T3. 选单下推：同一明细重复提交 60+60、采购量 100 → 被拒绝（保持既有行为不回归）
  T4. 聚合 helper 单元口径：累加、非 dict 行跳过、非法 id 跳过、缺数量按 0
  T5. 按单下推：数量为 0 的历史语义不变（走 core 的「没有可入库数量」，不误报超量）
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
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    db, Warehouse, User, Material, MaterialCategory, Unit, Supplier,
    PurchaseOrder, PurchaseOrderItem, InOrder, InOrderItem,
)
from app.routes.purchase_order import _aggregate_submitted_qty_by_item_id  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base():
    from werkzeug.security import generate_password_hash
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    sup = Supplier(code="SUP001", name="供应商甲")
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
        stock=0, price=10, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup, wh, user, mat])
    db.session.commit()
    return {"mat": mat, "wh": wh, "sup": sup, "user": user}


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


def _make_purchase_order(sup, mat, qty, order_no, status="pending"):
    po = PurchaseOrder(order_no=order_no, supplier_id=sup.id, status=status)
    db.session.add(po)
    db.session.flush()
    po_item = PurchaseOrderItem(
        purchase_order_id=po.id,
        material_id=mat.id,
        quantity=qty,
        received_quantity=0,
        price=10,
        amount=qty * 10,
    )
    db.session.add(po_item)
    db.session.commit()
    db.session.refresh(po)
    db.session.refresh(po_item)
    return po, po_item


class TestPushDuplicateItemAggregation:
    """T1：按单下推重复明细必须被超量校验拦下（修复前静默只记 60）。"""

    def test_push_route_rejects_duplicate_rows_exceeding_quantity(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po, pi = _make_purchase_order(seed["sup"], seed["mat"], 100, "PO-DUP-1")
            client = _make_client()

            resp = client.post(
                f"/purchase_order/{po.id}/create_in_order",
                json={
                    "items": [
                        {"item_id": pi.id, "quantity": 60},
                        {"item_id": pi.id, "quantity": 60},
                    ],
                    "warehouse": "仓库A",
                },
            )
            body = resp.get_json()
            # 修复前：赋值口径只记 60 → status=success（静默少入库）
            assert body["status"] == "error", body
            assert InOrder.query.count() == 0

    def test_push_route_accumulates_within_limit(self):
        """T2：重复 30+30 累加为 60，成功且入库明细数量为 60。"""
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po, pi = _make_purchase_order(seed["sup"], seed["mat"], 100, "PO-DUP-2")
            client = _make_client()

            resp = client.post(
                f"/purchase_order/{po.id}/create_in_order",
                json={
                    "items": [
                        {"item_id": pi.id, "quantity": 30},
                        {"item_id": pi.id, "quantity": 30},
                    ],
                    "warehouse": "仓库A",
                },
            )
            body = resp.get_json()
            assert body["status"] == "success", body
            in_order = InOrder.query.filter_by(order_no=body["order_no"]).first()
            assert in_order is not None
            items = InOrderItem.query.filter_by(in_order_id=in_order.id).all()
            assert len(items) == 1
            assert abs(float(items[0].quantity) - 60.0) < 1e-6

    def test_selection_route_still_rejects_duplicate_rows(self):
        """T3：选单路径既有累加语义不得回归。"""
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po, pi = _make_purchase_order(seed["sup"], seed["mat"], 100, "PO-DUP-3")
            client = _make_client()

            resp = client.post(
                "/purchase_order/create_in_order_from_selection",
                json={
                    "items": [
                        {"purchase_order_item_id": pi.id, "quantity": 60},
                        {"purchase_order_item_id": pi.id, "quantity": 60},
                    ],
                    "warehouse": "仓库A",
                },
            )
            body = resp.get_json()
            assert body["status"] == "error", body
            assert InOrder.query.count() == 0


class TestAggregateHelperContract:
    """T4：聚合 helper 的单元口径。"""

    def test_accumulates_duplicate_rows(self):
        rows = [
            {"item_id": 1, "quantity": 60},
            {"item_id": 1, "quantity": 60},
            {"item_id": 2, "quantity": 5},
        ]
        assert _aggregate_submitted_qty_by_item_id(rows) == {1: 120.0, 2: 5.0}

    def test_skips_non_dict_and_invalid_id(self):
        rows = ["x", None, {"quantity": 5}, {"item_id": "abc", "quantity": 5},
                {"item_id": 3, "quantity": 7}]
        assert _aggregate_submitted_qty_by_item_id(rows) == {3: 7.0}

    def test_missing_quantity_counts_as_zero(self):
        assert _aggregate_submitted_qty_by_item_id([{"item_id": 9}]) == {9: 0.0}

    def test_id_key_fallback_order(self):
        """选单路径的 purchase_order_item_id 优先，其后 item_id / id。"""
        rows = [{"purchase_order_item_id": 4, "item_id": 5, "quantity": 3}]
        assert _aggregate_submitted_qty_by_item_id(
            rows, id_keys=("purchase_order_item_id", "item_id", "id")) == {4: 3.0}

    def test_skip_non_positive_reserved_for_selection(self):
        """注意：parse_float_value 对负数返回 default(0)（既有行为），
        故不跳过的路径里负数同样落为 0.0，由调用方 `<= 0` 分支兜底。"""
        rows = [{"item_id": 1, "quantity": 0}, {"item_id": 2, "quantity": -5}]
        assert _aggregate_submitted_qty_by_item_id(rows, skip_non_positive=True) == {}
        assert _aggregate_submitted_qty_by_item_id(rows) == {1: 0.0, 2: 0.0}


class TestPushZeroQuantitySemanticsUnchanged:
    """T5：按单下推全 0 数量仍走 core 的「没有可入库数量」，不误报超量。"""

    def test_all_zero_quantity_keeps_original_message(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po, pi = _make_purchase_order(seed["sup"], seed["mat"], 100, "PO-DUP-5")
            client = _make_client()

            resp = client.post(
                f"/purchase_order/{po.id}/create_in_order",
                json={
                    "items": [{"item_id": pi.id, "quantity": 0}],
                    "warehouse": "仓库A",
                },
            )
            body = resp.get_json()
            assert body["status"] == "error", body
            assert "可入库数量" in body.get("msg", "") or "入库" in body.get("msg", "")
