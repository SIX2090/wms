# -*- coding: utf-8 -*-
"""BUG-2026-08-21-003 回归测试：采购入库明细表同时按「供应商 + 合同编号」筛选报 500。

根因：`_apply_header_or_item_contract_filters` 用相关子查询 `EXISTS` 判断
「表单头或任一明细匹配合同编号/工程名称」，但入库单列表外层查询已
`outerjoin` 明细表（`db.session.query(InOrder, InOrderItem).outerjoin(...)`），
SQLAlchemy 自动相关（auto-correlation）把子查询里的明细表也关联到外层 FROM，
导致子查询无 FROM 子句，编译抛
「Select statement ... returned no FROM clauses due to auto-correlation」→ 500。

修复：对两个 EXISTS 子查询显式 `.correlate(header_model)`，
只关联表头表、明细表保留为子查询自身 FROM。

测试用例：
  T1. 仅合同编号过滤 -> 200（此前正常路径不应回退）
  T2. 供应商 + 合同编号同时过滤 -> 200（原 BUG 触发点，此前 500）
  T3. 供应商 + 不匹配合同编号 -> 200 且结果为空（筛选正确排除）
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date
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
    InOrder, InOrderItem, _apply_header_or_item_contract_filters,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
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
    db.session.flush()
    order = InOrder(
        order_no="IN-001",
        date=date.today(),
        business_type="采购入库",
        warehouse="仓库A",
        supplier_id=sup.id,
        status="pending",
        contract_no="HD260814001",
        project_name="一号厂房",
    )
    db.session.add(order)
    db.session.flush()
    item = InOrderItem(
        in_order_id=order.id,
        material_id=mat.id,
        quantity=5, price=10, amount=50,
        contract_no="HD260814001",
        project_name="一号厂房",
    )
    db.session.add(item)
    db.session.commit()
    return sup.id


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


def test_T2_supplier_plus_contract_filter_returns_200():
    """原 BUG 触发点：同时输入供应商 + 合同编号，此前抛 auto-correlation 500。"""
    with app_module.app.app_context():
        _reset_db()
        sup_id = _seed()
    client = _make_client()
    resp = client.get(f"/in_order?type=purchase_in&supplier_id={sup_id}&contract_no=HD260814001")
    assert resp.status_code == 200, f"供应商+合同编号筛选返回 {resp.status_code}，应为 200"
    body = resp.data.decode("utf-8", errors="replace")
    assert "IN-001" in body, "筛选结果应包含匹配的单据 IN-001"


def test_T3_supplier_plus_mismatched_contract_filters_correctly():
    """供应商 + 不匹配合同编号 -> 200 且结果为空（筛选正确排除，不漏也不崩）。"""
    with app_module.app.app_context():
        _reset_db()
        sup_id = _seed()
    client = _make_client()
    resp = client.get(f"/in_order?type=purchase_in&supplier_id={sup_id}&contract_no=NOT_EXISTS")
    assert resp.status_code == 200, f"供应商+不匹配合同编号返回 {resp.status_code}，应为 200"
    body = resp.data.decode("utf-8", errors="replace")
    assert "IN-001" not in body, "不匹配的合同编号不应返回任何单据"


def test_T1_contract_only_filter_still_works():
    """仅合同编号过滤不应回退（本修复未破坏原有相关子查询正确形态）。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()
    client = _make_client()
    resp = client.get("/in_order?type=purchase_in&contract_no=HD260814001")
    assert resp.status_code == 200, f"仅合同编号过滤返回 {resp.status_code}，应为 200"
    assert "IN-001" in resp.data.decode("utf-8", errors="replace")


def test_helper_function_contract_filter():
    """直接验证修复后的 helper 可正常编译并返回过滤后的查询（防逻辑回退）。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()
        from sqlalchemy.orm import joinedload
        query = db.session.query(InOrder).outerjoin(InOrderItem, InOrderItem.in_order_id == InOrder.id).options(
            joinedload(InOrder.supplier),
        )
        query = _apply_header_or_item_contract_filters(
            query, InOrder, InOrderItem, 'in_order_id',
            contract_no_filter='HD260814001',
        )
        # 编译成功即不抛 auto-correlation 异常；且应能查出该单据
        orders = query.all()
        assert len(orders) == 1
        assert orders[0].order_no == "IN-001"