# -*- coding: utf-8 -*-
"""BUG-2026-10-17-015-F07（审计 B11）：单据页库存展示必须按仓库口径。"""
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import app as wms  # noqa: E402
from app import Material, MaterialCategory, StockTransaction, Unit, Warehouse, db  # noqa: E402

wms.app.config['TESTING'] = True


def test_serialize_material_with_stock():
    with wms.app.app_context():
        db.drop_all(); db.create_all()
        db.session.add_all([Unit(code='PCS', name='个'),
                            MaterialCategory(code='C', name='默认'),
                            Warehouse(code='WHA', name='A仓', is_default=True),
                            Warehouse(code='WHB', name='B仓')])
        db.session.flush()
        db.session.add(Material(code='M1', name='料', category_id=1, unit_id=1, stock=999))
        db.session.flush()
        db.session.add_all([
            StockTransaction(material_id=1, transaction_type='in', quantity=5, warehouse_id=1,
                             location='', reference_type='in_order', reference_id=0,
                             created_at=datetime.now()),
            StockTransaction(material_id=1, transaction_type='in', quantity=9, warehouse_id=2,
                             location='', reference_type='in_order', reference_id=0,
                             created_at=datetime.now()),
        ])
        db.session.commit()
        mat = db.session.get(Material, 1)
        wh_a = db.session.get(Warehouse, 1)
        assert wms.serialize_material_with_stock(mat, wh_a)['stock'] == 5
        assert wms.serialize_material_with_stock(mat, None)['stock'] == 999
        db.session.remove()


def test_serialize_material_without_stock():
    with wms.app.app_context():
        db.drop_all(); db.create_all()
        from app import MaterialCategory, Unit
        db.session.add_all([Unit(code='PCS2', name='个'),
                            MaterialCategory(code='C3', name='默认3')])
        db.session.flush()
        mat = Material(code='M2', name='料2', category_id=2, unit_id=2, stock=88)
        db.session.add(mat); db.session.commit()
        data = wms.serialize_material_without_stock(mat)
        assert 'stock' not in data, '无仓库上下文页面不得展示库存'
