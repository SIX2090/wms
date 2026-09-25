# -*- coding: utf-8 -*-
"""P1-7 前置判据：transfer / requisition / material 三条「绕过 apply_stock_delta」
路径的三账（①总账 / ②库位账 / ③流水账）行为基线。

审计结论 1.2（WMS代码审计结论_20260925.md）：
    | 调拨 transfer            | ❌ 完全绕过 | transfer.py:526-554 / 605-628 |
    | 领料 requisition         | ❌ 完全绕过 | requisition.py:561-575 / 616-630 |
    | 物料初始库存 material    | ❌ 绕过且零测试 | material.py:239 / 275 |

在动手术（把它们收敛到 apply_stock_delta）之前必须先把**当前行为钉死**，
否则重构一旦改变了账的走向没人能发现。本文件就是这颗钉子：

恒等式（INVENTORY_TRUTH.md §1）：① material.stock = Σ② = Σ③
    - ② 仅在开启库位管理时参与校验（未开启时 location_inventory 为空属预期，
      与 scripts/verify_inventory_identity.py 的 no_location_rows 口径一致）。

各路径当前（收敛前）的真实语义，本文件逐条固化：
    - **调拨**：物料没离开公司，①**不动**；③ 写一对 transfer_out(-q) /
      transfer_in(+q)；② 在开启库位时 from 减、to 加。故调拨后 Σ③ 净增 0。
    - **领料**：物料离开仓库，① 减 q；③ 记 -q；② 同步减。
    - **物料初始库存**：① = initial_stock；③ 记一条 'opening' +q；
      ② 在开启库位时 +q。

测试用例：
  T1. 调拨完成（关库位）：① 不变、Σ③ = 0、留下两条异号流水
  T2. 调拨完成（开库位）：② from 减 to 加、Σ② = 0，且 ① 仍不变
  T3. 调拨反提交（关库位）：账回到调拨前
  T4. 领料完成（关库位）：① = -q、Σ③ = -q，① == Σ③
  T5. 领料完成（开库位）：② 同步 -q，① == Σ② == Σ③
  T6. 领料撤销：账回到领料前
  T7. 物料初始库存：① == Σ③ == initial（开库位时 Σ② 也相等）
"""
from __future__ import annotations

import datetime
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
    LocationInventory, Material, MaterialCategory, StockTransaction, Unit,
    User, Warehouse, db, generate_order_no, set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

TOL = 0.01


# ────────────────────────── 夹具 ──────────────────────────

def _reset_db():
    db.drop_all()
    db.create_all()


def _login(client):
    client.post("/login",
                data={"username": "p17", "password": "admin"},
                content_type="application/x-www-form-urlencoded")


def _seed(location_on: bool):
    set_system_setting("location_management_enabled", "1" if location_on else "0")
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
        Warehouse(code="WHB", name="仓库B", status="active"),
        User(username="p17", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False),
    ])
    db.session.commit()
    mat = Material(code="M-P17", name="基线料", spec="S",
                   category_id=1, unit_id=1, stock=0, price=10)
    db.session.add(mat)
    db.session.commit()
    return mat


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
    c = app_module.app.test_client()
    yield c


# ────────────────────────── 三账读数 ──────────────────────────

def _ledger(mat_id):
    """① 总账。"""
    with app_module.app.app_context():
        return float(Material.query.get(mat_id).stock or 0)


def _txn_sum(mat_id):
    """③ 流水账合计。"""
    with app_module.app.app_context():
        rows = StockTransaction.query.filter_by(material_id=mat_id).all()
        return float(sum((r.quantity or 0) for r in rows))


def _loc_sum(mat_id):
    """② 库位账合计。"""
    with app_module.app.app_context():
        rows = LocationInventory.query.filter_by(material_id=mat_id).all()
        return float(sum((r.quantity or 0) for r in rows))


def _txn_types(mat_id):
    with app_module.app.app_context():
        rows = StockTransaction.query.filter_by(material_id=mat_id).all()
        return sorted(r.transaction_type for r in rows)


def _assert_identity(mat_id, *, location_on):
    """恒等式：① == Σ③；开启库位管理时还要求 ① == Σ②。"""
    one, three = _ledger(mat_id), _txn_sum(mat_id)
    assert abs(one - three) <= TOL, f"①({one}) != Σ③({three})"
    if location_on:
        two = _loc_sum(mat_id)
        assert abs(one - two) <= TOL, f"①({one}) != Σ②({two})"


# ────────────────────────── 单据构造 ──────────────────────────

def _make_transfer(client, from_wh, to_wh, qty, *, from_loc=None, to_loc=None):
    with app_module.app.test_request_context():
        transfer_no = generate_order_no("TF")
    payload = {
        "order_no": transfer_no,
        "header": {"from_warehouse": from_wh, "to_warehouse": to_wh},
        "items": [{"code": "M-P17", "quantity": qty, "unit_id": 1}],
    }
    if from_loc or to_loc:
        payload["header"]["from_location"] = from_loc or ""
        payload["header"]["to_location"] = to_loc or ""
    resp = client.post("/transfer/save_table", json=payload)
    data = resp.get_json()
    assert data.get("status") == "success", data
    return data.get("id") or data.get("order_id")


def _make_requisition(client, warehouse, qty, *, location=None):
    with app_module.app.test_request_context():
        from app import ProductionRequisition
        req = ProductionRequisition(
            req_no=generate_order_no("REQ"), date=datetime.date.today(),
            warehouse=warehouse, location=location or "", status="pending")
        db.session.add(req)
        db.session.commit()
        rid = req.id
    # /requisition/<id>/update 只改表头；明细必须走 /requisition/<id>/item/add
    resp = client.post(f"/requisition/{rid}/update", data={
        "date": datetime.date.today().isoformat(),
        "warehouse": warehouse,
        "location": location or "",
    }, content_type="application/x-www-form-urlencoded")
    body = resp.get_json()
    assert body.get("status") == "success", body
    resp = client.post(f"/requisition/{rid}/item/add", data={
        "material_code": "M-P17",
        "quantity": str(qty),
        "unit_id": "1",
    }, content_type="application/x-www-form-urlencoded")
    body = resp.get_json()
    assert body.get("status") == "success", body
    return rid


# ────────────────────────── T1~T3 调拨 ──────────────────────────

class TestTransferThreeLedgers:

    def test_complete_keeps_total_ledger_untouched(self, client):
        """T1（关库位）：物料没离开公司，①必须不变，③留一对异号流水。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(location_on=False)
            # 先给仓库A 灌 10 的库存，否则源仓库校验会拒绝
            from app import add_stock
            add_stock(mat, 10, transaction_type='opening', warehouse='仓库A')
            db.session.commit()
            mid = mat.id
        _login(client)
        tid = _make_transfer(client, "仓库A", "仓库B", 4)
        resp = client.post(f"/transfer/{tid}/complete")
        assert resp.get_json().get("status") == "success", resp.get_json()
        # ① 不变（仍为 10）
        assert abs(_ledger(mid) - 10) <= TOL, _ledger(mid)
        # ③ 净增 0，且确实写了 transfer_out / transfer_in 两条
        assert abs(_txn_sum(mid) - 10) <= TOL, _txn_sum(mid)
        assert _txn_types(mid) == ['opening', 'transfer_in', 'transfer_out'], _txn_types(mid)
        _assert_identity(mid, location_on=False)

    def test_complete_with_location_moves_location_ledger(self, client):
        """T2（开库位）：② from 减、to 加，Σ② 净 0；① 仍不变。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(location_on=True)
            from app import add_stock, update_location_inventory
            add_stock(mat, 10, transaction_type='opening', warehouse='仓库A')
            ok, _err = update_location_inventory(mat, '仓库A', 10, warehouse='仓库A')
            assert ok
            db.session.commit()
            mid = mat.id
        _login(client)
        tid = _make_transfer(client, "仓库A", "仓库B", 4,
                             from_loc="仓库A", to_loc="仓库B")
        resp = client.post(f"/transfer/{tid}/complete")
        body = resp.get_json()
        assert body.get("status") == "success", body
        assert abs(_ledger(mid) - 10) <= TOL, _ledger(mid)
        _assert_identity(mid, location_on=True)

    def test_revert_restores_ledgers(self, client):
        """T3（关库位）：反提交后 ③ 回到调拨前，① 全程不变。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(location_on=False)
            from app import add_stock
            add_stock(mat, 10, transaction_type='opening', warehouse='仓库A')
            db.session.commit()
            mid = mat.id
        _login(client)
        tid = _make_transfer(client, "仓库A", "仓库B", 4)
        assert client.post(f"/transfer/{tid}/complete").get_json().get("status") == "success"
        before_ledger, before_txn = _ledger(mid), _txn_sum(mid)
        resp = client.post(f"/transfer/{tid}/revert")
        assert resp.get_json().get("status") == "success", resp.get_json()
        assert abs(_ledger(mid) - before_ledger) <= TOL
        assert abs(_txn_sum(mid) - before_txn) <= TOL
        _assert_identity(mid, location_on=False)


# ────────────────────────── T4~T6 领料 ──────────────────────────

class TestRequisitionThreeLedgers:

    def test_complete_deducts_total_ledger(self, client):
        """T4（关库位）：领料出库，① = -q、③ = -q，且 ① == Σ③。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(location_on=False)
            from app import add_stock
            add_stock(mat, 10, transaction_type='opening', warehouse='仓库A')
            db.session.commit()
            mid = mat.id
        _login(client)
        rid = _make_requisition(client, "仓库A", 3)
        resp = client.post(f"/requisition/{rid}/complete")
        assert resp.get_json().get("status") == "success", resp.get_json()
        assert abs(_ledger(mid) - 7) <= TOL, _ledger(mid)
        assert abs(_txn_sum(mid) - 7) <= TOL, _txn_sum(mid)
        assert 'requisition' in _txn_types(mid), _txn_types(mid)
        _assert_identity(mid, location_on=False)

    def test_complete_with_location_deducts_location_ledger(self, client):
        """T5（开库位）：② 同步 -q，三账恒等。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(location_on=True)
            from app import add_stock, update_location_inventory
            add_stock(mat, 10, transaction_type='opening', warehouse='仓库A')
            ok, _err = update_location_inventory(mat, '仓库A', 10, warehouse='仓库A')
            assert ok
            db.session.commit()
            mid = mat.id
        _login(client)
        rid = _make_requisition(client, "仓库A", 3, location="仓库A")
        resp = client.post(f"/requisition/{rid}/complete")
        assert resp.get_json().get("status") == "success", resp.get_json()
        _assert_identity(mid, location_on=True)
        assert abs(_loc_sum(mid) - 7) <= TOL, _loc_sum(mid)

    def test_revert_restores_ledgers(self, client):
        """T6：撤销后三账回到领料前。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(location_on=False)
            from app import add_stock
            add_stock(mat, 10, transaction_type='opening', warehouse='仓库A')
            db.session.commit()
            mid = mat.id
        _login(client)
        rid = _make_requisition(client, "仓库A", 3)
        assert client.post(f"/requisition/{rid}/complete").get_json().get("status") == "success"
        assert abs(_ledger(mid) - 7) <= TOL
        resp = client.post(f"/requisition/{rid}/revert")
        assert resp.get_json().get("status") == "success", resp.get_json()
        assert abs(_ledger(mid) - 10) <= TOL, _ledger(mid)
        assert abs(_txn_sum(mid) - 10) <= TOL, _txn_sum(mid)
        _assert_identity(mid, location_on=False)


# ────────────────────────── T7 物料初始库存 ──────────────────────────

class TestMaterialInitialStockThreeLedgers:

    def test_initial_stock_writes_opening_transaction(self, client):
        """T7（关库位）：新增物料带初始库存 → ① == Σ③ == initial。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed(location_on=False)
        _login(client)
        resp = client.post("/material/add", data={
            "code": "M-INIT", "name": "初始库存料", "spec": "S",
            "category_id": "1", "unit_id": "1",
            # 表单字段名是 stock（material.py:239），不是 initial_stock
            "stock": "25", "price": "5",
        }, content_type="application/x-www-form-urlencoded")
        body = resp.get_json()
        assert body.get("status") == "success", (resp.status_code, body)
        with app_module.app.app_context():
            mat = Material.query.filter_by(code="M-INIT").one()
            mid = mat.id
        assert abs(_ledger(mid) - 25) <= TOL, _ledger(mid)
        assert abs(_txn_sum(mid) - 25) <= TOL, _txn_sum(mid)
        assert 'opening' in _txn_types(mid), _txn_types(mid)
        _assert_identity(mid, location_on=False)
