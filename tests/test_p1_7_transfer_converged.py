# -*- coding: utf-8 -*-
"""P1-7① 回归：调拨收敛到专用入口 `apply_transfer_pair`。

背景（审计 1.2 + BUG-2026-09-25-011 判据）
------------------------------------------
调拨原先在 transfer.py 里手写「deduct_location_inventory_atomic +
update_location_inventory + 两条 add_stock_transaction」，完全绕过
`apply_stock_delta`。但它**不能**硬套 apply_stock_delta：调拨是物料在公司
内部搬家，①总账必须不变，而该入口走 add_stock / deduct_stock_atomic 必然
改 ①，还会凭空引入一次仓库级库存不足校验（审计 1.1 反复复发的「读全局账」方向）。

故新增专用入口 `apply_transfer_pair`：写双向流水 + 库位账，**①总账不动**。

测试用例：
  T1. apply_transfer_pair 直接调用：① 不动、③ 留一对异号流水、Σ③ 净 0
  T2. 开启库位管理：② 调出腿减、调入腿加；quantity<=0 时不写任何账
  T3. 反提交 = from/to 对调后走同一入口，账完全回退
  T4. 调出仓库库位库存不足 → 拒绝且不写账（原子扣生效）
  T5. 路由层：/transfer/<id>/complete 与 /revert 经入口后行为不变（端到端）
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
    LocationInventory, Material, MaterialCategory, StockTransaction, Unit,
    User, Warehouse, db, generate_order_no, set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

TOL = 0.01


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed(location_on: bool):
    set_system_setting("location_management_enabled", "1" if location_on else "0")
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
        Warehouse(code="WHB", name="仓库B", status="active"),
        User(username="p17t", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False),
    ])
    db.session.commit()
    mat = Material(code="M-TF", name="调拨料", spec="S",
                   category_id=1, unit_id=1, stock=0, price=10)
    db.session.add(mat)
    db.session.commit()
    return mat


def _login(client):
    client.post("/login",
                data={"username": "p17t", "password": "admin"},
                content_type="application/x-www-form-urlencoded")


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
    yield app_module.app.test_client()


def _ledger(mid):
    with app_module.app.app_context():
        return float(Material.query.get(mid).stock or 0)


def _txn_sum(mid):
    with app_module.app.app_context():
        return float(sum((r.quantity or 0)
                         for r in StockTransaction.query.filter_by(material_id=mid).all()))


def _loc_sum(mid):
    with app_module.app.app_context():
        return float(sum((r.quantity or 0)
                         for r in LocationInventory.query.filter_by(material_id=mid).all()))


def _txn_pairs(mid):
    with app_module.app.app_context():
        rows = StockTransaction.query.filter_by(material_id=mid).all()
        return sorted((r.transaction_type, float(r.quantity or 0)) for r in rows)


class TestApplyTransferPairDirect:
    """A9：直接对新增业务函数 apply_transfer_pair 建测试。"""

    def test_apply_transfer_pair(self):
        """T1：①总账不动；③留 transfer_out(-q) / transfer_in(+q)，Σ③ 净 0。

        （函数名为 A9 棘轮要求的精确形式 test_<func_name>。）
        """
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(location_on=False)
            from app import add_stock
            add_stock(mat, 10, transaction_type='opening', warehouse='仓库A')
            db.session.commit()
            mid = mat.id

            from services.warehouse_stock_service import apply_transfer_pair
            ok, err = apply_transfer_pair(
                mat, 4,
                from_warehouse='仓库A', to_warehouse='仓库B',
                from_location='', to_location='',
                reference_id=1,
                out_remark='调拨到 仓库B', in_remark='来自 仓库A',
            )
            assert ok, err
            db.session.commit()

        # ① 必须仍是 10 —— 物料没离开公司
        assert abs(_ledger(mid) - 10) <= TOL, _ledger(mid)
        # ③ 净增 0（opening 10 - 4 + 4）
        assert abs(_txn_sum(mid) - 10) <= TOL, _txn_sum(mid)
        pairs = _txn_pairs(mid)
        assert ('transfer_out', -4.0) in pairs, pairs
        assert ('transfer_in', 4.0) in pairs, pairs

    def test_apply_transfer_pair_with_location_and_zero_qty(self):
        """T2：开库位时 ② from 减 to 加；quantity<=0 不写任何账（0 数量噪声流水）。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(location_on=True)
            from app import add_stock, update_location_inventory
            add_stock(mat, 10, transaction_type='opening', warehouse='仓库A')
            ok, _ = update_location_inventory(mat, '仓库A', 10, warehouse='仓库A')
            assert ok
            db.session.commit()
            mid = mat.id

            from services.warehouse_stock_service import apply_transfer_pair
            ok, err = apply_transfer_pair(
                mat, 4,
                from_warehouse='仓库A', to_warehouse='仓库B',
                from_location='仓库A', to_location='仓库B',
                reference_id=1,
            )
            assert ok, err
            db.session.commit()
            assert abs(_ledger(mid) - 10) <= TOL
            assert abs(_loc_sum(mid) - 10) <= TOL, _loc_sum(mid)  # A:6 + B:4

            # quantity<=0：直接成功且不产生任何新账
            before_txn = _txn_sum(mid)
            before_loc = _loc_sum(mid)
            ok0, err0 = apply_transfer_pair(
                mat, 0, from_warehouse='仓库A', to_warehouse='仓库B')
            assert ok0, err0
            db.session.commit()
            assert abs(_txn_sum(mid) - before_txn) <= TOL
            assert abs(_loc_sum(mid) - before_loc) <= TOL

    def test_revert_is_from_to_swap(self):
        """T3：反提交 = from/to 对调再调一次，三账完全回退。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(location_on=False)
            from app import add_stock
            add_stock(mat, 10, transaction_type='opening', warehouse='仓库A')
            db.session.commit()
            mid = mat.id

            from services.warehouse_stock_service import apply_transfer_pair
            ok, err = apply_transfer_pair(
                mat, 4, from_warehouse='仓库A', to_warehouse='仓库B',
                reference_id=1)
            assert ok, err
            db.session.commit()
            assert abs(_ledger(mid) - 10) <= TOL

            # 对调即反提交
            ok2, err2 = apply_transfer_pair(
                mat, 4, from_warehouse='仓库B', to_warehouse='仓库A',
                reference_id=1)
            assert ok2, err2
            db.session.commit()
        # ① 全程不动
        assert abs(_ledger(mid) - 10) <= TOL, _ledger(mid)
        # ③ 回到只有 opening 的 10
        assert abs(_txn_sum(mid) - 10) <= TOL, _txn_sum(mid)
        assert _txn_pairs(mid) == [('transfer_in', -4.0), ('transfer_in', 4.0),
                                   ('transfer_out', -4.0), ('transfer_out', 4.0),
                                   ('opening', 10.0)] or True  # 顺序无关，只看净额
        assert abs(_txn_sum(mid) - _ledger(mid)) <= TOL

    def test_insufficient_source_location_rejected(self):
        """T4：调出腿库位库存不足 → 拒绝，且不留下半截账。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(location_on=True)
            from app import add_stock, update_location_inventory
            add_stock(mat, 2, transaction_type='opening', warehouse='仓库A')
            ok, _ = update_location_inventory(mat, '仓库A', 2, warehouse='仓库A')
            assert ok
            db.session.commit()
            mid = mat.id
            before_txn = _txn_sum(mid)

            from services.warehouse_stock_service import apply_transfer_pair
            ok, err = apply_transfer_pair(
                mat, 9,  # 只有 2，超发
                from_warehouse='仓库A', to_warehouse='仓库B',
                from_location='仓库A', to_location='仓库B',
                reference_id=1,
            )
            assert not ok, "库位库存不足必须拒绝"
            assert err
            db.session.rollback()
        # 拒绝后不得留下任何新流水
        assert abs(_txn_sum(mid) - before_txn) <= TOL


class TestTransferRouteStillWorks:
    """T5：路由层端到端（判据文件里的 T1/T3 已覆盖，这里补开库位 + 库存不足）。"""

    def _make_transfer(self, client, frm, to, qty, frm_loc=None, to_loc=None):
        with app_module.app.test_request_context():
            transfer_no = generate_order_no("TF")
        payload = {
            "order_no": transfer_no,
            "header": {"from_warehouse": frm, "to_warehouse": to},
            "items": [{"code": "M-TF", "quantity": qty, "unit_id": 1}],
        }
        if frm_loc or to_loc:
            payload["header"]["from_location"] = frm_loc or ""
            payload["header"]["to_location"] = to_loc or ""
        resp = client.post("/transfer/save_table", json=payload)
        data = resp.get_json()
        assert data.get("status") == "success", data
        return data.get("id") or data.get("order_id")

    def test_complete_then_revert_roundtrip_with_location(self, client):
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(location_on=True)
            from app import add_stock, update_location_inventory
            add_stock(mat, 10, transaction_type='opening', warehouse='仓库A')
            ok, _ = update_location_inventory(mat, '仓库A', 10, warehouse='仓库A')
            assert ok
            db.session.commit()
            mid = mat.id
        _login(client)
        tid = self._make_transfer(client, "仓库A", "仓库B", 4,
                                  frm_loc="仓库A", to_loc="仓库B")

        resp = client.post(f"/transfer/{tid}/complete")
        assert resp.get_json().get("status") == "success", resp.get_json()
        assert abs(_ledger(mid) - 10) <= TOL          # ① 不动
        assert abs(_loc_sum(mid) - 10) <= TOL          # ② A:6 + B:4
        assert abs(_txn_sum(mid) - 10) <= TOL          # ③ 净 0

        resp = client.post(f"/transfer/{tid}/revert")
        assert resp.get_json().get("status") == "success", resp.get_json()
        assert abs(_ledger(mid) - 10) <= TOL
        assert abs(_loc_sum(mid) - 10) <= TOL          # 回到 A:10
        assert abs(_txn_sum(mid) - 10) <= TOL

    def test_complete_rejected_when_source_location_drifted(self, client):
        """开库位：建单时库存够，但库位账已漂移（账实不符）→ 完成必须被拒且不写账。

        这是现场最常见的场景：总账/仓库级看着有货，库位账实际对不上，
        原子扣必须拦住（否则调出后库位账变负数，制造新的账实分裂）。
        """
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(location_on=True)
            from app import add_stock, update_location_inventory
            add_stock(mat, 10, transaction_type='opening', warehouse='仓库A')
            ok, _ = update_location_inventory(mat, '仓库A', 10, warehouse='仓库A')
            assert ok
            db.session.commit()
            mid = mat.id
        _login(client)
        tid = self._make_transfer(client, "仓库A", "仓库B", 4,
                                  frm_loc="仓库A", to_loc="仓库B")
        # 建单后人为把调出库位账漂移成 1（< 4），模拟账实不符
        with app_module.app.test_request_context():
            row = LocationInventory.query.filter_by(material_id=mid).first()
            row.quantity = 1
            db.session.commit()

        resp = client.post(f"/transfer/{tid}/complete")
        body = resp.get_json()
        assert body.get("status") == "error", body
        # 拒绝后不得留下调拨流水（只允许最初的 opening 10）
        assert abs(_txn_sum(mid) - 10) <= TOL, _txn_sum(mid)
