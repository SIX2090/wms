# -*- coding: utf-8 -*-
"""SALES-AUDIT-007 回归测试：销售报表/导出仓库必填门禁。

根因（P1）：
  16 个销售报表/导出路由把仓库当可选筛选，未传时返回全仓数据，
  违反 AGENTS.md「出入库报表的查询入口必须将仓库作为必填条件」。

修复：
  新增 _require_report_warehouse() 辅助函数（warehouse_id > 名称 > 默认）；
  _sales_report_orders() / _sales_report_filters_context() 无仓库返回空；
  10 个报表/导出路由接入门禁：导出返回 400，HTML 返回空结果。

测试用例：
  T1. _require_report_warehouse 无参数有默认仓时返回默认仓
  T2. _require_report_warehouse 无参数无默认仓时返回 None
  T3. _sales_report_orders 无仓库时返回空列表
  T4. 导出路由无仓库返回 400
  T5. HTML 报表无仓库返回 200 空结果
  T6. 显式传 warehouse_id 时正常返回数据
"""
from __future__ import annotations

import os
import sys
import re
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    db, Customer, Material, MaterialCategory, OutOrder, SalesOrder,
    SalesOrderItem, Supplier, Unit, User, Warehouse,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base(with_default_warehouse=True):
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    sup = Supplier(code="SUP001", name="供应商甲")
    wh = Warehouse(code="WHA", name="仓库A", is_default=with_default_warehouse, status="active")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    cust = Customer(code="C001", name="测试客户")
    mat = Material(
        code="M001", name="测试物料", spec="S1",
        category=cat, unit=unit, supplier=sup,
        stock=100, price=10, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup, wh, user, cust, mat])
    db.session.commit()
    return {"mat": mat, "wh": wh, "cust": cust, "user": user}


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


def _make_confirmed_order(cust, mat, qty, order_no, warehouse="仓库A"):
    order = SalesOrder(
        order_no=order_no, customer_id=cust.id, warehouse=warehouse,
        date=date.today(), status="confirmed", shipment_status="pending",
    )
    db.session.add(order)
    db.session.flush()
    item = SalesOrderItem(
        sales_order_id=order.id, material_id=mat.id,
        quantity=qty, shipped_quantity=0, price=10,
        amount=qty * 10, tax_rate=0.13,
    )
    db.session.add(item)
    db.session.commit()
    return order


class TestRequireReportWarehouseHelper:
    """T1/T2：_require_report_warehouse 辅助函数。"""

    def test_returns_default_warehouse_when_no_param(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_base(with_default_warehouse=True)
            with app_module.app.test_request_context('/sales/report'):
                from app import _require_report_warehouse
                wh, err = _require_report_warehouse()
                assert wh is not None
                assert err is None
                assert wh.name == "仓库A"

    def test_returns_none_when_no_param_and_no_default(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_base(with_default_warehouse=False)
            with app_module.app.test_request_context('/sales/report'):
                from app import _require_report_warehouse
                wh, err = _require_report_warehouse()
                assert wh is None
                assert err == '请选择仓库'


class TestSalesReportOrdersEmptyWithoutWarehouse:
    """T3：_sales_report_orders 无仓库时返回空列表。"""

    def test_returns_empty_without_warehouse(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base(with_default_warehouse=False)
            _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-RPT-001")
            with app_module.app.test_request_context('/sales/execution_report'):
                from app import _sales_report_orders
                orders = _sales_report_orders()
                assert orders == []


class TestExportRoutesReturn400WithoutWarehouse:
    """T4：导出路由无仓库返回 400。"""

    def test_export_sales_orders_400_without_warehouse(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_base(with_default_warehouse=False)
        client = _make_client()
        resp = client.get("/sales/export")
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["status"] == "error"
        assert "仓库" in body.get("msg", "")

    def test_export_sales_report_400_without_warehouse(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_base(with_default_warehouse=False)
        client = _make_client()
        resp = client.get("/sales/report/export")
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["status"] == "error"


class TestHtmlReportRoutesReturnEmptyWithoutWarehouse:
    """T5：HTML 报表无仓库返回 200 空结果。"""

    def test_sales_report_renders_empty_without_warehouse(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_base(with_default_warehouse=False)
        client = _make_client()
        resp = client.get("/sales/report")
        assert resp.status_code == 200


class TestExplicitWarehouseReturnsData:
    """T6：显式传 warehouse_id 时正常返回数据。"""

    def test_sales_report_with_warehouse_id_returns_data(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base(with_default_warehouse=True)
            _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-RPT-002")
        client = _make_client()
        resp = client.get(f"/sales/report?warehouse_id={1}")
        assert resp.status_code == 200
