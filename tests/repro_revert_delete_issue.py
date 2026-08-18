# -*- coding: utf-8 -*-
"""临时复现：用户反馈"明明有库存，反提交采购入库单却不能删除"。

覆盖场景，跑真实路由定位卡点：
  T1 无来源采购单的已完成入库单 -> 反提交 -> 删除（基线，期望成功）
  T2 有来源采购单的已完成入库单 -> 反提交 -> 删除（期望成功）
  T3 auto_push_requisition 自动下推的已完成入库单 -> 反提交 -> 删除
  T4 存在 active 下推行 -> 反提交 / 删除
  T5 多仓库 + 关库位管理 + 历史 NULL location 流水 -> 反提交库存校验
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    DocumentPushLine, InOrder, InOrderItem, Material, MaterialCategory, PurchaseOrder,
    PurchaseOrderItem, StockTransaction, Supplier, Unit, User, Warehouse,
    _stock_location_from_warehouse, add_stock, db, set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed(location_mgmt="0"):
    set_system_setting("location_management_enabled", location_mgmt)
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        Supplier(code="SUP001", name="供应商"),
        Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
        Warehouse(code="WHB", name="仓库B", status="active"),
        User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False),
    ])
    db.session.commit()
    mat = Material(code="M001", name="轴承", spec="6204",
                   category_id=1, unit_id=1, supplier_id=1, stock=0, price=10)
    db.session.add(mat)
    db.session.commit()
    return mat


def _make_completed_in_order(order_no, warehouse, qty, with_source_po=False, auto_push=False, location=None):
    user = User.query.filter_by(username="admin").first()
    order = InOrder(order_no=order_no, business_type="采购入库",
                    warehouse=warehouse, status="completed",
                    operator_id=user.id, supplier_id=1,
                    location=location or "")
    db.session.add(order)
    db.session.flush()
    source_item = None
    if with_source_po:
        po = PurchaseOrder(order_no=f"PO-{order_no}", status="partial")
        db.session.add(po)
        db.session.flush()
        source_item = PurchaseOrderItem(purchase_order_id=po.id, material_id=1,
                                        quantity=qty, received_quantity=qty,
                                        price=10, amount=qty * 10)
        db.session.add(source_item)
        db.session.flush()
    db.session.add(InOrderItem(
        in_order_id=order.id, material_id=1,
        quantity=qty, price=10, amount=qty * 10,
        source_purchase_order_item_id=source_item.id if source_item else None,
    ))
    if auto_push:
        order.auto_push_requisition = True
    db.session.commit()
    return order.id


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
        _seed()
    c = app_module.app.test_client()
    _login(c)
    yield c


class TestReproRevertDelete:

    def test_t1_no_source_revert_delete(self, client):
        """T1 基线：无来源采购单，反提交后删除成功。"""
        with app_module.app.test_request_context():
            mat = Material.query.filter_by(code="M001").first()
            wh = Warehouse.query.filter_by(code="WHA").first()
            ok, _ = add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh.name)
            assert ok
            db.session.commit()
            tid = _make_completed_in_order("IN-T1", "仓库A", 10)
        r1 = client.post(f"/in_order/{tid}/revert")
        d1 = r1.get_json()
        assert d1["status"] == "success", d1
        with app_module.app.app_context():
            assert db.session.get(InOrder, tid).status == "pending"
        r2 = client.post(f"/in_order/{tid}/delete")
        d2 = r2.get_json()
        assert d2["status"] == "success", d2

    def test_t2_with_source_po_revert_delete(self, client):
        """T2 有来源采购单，反提交后删除成功且释放 received_quantity。"""
        with app_module.app.test_request_context():
            mat = Material.query.filter_by(code="M001").first()
            wh = Warehouse.query.filter_by(code="WHA").first()
            ok, _ = add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh.name)
            assert ok
            db.session.commit()
            tid = _make_completed_in_order("IN-T2", "仓库A", 10, with_source_po=True)
            src_item = InOrderItem.query.filter_by(in_order_id=tid).first().source_purchase_order_item
            assert src_item.received_quantity == 10
        r1 = client.post(f"/in_order/{tid}/revert")
        d1 = r1.get_json()
        assert d1["status"] == "success", d1
        r2 = client.post(f"/in_order/{tid}/delete")
        d2 = r2.get_json()
        assert d2["status"] == "success", d2

    def test_t3_auto_push_revert_delete(self, client):
        """T3 auto_push_requisition 自动下推后，反提交/删除是否被 active 下推阻挡。"""
        with app_module.app.test_request_context():
            mat = Material.query.filter_by(code="M001").first()
            wh = Warehouse.query.filter_by(code="WHA").first()
            ok, _ = add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh.name)
            assert ok
            db.session.commit()
            tid = _make_completed_in_order("IN-T3", "仓库A", 10, auto_push=True)
            push_lines = DocumentPushLine.query.filter_by(source_document_id=tid).all()
            print(f"T3 push_lines={[(p.status, p.target_document_type) for p in push_lines]}")
        r1 = client.post(f"/in_order/{tid}/revert")
        d1 = r1.get_json()
        print(f"T3 revert -> {d1}")
        r2 = client.post(f"/in_order/{tid}/delete")
        d2 = r2.get_json()
        print(f"T3 delete -> {d2}")

    def test_t5_legacy_null_location_multiwrh(self, client):
        """T5 多仓库+关库位管理+历史 NULL location 流水：反提交是否误报库存不足。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed()
            mat = Material.query.filter_by(code="M001").first()
            wh_a = Warehouse.query.filter_by(code="WHA").first()
            # 模拟老数据：加库存但流水 location 为空（NULL 不入列）
            mat.stock = 50
            db.session.add(StockTransaction(
                material_id=mat.id, transaction_type="in", quantity=50,
                location=None,  # 老数据没有 location
                reference_type="in_order", reference_id=999,
            ))
            db.session.commit()
            tid = _make_completed_in_order("IN-T5", "仓库A", 50)
        r1 = client.post(f"/in_order/{tid}/revert")
        d1 = r1.get_json()
        print(f"T5 revert -> {d1}")
        assert d1["status"] == "success", d1
