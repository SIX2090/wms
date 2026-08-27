# -*- coding: utf-8 -*-
"""BUG-2026-08-27-003 回归：多仓库下库存台账把空 location 流水按来源单据仓库归属。

根因：历史流水 StockTransaction.location 为 NULL/空，多仓库时无法按 location 归属到具体
仓库，被台账仓库过滤排除——用户"选了仓库+物料+日期仍查不到"。但这些流水的来源单据
（入库单/出库单/期初/调拨等）本身记录了仓库，可据此归属。

修复：多仓库按仓库查询时，空 location 流水一并取出，再按来源单据仓库过滤——归属所选
仓库的保留，否则剔除；location 非空流水已被 SQL 过滤、不受影响。

T1. 空 location 流水，来源入库单 warehouse=仓库A：查仓库A 可见。
T2. 同上，查仓库B 不可见（不串仓）。
T3. location 非空流水（仓库名）仍正常可见（不回归）。
T4. 调拨空 location 流水：调出归 from_warehouse、调入归 to_warehouse。
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
    db, InOrder, Material, MaterialCategory, StockTransaction, TransferOrder,
    Unit, Warehouse, set_system_setting, _collect_ledger_rows,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    set_system_setting("location_management_enabled", "0")  # 关库位管理
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


def _filters(wh, mat):
    return {
        'start_date': None, 'end_date': None,
        'warehouse_id': wh.id, 'warehouse': wh.name, 'warehouse_code': wh.code or '',
        'business_type': '', 'material_code': mat.code,
        'supplier_id': 0, 'supplier': '', 'customer': '', 'status': '',
        'sort_field': '', 'sort_order': 'asc', 'page': 1, 'page_size': 20,
        'hide_zero': False, 'export': '',
    }


def _mk_in_order(warehouse_name):
    o = InOrder(order_no=f"IN-{warehouse_name}", date=date.today(), warehouse=warehouse_name,
                status='completed', business_type='采购入库')
    db.session.add(o)
    db.session.commit()
    return o


class TestLedgerSourceWarehouseAttribution:

    def test_null_location_attributed_to_source_warehouse(self):
        """T1：空 location 流水，来源入库单属仓库A，查仓库A 可见。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a = Warehouse.query.get(1)
            order = _mk_in_order('仓库A')
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=100,
                                            location=None, reference_type='in_order', reference_id=order.id))
            db.session.commit()
            rows = _collect_ledger_rows(_filters(wh_a, mat))
            assert len(rows) == 1, f"空location流水应按来源单据归属仓库A，实际 {len(rows)} 行"
            assert abs(rows[0]['in_quantity'] - 100) < 1e-6

    def test_null_location_not_visible_in_other_warehouse(self):
        """T2：同上，查仓库B 不可见（不串仓）。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_b = Warehouse.query.get(2)
            order = _mk_in_order('仓库A')
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=100,
                                            location=None, reference_type='in_order', reference_id=order.id))
            db.session.commit()
            rows = _collect_ledger_rows(_filters(wh_b, mat))
            assert len(rows) == 0, f"空location流水不应出现在仓库B，实际 {len(rows)} 行"

    def test_named_location_still_visible(self):
        """T3：location 非空（仓库名）流水仍正常可见（不回归）。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a = Warehouse.query.get(1)
            order = _mk_in_order('仓库A')
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=10,
                                            location='仓库A', reference_type='in_order', reference_id=order.id))
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=5,
                                            location=None, reference_type='in_order', reference_id=order.id))
            db.session.commit()
            rows = _collect_ledger_rows(_filters(wh_a, mat))
            assert len(rows) == 2, f"仓库名流水+空location流水应共2行，实际 {len(rows)}"

    def test_transfer_attribution_by_sign(self):
        """T4：调拨空 location 流水，调出归 from_warehouse、调入归 to_warehouse。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a = Warehouse.query.get(1)
            wh_b = Warehouse.query.get(2)
            t = TransferOrder(transfer_no="TR-1", date=date.today(), from_warehouse='仓库A',
                              to_warehouse='仓库B', from_location='仓库A', to_location='仓库B',
                              status='completed')
            db.session.add(t)
            db.session.commit()
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='transfer_out', quantity=-4,
                                            location=None, reference_type='transfer', reference_id=t.id))
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='transfer_in', quantity=4,
                                            location=None, reference_type='transfer', reference_id=t.id))
            db.session.commit()
            rows_a = _collect_ledger_rows(_filters(wh_a, mat))
            rows_b = _collect_ledger_rows(_filters(wh_b, mat))
            assert len(rows_a) == 1 and abs(rows_a[0]['out_quantity'] - 4) < 1e-6, f"调出应归仓库A: {len(rows_a)}"
            assert len(rows_b) == 1 and abs(rows_b[0]['in_quantity'] - 4) < 1e-6, f"调入应归仓库B: {len(rows_b)}"
