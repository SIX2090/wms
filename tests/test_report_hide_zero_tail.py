"""Hide only stock rounding residue; preserve warehouse scope and four-digit balances."""
import io

import pytest
from openpyxl import load_workbook

import app as w


@pytest.fixture(params=[(False, False), (False, True), (True, False), (True, True)])
def tail_case(request, monkeypatch):
    locations, legacy = request.param
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    monkeypatch.setattr(w, 'location_management_enabled', lambda: locations)
    with w.app.app_context():
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.session.remove()
        w.db.drop_all()
        w.db.create_all()
        a = w.Warehouse(code='TA', name='尾差甲仓', status='active', is_default=True)
        b = w.Warehouse(code='TB', name='尾差乙仓', status='active')
        user = w.User(username='tail-report', role='admin', password_hash='unused',
                      must_change_password=False)
        w.db.session.add_all([a, b, user])
        w.db.session.flush()
        balances = {'TAIL-P': 2.7755575615628914e-17, 'TAIL-N': -2.7755575615628914e-17,
                    'ZERO': 0, 'SMALL-P': 0.0001, 'SMALL-N': -0.0001}
        for code, quantity in balances.items():
            material = w.Material(code=code, name=code, price=2,
                                  stock=quantity + (12 if code == 'TAIL-P' else 0))
            w.db.session.add(material)
            w.db.session.flush()
            for warehouse, balance in [(a, quantity), (b, 12 if code == 'TAIL-P' else 0)]:
                w.db.session.add(w.StockTransaction(
                    material_id=material.id, quantity=balance, transaction_type='opening',
                    warehouse_id=None if legacy else warehouse.id,
                    location=warehouse.code if legacy else warehouse.name))
                if locations:
                    w.db.session.add(w.LocationInventory(
                        material_id=material.id, quantity=balance,
                        warehouse_id=None if legacy else warehouse.id,
                        location=warehouse.code if legacy else warehouse.name))
        w.db.session.commit()
        ids = {'a': a.id, 'b': b.id, 'user': user.id, 'balances': balances}
    client = w.app.test_client()
    with client.session_transaction() as session:
        session.update(_user_id=str(ids['user']), _fresh=True)
    yield client, ids
    with w.app.app_context():
        w.db.session.remove()


@pytest.mark.parametrize('report', ['inventory', 'inventory_analysis'])
def test_hide_zero_residue_matches_pagination_summary_and_export(tail_case, report):
    client, ids = tail_case
    query = {'warehouse_id': ids['a'], 'hide_zero': 1, 'page_size': 1}
    rows = []
    for page in (1, 2):
        response = client.get('/report/api/' + report, query_string=dict(query, page=page))
        assert response.status_code == 200
        data = response.get_json()
        assert data['total'] == 2
        assert data['total_pages'] == 2
        assert data['summary']['count'] == 2
        assert data['summary']['quantity'] == pytest.approx(0, abs=1e-20)
        rows.extend(data['data'])
    assert {row['code']: row['stock'] for row in rows} == {'SMALL-P': 0.0001, 'SMALL-N': -0.0001}
    exported = client.get('/report/api/' + report,
                          query_string=dict(query, page=2, export='excel'))
    assert exported.status_code == 200
    sheet = load_workbook(io.BytesIO(exported.data), data_only=True).active
    assert {row[0] for row in sheet.iter_rows(values_only=True)
            if row[0] in ids['balances']} == {'SMALL-P', 'SMALL-N'}


@pytest.mark.parametrize('report', ['inventory', 'inventory_analysis'])
def test_zero_filter_is_warehouse_scoped_and_does_not_rewrite_stock(tail_case, report):
    client, ids = tail_case
    all_rows = client.get('/report/api/' + report,
                         query_string={'warehouse_id': ids['a']}).get_json()['data']
    assert {row['code'] for row in all_rows} == set(ids['balances'])
    other = client.get('/report/api/' + report,
                       query_string={'warehouse_id': ids['b'], 'hide_zero': 1}).get_json()
    assert {row['code']: row['stock'] for row in other['data']} == {'TAIL-P': 12}
    with w.app.app_context():
        stored = {row.code: row.stock for row in w.Material.query.all()}
        expected = dict(ids['balances'], **{'TAIL-P': 12 + ids['balances']['TAIL-P']})
        assert stored == expected
        assert w.StockTransaction.query.count() == 10
