# -*- coding: utf-8 -*-
"""BUG-2026-08-16-005 回归：批量完成入库必须补齐来源/超收/未来日期校验。

审计发现（AUDIT-2026-08-16 P1）：batch_complete_in_order 相比单据版
complete_in_order 缺校验——is_future_date、validate_purchase_in_order_source、
_check_in_order_anomalies，超收校验（validate_purchase_receive_quantity）
只在新增/编辑明细时执行，完成时不再复核：草稿期间来源采购单的未入库
数量被其他单推进后，超收草稿可经批量放行。

修复后要求（批量循环体内，skip 不阻断整批）：
- 未来日期草稿 → skipped；
- 超收草稿（数量 > 来源采购单行未入库数量，strict+forbid 默认开）→ skipped；
- 异常检测命中 → skipped；
- 合法草稿正常完成、库存入账。
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
    InOrder, InOrderItem, Material, MaterialCategory, PurchaseOrder,
    PurchaseOrderItem, StockTransaction, Supplier, Unit, User, Warehouse, db,
    set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    from werkzeug.security import generate_password_hash
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        Supplier(code="SUP001", name="供应商"),
        Supplier(code="SUP002", name="供应商乙"),
        Warehouse(code="WH01", name="主仓", is_default=True, status="active"),
        User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False),
    ])
    db.session.commit()
    db.session.add(Material(
        code="M001", name="轴承", spec="6204",
        category_id=1, unit_id=1, supplier_id=1, stock=0, price=10,
    ))
    db.session.commit()
    # 超收控制：严格按单 + 禁止超收（系统默认值，显式落库保证测试稳定）
    set_system_setting("purchase_receipt_strict_order", "1")
    set_system_setting("purchase_over_receive_control_mode", "forbid")
    db.session.commit()


def _login(client):
    page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    token = m.group(1) if m else ""
    client.post("/login", data={
        "username": "admin", "password": "admin", "csrf_token": token})


def _make_po_draft(order_no, po_qty, receive_qty, *, doc_date=None,
                   supplier_id=1):
    """建采购订单（quantity=po_qty）+ 关联入库草稿（数量 receive_qty）。"""
    user = User.query.filter_by(username="admin").first()
    po = PurchaseOrder(order_no=f"PO-{order_no}", supplier_id=supplier_id,
                       status="pending")
    db.session.add(po)
    db.session.flush()
    po_item = PurchaseOrderItem(
        purchase_order_id=po.id, material_id=1,
        quantity=po_qty, received_quantity=0, price=10, amount=po_qty * 10)
    db.session.add(po_item)
    db.session.flush()
    draft = InOrder(
        order_no=order_no, business_type="采购入库", warehouse="主仓",
        status="pending", date=doc_date or date.today(),
        operator_id=user.id, supplier_id=supplier_id)
    db.session.add(draft)
    db.session.flush()
    db.session.add(InOrderItem(
        in_order_id=draft.id, material_id=1,
        source_purchase_order_item_id=po_item.id,
        quantity=receive_qty, price=10, amount=receive_qty * 10))
    db.session.commit()
    return draft, po_item


def _batch_complete(client, *order_ids):
    return client.post("/in_order/batch_complete", json={"ids": list(order_ids)})


class TestBatchCompleteInOrderGuards:

    def test_future_date_draft_is_skipped(self):
        """T1：未来日期草稿批量完成被拒。"""
        with app_module.app.app_context():
            _reset_db()
            _seed()
            draft, _po_item = _make_po_draft(
                "IN-FUTURE", 10, 5, doc_date=date.today() + timedelta(days=3))
            client = app_module.app.test_client()
            _login(client)
            resp = _batch_complete(client, draft.id)
            data = resp.get_json()
            assert data["completed"] == 0
            assert "入库日期晚于今天" in data["msg"]
            db.session.expire_all()
            assert db.session.get(InOrder, draft.id).status == "pending"

    def test_over_receive_draft_is_skipped(self):
        """T2：超收草稿（PO 行 5 张收 10 张）批量完成被拒，库存不入账。

        草稿创建时 received_quantity 已被推进到 5（模拟另一张单先完成），
        剩余 0，本单 10 张全为超收。
        """
        with app_module.app.app_context():
            _reset_db()
            _seed()
            draft, po_item = _make_po_draft("IN-OVER", 5, 10)
            # 模拟草稿期间来源 PO 已被其他入库单推进：剩余 0
            po_item.received_quantity = 5
            db.session.commit()
            client = app_module.app.test_client()
            _login(client)
            resp = _batch_complete(client, draft.id)
            data = resp.get_json()
            assert data["completed"] == 0, data
            assert "未入库数量" in data["msg"]
            db.session.expire_all()
            assert db.session.get(InOrder, draft.id).status == "pending"
            mat = db.session.get(Material, 1)
            db.session.expire(mat, ["stock"])
            assert mat.stock == 0

    def test_valid_draft_completes(self):
        """T3：合法草稿（5 张订单收 3 张）批量完成正常，库存入账。"""
        with app_module.app.app_context():
            _reset_db()
            _seed()
            draft, po_item = _make_po_draft("IN-OK", 5, 3)
            client = app_module.app.test_client()
            _login(client)
            resp = _batch_complete(client, draft.id)
            data = resp.get_json()
            assert data["completed"] == 1, data
            db.session.expire_all()
            assert db.session.get(InOrder, draft.id).status == "completed"
            mat = db.session.get(Material, 1)
            db.session.expire(mat, ["stock"])
            assert abs(mat.stock - 3) < 1e-6
            assert StockTransaction.query.filter_by(
                reference_type="in_order", reference_id=draft.id).count() == 1

    def test_mixed_batch_skips_bad_and_completes_good(self):
        """T4：混合批次——超收单被跳过，合法单正常完成，整批不中断。"""
        with app_module.app.app_context():
            _reset_db()
            _seed()
            bad, bad_po_item = _make_po_draft("IN-BAD", 5, 10)
            bad_po_item.received_quantity = 5
            # 合法单用不同供应商，避免触发"同日同供应商同物料"重复单据检测
            good, _g = _make_po_draft("IN-GOOD", 8, 4, supplier_id=2)
            client = app_module.app.test_client()
            _login(client)
            resp = _batch_complete(client, bad.id, good.id)
            data = resp.get_json()
            assert data["completed"] == 1, data
            db.session.expire_all()
            assert db.session.get(InOrder, bad.id).status == "pending"
            assert db.session.get(InOrder, good.id).status == "completed"
            mat = db.session.get(Material, 1)
            db.session.expire(mat, ["stock"])
            assert abs(mat.stock - 4) < 1e-6
