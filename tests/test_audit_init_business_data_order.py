# -*- coding: utf-8 -*-
"""BUG-2026-10-17-012-F04：业务数据初始化必须先删流水账再归零总账，失败即中止。

旧顺序"先归零①再删③"且删表失败被吞掉，可能留下 ①=0/③≠0 的永久分裂。
"""
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import app as wms  # noqa: E402
from app import Material, StockTransaction, db  # noqa: E402

wms.app.config['TESTING'] = True
wms.app.config['WTF_CSRF_ENABLED'] = False


@pytest.fixture(autouse=True)
def _ctx():
    with wms.app.app_context():
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()


def _seed():
    db.session.add(Material(code='M1', name='轴承', spec='6204', stock=50))
    db.session.flush()
    db.session.add(StockTransaction(material_id=1, transaction_type='in',
                                    quantity=50, warehouse_id=1,
                                    reference_type='in_order', reference_id=1,
                                    created_at=datetime.now()))
    db.session.commit()


def test_init_deletes_ledger_before_zeroing_stock():
    _seed()
    deleted = wms._init_business_data_keep_users_and_settings(include_master_data=False)
    assert deleted['zeroed_materials'] == 1
    assert Material.query.first().stock == 0
    assert StockTransaction.query.count() == 0


def test_init_aborts_without_zeroing_when_ledger_delete_fails(monkeypatch):
    _seed()
    original = wms._bulk_delete_model_required

    def boom(model_cls, label):
        if model_cls is StockTransaction:
            raise RuntimeError('模拟删流水失败')
        return original(model_cls, label)

    monkeypatch.setattr(wms, '_bulk_delete_model_required', boom)
    with pytest.raises(RuntimeError):
        wms._init_business_data_keep_users_and_settings(include_master_data=False)
    db.session.rollback()
    assert Material.query.first().stock == 50, '删流水失败时不得先把总账归零'
