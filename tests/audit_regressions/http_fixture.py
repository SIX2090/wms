"""Round26: complete WMS dispatch with real auth, CSRF and fresh RAM data.

Sessions are synthetic; invalid password hashes cannot be used for real login.
No real provider, device, credential generation, merge, or nonempty deletion.
"""
import json
from datetime import date, datetime, timedelta

import pytest
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import app as m


@pytest.fixture
def http_case(monkeypatch):
    monkeypatch.setitem(m.app.config, 'TESTING', True)
    monkeypatch.setitem(m.app.config, 'PROPAGATE_EXCEPTIONS', False)
    monkeypatch.setitem(m.app.config, 'WTF_CSRF_ENABLED', True)
    monkeypatch.setitem(m.app.config, 'SESSION_COOKIE_SECURE', False)
    calls = []
    def no_io(*args, **kwargs):
        calls.append('unexpected external effect')
        raise AssertionError('No external I/O or image/stock side effects in input tests')
    monkeypatch.setattr(m, '_ai_call_llm_chat', no_io)
    monkeypatch.setattr(m, '_save_material_image_from_url', no_io)
    engine = create_engine('sqlite://', poolclass=StaticPool)
    with m.app.app_context():
        old_engine = m.db.engines[None]
        m.db.session.remove()
        m.db.engines[None] = engine
        m.db.create_all()
        m.db.session.add_all([
            m.SystemSetting(key='ai_feature_rollout_mode', value='all'),
            m.SystemSetting(key='ai_feature_global_enabled', value='1'),
        ])
        users = {}
        for role in ('admin', 'warehouse', 'finance'):
            user = m.User(username='QA27-' + role, role=role,
                password_hash='!invalid-unusable-test-hash', must_change_password=False, status='normal')
            m.db.session.add(user)
            m.db.session.flush()
            users[role] = user.id
        a = m.Warehouse(code='QA27-A', name='QA27-A', status='active')
        b = m.Warehouse(code='QA27-B', name='QA27-B', status='active')
        unit = m.Unit(code='QA27-U', name='个')
        m.db.session.add_all([a, b, unit]); m.db.session.flush()
        material = m.Material(code='QA27-M', name='合成物料', unit_id=unit.id, stock=30)
        m.db.session.add(material); m.db.session.flush()
        for wh, quantity, kind in [(a,190,'in'),(a,-180,'out'),(b,20,'in')]:
            m.db.session.add(m.StockTransaction(material_id=material.id, warehouse_id=wh.id,
                location=wh.name, quantity=quantity, transaction_type=kind,
                created_at=datetime.now()-timedelta(days=2)))
        check = m.InventoryCheck(check_no='QA27-CK', warehouse=a.name, status='pending',
            frozen_at=datetime.now()-timedelta(days=1), operator_id=users['warehouse'])
        m.db.session.add(check); m.db.session.flush()
        m.db.session.add(m.InventoryCheckItem(inventory_check_id=check.id, material_id=material.id,
            system_stock=10, actual_stock=10, difference=0,
            counted_by=users['warehouse'], counted_at=datetime.now()))
        m.db.session.commit()
        ids = dict(material=material.id, check=check.id, a=a.id, b=b.id, unit=unit.id)

    def client(role='admin', csrf=True):
        c = m.app.test_client()
        c.environ_base['HTTP_ACCEPT'] = 'application/json'
        c.environ_base['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        with c.session_transaction() as session:
            if role:
                session['_user_id'] = str(users[role])
                session['_fresh'] = True
            session['csrf_token'] = 'qa27-fixed-public-csrf-seed'
        if csrf:
            serializer=URLSafeTimedSerializer(m.app.secret_key, salt='wtf-csrf-token')
            c.environ_base['HTTP_X_CSRFTOKEN'] = serializer.dumps('qa27-fixed-public-csrf-seed')
        return c

    def business_state():
        with m.app.app_context():
            return dict(adjustments=m.AdjustmentOrder.query.count(),
                details=m.AdjustmentOrderItem.query.count(),
                flows=m.StockTransaction.query.count(), material=m.db.session.get(m.Material, ids['material']).stock,
                check=m.db.session.get(m.InventoryCheck, ids['check']).status,
                images=m.db.session.get(m.Material, ids['material']).image)
    try:
        yield client, ids, business_state
    finally:
        with m.app.app_context():
            m.db.session.remove()
            m.db.engines[None] = old_engine
        engine.dispose()
        assert calls == []
