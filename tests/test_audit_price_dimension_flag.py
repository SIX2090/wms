# -*- coding: utf-8 -*-
"""BUG-2026-10-17-014-F04（审计 §3.6）：价格维度默认关闭，资金类报表下线。"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import app as wms  # noqa: E402
from app import User, db, set_system_setting  # noqa: E402

wms.app.config['TESTING'] = True
wms.app.config['WTF_CSRF_ENABLED'] = False


@pytest.fixture(autouse=True)
def _ctx():
    # 注意：不能在 yield 外层常驻 app context——Flask 会复用该 context，
    # g._system_setting_cache 会跨请求残留，导致「改设置后请求仍读旧值」的假失败。
    with wms.app.app_context():
        db.drop_all()
        db.create_all()
        from werkzeug.security import generate_password_hash
        db.session.add(User(username='admin', password_hash=generate_password_hash('admin'),
                            role='admin', must_change_password=False))
        db.session.commit()
    yield
    with wms.app.app_context():
        db.session.remove()


def _client():
    c = wms.app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = '1'
        sess['_fresh'] = True
    return c


def _set(enabled):
    with wms.app.app_context():
        set_system_setting('price_dimension_enabled', '1' if enabled else '0')
        db.session.commit()


def test_price_dimension_enabled():
    with wms.app.app_context():
        assert wms.price_dimension_enabled() is False
    _set(True)
    with wms.app.app_context():
        assert wms.price_dimension_enabled() is True


def test_price_report_routes_redirect_when_disabled():
    _set(False)
    c = _client()
    assert c.get('/sales/price_analysis').status_code == 302
    assert c.get('/report/view/purchase_price_analysis').status_code == 302
    assert c.get('/report/api/purchase_price_analysis').status_code == 400


def test_price_report_routes_available_when_enabled():
    _set(True)
    c = _client()
    assert c.get('/sales/price_analysis').status_code == 200
    assert c.get('/report/view/purchase_price_analysis').status_code == 200


def test_report_center_hides_price_cards_when_disabled():
    _set(False)
    c = _client()
    assert '价格分析' not in c.get('/report').get_data(as_text=True)
    assert '价格分析' not in c.get('/purchase_report').get_data(as_text=True)
    _set(True)
    with wms.app.app_context():
        assert wms.price_dimension_enabled() is True
    assert '价格分析' in c.get('/report').get_data(as_text=True)
