# -*- coding: utf-8 -*-
"""B 治本（BUG-2026-08-27-004 后续）：stock_transaction 增加 warehouse_id 外键。

根因：stock_transaction 无 warehouse_id 列，仓库归属全靠 location 字符串
（历史承载仓库名/编码、库位名、空值三种语义），仓库级报表靠字符串匹配
重建归属、口径分散（102/220 个历史 BUG 属此类）。B 步骤加外键列 + 迁移
回填 + 写入端统一，仓库过滤从此是精确匹配。

T1.  模型：建表后 stock_transaction 含 warehouse_id 列。
T2.  写入端 add_stock：带 warehouse 落 warehouse_id；不带则为 NULL。
T3.  写入端 deduct_stock_atomic：带 warehouse 落 warehouse_id。
T4.  写入端 add_stock_transaction：带 warehouse 落 warehouse_id；不带为 NULL。
T5.  写入端期初调整 _apply_opening_stock_balance：warehouse_id 正确落库。
T6.  回填-仓库名：location='仓库A' → warehouse_id=1。
T7.  回填-仓库编码：location='WHA' → warehouse_id=1。
T8.  回填-库位名：LocationInventory 唯一归属 → warehouse_id 跟随。
T9.  回填-空 location：按来源单据（入库单/调拨正负）推断。
T10. 回填-歧义不填：同名仓库/跨仓同名库位 → 保持 NULL，不猜。
T11. 回填-幂等：重复执行不重复处理。
"""
from __future__ import annotations

import os
import sys
from datetime import date
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
    db, InOrder, LocationInventory, Material, MaterialCategory, OpeningStock,
    StockTransaction, TransferOrder, Unit, Warehouse, add_stock,
    add_stock_transaction, backfill_stock_txn_warehouse_id,
    deduct_stock_atomic, set_system_setting, _apply_opening_stock_balance,
)
from sqlalchemy import text  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed(with_locations=False):
    set_system_setting("location_management_enabled", "1" if with_locations else "0")
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT"),
        Warehouse(id=1, code="WHA", name="仓库A", is_default=True, status="active"),
        Warehouse(id=2, code="WHB", name="仓库B", status="active"),
    ])
    db.session.commit()
    mat = Material(code="M001", name="轴承", spec="6204", category_id=1, unit_id=1, stock=0, price=10)
    db.session.add(mat)
    db.session.commit()
    return mat


def _txn_rows(mat=None):
    q = StockTransaction.query
    if mat is not None:
        q = q.filter(StockTransaction.material_id == mat.id)
    return q.order_by(StockTransaction.id.asc()).all()


def _mk_in_order(warehouse_name, no="IN-1"):
    o = InOrder(order_no=no, date=date.today(), warehouse=warehouse_name,
                status='completed', business_type='采购入库')
    db.session.add(o)
    db.session.commit()
    return o


class TestStockTxnWarehouseIdSchema:

    def test_column_exists(self):
        """T1：建表后 stock_transaction 含 warehouse_id 列。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed()
            cols = [row[1] for row in db.session.execute(
                text("PRAGMA table_info(stock_transaction)")).fetchall()]
            assert 'warehouse_id' in cols, \
                f"stock_transaction 缺 warehouse_id 列，实际: {cols}"


class TestStockTxnWarehouseIdWriters:

    def test_add_stock_writes_warehouse_id(self):
        """T2：add_stock 带 warehouse 落 warehouse_id；不带则为 NULL。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a = Warehouse.query.get(1)
            ok, _ = add_stock(mat, 10, transaction_type='in',
                              reference_type='in_order', reference_id=1,
                              warehouse=wh_a)
            assert ok
            ok2, _ = add_stock(mat, 5, transaction_type='in',
                               reference_type='in_order', reference_id=2,
                               warehouse=None)
            assert ok2
            rows = _txn_rows(mat)
            assert len(rows) == 2
            assert rows[0].warehouse_id == 1, \
                f"add_stock 带仓库应落 warehouse_id=1，实际 {rows[0].warehouse_id}"
            assert rows[1].warehouse_id is None, \
                f"add_stock 不带仓库应 NULL，实际 {rows[1].warehouse_id}"

    def test_deduct_stock_atomic_writes_warehouse_id(self):
        """T3：deduct_stock_atomic 带 warehouse 落 warehouse_id。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_b = Warehouse.query.get(2)
            # 先入 100 再扣 30，库存足够
            add_stock(mat, 100, transaction_type='in', warehouse=wh_b)
            ok, _, _ = deduct_stock_atomic(mat.id, 30, transaction_type='out',
                                           reference_type='out_order', reference_id=1,
                                           warehouse=wh_b)
            assert ok
            rows = _txn_rows(mat)
            out_row = next(r for r in rows if r.transaction_type == 'out')
            assert out_row.warehouse_id == 2, \
                f"deduct_stock_atomic 带仓库应落 warehouse_id=2，实际 {out_row.warehouse_id}"

    def test_add_stock_transaction(self):
        """A9 精确命名直测：基础行为——记录流水且不动总库存。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            add_stock_transaction(mat, 2, 'adjustment_in',
                                  reference_type='adjustment', reference_id=1)
            rows = _txn_rows(mat)
            assert len(rows) == 1 and rows[0].quantity == 2
            assert mat.stock == 0  # 该函数不改总库存

    def test_add_stock_transaction_writes_warehouse_id(self):
        """T4：add_stock_transaction 带 warehouse 落 warehouse_id；不带为 NULL。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a = Warehouse.query.get(1)
            add_stock_transaction(mat, 3, 'adjustment_in',
                                  reference_type='adjustment', reference_id=1,
                                  location='仓库A', warehouse=wh_a)
            add_stock_transaction(mat, -1, 'adjustment_out',
                                  reference_type='adjustment', reference_id=2,
                                  location=None)
            rows = _txn_rows(mat)
            assert len(rows) == 2
            assert rows[0].warehouse_id == 1, \
                f"add_stock_transaction 带仓库应落 warehouse_id=1，实际 {rows[0].warehouse_id}"
            assert rows[1].warehouse_id is None, \
                f"add_stock_transaction 不带仓库应 NULL，实际 {rows[1].warehouse_id}"

    def test_opening_stock_writes_warehouse_id(self):
        """T5：期初调整 _apply_opening_stock_balance 落 warehouse_id。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a = Warehouse.query.get(1)
            opening = OpeningStock(material_id=mat.id, warehouse_id=1, date=date.today(),
                                   location='仓库A', quantity=0, price=10, amount=0)
            db.session.add(opening)
            db.session.commit()
            _apply_opening_stock_balance(
                opening, mat, 50, 10, 500,
                remark='期初', warehouse=wh_a, doc_date=date.today(), location='仓库A')
            db.session.commit()
            rows = _txn_rows(mat)
            opening_rows = [r for r in rows if r.transaction_type == 'opening']
            assert opening_rows, "期初调整应产生 opening 流水"
            assert opening_rows[0].warehouse_id == 1, \
                f"期初调整应落 warehouse_id=1，实际 {opening_rows[0].warehouse_id}"


class TestStockTxnWarehouseIdBackfill:

    def test_backfill_stock_txn_warehouse_id(self):
        """A9 精确命名直测：回填函数可调用且空库幂等返回 0。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed()
            assert backfill_stock_txn_warehouse_id() == 0

    def test_backfill_by_warehouse_name(self):
        """T6：location=仓库名 → 回填对应 warehouse_id。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            order = _mk_in_order('仓库A')
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=9,
                                            location='仓库A', reference_type='in_order',
                                            reference_id=order.id))
            db.session.commit()
            assert _txn_rows(mat)[0].warehouse_id is None
            n = backfill_stock_txn_warehouse_id()
            assert n == 1, f"应回填 1 条，实际 {n}"
            assert _txn_rows(mat)[0].warehouse_id == 1, \
                f"仓库名匹配应回填 warehouse_id=1，实际 {_txn_rows(mat)[0].warehouse_id}"

    def test_backfill_by_warehouse_code(self):
        """T7：location=仓库编码 → 回填对应 warehouse_id。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=9,
                                            location='WHB', reference_type='in_order',
                                            reference_id=1))
            db.session.commit()
            backfill_stock_txn_warehouse_id()
            assert _txn_rows(mat)[0].warehouse_id == 2, \
                f"编码 WHA 应回填 warehouse_id=2，实际 {_txn_rows(mat)[0].warehouse_id}"

    def test_backfill_by_location_inventory(self):
        """T8：location=库位名且唯一归属 → warehouse_id 跟随 LocationInventory。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            db.session.add(LocationInventory(material_id=mat.id, warehouse_id=1,
                                             location='拣货区', quantity=5))
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=9,
                                            location='拣货区', reference_type='in_order',
                                            reference_id=1))
            db.session.commit()
            backfill_stock_txn_warehouse_id()
            assert _txn_rows(mat)[0].warehouse_id == 1, \
                f"库位名唯一归属应回填 warehouse_id=1，实际 {_txn_rows(mat)[0].warehouse_id}"

    def test_backfill_null_location_by_source_doc(self):
        """T9：空 location 按来源单据推断（入库单仓库 / 调拨正负归 from/to）。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            order_a = _mk_in_order('仓库A', no='IN-A')
            t = TransferOrder(transfer_no="TR-1", date=date.today(), from_warehouse='仓库A',
                              to_warehouse='仓库B', from_location='仓库A', to_location='仓库B',
                              status='completed')
            db.session.add(t)
            db.session.commit()
            db.session.add_all([
                StockTransaction(material_id=mat.id, transaction_type='in', quantity=8,
                                 location=None, reference_type='in_order', reference_id=order_a.id),
                StockTransaction(material_id=mat.id, transaction_type='transfer_out', quantity=-3,
                                 location=None, reference_type='transfer', reference_id=t.id),
                StockTransaction(material_id=mat.id, transaction_type='transfer_in', quantity=3,
                                 location=None, reference_type='transfer', reference_id=t.id),
            ])
            db.session.commit()
            backfill_stock_txn_warehouse_id()
            rows = {r.transaction_type: r.warehouse_id for r in _txn_rows(mat)}
            assert rows.get('in') == 1, f"入库单归属仓库A 应回填 1，实际 {rows.get('in')}"
            assert rows.get('transfer_out') == 1, \
                f"调拨出应归 from 仓库A=1，实际 {rows.get('transfer_out')}"
            assert rows.get('transfer_in') == 2, \
                f"调拨入应归 to 仓库B=2，实际 {rows.get('transfer_in')}"

    def test_backfill_ambiguous_keeps_null(self):
        """T10：歧义不猜——跨仓同名库位保持 NULL。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            # 库位 '共用位' 同时挂在仓库A、仓库B → 歧义
            db.session.add_all([
                LocationInventory(material_id=mat.id, warehouse_id=1, location='共用位', quantity=1),
                LocationInventory(material_id=mat.id, warehouse_id=2, location='共用位', quantity=1),
                StockTransaction(material_id=mat.id, transaction_type='in', quantity=9,
                                 location='共用位', reference_type='in_order', reference_id=1),
            ])
            db.session.commit()
            backfill_stock_txn_warehouse_id()
            assert _txn_rows(mat)[0].warehouse_id is None, \
                f"跨仓同名库位歧义应保持 NULL，实际 {_txn_rows(mat)[0].warehouse_id}"

    def test_backfill_idempotent(self):
        """T11：幂等——已回填的行再次执行不再变更。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=9,
                                            location='仓库A', reference_type='in_order',
                                            reference_id=1))
            db.session.commit()
            assert backfill_stock_txn_warehouse_id() == 1
            assert _txn_rows(mat)[0].warehouse_id == 1
            n2 = backfill_stock_txn_warehouse_id()
            assert n2 == 0, f"幂等回填第二次应 0 变更，实际 {n2}"
            assert _txn_rows(mat)[0].warehouse_id == 1
