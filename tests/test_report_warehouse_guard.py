# -*- coding: utf-8 -*-
"""业务报表「仓库必填守卫」回归测试（BUG-2026-08-16-017 F7，2026-09-12 收口）。

为什么单独落在 test_ 前缀文件里：
原断言在 tests/verify_bug_P15_P16_P21.py（TestBugP21BizReportWarehouseGuard），
而 ci.yml 的 Verify regression 步骤把该文件登记在 known_failures 清单里**整文件跳过**，
断言等于从没在 CI 跑过（这就是它"豁免"了两年的真实含义）。摘清单要改 workflow 文件、
需要 workflow scope 的 token；本文件以 test_ 前缀进入主 pytest 收集
（`pytest tests/` 步骤），因此**无需 workflow 权限即可让守卫真正进入 CI**。
verify_bug_P15_P16_P21.py 中的同类已删除，避免两处维护。

守卫契约（AGENTS.md 仓库必填）：
1. 无仓库参数 + 无默认仓库 → 明确拒绝（HTTP 400「请选择仓库」），绝不返回跨仓全量；
2. 有默认仓库且未显式传参 → 自动带入默认仓，正常出数（不误伤）；
3. 显式传 warehouse_id → 按指定仓出数；
4. 换一个仓查询 → 必须为空（串仓是这个系统 20+ 个多仓 BUG 的共同根因）。

仓库归属口径（种子必须落到各自的归属字段，否则"有数查不出"会被误判成守卫误伤）：
- 采购执行表：采购订单本身不记仓库，按**来源入库单**的 InOrder.warehouse 归属；
- 委外表：SubcontractOrder.warehouse（名称/编码任一匹配）；
- 工单领料表：ProductionRequisition.warehouse。
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

REPORTS = ('purchase_order_execution', 'subcontract', 'requisition')


def _login(client):
    """/report/api 走 @login_required（web session），故用表单登录而非 /api/login。"""
    resp = client.post("/login", data={"username": "admin", "password": "admin"},
                       follow_redirects=True)
    assert resp.status_code == 200, resp.get_data(as_text=True)


def _seed_base(with_default_warehouse: bool, with_second_warehouse: bool = False):
    """基础种子：用户 + 物料 + 仓库（可选默认仓/第二仓）。返回仓库名。"""
    from app import Material, MaterialCategory, Unit, User, Warehouse

    user = User(username="admin", password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False)
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    db.session.add_all([user, unit, cat])
    db.session.flush()
    db.session.add(Material(code="M001", name="测试物料", spec="S1", category=cat,
                            unit=unit, stock=0, price=10, min_stock=0,
                            max_stock=9999, reorder_point=0))
    wh_name = None
    if with_default_warehouse:
        wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
        db.session.add(wh)
        wh_name = wh.name
    if with_second_warehouse:
        db.session.add(Warehouse(code="WHB", name="仓库B", status="active"))
    db.session.commit()
    return wh_name


def _seed_biz_orders(warehouse_name: str | None):
    """造采购订单（带来源入库单）/委外单/领料单各一条，仓库归属落在各自口径上。"""
    from app import (InOrder, InOrderItem, Material, ProductionRequisition,
                     ProductionRequisitionItem, PurchaseOrder, PurchaseOrderItem,
                     SubcontractItem, SubcontractOrder, Supplier)

    mat = Material.query.filter_by(code="M001").first()
    sup = Supplier(code="SUP001", name="测试供应商")
    db.session.add(sup)
    db.session.flush()

    po = PurchaseOrder(order_no="PO-001", date=date.today(), supplier_id=sup.id,
                       status="pending", total_amount=100)
    db.session.add(po)
    db.session.flush()
    po_item = PurchaseOrderItem(purchase_order_id=po.id, material_id=mat.id,
                                quantity=10, received_quantity=0, price=10, amount=100)
    db.session.add(po_item)
    db.session.flush()
    # 采购执行的仓库归属来自入库单：补一张该仓采购入库单并回指采购行
    io = InOrder(order_no="IN-001", date=date.today(), supplier_id=sup.id,
                 business_type="采购入库", warehouse=warehouse_name or "",
                 source_purchase_order_id=po.id, status="completed", total_amount=100)
    db.session.add(io)
    db.session.flush()
    db.session.add(InOrderItem(in_order_id=io.id, material_id=mat.id,
                               source_purchase_order_item_id=po_item.id,
                               quantity=4, price=10, amount=40))

    sc = SubcontractOrder(order_no="SC-001", date=date.today(), supplier_id=sup.id,
                          status="pending", total_amount=50,
                          warehouse=warehouse_name or "")
    db.session.add(sc)
    db.session.flush()
    db.session.add(SubcontractItem(subcontract_order_id=sc.id, material_id=mat.id,
                                   quantity=5))

    pr = ProductionRequisition(req_no="REQ-001", date=date.today(), purpose="测试领料",
                               status="pending", warehouse=warehouse_name)
    db.session.add(pr)
    db.session.flush()
    db.session.add(ProductionRequisitionItem(requisition_id=pr.id, material_id=mat.id,
                                             quantity=3))
    db.session.commit()


@pytest.fixture()
def client():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        db.session.remove()
    c = app_module.app.test_client()
    yield c
    with app_module.app.app_context():
        db.session.remove()


def test_no_warehouse_and_no_default_is_rejected(client):
    """无仓库参数 + 无默认仓库 → 400「请选择仓库」，绝不返回数据行。"""
    with app_module.app.app_context():
        _seed_base(with_default_warehouse=False)
    _login(client)
    for report_type in REPORTS:
        resp = client.get(f"/report/api/{report_type}")
        body = resp.get_json() or {}
        assert resp.status_code == 400, (report_type, body)
        assert body.get("status") == "error", (report_type, body)
        assert "请选择仓库" in (body.get("msg") or ""), (report_type, body)
        assert "data" not in body, f"{report_type} 无仓库时不应返回任何数据行：{body}"


def test_default_warehouse_auto_applied(client):
    """有默认仓库且未显式传参 → 自动带入默认仓，三个报表都出数（不误伤）。"""
    with app_module.app.app_context():
        wh_name = _seed_base(with_default_warehouse=True)
        _seed_biz_orders(wh_name)
    _login(client)
    for report_type in REPORTS:
        resp = client.get(f"/report/api/{report_type}")
        body = resp.get_json() or {}
        assert resp.status_code == 200, (report_type, body)
        assert body.get("status") == "success", (report_type, body)
        assert body.get("data") != [], (
            f"{report_type} 有默认仓时不应被守卫拦截（自动带入默认仓）：{body}")


def test_explicit_warehouse_returns_rows_and_isolates(client):
    """显式指定仓 → 出数；换成另一个仓 → 必须为空（跨仓隔离）。"""
    with app_module.app.app_context():
        wh_name = _seed_base(with_default_warehouse=True, with_second_warehouse=True)
        _seed_biz_orders(wh_name)
        from app import Warehouse
        wh_a_id = Warehouse.query.filter_by(code="WHA").first().id
        wh_b_id = Warehouse.query.filter_by(code="WHB").first().id
    _login(client)
    for report_type in REPORTS:
        resp = client.get(f"/report/api/{report_type}?warehouse_id={wh_a_id}")
        body = resp.get_json() or {}
        assert resp.status_code == 200, (report_type, body)
        assert body.get("data") != [], (
            f"{report_type} 显式指定仓库时应返回数据：{body}")

        other = client.get(f"/report/api/{report_type}?warehouse_id={wh_b_id}")
        other_body = other.get_json() or {}
        assert other.status_code == 200, (report_type, other_body)
        assert other_body.get("data") == [], (
            f"{report_type} 换仓查询仍返回数据，仓库过滤失效（串仓）：{other_body}")
