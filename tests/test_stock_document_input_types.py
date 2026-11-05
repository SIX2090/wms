"""Malformed stock-document JSON must fail before header/detail/stock changes."""
from datetime import date
import pytest
import app as w
from tests.test_document_create_number_conflicts import case, payload, snapshot


TEXT_FIELDS = ['order_no', 'date', 'business_type', 'purpose', 'warehouse',
               'location', 'remark', 'contract_no', 'project_name', 'customer', 'picker']
EXPECTED_LABELS = dict(zip(TEXT_FIELDS, ['单据编号', '日期', '业务类型', '用途', '仓库',
    '库位', '备注', '合同编号', '工程名称', '客户', '领料人']))


@pytest.mark.parametrize('family', ['in_order', 'out_order'])
@pytest.mark.parametrize('field', TEXT_FIELDS)
@pytest.mark.parametrize('invalid', [['产品入库'], {'bad': 'value'}, True, 123, 'x'*10001])
def test_validate_document_json_input(case, family, field, invalid):
    clients, ids = case
    data = payload('other', ids, 'TYPED-STOCK')
    data.update(date=date.today().isoformat(), business_type='其他入库' if family == 'in_order' else '其他出库')
    data[field] = invalid
    model = w.InOrder if family == 'in_order' else w.OutOrder
    with w.app.app_context():
        before = snapshot(model)
    response = clients[0].post(f'/{family}/add', json=data)
    assert response.status_code == 400, (family, field, response.json)
    assert response.json['code'] == 'INVALID_DOCUMENT_INPUT'
    assert EXPECTED_LABELS[field] in response.json['msg']
    with w.app.app_context():
        assert snapshot(model) == before


@pytest.mark.parametrize('family', ['in_order', 'out_order'])
@pytest.mark.parametrize('invalid', [[], [1], None, 123, True, 'invalid'])
def test_stock_document_root_must_be_object(case, family, invalid):
    import json
    clients, _ = case
    response = clients[0].post(f'/{family}/add', data=json.dumps(invalid), content_type='application/json')
    assert response.status_code == 400, response.json


@pytest.mark.parametrize('family', ['in_order', 'out_order'])
@pytest.mark.parametrize('field', ['code', 'material_code', 'remark', 'location', 'contract_no', 'project_name'])
def test_stock_document_item_text_types(case, family, field):
    clients, ids = case
    data = payload('other', ids, 'TYPED-ITEM')
    data['business_type'] = '其他入库' if family == 'in_order' else '其他出库'
    data['items'][0][field] = {'not': 'text'}
    model = w.InOrder if family == 'in_order' else w.OutOrder
    with w.app.app_context():
        before = snapshot(model)
    response = clients[0].post(f'/{family}/add', json=data)
    assert response.status_code == 400, response.json
    with w.app.app_context():
        assert snapshot(model) == before


@pytest.mark.parametrize('family', ['in_order', 'out_order'])
@pytest.mark.parametrize('field', ['quantity', 'price', 'material_id'])
@pytest.mark.parametrize('invalid', [[1], {'value': 1}, True])
def test_stock_field_type(case, family, field, invalid):
    clients, ids = case
    data = payload('other', ids, 'TYPED-NUMBER')
    data['business_type'] = '其他入库' if family == 'in_order' else '其他出库'
    data['items'][0][field] = invalid
    model = w.InOrder if family == 'in_order' else w.OutOrder
    with w.app.app_context():
        before = snapshot(model)
    response = clients[0].post(f'/{family}/add', json=data)
    assert response.status_code == 400, response.json
    with w.app.app_context():
        assert snapshot(model) == before
