# -*- coding: utf-8 -*-
"""BUG-2026-08-17-004：报表仪表盘必须按所选仓库聚合。"""
import os
import sys
from datetime import date
from pathlib import Path

from flask_login import login_user
from werkzeug.security import generate_password_hash

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
    OutOrder,
    OutOrderItem,
    StockTransaction,
    Supplier,
    Unit,
    Warehouse,
    build_report_dashboard_context,
)


app_module.app.config["TESTING"] = True


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
    material_a = Material(
        code="M-A", name="物料A", unit_id=unit.id, category_id=category.id,
        stock=15, price=10,
    )
    material_b = Material(
        code="M-B", name="物料B", unit_id=unit.id, category_id=category.id,
        stock=30, price=20,
    )
    db.session.add_all([material_a, material_b])
    db.session.flush()
    today = date.today()
    in_a = InOrder(
        order_no="IN-A", date=today, supplier_id=supplier.id,
        warehouse=wh_a.name, status="completed", total_amount=150,
    )
    in_b = InOrder(
        order_no="IN-B", date=today, supplier_id=supplier.id,
        warehouse=wh_b.name, status="completed", total_amount=600,
    )
    out_a = OutOrder(
        order_no="OUT-A", date=today, warehouse=wh_a.name,
        status="completed", total_amount=30,
    )
    out_b = OutOrder(
        order_no="OUT-B", date=today, warehouse=wh_b.name,
        status="completed", total_amount=80,
    )
    db.session.add_all([in_a, in_b, out_a, out_b])
    db.session.flush()
    db.session.add_all([
        InOrderItem(in_order_id=in_a.id, material_id=material_a.id, quantity=15, price=10, amount=150),
        InOrderItem(in_order_id=in_b.id, material_id=material_b.id, quantity=30, price=20, amount=600),
        OutOrderItem(out_order_id=out_a.id, material_id=material_a.id, quantity=3, price=10, amount=30),
        OutOrderItem(out_order_id=out_b.id, material_id=material_b.id, quantity=4, price=20, amount=80),
        StockTransaction(material_id=material_a.id, transaction_type="in", quantity=15, location=wh_a.name),
        StockTransaction(material_id=material_b.id, transaction_type="in", quantity=30, location=wh_b.name),
    ])
    db.session.commit()
    return wh_a, wh_b


def test_build_report_dashboard_context():
    with app_module.app.app_context():
        wh_a, wh_b = _seed()
        stats_a, charts_a = build_report_dashboard_context(wh_a)
        stats_b, charts_b = build_report_dashboard_context(wh_b)

        assert stats_a["month_in_amount"] == 150
        assert stats_a["month_out_amount"] == 30
        assert stats_a["month_in_count"] == 1
        assert stats_a["month_out_count"] == 1
        assert stats_a["total_stock"] == 15
        assert stats_a["stock_value"] == 150
        assert charts_a["top_stock"]["labels"] == ["M-A"]

        assert stats_b["month_in_amount"] == 600
        assert stats_b["month_out_amount"] == 80
        assert stats_b["total_stock"] == 30
        assert stats_b["stock_value"] == 600
        assert charts_b["top_stock"]["labels"] == ["M-B"]


def test_dashboard_route_unpacks_resolved_warehouse():
    with app_module.app.app_context():
        wh_a, _ = _seed()
        user = app_module.User(
            username="dashboard-admin",
            password_hash=generate_password_hash("admin"),
            role="admin",
        )
        db.session.add(user)
        db.session.commit()
        with app_module.app.test_request_context(f"/report/dashboard?warehouse_id={wh_a.id}"):
            login_user(user)
            response = app_module.app.make_response(
                app_module.app.view_functions["report_dashboard"]()
            )
        assert response.status_code == 200
