# -*- coding: utf-8 -*-
"""BUG-2026-09-07-005 回归：仓库月报出入库金额按来源单据实际单价。

背景：月报此前一律「数量 × 物料当前单价」估算金额（代码自述"金额按物料
当前单价估算"），历史月份单价变动后 in_amount/out_amount 失真。
修复：流水按 reference 反查来源单据明细加权单价（sum(amount)/sum(quantity)）
累计金额；无单据价的类型（transfer/adjustment/check/requisition 等）用
物料当前价兜底；期末库存金额仍按当前价估值。

断言：
  T1. 入库金额按入库单实际价（10）而非物料当前价（99）。
  T2. 出库金额按出库单实际价（15）。
  T3. 售后出库金额按售后单实际价（20）。
  T4. 无单据价流水（adjustment_in）按物料当前价兜底。
  T5. 期末库存金额仍按当前价估值；remark 说明新口径。
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import (AfterSaleOutOrder, AfterSaleOutOrderItem, InOrder, InOrderItem,  # noqa: E402
                 Material, OutOrder, OutOrderItem, StockTransaction, Unit, User,
                 Warehouse, db)

app_module.app.config["TESTING"] = True


def _filters(**overrides):
    base = {
        'start_date': None, 'end_date': None,
        'warehouse_id': 0, 'warehouse': '', 'warehouse_code': '',
        'business_type': '', 'material_code': '',
        'supplier_id': 0, 'supplier': '', 'customer': '', 'status': '',
        'sort_field': '', 'sort_order': 'asc',
        'page': 1, 'page_size': 20, 'hide_zero': False, 'export': '',
    }
    base.update(overrides)
    return base


class TestBug20260907005:
    def setup_method(self):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            from werkzeug.security import generate_password_hash
            wh = Warehouse(code="WHM", name="主仓", is_default=True, status="active")
            unit = Unit(code="PCS", name="个")
            user = User(username="admin",
                        password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False)
            db.session.add_all([wh, unit, user])
            db.session.flush()
            # 物料当前价 99；库存净额 = 5+3-2-1 = 5
            mat = Material(code="M001", name="电缆", unit_id=unit.id,
                           price=99.0, stock=5.0)
            db.session.add(mat)
            db.session.flush()
            self.wh_id, self.mat_id = wh.id, mat.id
            today = date.today()
            now = datetime.combine(today, datetime.min.time())

            # 入库单：实际价 10 × 5
            io = InOrder(order_no="IN-1", date=today, warehouse="主仓",
                         status="completed", operator_id=user.id, business_type="采购入库")
            db.session.add(io)
            db.session.flush()
            db.session.add(InOrderItem(in_order_id=io.id, material_id=mat.id,
                                       quantity=5, price=10.0, amount=50.0))
            db.session.add(StockTransaction(
                material_id=mat.id, transaction_type='in', quantity=5,
                location='主仓', warehouse_id=wh.id,
                reference_type='in_order', reference_id=io.id, created_at=now))
            # 出库单：实际价 15 × 2
            oo = OutOrder(order_no="OUT-1", date=today, warehouse="主仓",
                          status="completed", operator_id=user.id)
            db.session.add(oo)
            db.session.flush()
            db.session.add(OutOrderItem(out_order_id=oo.id, material_id=mat.id,
                                        quantity=2, price=15.0, amount=30.0))
            db.session.add(StockTransaction(
                material_id=mat.id, transaction_type='out', quantity=-2,
                location='主仓', warehouse_id=wh.id,
                reference_type='out_order', reference_id=oo.id, created_at=now))
            # 售后出库单：实际价 20 × 1
            so = AfterSaleOutOrder(order_no="AS-1", date=today, warehouse="主仓",
                                   status="completed", operator_id=user.id)
            db.session.add(so)
            db.session.flush()
            db.session.add(AfterSaleOutOrderItem(after_sale_out_order_id=so.id,
                                                 material_id=mat.id, quantity=1,
                                                 price=20.0, amount=20.0))
            db.session.add(StockTransaction(
                material_id=mat.id, transaction_type='after_sale_out', quantity=-1,
                location='主仓', warehouse_id=wh.id,
                reference_type='after_sale_out_order', reference_id=so.id,
                created_at=now))
            # 无单据价流水：调整入库 +3（兜底当前价 99）
            db.session.add(StockTransaction(
                material_id=mat.id, transaction_type='adjustment_in', quantity=3,
                location='主仓', warehouse_id=wh.id,
                reference_type='adjustment', reference_id=999, created_at=now))
            db.session.commit()

    def _monthly_row(self):
        cols, rows, summary = app_module._build_warehouse_monthly_report(_filters(
            warehouse_id=self.wh_id, warehouse="主仓", warehouse_code="WHM"))
        assert len(rows) == 1, f"当月单物料应 1 行，实际 {len(rows)}"
        return rows[0], summary

    def test_T1_in_amount_uses_order_price(self):
        """入库金额 = 5×10(单据价) + 3×99(调整兜底) = 347，而非 8×99=792。"""
        with app_module.app.app_context():
            row, _ = self._monthly_row()
            assert row['in_quantity'] == 8, f"入库数量应 8，实际 {row['in_quantity']}"
            assert row['in_amount'] == 347.0, f"入库金额应按实际价 347，实际 {row['in_amount']}"

    def test_T2_out_amount_uses_order_price(self):
        """出库金额 = 2×15 = 30。"""
        with app_module.app.app_context():
            row, _ = self._monthly_row()
            assert row['out_quantity'] == 3
            # 2×15(出库单) + 1×20(售后单) = 50
            assert row['out_amount'] == 50.0, f"出库金额应按实际价 50，实际 {row['out_amount']}"

    def test_T3_after_sale_uses_order_price(self):
        """售后出库单价解析：单独验证 price map 命中 after_sale_out_order。"""
        with app_module.app.app_context():
            txns = StockTransaction.query.filter_by(transaction_type='after_sale_out').all()
            prices = app_module._monthly_txn_price_map(txns)
            assert prices.get(txns[0].id) == 20.0, f"售后单价应解析为 20，实际 {prices}"

    def test_T4_adjustment_fallback_to_current_price(self):
        """无单据价流水不进 price map，由调用方用当前价 99 兜底。"""
        with app_module.app.app_context():
            txns = StockTransaction.query.filter_by(transaction_type='adjustment_in').all()
            prices = app_module._monthly_txn_price_map(txns)
            assert txns[0].id not in prices, "调整流水不应有单据价"
            row, _ = self._monthly_row()
            # 调整入库 3×99=297 已含在 in_amount=347（=50+297）中，T1 已覆盖
            assert row['in_amount'] == 347.0

    def test_T5_inventory_amount_still_current_price(self):
        """期末库存金额 = 期末结存 5 × 当前价 99 = 495；remark 说明新口径。"""
        with app_module.app.app_context():
            row, _ = self._monthly_row()
            assert row['ending_quantity'] == 5, f"期末结存应 5，实际 {row['ending_quantity']}"
            assert row['inventory_amount'] == 495.0, f"期末估值应 495，实际 {row['inventory_amount']}"
            assert '实际单价' in row['remark'], "remark 必须说明出入库金额按实际单价"
