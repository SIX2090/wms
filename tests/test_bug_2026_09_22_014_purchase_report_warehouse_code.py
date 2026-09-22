# -*- coding: utf-8 -*-
"""BUG-2026-09-22-014：采购类报表/列表按仓库过滤时只匹配仓库名，漏掉编码写法。

现场复现路径（真人操作）：
  1. 移动端/API 录入采购入库单，warehouse 落库为仓库**编码**（如 WH-TEST）；
  2. Web 端打开「采购订单执行统计表」，仓库选「WH-TEST - 测试主仓」，点查询；
  3. 页面显示「当前条件下没有数据 / 共 0 条」，而库里明明有可关联的采购明细。

根因：_purchase_order_item_query 用 `InOrder.warehouse == filters['warehouse']`
（filters['warehouse'] 是仓库**名**）单边等值匹配，而入库单 warehouse 可能是
名称（Web 端 in_order_add.html option value=warehouse.name）或编码
（native_api payload.warehouse_code）。仓库内其余 17 处同类过滤均已采用
`db.or_(name, code)` 双匹配（BUG-2026-08-17-002 / BUG-2026-08-18-004），
采购类报表是唯一漏网消费点（R6 同根因未收敛）。

回归断言：
  T1 编码写法的采购入库单能进采购执行报表
  T2 名称写法的采购入库单仍能进采购执行报表（不回归）
  T3 只查本仓，不串仓
  T4 供应商/物料/价格三张汇总报表同源可见（共用采集器）
"""
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
    """造两个仓库，入库单分别以『编码』和『名称』两种写法落库。"""
    db.drop_all()
    db.create_all()
    unit = Unit(name="个", code="PCS")
    category = MaterialCategory(name="默认分类", code="DEFAULT")
    supplier = Supplier(name="供应商A", code="SUP-A")
    wh_a = Warehouse(name="仓库A", code="WHA", status="active")
    wh_b = Warehouse(name="仓库B", code="WHB", status="active")
    db.session.add_all([unit, category, supplier, wh_a, wh_b])
    db.session.flush()

    m1 = Material(code="M001", name="轴承", spec="6204", stock=0,
                  price=10, unit_id=unit.id, category_id=category.id)
    m2 = Material(code="M002", name="电机", spec="400W", stock=0,
                  price=20, unit_id=unit.id, category_id=category.id)
    db.session.add_all([m1, m2])
    db.session.flush()

    # 仓库A：入库单以【编码】落库（移动端/API 写法）—— 本 bug 的受害者
    po_code = PurchaseOrder(order_no="PO-CODE", date=date(2026, 9, 1),
                            supplier_id=supplier.id, status="partial",
                            total_amount=100)
    # 仓库B：入库单以【名称】落库（Web 端写法）—— 对照组
    po_name = PurchaseOrder(order_no="PO-NAME", date=date(2026, 9, 2),
                            supplier_id=supplier.id, status="partial",
                            total_amount=200)
    db.session.add_all([po_code, po_name])
    db.session.flush()

    item_code = PurchaseOrderItem(
        purchase_order_id=po_code.id, material_id=m1.id,
        quantity=10, received_quantity=5, price=10, amount=100)
    item_name = PurchaseOrderItem(
        purchase_order_id=po_name.id, material_id=m2.id,
        quantity=10, received_quantity=5, price=20, amount=200)
    db.session.add_all([item_code, item_name])
    db.session.flush()

    in_code = InOrder(order_no="IN-CODE", date=date(2026, 9, 3),
                      supplier_id=supplier.id, business_type="采购入库",
                      warehouse=wh_a.code,          # ← 编码写法
                      status="completed", total_amount=50,
                      source_purchase_order_id=po_code.id)
    in_name = InOrder(order_no="IN-NAME", date=date(2026, 9, 4),
                      supplier_id=supplier.id, business_type="采购入库",
                      warehouse=wh_b.name,          # ← 名称写法
                      status="completed", total_amount=100,
                      source_purchase_order_id=po_name.id)
    db.session.add_all([in_code, in_name])
    db.session.flush()

    db.session.add_all([
        InOrderItem(in_order_id=in_code.id, material_id=m1.id,
                    source_purchase_order_item_id=item_code.id,
                    quantity=5, price=10, amount=50),
        InOrderItem(in_order_id=in_name.id, material_id=m2.id,
                    source_purchase_order_item_id=item_name.id,
                    quantity=5, price=20, amount=100),
    ])
    db.session.commit()
    return wh_a, wh_b


def test_t1_code_written_inbound_visible():
    """T1：入库单 warehouse 写『编码』时，采购执行报表必须查得到。"""
    with app_module.app.app_context():
        wh_a, _ = _seed()
        payload = _build_report_payload(
            "purchase_order_execution", _filters(wh_a))
        order_nos = [r["order_no"] for r in payload["all_rows"]]
        assert order_nos == ["PO-CODE"], (
            f"编码写法的入库单未能进入采购执行报表，实际={order_nos}"
        )


def test_t2_name_written_inbound_still_visible():
    """T2：入库单 warehouse 写『名称』时行为不回归。"""
    with app_module.app.app_context():
        _, wh_b = _seed()
        payload = _build_report_payload(
            "purchase_order_execution", _filters(wh_b))
        order_nos = [r["order_no"] for r in payload["all_rows"]]
        assert order_nos == ["PO-NAME"], (
            f"名称写法的入库单查不到了（回归），实际={order_nos}"
        )


def test_t3_no_cross_warehouse_leak():
    """T3：查 A 仓不得带出 B 仓（R2 不串仓）。"""
    with app_module.app.app_context():
        wh_a, wh_b = _seed()
        a = _build_report_payload("purchase_order_execution", _filters(wh_a))
        b = _build_report_payload("purchase_order_execution", _filters(wh_b))
        a_nos = {r["order_no"] for r in a["all_rows"]}
        b_nos = {r["order_no"] for r in b["all_rows"]}
        assert a_nos == {"PO-CODE"}, f"A 仓串味: {a_nos}"
        assert b_nos == {"PO-NAME"}, f"B 仓串味: {b_nos}"
        assert not (a_nos & b_nos), "两仓结果出现交集"


def test_t4_summary_reports_share_fix():
    """T4：供应商/物料/价格三张汇总报表共用采集器，同源可见。"""
    with app_module.app.app_context():
        wh_a, _ = _seed()
        for report_type in ("supplier_purchase_summary",
                            "material_purchase_summary",
                            "purchase_price_analysis"):
            payload = _build_report_payload(report_type, _filters(wh_a))
            assert payload["all_rows"], (
                f"{report_type} 在编码写法入库单下仍为空"
            )
