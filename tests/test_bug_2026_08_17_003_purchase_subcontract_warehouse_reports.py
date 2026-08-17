# -*- coding: utf-8 -*-
"""BUG-2026-08-17-003：采购/委外报表必须按仓库隔离。"""
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    db,
    InOrder,
    InOrderItem,
    Material,
    MaterialCategory,
    PurchaseOrder,
    PurchaseOrderItem,
    SubcontractOrder,
    Supplier,
    Unit,
    Warehouse,
    _build_report_payload,
)


app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _filters(warehouse):
    return {
        "warehouse_id": warehouse.id,
        "warehouse": warehouse.name,
        "warehouse_code": warehouse.code,
        "start_date": None,
        "end_date": None,
        "supplier_id": None,
        "supplier": "",
        "material_code": "",
        "status": "",
        "stock_status": "",
        "location": "",
        "page": 1,
        "page_size": 100,
        "sort_field": "",
        "sort_order": "asc",
        "export": "",
    }


def _seed():
    db.drop_all()
    db.create_all()
    unit = Unit(name="个", code="PCS")
    category = MaterialCategory(name="默认分类", code="DEFAULT")
    supplier = Supplier(name="供应商A", code="SUP-A")
    wh_a = Warehouse(name="仓库A", code="WHA", status="active")
    wh_b = Warehouse(name="仓库B", code="WHB", status="active")
    db.session.add_all([unit, category, supplier, wh_a, wh_b])
    db.session.flush()
    material = Material(
        code="M001", name="轴承", spec="6204", stock=0,
        price=10, unit_id=unit.id, category_id=category.id,
    )
    db.session.add(material)
    db.session.flush()

    po_a = PurchaseOrder(
        order_no="PO-A", date=date(2026, 8, 1), supplier_id=supplier.id,
        status="partial", total_amount=100,
    )
    po_b = PurchaseOrder(
        order_no="PO-B", date=date(2026, 8, 2), supplier_id=supplier.id,
        status="partial", total_amount=200,
    )
    db.session.add_all([po_a, po_b])
    db.session.flush()
    item_a = PurchaseOrderItem(
        purchase_order_id=po_a.id, material_id=material.id,
        quantity=10, received_quantity=5, price=10, amount=100,
    )
    item_b = PurchaseOrderItem(
        purchase_order_id=po_b.id, material_id=material.id,
        quantity=20, received_quantity=5, price=10, amount=200,
    )
    db.session.add_all([item_a, item_b])
    db.session.flush()
    inbound_a = InOrder(
        order_no="IN-A", date=date(2026, 8, 3), supplier_id=supplier.id,
        warehouse=wh_a.name, status="completed", total_amount=50,
    )
    inbound_b = InOrder(
        order_no="IN-B", date=date(2026, 8, 4), supplier_id=supplier.id,
        warehouse=wh_b.name, status="completed", total_amount=50,
        source_purchase_order_id=po_b.id,
    )
    db.session.add_all([inbound_a, inbound_b])
    db.session.flush()
    db.session.add_all([
        InOrderItem(
            in_order_id=inbound_a.id, material_id=material.id,
            source_purchase_order_item_id=item_a.id,
            quantity=5, price=10, amount=50,
        ),
        InOrderItem(
            in_order_id=inbound_b.id, material_id=material.id,
            quantity=5, price=10, amount=50,
        ),
    ])
    db.session.add_all([
        SubcontractOrder(
            order_no="SC-A", date=date(2026, 8, 5), supplier_id=supplier.id,
            warehouse=wh_a.name, status="processing",
        ),
        SubcontractOrder(
            order_no="SC-B", date=date(2026, 8, 6), supplier_id=supplier.id,
            warehouse=wh_b.name, status="processing",
        ),
    ])
    db.session.commit()
    return wh_a, wh_b


def test_purchase_reports_filter_by_inbound_warehouse():
    with app_module.app.app_context():
        wh_a, wh_b = _seed()
        payload_a = _build_report_payload(
            "purchase_order_execution", _filters(wh_a)
        )
        payload_b = _build_report_payload(
            "purchase_order_execution", _filters(wh_b)
        )
        assert [row["order_no"] for row in payload_a["all_rows"]] == ["PO-A"]
        assert [row["order_no"] for row in payload_b["all_rows"]] == ["PO-B"]


def test_subcontract_report_filters_by_warehouse():
    with app_module.app.app_context():
        wh_a, wh_b = _seed()
        payload_a = _build_report_payload("subcontract", _filters(wh_a))
        payload_b = _build_report_payload("subcontract", _filters(wh_b))
        assert [row["order_no"] for row in payload_a["all_rows"]] == ["SC-A"]
        assert [row["order_no"] for row in payload_b["all_rows"]] == ["SC-B"]
