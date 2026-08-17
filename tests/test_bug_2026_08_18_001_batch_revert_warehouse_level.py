# -*- coding: utf-8 -*-
"""BUG-2026-08-18-001 回归：batch_revert_in_order 库存充足校验改仓库级口径。

根因：批量反提交此前用全局 `Material.stock` 校验，多仓库下 A 仓库存可掩护
B 仓入库单批量反提交，B 仓账面被打穿（与 BUG-2026-08-16-009 单张反提交同类）。

修复：batch_revert_in_order 改用 get_warehouse_stock_quantities 的仓库级口径
（OFF 按流水 location 聚合、ON 按 LocationInventory 聚合）。

测试用例：
  T1. 全局库存 100 但源仓库 B 为 0 时，批量反提交 B 仓入库单被跳过
  T2. B 仓库存充足时批量反提交成功，状态回退为 pending
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
    InOrder, InOrderItem, Material, MaterialCategory, Supplier, Unit, User,
    Warehouse, add_stock, db, set_system_setting,
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


def _seed():
    set_system_setting("location_management_enabled", "0")
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


def _make_completed_in_order(order_no, warehouse, qty):
    user = User.query.filter_by(username="admin").first()
    order = InOrder(order_no=order_no, business_type="采购入库",
                    warehouse=warehouse, status="completed",
                    operator_id=user.id, supplier_id=1)
    db.session.add(order)
    db.session.flush()
    db.session.add(InOrderItem(
        in_order_id=order.id, material_id=1,
        quantity=qty, price=10, amount=qty * 10))
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


class TestBatchRevertWarehouseLevel:

    def test_batch_reject_when_warehouse_empty_but_global_high(self, client):
        """T1：全局库存全在 A 仓（B 仓 0）时，批量反提交 B 仓入库单被跳过。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed()
            mat = Material.query.filter_by(code="M001").first()
            wh_a = Warehouse.query.filter_by(code="WHA").first()
            ok, _ = add_stock(mat, 100, 'in', 'in_order', 1, warehouse=wh_a)
            assert ok
            db.session.commit()
            tid = _make_completed_in_order("IN-B-BATCH-BLOCK", "仓库B", 10)

        resp = client.post("/in_order/batch_revert", json={"ids": [tid]})
        data = resp.get_json()
        assert resp.status_code == 200, data
        assert data.get("reverted") == 0, data
        assert "库存不足" in (data.get("msg") or ""), data
        with app_module.app.app_context():
            assert db.session.get(InOrder, tid).status == "completed"

    def test_batch_succeed_when_warehouse_sufficient(self, client):
        """T2：B 仓库存充足时批量反提交成功，状态回退为 pending。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed()
            mat = Material.query.filter_by(code="M001").first()
            wh_b = Warehouse.query.filter_by(code="WHB").first()
            ok, _ = add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh_b)
            assert ok
            db.session.commit()
            tid = _make_completed_in_order("IN-B-BATCH-OK", "仓库B", 10)

        resp = client.post("/in_order/batch_revert", json={"ids": [tid]})
        data = resp.get_json()
        assert resp.status_code == 200, data
        assert data.get("reverted") == 1, data
        with app_module.app.app_context():
            assert db.session.get(InOrder, tid).status == "pending"