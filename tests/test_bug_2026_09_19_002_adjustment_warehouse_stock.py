# -*- coding: utf-8 -*-
"""BUG-2026-09-19-002 回归：库存调整单报损校验按「单据仓库」口径。

修复前：add_adjustment 保存报损单时用全局 Material.stock 校验，
导致 A 仓有库存即可掩护 B 仓报损（双仓隔离失效），
与 BUG-2026-08-16-009（出库单同根因）属同一模式（A11 / R2）。

修复后：
1. 双仓场景：库存全部归属副仓时，主仓报损单必须被拒；
2. 兼容场景：库存全部来自无法归属仓库的历史遗留流水时，
   回退全局口径放行（R2 历史脏数据兼容，与 deduct_stock_atomic 一致）。
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
    AdjustmentOrder, Material, MaterialCategory, StockTransaction, Supplier,
    Unit, User, Warehouse, db, set_system_setting,
)


def _login(client):
    page = client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    return token.group(1) if token else ""


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False,
        ))
        db.session.add_all([
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Supplier(code="SUP001", name="供应商"),
            Warehouse(code="WH01", name="主仓", is_default=True),
            Warehouse(code="WH02", name="副仓", is_default=False),
        ])
        db.session.commit()
        db.session.add(Material(
            code="M-ADJ", name="调整料", spec="S",
            category_id=1, unit_id=1, supplier_id=1, stock=10, price=1,
        ))
        db.session.commit()
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
    c = app_module.app.test_client()
    token = _login(c)
    c.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})
    yield c


def _post_loss_order(client, warehouse="主仓"):
    payload = {
        "adjustment_type": "loss",
        "warehouse": warehouse,
        "items": [{"material_id": 1, "code": "M-ADJ", "quantity": 5, "reason": "测试报损"}],
    }
    resp = client.post("/adjustment/add", json=payload)
    # api_error 返回 400，成功返回 200 且 status=success
    assert resp.status_code in (200, 400), resp.get_data(as_text=True)
    return resp.get_json()


def test_loss_rejected_when_stock_only_in_other_warehouse(client):
    """库存全部归属副仓时，主仓报损单必须被拒（双仓隔离）。"""
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M-ADJ").first()
        wh_b = Warehouse.query.filter_by(name="副仓").first()
        db.session.add(StockTransaction(
            material_id=m.id, transaction_type="in", quantity=10,
            warehouse_id=wh_b.id, location=None, remark="副仓入库",
        ))
        db.session.commit()
    data = _post_loss_order(client, warehouse="主仓")
    assert data.get("status") == "error", data
    assert "库存不足" in (data.get("msg") or ""), data
    with app_module.app.app_context():
        assert AdjustmentOrder.query.count() == 0  # 未落库


def test_loss_allowed_when_stock_unattributed(client):
    """库存全部来自无归属历史遗留流水时，回退全局口径放行。"""
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M-ADJ").first()
        db.session.add(StockTransaction(
            material_id=m.id, transaction_type="in", quantity=10,
            warehouse_id=None, location=None, remark="历史遗留",
        ))
        db.session.commit()
    data = _post_loss_order(client, warehouse="主仓")
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        order = AdjustmentOrder.query.filter_by(adjustment_no=data.get("adjustment_no")).first()
        assert order is not None and order.status == "pending"
