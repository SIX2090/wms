#!/usr/bin/env python3
"""
BUG-2026-08-02-011 验证：batch_delete_in_order 与 delete_in_order 逻辑对齐。

覆盖：
  1. 静态：batch_delete_in_order 含 _acquire_order_write_lock / source_purchase_order_item 回退 /
     update_purchase_order_status
  2. 动态 E1：批量删除带来源的 pending 入库单 → received_quantity 回退 + 入库单删除 + 采购订单状态更新
  3. 动态 E2：批量删除包含已完成单 → fast-path 拒绝（400/409）
  4. 动态 E3：批量删除两张 pending（一张带来源、一张不带来源）→ 都删除，仅带来源的回退进度
"""
from __future__ import annotations

import os
import re
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    InOrder,
    InOrderItem,
    Material,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    User,
    Warehouse,
    db,
)

flask_app = app_module.app
results = []


def record(checkpoint: str, ok: bool, detail: str) -> None:
    results.append((checkpoint, "PASS" if ok else "FAIL", detail))
    print(f"{'PASS' if ok else 'FAIL'}: {checkpoint} - {detail}")


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8", errors="ignore")


# ============== 静态检查 ==============
app_py = read_text("app/app.py")
match = re.search(r"^def\s+batch_delete_in_order\s*\([^)]*\):", app_py, re.M)
body = ""
if match:
    next_match = re.search(r"^def\s+\w+\s*\(", app_py[match.end() :], re.M)
    end = match.end() + next_match.start() if next_match else len(app_py)
    body = app_py[match.start() : end]

record(
    "S1-has-write-lock",
    "_acquire_order_write_lock" in body,
    "batch_delete_in_order 含写锁调用",
)
record(
    "S2-has-source-revert",
    "source_purchase_order_item" in body and "received_quantity" in body,
    "batch_delete_in_order 含来源 received_quantity 回退",
)
record(
    "S3-has-update-po-status",
    "update_purchase_order_status" in body,
    "batch_delete_in_order 含 update_purchase_order_status 调用",
)
record(
    "S4-has-source-push-check",
    "_source_has_active_push" in body,
    "batch_delete_in_order 含下推占用校验",
)
record(
    "S5-has-per-order-commit",
    body.count("db.session.commit()") >= 2,
    "batch_delete_in_order 含逐条独立 commit（>=2 处）",
)


# ============== 动态检查 ==============
flask_app.config["TESTING"] = True
flask_app.config["WTF_CSRF_ENABLED"] = False


def login_client(client):
    with client.session_transaction() as sess:
        sess["_user_id"] = "1"
        sess["_fresh"] = True


def create_test_data():
    wh = Warehouse.query.filter_by(name="默认测试仓").first()
    if not wh:
        wh = Warehouse(code="DEFAULT-TEST", name="默认测试仓", status="active", is_default=True)
        db.session.add(wh)
    supplier = Supplier.query.filter_by(name="测试供应商").first()
    if not supplier:
        supplier = Supplier(name="测试供应商", code="TEST-SUP")
        db.session.add(supplier)
    material = Material.query.filter_by(code="TEST-MAT").first()
    if not material:
        material = Material(code="TEST-MAT", name="测试物料", spec="", stock=0, price=1)
        db.session.add(material)
    user = User.query.filter_by(id=1).first()
    if not user:
        from werkzeug.security import generate_password_hash

        user = User(
            id=1,
            username="testuser",
            password_hash=generate_password_hash("Password123!"),
            role="warehouse",
            status="normal",
        )
        db.session.add(user)
    user.must_change_password = False
    db.session.commit()
    return wh, supplier, material


with flask_app.app_context():
    db.create_all()
    default_wh, supplier, material = create_test_data()
    suffix = str(int(time.time()))[-6:]
    client = flask_app.test_client()
    login_client(client)

    # ---------- E1: 批量删除带来源 pending 入库单 → 回退 received_quantity ----------
    po = PurchaseOrder(
        order_no=f"PO{suffix}E1",
        date=date(2026, 8, 2),
        supplier_id=supplier.id,
        status="partial",
        total_amount=100,
        operator_id=1,
    )
    db.session.add(po)
    db.session.flush()
    po_item = PurchaseOrderItem(
        purchase_order_id=po.id,
        material_id=material.id,
        quantity=20,
        received_quantity=10,  # 假设此前已下推 10
        price=5,
        amount=100,
    )
    db.session.add(po_item)
    db.session.flush()

    order = InOrder(
        order_no=f"IN{suffix}E1",
        date=date(2026, 8, 2),
        business_type="采购入库",
        supplier_id=supplier.id,
        warehouse=default_wh.name,
        status="pending",
        operator_id=1,
    )
    db.session.add(order)
    db.session.flush()
    in_item = InOrderItem(
        in_order_id=order.id,
        material_id=material.id,
        source_purchase_order_item_id=po_item.id,
        quantity=10,
        price=5,
        amount=50,
    )
    db.session.add(in_item)
    db.session.commit()

    order_id = order.id
    po_id = po.id
    po_item_id = po_item.id

    rv = client.post("/in_order/batch_delete", json={"ids": [order_id]})
    data = rv.get_json(force=True)
    db.session.expire_all()

    deleted_order = db.session.get(InOrder, order_id)
    refreshed_po_item = db.session.get(PurchaseOrderItem, po_item_id)
    refreshed_po = db.session.get(PurchaseOrder, po_id)
    record(
        "E1-batch-delete-with-source",
        rv.status_code == 200
        and data.get("status") == "success"
        and deleted_order is None
        and refreshed_po_item is not None
        and refreshed_po_item.received_quantity == 0,
        f"批量删除带来源入库单 status={rv.status_code} resp={data.get('status')} "
        f"order_deleted={deleted_order is None} received_qty={refreshed_po_item.received_quantity if refreshed_po_item else None}",
    )
    # 采购订单状态应回退为 pending（已下推 0/20）
    record(
        "E1-po-status-reverted",
        refreshed_po is not None and refreshed_po.status == "pending",
        f"采购订单状态回退为 pending，实际={refreshed_po.status if refreshed_po else None}",
    )

    # 清理
    if refreshed_po_item is not None:
        db.session.delete(refreshed_po_item)
    if refreshed_po is not None:
        db.session.delete(refreshed_po)
    db.session.commit()

    # ---------- E2: 批量删除包含已完成单 → fast-path 拒绝 ----------
    completed_order = InOrder(
        order_no=f"IN{suffix}E2",
        date=date(2026, 8, 2),
        business_type="其他入库",
        supplier_id=supplier.id,
        warehouse=default_wh.name,
        status="completed",
        operator_id=1,
    )
    db.session.add(completed_order)
    db.session.flush()
    comp_item = InOrderItem(
        in_order_id=completed_order.id,
        material_id=material.id,
        quantity=2,
        price=1,
        amount=2,
    )
    db.session.add(comp_item)
    db.session.commit()
    completed_id = completed_order.id

    rv = client.post("/in_order/batch_delete", json={"ids": [completed_id]})
    data = rv.get_json(force=True)
    db.session.expire_all()
    still_there = db.session.get(InOrder, completed_id)
    record(
        "E2-completed-blocked",
        rv.status_code in (400, 409) and still_there is not None,
        f"批量删除已完成单被拒绝 status={rv.status_code} order_still_exists={still_there is not None}",
    )

    # 清理
    for it in list(still_there.items):
        db.session.delete(it)
    db.session.delete(still_there)
    db.session.commit()

    # ---------- E3: 批量删除两张 pending（一张带来源、一张不带来源）→ 都删除 ----------
    po2 = PurchaseOrder(
        order_no=f"PO{suffix}E3",
        date=date(2026, 8, 2),
        supplier_id=supplier.id,
        status="partial",
        total_amount=50,
        operator_id=1,
    )
    db.session.add(po2)
    db.session.flush()
    po_item2 = PurchaseOrderItem(
        purchase_order_id=po2.id,
        material_id=material.id,
        quantity=10,
        received_quantity=4,
        price=5,
        amount=50,
    )
    db.session.add(po_item2)
    db.session.flush()

    order_a = InOrder(
        order_no=f"IN{suffix}E3A",
        date=date(2026, 8, 2),
        business_type="采购入库",
        supplier_id=supplier.id,
        warehouse=default_wh.name,
        status="pending",
        operator_id=1,
    )
    db.session.add(order_a)
    db.session.flush()
    in_item_a = InOrderItem(
        in_order_id=order_a.id,
        material_id=material.id,
        source_purchase_order_item_id=po_item2.id,
        quantity=4,
        price=5,
        amount=20,
    )
    db.session.add(in_item_a)

    order_b = InOrder(
        order_no=f"IN{suffix}E3B",
        date=date(2026, 8, 2),
        business_type="其他入库",
        supplier_id=supplier.id,
        warehouse=default_wh.name,
        status="pending",
        operator_id=1,
    )
    db.session.add(order_b)
    db.session.flush()
    in_item_b = InOrderItem(
        in_order_id=order_b.id,
        material_id=material.id,
        quantity=3,
        price=2,
        amount=6,
    )
    db.session.add(in_item_b)
    db.session.commit()

    id_a = order_a.id
    id_b = order_b.id
    po_item2_id = po_item2.id
    po2_id = po2.id

    rv = client.post("/in_order/batch_delete", json={"ids": [id_a, id_b]})
    data = rv.get_json(force=True)
    db.session.expire_all()

    gone_a = db.session.get(InOrder, id_a) is None
    gone_b = db.session.get(InOrder, id_b) is None
    refreshed_po_item2 = db.session.get(PurchaseOrderItem, po_item2_id)
    refreshed_po2 = db.session.get(PurchaseOrder, po2_id)
    record(
        "E3-both-deleted-source-reverted",
        rv.status_code == 200
        and data.get("status") == "success"
        and data.get("deleted") == 2
        and gone_a
        and gone_b
        and refreshed_po_item2 is not None
        and refreshed_po_item2.received_quantity == 0,
        f"批量删除两张 pending status={rv.status_code} resp={data.get('status')} "
        f"deleted={data.get('deleted')} gone_a={gone_a} gone_b={gone_b} "
        f"received_qty={refreshed_po_item2.received_quantity if refreshed_po_item2 else None}",
    )

    # 清理
    if refreshed_po_item2 is not None:
        db.session.delete(refreshed_po_item2)
    if refreshed_po2 is not None:
        db.session.delete(refreshed_po2)
    db.session.commit()


failures = [r for r in results if r[1] == "FAIL"]
if failures:
    print(f"\n共 {len(failures)} 项失败")
    raise SystemExit(1)
print("\n全部通过")
raise SystemExit(0)
