# -*- coding: utf-8 -*-
"""BUG-2026-08-18-002 回归：历史未归属流水导致“明明有库存却拒绝反提交”。

根因：多仓库 + 关库位管理时，get_warehouse_stock_quantities 按
StockTransaction.location IN (仓库名/编码) 聚合。历史遗留数据的库存流水
location 为 NULL/''，无法按仓库聚合，仓库级查得 0 → 反提交（单张/批量）
误报“库存不足”，单据卡在 completed，进而无法删除（已完成单禁止直接删除）。

修复：revert_in_order / batch_revert_in_order / update_completed_in_order
在仓库级校验失败时调用 _material_stock_unattributed(material_id)：
- 该物料库存全部为未归属流水（location 全空 / LocationInventory.warehouse_id 全 NULL）
  → 回退全局 Material.stock 口径，允许反提交/删除；
- 存在任何可归属流水 → 保持仓库级严格校验，避免 A 仓掩护 B 仓（BUG-2026-08-16-009）。

测试用例：
  T1. 单张反提交：历史 NULL location 流水 + 多仓库 → 反提交成功、状态回退 pending、可删除
  T2. 批量反提交：历史 NULL location 流水 + 多仓库 → reverted == 1、状态回退 pending
  T3. 兜底守卫：存在可归属流水在 A 仓时，B 仓入库单批量反提交仍被拒绝（防 A 掩护 B）
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
    InOrder, InOrderItem, Material, MaterialCategory, StockTransaction, Supplier,
    Unit, User, Warehouse, add_stock, db, set_system_setting,
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


def _legacy_unattributed_stock(mat, qty):
    """模拟历史遗留数据：Material.stock 有库存，但流水 location 为 NULL。"""
    mat.stock = qty
    db.session.add(StockTransaction(
        material_id=mat.id, transaction_type="in", quantity=qty,
        location=None,  # 老数据没有 location，无法按仓库聚合
        reference_type="in_order", reference_id=999,
    ))
    db.session.commit()


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


class TestRevertLegacyUnattributedStock:

    def test_t1_single_revert_legacy_unattributed_then_delete(self, client):
        """T1：历史 NULL location 流水，单张反提交成功并回退 pending，之后可删除。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed()
            mat = Material.query.filter_by(code="M001").first()
            _legacy_unattributed_stock(mat, 50)
            tid = _make_completed_in_order("IN-002-T1", "仓库A", 50)

        r1 = client.post(f"/in_order/{tid}/revert")
        d1 = r1.get_json()
        assert d1["status"] == "success", d1
        with app_module.app.app_context():
            assert db.session.get(InOrder, tid).status == "pending"

        r2 = client.post(f"/in_order/{tid}/delete")
        d2 = r2.get_json()
        assert d2["status"] == "success", d2

    def test_t2_batch_revert_legacy_unattributed(self, client):
        """T2：历史 NULL location 流水，批量反提交成功（reverted == 1）。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed()
            mat = Material.query.filter_by(code="M001").first()
            _legacy_unattributed_stock(mat, 50)
            tid = _make_completed_in_order("IN-002-T2", "仓库A", 50)

        resp = client.post("/in_order/batch_revert", json={"ids": [tid]})
        data = resp.get_json()
        assert resp.status_code == 200, data
        assert data.get("reverted") == 1, data
        with app_module.app.app_context():
            assert db.session.get(InOrder, tid).status == "pending"

    def test_t3_attributed_stock_elsewhere_still_rejected(self, client):
        """T3：存在可归属流水（A 仓）时，B 仓入库单批量反提交仍被拒绝，防 A 掩护 B。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed()
            mat = Material.query.filter_by(code="M001").first()
            wh_a = Warehouse.query.filter_by(code="WHA").first()
            ok, _ = add_stock(mat, 50, 'in', 'in_order', 1, warehouse=wh_a)
            assert ok
            db.session.commit()
            tid = _make_completed_in_order("IN-002-T3", "仓库B", 10)

        resp = client.post("/in_order/batch_revert", json={"ids": [tid]})
        data = resp.get_json()
        assert resp.status_code == 200, data
        assert data.get("reverted") == 0, data
        assert "库存不足" in (data.get("msg") or ""), data
        with app_module.app.app_context():
            assert db.session.get(InOrder, tid).status == "completed"
