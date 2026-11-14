"""No-document clients must never choose or steal a cross-document row."""
from datetime import date, datetime, timedelta
from scripts.verify_db_guard import require_isolated_test_runtime
require_isolated_test_runtime()

import pytest
from flask import g
import app as w
from tests.document_revision_client import document_post


@pytest.fixture
def legacy_scene(monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    with w.app.app_context():
        w.db.session.remove()
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.drop_all()
        w.db.create_all()
        def fresh_user():
            g.pop('_login_user', None)
        hooks = dict(w.app.before_request_funcs)
        hooks[None] = [fresh_user, *hooks.get(None, [])]
        monkeypatch.setattr(w.app, 'before_request_funcs', hooks)
        user = w.User(username='synthetic-legacy', password_hash='not-for-login',
                      role='admin', must_change_password=False)
        a = w.Warehouse(code='SYN-A', name='合成甲仓', status='active', is_default=True)
        b = w.Warehouse(code='SYN-B', name='合成乙仓', status='active')
        material = w.Material(code='SYN-M', name='合成物料', price=2, stock=0)
        w.db.session.add_all([user, a, b, material])
        w.db.session.flush()
        w.db.session.add(w.ApiToken(token='synthetic-opening', user_id=user.id,
            expires_at=datetime.now() + timedelta(hours=1), revoked=False))
        w.db.session.commit()
        client = w.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'], session['_fresh'] = str(user.id), True
        yield client, a, b, material, user
        w.db.session.remove()


def _seed(scene, warehouse, quantity, label, owned=True):
    _, _, _, material, user = scene
    doc = w.OpeningStockDoc(doc_no='SYN-' + label, date=date(2020, 1, 1),
                           status='active', warehouse_id=warehouse.id, operator_id=user.id)
    if owned:
        w.db.session.add(doc)
        w.db.session.flush()
    with w.app.test_request_context():
        g._login_user = user
        row, _ = w._apply_opening_stock_balance(None, material, quantity, 2, quantity * 2,
            '合成期初', warehouse, date(2020, 1, 1), '', doc_id=doc.id if owned else None)
    w.db.session.commit()
    return row


def _state():
    w.db.session.expire_all()
    return (
        [(r.id, r.doc_id, r.quantity, r.price, r.amount, r.date) for r in w.OpeningStock.query.order_by(w.OpeningStock.id)],
        [(r.id, r.doc_no, r.date) for r in w.OpeningStockDoc.query.order_by(w.OpeningStockDoc.id)],
        [(r.id, r.stock) for r in w.Material.query.order_by(w.Material.id)],
        [(r.id, r.quantity, r.reference_type, r.reference_id) for r in w.StockTransaction.query.order_by(w.StockTransaction.id)],
        [(r.id, r.quantity) for r in w.LocationInventory.query.order_by(w.LocationInventory.id)],
        [(r.id, r.endpoint, r.request_key, r.response_json) for r in w.MobileApiRequest.query.order_by(w.MobileApiRequest.id)],
    )


def _post(scene, channel, quantity=9, key='synthetic-request', extra=None):
    client, a, _, material, _ = scene
    if channel == 'native':
        payload = {'date': '2026-11-14', 'warehouse_code': a.code,
                   'lines': [{'material_code': material.code, 'quantity': quantity, 'price': 2}]}
        if extra:
            payload['lines'].extend(extra)
        # Use a genuinely bearer-only client.
        return w.app.test_client().post('/api/opening_stock', json=payload,
            headers={'Authorization': 'Bearer synthetic-opening', 'X-Idempotency-Key': key})
    payload = {'date': '2026-11-14', 'items': [{'material_id': material.id,
        'warehouse_id': a.id, 'quantity': quantity, 'price': 2}]}
    if extra:
        payload['items'].extend(extra)
    return document_post(client, '/opening_stock/batch_save', json=payload,
                         headers={'X-Idempotency-Key': key})


@pytest.mark.parametrize('channel', ['native', 'web'])
@pytest.mark.parametrize('location_on', [False, True])
def test_unique_owned_row_keeps_document_and_header_date(legacy_scene, channel, location_on):
    w.set_system_setting('location_management_enabled', '1' if location_on else '0')
    w.db.session.commit()
    _, a, b, material, _ = legacy_scene
    row = _seed(legacy_scene, a, 5, 'OWNER')
    other = _seed(legacy_scene, b, 7, 'OTHER')
    owner, row_id, other_id = row.doc_id, row.id, other.id
    response = _post(legacy_scene, channel)
    assert response.status_code == 200, response.get_json()
    w.db.session.expire_all()
    saved = w.db.session.get(w.OpeningStock, row_id)
    assert saved.doc_id == owner and saved.date == date(2020, 1, 1)
    assert saved.quantity == 9 and saved.amount == 18
    assert w.db.session.get(w.OpeningStock, other_id).quantity == 7
    assert material.stock == 16
    assert w.OpeningStockDoc.query.count() == 2
    before = _state()
    assert _post(legacy_scene, channel).status_code == 200
    assert _state() == before, 'The same request must replay without a second stock movement'


@pytest.mark.parametrize('channel', ['native', 'web'])
@pytest.mark.parametrize('legacy_null', [False, True])
@pytest.mark.parametrize('location_on', [False, True])
def test_ambiguous_rows_rejected_without_changing_any_state(legacy_scene, channel, legacy_null, location_on):
    w.set_system_setting('location_management_enabled', '1' if location_on else '0')
    w.db.session.commit()
    _seed(legacy_scene, legacy_scene[1], 5, 'FIRST', owned=not legacy_null)
    _seed(legacy_scene, legacy_scene[1], 7, 'SECOND')
    before = _state()
    response = _post(legacy_scene, channel)
    assert response.status_code == 400, response.get_json()
    assert '明确单据' in response.get_json()['msg']
    assert _state() == before


@pytest.mark.parametrize('channel', ['native', 'web'])
def test_null_unique_adoption_and_new_row_remain_compatible(legacy_scene, channel):
    row = _seed(legacy_scene, legacy_scene[1], 5, 'NULL', owned=False)
    row_id = row.id
    assert _post(legacy_scene, channel).status_code == 200
    w.db.session.expire_all()
    row = w.db.session.get(w.OpeningStock, row_id)
    assert row.doc_id and row.quantity == 9
    assert w.db.session.get(w.OpeningStockDoc, row.doc_id).doc_no == 'QSLEGACY2611'


def test_balance_helper_rejects_existing_owner_reassignment(legacy_scene):
    row = _seed(legacy_scene, legacy_scene[1], 5, 'FIRST')
    other = _seed(legacy_scene, legacy_scene[2], 7, 'SECOND')
    before = _state()
    with w.app.test_request_context():
        g._login_user = legacy_scene[4]
        with pytest.raises(ValueError, match='归属'):
            w._apply_opening_stock_balance(row, legacy_scene[3], 9, 2, 18, '',
                legacy_scene[1], date.today(), '', doc_id=other.doc_id)
    w.db.session.rollback()
    assert _state() == before


@pytest.mark.parametrize('key', ['', 'synthetic-atomic-failure'])
def test_later_invalid_native_line_rolls_back_earlier_update(legacy_scene, key):
    _seed(legacy_scene, legacy_scene[1], 5, 'FIRST')
    before = _state()
    response = _post(legacy_scene, 'native', key=key,
                     extra=[{'material_code': 'SYN-MISSING', 'quantity': 2}])
    assert response.status_code == 400
    assert _state() == before


def test_unique_rows_from_two_documents_keep_both_owners_in_one_web_batch(legacy_scene):
    first = _seed(legacy_scene, legacy_scene[1], 5, 'FIRST')
    other_material = w.Material(code='SYN-OTHER', name='合成第二物料', stock=0, price=2)
    w.db.session.add(other_material)
    w.db.session.commit()
    other_scene = (*legacy_scene[:3], other_material, legacy_scene[4])
    second = _seed(other_scene, legacy_scene[1], 7, 'SECOND')
    owners = first.doc_id, second.doc_id
    response = _post(legacy_scene, 'web', extra=[{'material_id': other_material.id,
        'warehouse_id': legacy_scene[1].id, 'quantity': 10, 'price': 2}])
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['doc_id'] is None, 'A multi-document save must not be labelled as one document'
    w.db.session.expire_all()
    assert (first.doc_id, second.doc_id) == owners
    assert (first.quantity, second.quantity) == (9, 10)
    assert w.OpeningStockDoc.query.count() == 2
