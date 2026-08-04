# -*- coding: utf-8 -*-
"""
BUG-2026-08-04-015 回归测试：采购入库单 反提交→修改→重新完成 时
PurchaseOrderItem.received_quantity 可能被重复递增（双计数）。

生命周期梳理：
  - /in_order/add 保存时（pending）     ：received_quantity += 明细数量（line 26709）
  - /in_order/<id>/complete 首次完成    ：is_recompleted=False，不再递增
  - /in_order/<id>/revert 反提交        ：received_quantity -= 明细数量（line 28016）
  - /in_order/add 再次编辑（pending）   ：先减旧明细，再加新明细（line 26624/26709）
  - /in_order/<id>/complete 重新完成    ：is_recompleted=True（revert_in 流水仍存在）
                                            再次 received_quantity += 明细数量（line 27495）

问题1（已修复）：反提交后若在重新完成前编辑过明细（数量变化），重新完成时会把
"本次编辑已递增的 received_quantity" 再递增一次，导致双计数。
问题2（已修复）：单张反提交(revert_in_order)会释放 received_quantity 预留，
而批量反提交(batch_revert_in_order)不释放，两者行为不一致。

修复方案：
  - revert_in_order 不再释放 received_quantity 预留（草稿仍占用“已下推”数量，
    只有删除草稿 delete_in_order 才释放），与 batch_revert_in_order 一致。
  - complete_in_order 移除 is_recompleted 递增，避免双计数。

不变量：received_quantity = 该采购单明细当前所有未删除入库单草稿的数量之和。
  - 保存/编辑入库单：调整 received_quantity
  - 完成：仅入库存，不改变 received_quantity
  - 反提交：仅回退库存，不改变 received_quantity
  - 删除草稿：释放 received_quantity

测试策略：
  T1. 反提交→重新完成（不编辑）：received_quantity 保持正确（不双计数、不丢失）
  T2. 反提交→编辑→重新完成：received_quantity 应等于新数量（不双计数）
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
    PurchaseOrder, PurchaseOrderItem, InOrder, InOrderItem,
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
        stock=0, price=10, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup, wh, user, mat])
    db.session.commit()
    return {"mat": mat, "wh": wh, "user": user, "sup": sup}


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


def _make_purchase_order(mat, sup, qty=100):
    po = PurchaseOrder(order_no="PO-TEST-001", supplier_id=sup.id, status="pending")
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
    # 刷新 relationship，避免后续访问 stale
    db.session.refresh(po)
    return po, po_item


def _create_in_order(client, mat, po_item, qty, order_id=None):
    payload = {
        "order_id": order_id,
        "business_type": "采购入库",
        "warehouse": "仓库A",
        "supplier_id": po_item.purchase_order.supplier_id,
        "items": [{
            "code": mat.code,
            "quantity": qty,
            "price": 10,
            "source_purchase_order_item_id": po_item.id,
        }],
    }
    resp = client.post("/in_order/add", json=payload)
    return resp


class TestBug20260804015ReceivedDoubleCount:
    """received_quantity 在 反提交→(编辑)→重新完成 流程中的双计数问题。"""

    def test_T1_revert_recomplete_no_edit_ok(self):
        """反提交→重新完成（不编辑）：received_quantity 保持正确，不双计数、不丢失。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            po, po_item = _make_purchase_order(seeds["mat"], seeds["sup"], qty=100)

            resp = _create_in_order(client, seeds["mat"], po_item, qty=50)
            assert resp.get_json()["status"] == "success", resp.get_json()
            in_order = InOrder.query.filter_by(order_no=resp.get_json()["order_no"]).first()
            assert in_order is not None

            # 完成
            r = client.post(f"/in_order/{in_order.id}/complete")
            assert r.get_json()["status"] == "success", r.get_json()
            db.session.refresh(po_item)
            assert po_item.received_quantity == 50, f"完成后应为 50，实际 {po_item.received_quantity}"

            # 反提交：只回退库存，不释放预留
            r = client.post(f"/in_order/{in_order.id}/revert")
            assert r.get_json()["status"] == "success", r.get_json()
            db.session.refresh(po_item)
            assert po_item.received_quantity == 50, f"反提交后应保持 50（预留），实际 {po_item.received_quantity}"

            # 重新完成（不编辑）：不双计数
            r = client.post(f"/in_order/{in_order.id}/complete")
            assert r.get_json()["status"] == "success", r.get_json()
            db.session.refresh(po_item)
            assert po_item.received_quantity == 50, \
                f"重新完成应为 50，实际 {po_item.received_quantity}（双计数 BUG）"

    def test_T2_revert_edit_recomplete_double_count(self):
        """反提交→编辑(数量 50→60)→重新完成：received_quantity 应=60，不双计数。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            po, po_item = _make_purchase_order(seeds["mat"], seeds["sup"], qty=100)

            resp = _create_in_order(client, seeds["mat"], po_item, qty=50)
            assert resp.get_json()["status"] == "success", resp.get_json()
            in_order = InOrder.query.filter_by(order_no=resp.get_json()["order_no"]).first()

            # 完成
            r = client.post(f"/in_order/{in_order.id}/complete")
            assert r.get_json()["status"] == "success", r.get_json()
            db.session.refresh(po_item)
            assert po_item.received_quantity == 50

            # 反提交：只回退库存，不释放预留
            r = client.post(f"/in_order/{in_order.id}/revert")
            assert r.get_json()["status"] == "success", r.get_json()
            db.session.refresh(po_item)
            assert po_item.received_quantity == 50

            # 编辑：数量 50 → 60（走 /in_order/add 保存，带 order_id）
            cresp = _create_in_order(client, seeds["mat"], po_item, qty=60, order_id=in_order.id)
            assert cresp.get_json()["status"] == "success", cresp.get_json()
            db.session.refresh(po_item)
            assert po_item.received_quantity == 60, \
                f"编辑后应为 60，实际 {po_item.received_quantity}"

            # 重新完成：应保持 60，不得双计数为 120
            r = client.post(f"/in_order/{in_order.id}/complete")
            assert r.get_json()["status"] == "success", r.get_json()
            db.session.refresh(po_item)
            assert po_item.received_quantity == 60, \
                f"BUG：received_quantity 应=60，实际={po_item.received_quantity}（双计数）"


if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)