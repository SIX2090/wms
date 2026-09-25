# -*- coding: utf-8 -*-
"""P1-7③ 下半：期初建账 _apply_opening_stock_balance 收敛后的落库口径钉子。

这块**不能**无脑换成 apply_opening_balance，因为旧实现有三处"不整齐"的口径，
收敛时必须逐条对齐，否则落库值就变了：

  1. 流水 location 恒为 **warehouse.name**；而库位账用的是 **location or warehouse.name**
     ——两处本就不一致（明细行填了库位时，流水记仓库名、库位账记明细行库位）。
  2. warehouse 为 None 时流水 location 还要回退 **opening.warehouse.name**，
     且库位账**根本不写**（旧条件 `and warehouse`）。
  3. 调减且老库位账缺行时，要先按**旧期初数量补基线**（legacy 回填）再扣差额，
     使最终行值 == new_quantity。

本文件把这些"不整齐"全部钉成显式断言：以后谁想"顺手整理整齐"，测试会先红。

测试用例：
  T1. 新建期初行（关库位）：① += qty，③ 一条 opening +qty，location/warehouse_id/reference 正确
  T2. 改小（10 → 4）：① 随 delta 变，③ 追加 -6，累计 Σ③ == 4
  T3. 开库位 + 明细行库位：② 记在明细行库位，③ location 仍是仓库名（口径不一致处）
  T4. 开库位 + 调减 + 老库位账缺行：legacy 回填生效，② 最终 == new_quantity
  T5. warehouse=None：③ location 回退 opening.warehouse.name，② 不写
  T6. 差额小于 STOCK_COMPARE_EPSILON：一笔账都不写

跨 context 只传 id（ORM 实例出了 app_context 会 detached，必须重新按 id 查）。
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

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    LocationInventory, Material, MaterialCategory, OpeningStock,
    StockTransaction, Unit, Warehouse, db, set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

TOL = 0.01
EPS = 1e-6


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed(location_on: bool, initial_stock: float = 0):
    """在同一个 request context 里建库 + 建物料，返回 (material_id,)。"""
    with app_module.app.test_request_context():
        _reset_db()
        set_system_setting("location_management_enabled", "1" if location_on else "0")
        db.session.add_all([
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
        ])
        db.session.commit()
        mat = Material(code="M-OS", name="期初料", spec="S",
                       category_id=1, unit_id=1, stock=initial_stock, price=5)
        db.session.add(mat)
        db.session.commit()
        return mat.id


def _apply(mid, new_quantity, *, warehouse_code=None, location='', opening_id=None):
    """调期初建账（需要在 request context 里：operator_id 读 current_user）。"""
    with app_module.app.test_request_context():
        fn = getattr(app_module, '_apply_opening_stock_balance')
        mat = Material.query.get(mid)
        wh = Warehouse.query.filter_by(code=warehouse_code).first() if warehouse_code else None
        opening = OpeningStock.query.get(opening_id) if opening_id else None
        opening, delta = fn(
            opening, mat, new_quantity, 5, new_quantity * 5, '期初建账',
            warehouse=wh, doc_date=datetime.date.today(), location=location)
        db.session.commit()
        return (opening.id if opening else None), delta


def _ledger(mid):
    with app_module.app.app_context():
        return float(Material.query.get(mid).stock or 0)


def _txn_sum(mid):
    with app_module.app.app_context():
        rows = StockTransaction.query.filter_by(material_id=mid).all()
        return float(sum((r.quantity or 0) for r in rows))


def _txn_rows(mid):
    with app_module.app.app_context():
        return StockTransaction.query.filter_by(material_id=mid).order_by(
            StockTransaction.id).all()


def _loc_rows(mid):
    with app_module.app.app_context():
        return LocationInventory.query.filter_by(material_id=mid).all()


def _loc_sum(mid):
    return float(sum((r.quantity or 0) for r in _loc_rows(mid)))


def _wh_id(code="WHA"):
    with app_module.app.app_context():
        return Warehouse.query.filter_by(code=code).first().id


def _clear_txn_and_loc(mid):
    with app_module.app.app_context():
        StockTransaction.query.filter_by(material_id=mid).delete()
        LocationInventory.query.filter_by(material_id=mid).delete()
        db.session.commit()


def _clear_loc(mid):
    with app_module.app.app_context():
        LocationInventory.query.filter_by(material_id=mid).delete()
        db.session.commit()


# ────────────────────────── T1~T6 ──────────────────────────

class TestOpeningStockBalanceConverged:

    def test_new_opening_line_writes_transaction_with_warehouse_name(self):
        """T1（关库位）：① += qty，③ 一条 opening +qty，落库字段与原实现一致。"""
        mid = _seed(location_on=False, initial_stock=2)
        opening_id, delta = _apply(mid, 10, warehouse_code="WHA")
        assert abs(delta - 10) <= TOL
        assert abs(_ledger(mid) - 12) <= TOL, _ledger(mid)   # 2 + 10
        rows = _txn_rows(mid)
        assert len(rows) == 1
        row = rows[0]
        assert row.transaction_type == 'opening'
        assert abs((row.quantity or 0) - 10) <= TOL
        # 关键口径：流水 location 恒为仓库名
        assert row.location == '仓库A', row.location
        assert row.warehouse_id == _wh_id()
        assert row.reference_type == 'opening_stock'
        assert row.reference_id == opening_id
        # 关库位：不写库位账
        assert _loc_rows(mid) == []

    def test_reduce_opening_line_appends_negative_delta(self):
        """T2：10 → 4，① 随 delta 变，Σ③ == 4（两条流水 +10 / -6）。"""
        mid = _seed(location_on=False, initial_stock=2)
        opening_id, _ = _apply(mid, 10, warehouse_code="WHA")
        opening_id, delta = _apply(mid, 4, warehouse_code="WHA", opening_id=opening_id)
        assert abs(delta - (-6)) <= TOL
        assert abs(_ledger(mid) - 6) <= TOL, _ledger(mid)    # 2 + 10 - 6
        assert abs(_txn_sum(mid) - 4) <= TOL, _txn_sum(mid)

    def test_location_ledger_uses_row_location_while_txn_uses_warehouse(self):
        """T3：把"两处口径不一致"钉死——②记明细行库位，③location 仍是仓库名。"""
        mid = _seed(location_on=True)
        opening_id, _ = _apply(mid, 10, warehouse_code="WHA", location='LOC-1')
        rows = _loc_rows(mid)
        assert len(rows) == 1
        assert rows[0].location == 'LOC-1', rows[0].location      # ② 用明细行库位
        assert abs(rows[0].quantity - 10) <= TOL
        txn = _txn_rows(mid)[0]
        assert txn.location == '仓库A', txn.location               # ③ 用仓库名

    def test_legacy_backfill_then_reduce_matches_new_quantity(self):
        """T4：调减且老库位账缺行 → 先补基线再扣差额，② 最终 == new_quantity。"""
        mid = _seed(location_on=True)
        opening_id, _ = _apply(mid, 10, warehouse_code="WHA")
        assert abs(_loc_sum(mid) - 10) <= TOL, _loc_sum(mid)
        _clear_loc(mid)   # 模拟老库：库位账缺行
        opening_id, delta = _apply(mid, 4, warehouse_code="WHA", opening_id=opening_id)
        assert abs(delta - (-6)) <= TOL
        # 补基线 10 再扣 6 == new_quantity 4（不补基线就会变成 -6 或失败）
        assert abs(_loc_sum(mid) - 4) <= TOL, _loc_sum(mid)
        assert abs(_ledger(mid) - 4) <= TOL, _ledger(mid)

    def test_warehouse_none_falls_back_to_opening_warehouse_and_skips_location(self):
        """T5：warehouse=None → ③location 回退 opening.warehouse.name，② 不写。"""
        mid = _seed(location_on=True)
        opening_id, _ = _apply(mid, 10, warehouse_code="WHA")
        _clear_txn_and_loc(mid)
        # 第二次不传 warehouse：回退 opening.warehouse
        opening_id, delta = _apply(mid, 13, opening_id=opening_id)
        assert abs(delta - 3) <= TOL
        rows = _txn_rows(mid)
        assert len(rows) == 1
        assert rows[0].location == '仓库A', rows[0].location    # 回退 opening.warehouse.name
        assert rows[0].warehouse_id == _wh_id()
        # 旧实现 warehouse 为 None 时不写库位账，收敛后必须保持
        assert _loc_rows(mid) == []

    def test_delta_below_epsilon_writes_nothing(self):
        """T6：差额小于 STOCK_COMPARE_EPSILON（1e-6）时一笔账都不写。"""
        mid = _seed(location_on=True)
        opening_id, _ = _apply(mid, 10, warehouse_code="WHA")
        count_before = len(_txn_rows(mid))
        opening_id, delta = _apply(mid, 10 + (EPS / 10), warehouse_code="WHA",
                                   opening_id=opening_id)
        assert abs(delta) <= EPS
        assert len(_txn_rows(mid)) == count_before
        assert abs(_loc_sum(mid) - 10) <= TOL, _loc_sum(mid)
