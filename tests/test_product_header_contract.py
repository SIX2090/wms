"""Product header contract linkage uses isolated master data and preserves stock."""
from copy import deepcopy
from datetime import date

import pytest

import app as w
from tests.test_web_document_idempotency import receipt_case
from tests.test_document_edit_conflicts import revision


@pytest.fixture
def contract_case(receipt_case):
    client, payload = receipt_case
    with w.app.app_context():
        w.db.session.add(w.Contract(contract_no='HD261017', project_name='合同档案工程', status='active'))
        w.db.session.commit()
    return client, deepcopy(payload)


@pytest.mark.parametrize('entry', ['create', 'edit', 'header'])
def test_product_header_project_resolves_master_on_every_save(contract_case, entry):
    client, payload = contract_case
    if entry == 'create':
        payload.update(contract_no='HD261017', project_name='')
        result = client.post('/in_order/add', json=payload)
    else:
        created = client.post('/in_order/add', json=payload)
        assert created.status_code == 200, created.json
        oid = created.json['id']
        if entry == 'edit':
            payload.update(order_id=oid, contract_no='HD261017', project_name='')
            result = client.post('/in_order/add', json=payload, headers={
                'X-WMS-Document-Revision': revision(client, f'/in_order/add?order_id={oid}')})
        else:
            result = client.post(f'/in_order/{oid}/update', json={
                'date': date.today().isoformat(), 'warehouse_id': payload['warehouse_id'],
                'contract_no': 'HD261017', 'project_name': ''}, headers={
                    'X-WMS-Document-Revision': revision(client, f'/in_order/{oid}')})
    assert result.status_code == 200, result.json
    with w.app.app_context():
        order = w.InOrder.query.one()
        assert (order.contract_no, order.project_name) == ('HD261017', '合同档案工程')
        assert w.Material.query.one().stock == 0
        assert w.StockTransaction.query.count() == 0


@pytest.mark.parametrize('contract_no,project,expected', [
    ('HD261017', '手工补充工程', '手工补充工程'),
    ('尚未建档合同', '', None),
    ('尚未建档合同', '手工工程', '手工工程'),
])
def test_product_header_project_preserves_manual_and_unmatched_values(contract_case, contract_no, project, expected):
    client, payload = contract_case
    payload.update(contract_no=contract_no, project_name=project)
    result = client.post('/in_order/add', json=payload)
    assert result.status_code == 200, result.json
    with w.app.app_context():
        assert w.InOrder.query.one().project_name == expected


def test_product_header_contract_binding_in_create_edit_and_header_modal(contract_case):
    client, payload = contract_case
    page = client.get('/in_order/add?type=product')
    assert 'data-product-contract' in page.text
    assert '/static/js/product-receipt-contract.js?' in page.text
    created = client.post('/in_order/add', json=payload)
    assert created.status_code == 200, created.json
    oid = created.json['id']
    for path in (f'/in_order/add?order_id={oid}', f'/in_order/{oid}'):
        page = client.get(path)
        assert page.status_code == 200
        assert 'data-product-contract' in page.text
        assert '/static/js/product-receipt-contract.js?' in page.text
    assert 'data-product-contract' not in client.get('/in_order/add').text
