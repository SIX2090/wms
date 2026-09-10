# -*- coding: utf-8 -*-
"""BUG-2026-09-10-001 回归：删除已反提交的单据必须同步清理库存流水。

同根因历史：BUG-2026-08-17-006 只修了采购入库单（in_order）删除清流水；
领料单/工单领料单/调拨单/库存调整单/售后出库单/委外发料单/委外收货单
的删除与批量删除路由遗漏同一清理，导致反提交+删除后库存台账保留指向
已删除单据的悬挂流水（用户实测：台账仍显示 out_order-111/out_order-169
等已删除领料单）。按 R6 一次性补齐全部同类消费点，本测试逐类锁定。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    AdjustmentOrder,
    AdjustmentOrderItem,
    AfterSaleOutOrder,
    AfterSaleOutOrderItem,
    Material,
    MaterialCategory,
    OutOrder,
    OutOrderItem,
    ProductionRequisition,
    ProductionRequisitionItem,
    StockTransaction,
    SubcontractIssue,
    SubcontractIssueItem,
    SubcontractReceive,
    SubcontractReceiveItem,
    TransferOrder,
    TransferOrderItem,
    Unit,
    User,
    Warehouse,
    _collect_ledger_rows,
    db,
    set_system_setting,
)


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        set_system_setting("location_management_enabled", "0")
        warehouse = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
        db.session.add_all([
            User(username="admin", password_hash=generate_password_hash("admin"),
                 role="admin", must_change_password=False),
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT"),
            warehouse,
        ])
        db.session.commit()
        db.session.add(Material(code="M001", name="测试物料", category_id=1, unit_id=1, stock=0))
        db.session.commit()

    test_client = app_module.app.test_client()
    login_page = test_client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page).group(1)
    response = test_client.post("/login", data={
        "username": "admin", "password": "admin", "csrf_token": token,
    })
    assert response.status_code in (302, 303)
    return test_client


def _ids():
    material = Material.query.filter_by(code="M001").first()
    warehouse = Warehouse.query.filter_by(code="WHA").first()
    user = User.query.filter_by(username="admin").first()
    return material, warehouse, user


def _seed_transaction(material, warehouse, user, reference_type, reference_id,
                      transaction_type="out", quantity=-1, location=None):
    db.session.add(StockTransaction(
        material_id=material.id,
        transaction_type=transaction_type,
        quantity=quantity,
        location=location if location is not None else warehouse.name,
        reference_type=reference_type,
        reference_id=reference_id,
        operator_id=user.id,
    ))


def _assert_ledger_empty(warehouse):
    rows = _collect_ledger_rows({
        "warehouse_id": warehouse.id,
        "warehouse": warehouse.name,
        "warehouse_code": warehouse.code,
    })
    assert rows == []


# ---------------------------------------------------------------------------
# 领料单（用户实测场景）：完成 → 反提交 → 删除，台账不得留流水
# ---------------------------------------------------------------------------

def test_out_order_revert_then_delete_cleans_ledger(client):
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        order = OutOrder(
            order_no="OU-DEL-001", business_type="领料出库", warehouse=warehouse.name,
            status="completed", operator_id=user.id,
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(OutOrderItem(out_order_id=order.id, material_id=material.id, quantity=10, price=1, amount=10))
        _seed_transaction(material, warehouse, user, "out_order", order.id, "out", -10)
        db.session.commit()
        order_id = order.id

    reverted = client.post(f"/out_order/{order_id}/revert")
    assert reverted.get_json()["status"] == "success", reverted.get_json()
    # 反提交后应存在 out + revert_out 两条指向该单的流水
    with app_module.app.app_context():
        assert StockTransaction.query.filter_by(
            reference_type="out_order", reference_id=order_id).count() == 2

    deleted = client.post(f"/out_order/{order_id}/delete")
    assert deleted.get_json()["status"] == "success", deleted.get_json()

    with app_module.app.app_context():
        assert db.session.get(OutOrder, order_id) is None
        assert StockTransaction.query.filter_by(
            reference_type="out_order", reference_id=order_id).count() == 0
        _assert_ledger_empty(Warehouse.query.filter_by(code="WHA").first())


def test_batch_delete_out_order_cleans_transactions(client):
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        order = OutOrder(
            order_no="OU-DEL-B001", business_type="领料出库", warehouse=warehouse.name,
            status="pending", operator_id=user.id,
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(OutOrderItem(out_order_id=order.id, material_id=material.id, quantity=5, price=1, amount=5))
        # 模拟完成+反提交后遗留的两条流水
        _seed_transaction(material, warehouse, user, "out_order", order.id, "out", -5)
        _seed_transaction(material, warehouse, user, "out_order", order.id, "revert_out", 5)
        db.session.commit()
        order_id = order.id

    resp = client.post("/out_order/batch_delete", json={"ids": [order_id]})
    assert resp.get_json()["status"] == "success", resp.get_json()
    with app_module.app.app_context():
        assert db.session.get(OutOrder, order_id) is None
        assert StockTransaction.query.filter_by(
            reference_type="out_order", reference_id=order_id).count() == 0


# ---------------------------------------------------------------------------
# 工单领料单
# ---------------------------------------------------------------------------

def test_delete_requisition_cleans_transactions(client):
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        req = ProductionRequisition(
            req_no="PR-DEL-001", warehouse=warehouse.name, status="pending",
            operator_id=user.id,
        )
        db.session.add(req)
        db.session.flush()
        db.session.add(ProductionRequisitionItem(
            requisition_id=req.id, material_id=material.id, quantity=3))
        _seed_transaction(material, warehouse, user, "requisition", req.id, "requisition_out", -3)
        _seed_transaction(material, warehouse, user, "requisition", req.id, "revert_requisition", 3)
        db.session.commit()
        req_id = req.id

    resp = client.post(f"/requisition/{req_id}/delete")
    assert resp.get_json()["status"] == "success", resp.get_json()
    with app_module.app.app_context():
        assert db.session.get(ProductionRequisition, req_id) is None
        assert StockTransaction.query.filter_by(
            reference_type="requisition", reference_id=req_id).count() == 0


def test_batch_delete_requisition_cleans_transactions(client):
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        req = ProductionRequisition(
            req_no="PR-DEL-B001", warehouse=warehouse.name, status="pending",
            operator_id=user.id,
        )
        db.session.add(req)
        db.session.flush()
        db.session.add(ProductionRequisitionItem(
            requisition_id=req.id, material_id=material.id, quantity=2))
        _seed_transaction(material, warehouse, user, "requisition", req.id, "requisition_out", -2)
        _seed_transaction(material, warehouse, user, "requisition", req.id, "revert_requisition", 2)
        db.session.commit()
        req_id = req.id

    resp = client.post("/requisition/batch_delete", json={"ids": [req_id]})
    assert resp.get_json()["status"] == "success", resp.get_json()
    with app_module.app.app_context():
        assert db.session.get(ProductionRequisition, req_id) is None
        assert StockTransaction.query.filter_by(
            reference_type="requisition", reference_id=req_id).count() == 0


# ---------------------------------------------------------------------------
# 调拨单
# ---------------------------------------------------------------------------

def _seed_transfer(material, warehouse, user, transfer_no):
    transfer = TransferOrder(
        transfer_no=transfer_no, from_warehouse=warehouse.name, to_warehouse="仓库B",
        from_location=warehouse.name, to_location="仓库B",
        status="pending", operator_id=user.id,
    )
    db.session.add(transfer)
    db.session.flush()
    db.session.add(TransferOrderItem(
        transfer_order_id=transfer.id, material_id=material.id, quantity=4))
    _seed_transaction(material, warehouse, user, "transfer", transfer.id,
                      "transfer_out", -4, location=warehouse.name)
    _seed_transaction(material, warehouse, user, "transfer", transfer.id,
                      "transfer_in", 4, location="仓库B")
    db.session.commit()
    return transfer.id


def test_delete_transfer_cleans_transactions(client):
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        transfer_id = _seed_transfer(material, warehouse, user, "TR-DEL-001")

    resp = client.post(f"/transfer/{transfer_id}/delete")
    assert resp.get_json()["status"] == "success", resp.get_json()
    with app_module.app.app_context():
        assert db.session.get(TransferOrder, transfer_id) is None
        assert StockTransaction.query.filter_by(
            reference_type="transfer", reference_id=transfer_id).count() == 0


def test_batch_delete_transfer_cleans_transactions(client):
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        transfer_id = _seed_transfer(material, warehouse, user, "TR-DEL-B001")

    resp = client.post("/transfer/batch_delete", json={"ids": [transfer_id]})
    assert resp.get_json()["status"] == "success", resp.get_json()
    with app_module.app.app_context():
        assert db.session.get(TransferOrder, transfer_id) is None
        assert StockTransaction.query.filter_by(
            reference_type="transfer", reference_id=transfer_id).count() == 0


# ---------------------------------------------------------------------------
# 库存调整单
# ---------------------------------------------------------------------------

def _seed_adjustment(material, warehouse, user, adjustment_no):
    adjustment = AdjustmentOrder(
        adjustment_no=adjustment_no, adjustment_type="surplus",
        warehouse=warehouse.name, status="pending", operator_id=user.id,
    )
    db.session.add(adjustment)
    db.session.flush()
    db.session.add(AdjustmentOrderItem(
        adjustment_order_id=adjustment.id, material_id=material.id, quantity=6))
    _seed_transaction(material, warehouse, user, "adjustment", adjustment.id,
                      "adjustment_in", 6)
    _seed_transaction(material, warehouse, user, "adjustment", adjustment.id,
                      "revert_adjustment", -6)
    db.session.commit()
    return adjustment.id


def test_delete_adjustment_cleans_transactions(client):
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        adjustment_id = _seed_adjustment(material, warehouse, user, "ADJ-DEL-001")

    resp = client.post(f"/adjustment/{adjustment_id}/delete")
    assert resp.get_json()["status"] == "success", resp.get_json()
    with app_module.app.app_context():
        assert db.session.get(AdjustmentOrder, adjustment_id) is None
        assert StockTransaction.query.filter_by(
            reference_type="adjustment", reference_id=adjustment_id).count() == 0


def test_batch_delete_adjustment_cleans_transactions(client):
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        adjustment_id = _seed_adjustment(material, warehouse, user, "ADJ-DEL-B001")

    resp = client.post("/adjustment/batch_delete", json={"ids": [adjustment_id]})
    assert resp.get_json()["status"] == "success", resp.get_json()
    with app_module.app.app_context():
        assert db.session.get(AdjustmentOrder, adjustment_id) is None
        assert StockTransaction.query.filter_by(
            reference_type="adjustment", reference_id=adjustment_id).count() == 0


# ---------------------------------------------------------------------------
# 售后出库单
# ---------------------------------------------------------------------------

def _seed_after_sale(material, warehouse, user, order_no):
    order = AfterSaleOutOrder(
        order_no=order_no, warehouse=warehouse.name, status="pending",
        operator_id=user.id,
    )
    db.session.add(order)
    db.session.flush()
    db.session.add(AfterSaleOutOrderItem(
        after_sale_out_order_id=order.id, material_id=material.id, quantity=2, price=1, amount=2))
    _seed_transaction(material, warehouse, user, "after_sale_out_order", order.id,
                      "after_sale_out", -2)
    _seed_transaction(material, warehouse, user, "after_sale_out_order", order.id,
                      "revert_after_sale_out", 2)
    db.session.commit()
    return order.id


def test_delete_after_sale_out_cleans_transactions(client):
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        order_id = _seed_after_sale(material, warehouse, user, "ASO-DEL-001")

    resp = client.post(f"/after_sale_out/{order_id}/delete")
    assert resp.get_json()["status"] == "success", resp.get_json()
    with app_module.app.app_context():
        assert db.session.get(AfterSaleOutOrder, order_id) is None
        assert StockTransaction.query.filter_by(
            reference_type="after_sale_out_order", reference_id=order_id).count() == 0


def test_batch_delete_after_sale_out_cleans_transactions(client):
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        order_id = _seed_after_sale(material, warehouse, user, "ASO-DEL-B001")

    resp = client.post("/after_sale_out/batch_delete", json={"ids": [order_id]})
    assert resp.get_json()["status"] == "success", resp.get_json()
    with app_module.app.app_context():
        assert db.session.get(AfterSaleOutOrder, order_id) is None
        assert StockTransaction.query.filter_by(
            reference_type="after_sale_out_order", reference_id=order_id).count() == 0


# ---------------------------------------------------------------------------
# 委外发料单 / 委外收货单
# ---------------------------------------------------------------------------

def _seed_subcontract_issue(material, warehouse, user, issue_no):
    issue = SubcontractIssue(
        issue_no=issue_no, warehouse=warehouse.name, status="pending",
        operator_id=user.id,
    )
    db.session.add(issue)
    db.session.flush()
    db.session.add(SubcontractIssueItem(
        issue_id=issue.id, material_id=material.id, quantity=7))
    _seed_transaction(material, warehouse, user, "subcontract_issue", issue.id,
                      "subcontract_issue", -7)
    _seed_transaction(material, warehouse, user, "subcontract_issue", issue.id,
                      "revert_issue", 7)
    db.session.commit()
    return issue.id


def test_delete_subcontract_issue_cleans_transactions(client):
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        issue_id = _seed_subcontract_issue(material, warehouse, user, "SF-DEL-001")

    resp = client.post(f"/subcontract_issue/{issue_id}/delete")
    assert resp.get_json()["status"] == "success", resp.get_json()
    with app_module.app.app_context():
        assert db.session.get(SubcontractIssue, issue_id) is None
        assert StockTransaction.query.filter_by(
            reference_type="subcontract_issue", reference_id=issue_id).count() == 0


def test_batch_delete_subcontract_issue_cleans_transactions(client):
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        issue_id = _seed_subcontract_issue(material, warehouse, user, "SF-DEL-B001")

    resp = client.post("/subcontract_issue/batch_delete", json={"ids": [issue_id]})
    assert resp.get_json()["status"] == "success", resp.get_json()
    with app_module.app.app_context():
        assert db.session.get(SubcontractIssue, issue_id) is None
        assert StockTransaction.query.filter_by(
            reference_type="subcontract_issue", reference_id=issue_id).count() == 0


def _seed_subcontract_receive(material, warehouse, user, receive_no):
    receive = SubcontractReceive(
        receive_no=receive_no, warehouse=warehouse.name, status="pending",
        operator_id=user.id,
    )
    db.session.add(receive)
    db.session.flush()
    db.session.add(SubcontractReceiveItem(
        receive_id=receive.id, material_id=material.id, quantity=8))
    _seed_transaction(material, warehouse, user, "subcontract_receive", receive.id,
                      "subcontract_receive", 8)
    _seed_transaction(material, warehouse, user, "subcontract_receive", receive.id,
                      "revert_receive", -8)
    db.session.commit()
    return receive.id


def test_delete_subcontract_receive_cleans_transactions(client):
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        receive_id = _seed_subcontract_receive(material, warehouse, user, "SR-DEL-001")

    resp = client.post(f"/subcontract_receive/{receive_id}/delete")
    assert resp.get_json()["status"] == "success", resp.get_json()
    with app_module.app.app_context():
        assert db.session.get(SubcontractReceive, receive_id) is None
        assert StockTransaction.query.filter_by(
            reference_type="subcontract_receive", reference_id=receive_id).count() == 0


def test_batch_delete_subcontract_receive_cleans_transactions(client):
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        receive_id = _seed_subcontract_receive(material, warehouse, user, "SR-DEL-B001")

    resp = client.post("/subcontract_receive/batch_delete", json={"ids": [receive_id]})
    assert resp.get_json()["status"] == "success", resp.get_json()
    with app_module.app.app_context():
        assert db.session.get(SubcontractReceive, receive_id) is None
        assert StockTransaction.query.filter_by(
            reference_type="subcontract_receive", reference_id=receive_id).count() == 0


# ---------------------------------------------------------------------------
# 安全边界：删除一张单不得误删其他单据的流水；无流水草稿删除不报错
# ---------------------------------------------------------------------------

def test_delete_out_order_does_not_touch_other_documents(client):
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        keep = OutOrder(
            order_no="OU-KEEP-001", business_type="领料出库", warehouse=warehouse.name,
            status="completed", operator_id=user.id,
        )
        drop = OutOrder(
            order_no="OU-DROP-001", business_type="领料出库", warehouse=warehouse.name,
            status="pending", operator_id=user.id,
        )
        db.session.add_all([keep, drop])
        db.session.flush()
        db.session.add(OutOrderItem(out_order_id=keep.id, material_id=material.id, quantity=1, price=1, amount=1))
        db.session.add(OutOrderItem(out_order_id=drop.id, material_id=material.id, quantity=1, price=1, amount=1))
        _seed_transaction(material, warehouse, user, "out_order", keep.id, "out", -1)
        _seed_transaction(material, warehouse, user, "out_order", drop.id, "revert_out", 1)
        db.session.commit()
        keep_id, drop_id = keep.id, drop.id

    resp = client.post(f"/out_order/{drop_id}/delete")
    assert resp.get_json()["status"] == "success", resp.get_json()
    with app_module.app.app_context():
        assert db.session.get(OutOrder, drop_id) is None
        # 其他单据（含已完成单）的流水必须原样保留
        assert StockTransaction.query.filter_by(
            reference_type="out_order", reference_id=keep_id).count() == 1
        assert db.session.get(OutOrder, keep_id) is not None


def test_delete_fresh_draft_without_transactions_succeeds(client):
    """从未完成过的草稿没有任何流水，删除必须照常成功（清理为空操作）。"""
    with app_module.app.app_context():
        material, warehouse, user = _ids()
        order = OutOrder(
            order_no="OU-FRESH-001", business_type="领料出库", warehouse=warehouse.name,
            status="pending", operator_id=user.id,
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(OutOrderItem(out_order_id=order.id, material_id=material.id, quantity=1, price=1, amount=1))
        db.session.commit()
        order_id = order.id

    resp = client.post(f"/out_order/{order_id}/delete")
    assert resp.get_json()["status"] == "success", resp.get_json()
    with app_module.app.app_context():
        assert db.session.get(OutOrder, order_id) is None
        assert StockTransaction.query.count() == 0
