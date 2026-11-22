"""Stock document handoff across independent web sessions and the mobile read API."""
from io import BytesIO

import pytest
from openpyxl import load_workbook

import app as w
from tests.test_document_create_number_conflicts import case, payload
from tests.test_mobile_stock_audit_atomic import mobile_actors


def create_document(web, ids, kind):
    body = payload('other', ids, '')
    if kind == 'in_order':
        body['business_type'] = '产品入库'
    response = web.post(f'/{kind}/add', json=body)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    model = w.InOrder if kind == 'in_order' else w.OutOrder
    with w.app.app_context():
        order = model.query.one()
        assert order.operator_id == ids['user'] and order.status == 'pending'
        return model, order.id, order.order_no


@pytest.mark.parametrize('kind', ['in_order', 'out_order'])
@pytest.mark.parametrize('ambiguous', [False, True])
def test_mobile_list_and_detail_agree_for_legacy_warehouse(mobile_actors, kind, ambiguous):
    creator, mobile, headers, ids = mobile_actors
    model, oid, number = create_document(creator, ids, kind)
    url = f'/api/mobile/{kind}'
    with w.app.app_context():
        order = w.db.session.get(model, oid)
        order.warehouse = 'DC-A'
        if ambiguous:
            # Historical masters may reuse one warehouse's code as another's name.
            w.Warehouse.query.filter_by(id=ids['b']).update({'name': 'DC-A'})
        w.db.session.commit()

    def visible(warehouse_id, expected):
        query = {'warehouse_id': warehouse_id}
        listing = mobile.get(url + '/list', headers=headers, query_string=query)
        assert listing.status_code == 200
        assert (number in [r['order_no'] for r in listing.json['data']['items']]) == expected
        detail = mobile.get(f'{url}/{oid}', headers=headers, query_string=query)
        assert detail.status_code == (200 if expected else 404), detail.json
        if expected:
            assert detail.json['data']['order_no'] == number
    visible(ids['a'], not ambiguous)
    visible(ids['b'], False)


@pytest.mark.parametrize('kind,delta', [('in_order', 1), ('out_order', -1)])
def test_stock_document_account_handoff(mobile_actors, kind, delta):
    creator, mobile, headers, ids = mobile_actors
    model, oid, number = create_document(creator, ids, kind)
    poster = w.app.test_client()
    with poster.session_transaction() as session:
        session['_user_id'] = str(ids['mobile_actor'])
        session['_fresh'] = True
    base = f'/{kind}/{oid}'

    def balance():
        with w.app.app_context():
            return [w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse, wid))[ids['mats'][0]]
                    for wid in (ids['a'], ids['b'])]
    assert balance() == [20, 10]
    for action, status, expected_stock in (('complete', 'completed', 20 + delta), ('revert', 'pending', 20)):
        response = poster.post(f'{base}/{action}?force=1')
        assert response.status_code == 200 and response.json['status'] == 'success', response.json
        replay = poster.post(f'{base}/{action}?force=1')
        assert replay.json['status'] == 'error', replay.json
        assert balance() == [expected_stock, 10]
        with w.app.app_context():
            doc = w.db.session.get(model, oid)
            assert (doc.status, doc.operator_id) == (status, ids['user'])
            audit = w.OperationAudit.query.filter_by(operation=f'{action}_{kind}', target_id=oid).one()
            assert audit.user_id == ids['mobile_actor']
            moves = w.StockTransaction.query.filter_by(reference_type=kind, reference_id=oid).order_by(w.StockTransaction.id).all()
            assert [m.quantity for m in moves] == ([delta] if action == 'complete' else [delta, -delta])
            assert all((m.warehouse_id, m.operator_id) == (ids['a'], ids['mobile_actor']) for m in moves)
        detail = mobile.get('/api/mobile' + base, headers=headers, query_string={'warehouse_id': ids['a']})
        assert detail.status_code == 200, detail.json
        assert (detail.json['data']['order_no'], detail.json['data']['status']) == (number, status)

    with w.app.app_context():
        reader = w.User(username='handoff-reader', role='finance', password_hash='synthetic-unused',
                        must_change_password=False)
        w.db.session.add(reader)
        w.db.session.commit()
        reader_id = reader.id
    browser = w.app.test_client()
    with browser.session_transaction() as session:
        session['_user_id'] = str(reader_id)
        session['_fresh'] = True
    for path in (base, base + '/print'):
        response = browser.get(path)
        assert response.status_code == 200 and number in response.get_data(as_text=True), path
    response = browser.get(base + '/export')
    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.data), read_only=True)
    try:
        assert any(number in str(cell) for row in workbook.active.values for cell in row)
    finally:
        workbook.close()
    mobile_detail = browser.get('/api/mobile' + base, query_string={'warehouse_id': ids['a']})
    assert mobile_detail.status_code == 200 and mobile_detail.json['data']['order_no'] == number
    denied = browser.post(base + '/complete?force=1', json={})
    assert denied.status_code == 403 and balance() == [20, 10]
