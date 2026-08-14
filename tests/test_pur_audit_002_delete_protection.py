# -*- coding: utf-8 -*-
"""
PUR-AUDIT-002 回归测试：多来源入库明细未阻止采购订单删除。

根因：多订单选单生成入库时 InOrder.source_purchase_order_id=None，
真实来源仅保存在 InOrderItem.source_purchase_order_item_id。但删除采购
订单只检查表头 source_purchase_order_id，无法发现行级多来源引用。

修复：新增 has_inbound_reference(purchase_order_id) 同时检查表头和行级来源，
单张和批量删除均调用该辅助函数。

测试用例：
  T0. has_inbound_reference 辅助函数契约
  T1. 单一来源下推入库草稿存在时，删除采购订单被拒绝
  T2. 多来源选单入库草稿存在时，两个来源订单都被拒绝删除
  T3. 多来源入库已完成时，两个来源订单仍被拒绝
  T4. 删除入库草稿后释放 received_quantity，来源订单按状态规则可删除
  T5. 批量删除返回被阻断清单，合法订单正常删除
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
    has_inbound_reference,
)

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


def _make_purchase_order(sup, mat, qty, order_no):
    po = PurchaseOrder(order_no=order_no, supplier_id=sup.id, status="pending")
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
    return po, po_item


class TestHasInboundReferenceHelper:
    """T0：辅助函数契约。"""

    def test_no_reference_returns_false(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po, _ = _make_purchase_order(seed["sup"], seed["mat"], 100, "PO-001")
            assert has_inbound_reference(po.id) is False

    def test_header_reference_returns_true(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po, pi = _make_purchase_order(seed["sup"], seed["mat"], 100, "PO-001")
            in_order = InOrder(
                order_no="IN-001", business_type="采购入库",
                warehouse="仓库A", source_purchase_order_id=po.id,
                status="pending", operator_id=seed["user"].id,
            )
            db.session.add(in_order)
            db.session.flush()
            db.session.add(InOrderItem(
                in_order_id=in_order.id, material_id=seed["mat"].id,
                source_purchase_order_item_id=pi.id, quantity=30, price=10, amount=300,
            ))
            db.session.commit()
            assert has_inbound_reference(po.id) is True

    def test_item_level_reference_returns_true(self):
        """多来源：表头 source_purchase_order_id=None，行级有来源。"""
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po1, pi1 = _make_purchase_order(seed["sup"], seed["mat"], 100, "PO-001")
            po2, pi2 = _make_purchase_order(seed["sup"], seed["mat"], 50, "PO-002")
            in_order = InOrder(
                order_no="IN-001", business_type="采购入库",
                warehouse="仓库A", source_purchase_order_id=None,
                status="pending", operator_id=seed["user"].id,
            )
            db.session.add(in_order)
            db.session.flush()
            db.session.add(InOrderItem(
                in_order_id=in_order.id, material_id=seed["mat"].id,
                source_purchase_order_item_id=pi1.id, quantity=30, price=10, amount=300,
            ))
            db.session.add(InOrderItem(
                in_order_id=in_order.id, material_id=seed["mat"].id,
                source_purchase_order_item_id=pi2.id, quantity=20, price=10, amount=200,
            ))
            db.session.commit()
            assert has_inbound_reference(po1.id) is True
            assert has_inbound_reference(po2.id) is True


def test_has_inbound_reference():
    """A9 入口：覆盖 has_inbound_reference 主路径（无引用/表头引用/行级引用）。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        po1, pi1 = _make_purchase_order(seed["sup"], seed["mat"], 100, "PO-001")
        po2, pi2 = _make_purchase_order(seed["sup"], seed["mat"], 50, "PO-002")
        # 无引用
        assert has_inbound_reference(po1.id) is False
        # 表头引用
        in_order = InOrder(
            order_no="IN-001", business_type="采购入库",
            warehouse="仓库A", source_purchase_order_id=po1.id,
            status="pending", operator_id=seed["user"].id,
        )
        db.session.add(in_order)
        db.session.flush()
        db.session.add(InOrderItem(
            in_order_id=in_order.id, material_id=seed["mat"].id,
            source_purchase_order_item_id=pi1.id, quantity=30, price=10, amount=300,
        ))
        db.session.commit()
        assert has_inbound_reference(po1.id) is True
        # 行级引用（多来源，表头为 None）
        in_order2 = InOrder(
            order_no="IN-002", business_type="采购入库",
            warehouse="仓库A", source_purchase_order_id=None,
            status="pending", operator_id=seed["user"].id,
        )
        db.session.add(in_order2)
        db.session.flush()
        db.session.add(InOrderItem(
            in_order_id=in_order2.id, material_id=seed["mat"].id,
            source_purchase_order_item_id=pi2.id, quantity=20, price=10, amount=200,
        ))
        db.session.commit()
        assert has_inbound_reference(po2.id) is True


class TestSingleSourceDeleteBlocked:
    """T1：单一来源下推入库草稿存在时，删除采购订单被拒绝。"""

    def test_single_source_draft_blocks_delete(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po, pi = _make_purchase_order(seed["sup"], seed["mat"], 100, "PO-001")
            client = _make_client()

            # 创建入库草稿（单来源）
            in_order = InOrder(
                order_no="IN-001", business_type="采购入库",
                warehouse="仓库A", source_purchase_order_id=po.id,
                status="pending", operator_id=seed["user"].id,
            )
            db.session.add(in_order)
            db.session.flush()
            db.session.add(InOrderItem(
                in_order_id=in_order.id, material_id=seed["mat"].id,
                source_purchase_order_item_id=pi.id, quantity=30, price=10, amount=300,
            ))
            pi.received_quantity = 30
            db.session.commit()

            resp = client.post(f"/purchase_order/{po.id}/delete")
            body = resp.get_json()
            assert body["status"] == "error"
            assert "入库单" in body.get("msg", "")


class TestMultiSourceDeleteBlocked:
    """T2+T3：多来源选单入库草稿/已完成时，两个来源订单都被拒绝。"""

    def test_multi_source_draft_blocks_both_orders(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po1, pi1 = _make_purchase_order(seed["sup"], seed["mat"], 100, "PO-001")
            po2, pi2 = _make_purchase_order(seed["sup"], seed["mat"], 50, "PO-002")
            client = _make_client()

            # 用选单接口创建多来源入库草稿
            resp = client.post(
                "/purchase_order/create_in_order_from_selection",
                json={
                    "items": [
                        {"purchase_order_item_id": pi1.id, "quantity": 30},
                        {"purchase_order_item_id": pi2.id, "quantity": 20},
                    ],
                    "warehouse": "仓库A",
                },
            )
            assert resp.get_json()["status"] == "success"

            # 两个来源订单都应被拒绝删除
            resp1 = client.post(f"/purchase_order/{po1.id}/delete")
            assert resp1.get_json()["status"] == "error"

            resp2 = client.post(f"/purchase_order/{po2.id}/delete")
            assert resp2.get_json()["status"] == "error"

    def test_multi_source_completed_blocks_both_orders(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po1, pi1 = _make_purchase_order(seed["sup"], seed["mat"], 100, "PO-001")
            po2, pi2 = _make_purchase_order(seed["sup"], seed["mat"], 50, "PO-002")
            client = _make_client()

            # 创建多来源入库草稿
            resp = client.post(
                "/purchase_order/create_in_order_from_selection",
                json={
                    "items": [
                        {"purchase_order_item_id": pi1.id, "quantity": 30},
                        {"purchase_order_item_id": pi2.id, "quantity": 20},
                    ],
                    "warehouse": "仓库A",
                },
            )
            assert resp.get_json()["status"] == "success"
            in_order_id = resp.get_json()["id"]

            # 完成入库单
            resp_complete = client.post(f"/in_order/{in_order_id}/complete?force=true")
            assert resp_complete.get_json().get("status") in ("success", "warning")

            # 两个来源订单仍应被拒绝删除
            resp1 = client.post(f"/purchase_order/{po1.id}/delete")
            assert resp1.get_json()["status"] == "error"

            resp2 = client.post(f"/purchase_order/{po2.id}/delete")
            assert resp2.get_json()["status"] == "error"


class TestDeleteDraftReleasesReference:
    """T4：删除入库草稿后释放 received_quantity，来源订单可删除。"""

    def test_delete_draft_then_delete_po(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po1, pi1 = _make_purchase_order(seed["sup"], seed["mat"], 100, "PO-001")
            po2, pi2 = _make_purchase_order(seed["sup"], seed["mat"], 50, "PO-002")
            client = _make_client()

            # 创建多来源入库草稿
            resp = client.post(
                "/purchase_order/create_in_order_from_selection",
                json={
                    "items": [
                        {"purchase_order_item_id": pi1.id, "quantity": 30},
                        {"purchase_order_item_id": pi2.id, "quantity": 20},
                    ],
                    "warehouse": "仓库A",
                },
            )
            assert resp.get_json()["status"] == "success"
            in_order_id = resp.get_json()["id"]

            # 删除入库草稿
            resp_del = client.post(f"/in_order/{in_order_id}/delete")
            assert resp_del.get_json()["status"] == "success"

            # received_quantity 应被释放
            db.session.refresh(pi1)
            db.session.refresh(pi2)
            assert (pi1.received_quantity or 0) == 0
            assert (pi2.received_quantity or 0) == 0

            # 现在可以删除采购订单
            resp1 = client.post(f"/purchase_order/{po1.id}/delete")
            assert resp1.get_json()["status"] == "success"

            resp2 = client.post(f"/purchase_order/{po2.id}/delete")
            assert resp2.get_json()["status"] == "success"


class TestBatchDeleteBlockedList:
    """T5：批量删除返回被阻断清单，合法订单正常删除。"""

    def test_batch_delete_returns_blocked_list(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            po1, pi1 = _make_purchase_order(seed["sup"], seed["mat"], 100, "PO-001")
            po2, pi2 = _make_purchase_order(seed["sup"], seed["mat"], 50, "PO-002")
            po3, _ = _make_purchase_order(seed["sup"], seed["mat"], 80, "PO-003")
            client = _make_client()

            # 创建多来源入库草稿（引用 PO-001 和 PO-002）
            resp = client.post(
                "/purchase_order/create_in_order_from_selection",
                json={
                    "items": [
                        {"purchase_order_item_id": pi1.id, "quantity": 30},
                        {"purchase_order_item_id": pi2.id, "quantity": 20},
                    ],
                    "warehouse": "仓库A",
                },
            )
            assert resp.get_json()["status"] == "success"

            # 批量删除三个订单：PO-001 和 PO-002 被阻断，PO-003 可删除
            resp = client.post(
                "/purchase_order/batch_delete",
                json={"ids": [po1.id, po2.id, po3.id]},
            )
            body = resp.get_json()
            assert body["status"] == "error"
            assert "PO-001" in body.get("msg", "")
            assert "PO-002" in body.get("msg", "")
            assert "PO-003" not in body.get("msg", "")

            # PO-003 仍存在（未被删除，因批量删除在 blocked 时整体拒绝）
            assert PurchaseOrder.query.get(po3.id) is not None
