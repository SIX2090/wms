# -*- coding: utf-8 -*-
"""BUG-2026-08-16-004 回归：批量完成出库必须补齐销售专属校验。

审计发现（AUDIT-2026-08-16 P1）：batch_complete_out_order 相比单据版
complete_out_order 缺 4 项校验——is_future_date、validate_sales_outbound_warehouse、
sales_outbound_remaining_check、_check_out_order_anomalies。单据完成被拦的
超发草稿可经批量放行，shipped_quantity 回写无上限。

修复后要求（批量循环体内，skip 不阻断整批）：
- 未来日期草稿 → skipped；
- 销售出库仓库无效/与来源销售订单不一致 → skipped；
- 销售出库超出未发货数量 → skipped；
- 异常检测命中 → skipped；
- 合法草稿（含合法销售出库）正常完成并回写 shipped_quantity。
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
    Customer, Material, MaterialCategory, OutOrder, OutOrderItem, SalesOrder,
    SalesOrderItem, StockTransaction, Supplier, Unit, User, Warehouse, db,
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
        Customer(code="C001", name="客户甲"),
        Warehouse(code="WH01", name="主仓", is_default=True, status="active"),
        Warehouse(code="WH02", name="停用仓", status="inactive"),
        User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False),
    ])
    db.session.commit()
    db.session.add(Material(
        code="M001", name="轴承", spec="6204",
        category_id=1, unit_id=1, supplier_id=1, stock=100, price=10,
    ))
    db.session.commit()


def _login(client):
    page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    token = m.group(1) if m else ""
    client.post("/login", data={
        "username": "admin", "password": "admin", "csrf_token": token})


def _make_sales_out_draft(order_no, quantity, *, warehouse="主仓",
                          sales_qty=10, doc_date=None,
                          warehouse_mismatch=False, source_item=None):
    """建一张销售出库 pending 草稿 + 来源销售订单。

    source_item 显式传入时跳过自建销售订单（用于跨单复用）。
    """
    user = User.query.filter_by(username="admin").first()
    if source_item is None:
        wh_id = Warehouse.query.filter_by(name="主仓").first().id
        if warehouse_mismatch:
            # 销售订单挂主仓，出库草稿写停用仓 → 仓库不一致
            so_warehouse_id, so_warehouse = wh_id, "主仓"
        else:
            so_warehouse_id, so_warehouse = (
                Warehouse.query.filter_by(name=warehouse).first().id, warehouse)
        so = SalesOrder(order_no=f"SO-{order_no}", customer_id=1,
                        warehouse=so_warehouse, warehouse_id=so_warehouse_id,
                        status="confirmed", operator_id=user.id)
        db.session.add(so)
        db.session.flush()
        source_item = SalesOrderItem(
            sales_order_id=so.id, material_id=1,
            quantity=sales_qty, shipped_quantity=0, price=10)
        db.session.add(source_item)
        db.session.flush()
    draft = OutOrder(
        order_no=order_no, business_type="销售出库",
        warehouse=warehouse, status="pending",
        date=doc_date or date.today(), operator_id=user.id,
        source_sales_order_id=source_item.sales_order_id)
    db.session.add(draft)
    db.session.flush()
    db.session.add(OutOrderItem(
        out_order_id=draft.id, material_id=1,
        source_sales_order_item_id=source_item.id,
        quantity=quantity, price=10, amount=quantity * 10))
    db.session.commit()
    return draft, source_item


def _batch_complete(client, *order_ids):
    return client.post("/out_order/batch_complete", json={"ids": list(order_ids)})


class TestBatchCompleteOutOrderGuards:

    def test_over_shipped_draft_is_skipped(self):
        """T1：超发草稿（10 张订单量发 20）批量完成被拒，库存未动。"""
        with app_module.app.app_context():
            _reset_db()
            _seed()
            draft, so_item = _make_sales_out_draft("OUT-OVER", 20)
            client = app_module.app.test_client()
            _login(client)
            resp = _batch_complete(client, draft.id)
            data = resp.get_json()
            assert data["completed"] == 0
            assert "OUT-OVER" in data["msg"]
            db.session.expire_all()
            assert db.session.get(OutOrder, draft.id).status == "pending"
            mat = db.session.get(Material, 1)
            db.session.expire(mat, ["stock"])
            assert mat.stock == 100
            assert (so_item.shipped_quantity or 0) == 0

    def test_future_date_draft_is_skipped(self):
        """T2：未来日期草稿批量完成被拒。"""
        with app_module.app.app_context():
            _reset_db()
            _seed()
            draft, _si = _make_sales_out_draft(
                "OUT-FUTURE", 5, doc_date=date.today() + timedelta(days=3))
            client = app_module.app.test_client()
            _login(client)
            resp = _batch_complete(client, draft.id)
            data = resp.get_json()
            assert data["completed"] == 0
            assert "出库日期晚于今天" in data["msg"]

    def test_warehouse_mismatch_draft_is_skipped(self):
        """T3：销售出库仓库与来源销售订单不一致 → 批量完成被拒。"""
        with app_module.app.app_context():
            _reset_db()
            _seed()
            draft, _si = _make_sales_out_draft(
                "OUT-MISMATCH", 5, warehouse="停用仓", warehouse_mismatch=True)
            client = app_module.app.test_client()
            _login(client)
            resp = _batch_complete(client, draft.id)
            data = resp.get_json()
            assert data["completed"] == 0
            assert "OUT-MISMATCH" in data["msg"]

    def test_valid_drafts_complete_and_clamp_shipped(self):
        """T4：合法草稿批量完成不受影响，库存扣减 + shipped_quantity 回写。"""
        with app_module.app.app_context():
            _reset_db()
            _seed()
            draft, so_item = _make_sales_out_draft("OUT-OK", 6)
            client = app_module.app.test_client()
            _login(client)
            resp = _batch_complete(client, draft.id)
            data = resp.get_json()
            assert data["completed"] == 1, data
            db.session.expire_all()
            assert db.session.get(OutOrder, draft.id).status == "completed"
            mat = db.session.get(Material, 1)
            db.session.expire(mat, ["stock"])
            assert abs(mat.stock - 94) < 1e-6
            assert abs((so_item.shipped_quantity or 0) - 6) < 1e-6
            assert StockTransaction.query.filter_by(
                reference_type="out_order", reference_id=draft.id).count() == 1

    def test_mixed_batch_skips_bad_and_completes_good(self):
        """T5：混合批次——超发单被跳过，合法单正常完成，整批不中断。"""
        with app_module.app.app_context():
            _reset_db()
            _seed()
            bad, _bad_si = _make_sales_out_draft("OUT-BAD", 99)
            good, good_si = _make_sales_out_draft("OUT-GOOD", 3)
            client = app_module.app.test_client()
            _login(client)
            resp = _batch_complete(client, bad.id, good.id)
            data = resp.get_json()
            assert data["completed"] == 1
            db.session.expire_all()
            assert db.session.get(OutOrder, bad.id).status == "pending"
            assert db.session.get(OutOrder, good.id).status == "completed"
            assert abs((good_si.shipped_quantity or 0) - 3) < 1e-6
