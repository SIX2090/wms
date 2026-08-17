# -*- coding: utf-8 -*-
"""BUG-2026-08-17-002 回归：反提交/删明细的仓库级库存校验在解析不到仓库时
回退全局口径。

根因：BUG-2026-08-16-009 将 revert_in_order/update_completed_in_order 的库存
充足校验改为仓库级口径（get_warehouse_stock_quantities）。但老数据入库单
warehouse 为空、或仓库名解析不到 Warehouse 记录时，wh_obj=None 导致
warehouse_stock={}，所有物料 current_stock 恒为 0，即使全局 Material.stock
充足也报“库存不足，不能反提交”，单据卡在 completed 无法反提交。而实际回退
(deduct_stock/batch_revert_in_order) 用的是全局 Material.stock，校验口径与
回退口径不一致。

修复：wh_obj 解析失败时回退全局 Material.stock 口径；有仓库时仍走 009 的
仓库级口径（保留多仓库 A 仓不能掩护 B 仓的保护）。

测试用例：
  T1. warehouse 为空（老数据）+ 全局库存充足 → 反提交成功
  T2. 仓库可解析但该仓库存不足（全局充足）→ 仍被拒（009 保护不破坏）
  T3. warehouse 为空 + 全局库存不足 → 被拒
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
    # 关闭库位管理（OFF 分支为 BUG 场景所在）
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
    """直接建一张已完成入库单（warehouse 可为 None 模拟老数据）+ 明细。"""
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
    return order


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
        _seed()
    c = app_module.app.test_client()
    _login(c)
    yield c


class TestRevertInOrderWithoutWarehouse:

    def test_revert_succeeds_when_no_warehouse_and_global_sufficient(self, client):
        """T1：老数据 warehouse 为空 + 全局库存充足 → 反提交成功。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed()
            mat = Material.query.filter_by(code="M001").first()
            ok, _ = add_stock(mat, 100, 'in', 'in_order', 1, warehouse=None)
            assert ok
            db.session.commit()
            order = _make_completed_in_order("IN-NOWH", None, 10)
            tid = order.id
        resp = client.post(f"/in_order/{tid}/revert")
        data = resp.get_json()
        assert data.get("status") == "success", data
        with app_module.app.app_context():
            assert db.session.get(InOrder, tid).status == "pending"
            mat = Material.query.filter_by(code="M001").first()
            assert abs((mat.stock or 0) - 90) < 1e-6, mat.stock

    def test_revert_rejected_when_warehouse_resolvable_but_insufficient(self, client):
        """T2：仓库可解析但该仓库存不足（全局充足）→ 仍被拒，009 保护不破坏。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed()
            mat = Material.query.filter_by(code="M001").first()
            wh_a = Warehouse.query.filter_by(code="WHA").first()
            # 全局库存全在 A 仓（B 仓 0），单在 B 仓
            ok, _ = add_stock(mat, 100, 'in', 'in_order', 1, warehouse=wh_a)
            assert ok
            db.session.commit()
            order = _make_completed_in_order("IN-B-GUARD", "仓库B", 10)
            tid = order.id
        resp = client.post(f"/in_order/{tid}/revert")
        data = resp.get_json()
        assert data.get("status") == "error", data
        assert "库存不足" in (data.get("msg") or ""), data
        with app_module.app.app_context():
            assert db.session.get(InOrder, tid).status == "completed"

    def test_revert_rejected_when_no_warehouse_and_global_insufficient(self, client):
        """T3：warehouse 为空 + 全局库存不足 → 被拒。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed()
            mat = Material.query.filter_by(code="M001").first()
            ok, _ = add_stock(mat, 5, 'in', 'in_order', 1, warehouse=None)
            assert ok
            db.session.commit()
            order = _make_completed_in_order("IN-NOWH-LOW", None, 10)
            tid = order.id
        resp = client.post(f"/in_order/{tid}/revert")
        data = resp.get_json()
        assert data.get("status") == "error", data
        assert "库存不足" in (data.get("msg") or ""), data
        with app_module.app.app_context():
            assert db.session.get(InOrder, tid).status == "completed"
