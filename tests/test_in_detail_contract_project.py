"""入库报表合同/工程：行级筛选、历史回退及输出一致性。"""
import io

import pytest
from openpyxl import load_workbook

from tests.test_report_in_detail_business_type_warehouse import client
import app as wms


@pytest.fixture
def report_case(client):
    with wms.app.app_context():
        orders = wms.InOrder.query.order_by(wms.InOrder.order_no).all()
        for order in orders:
            order.contract_no = 'HEADER'
            order.project_name = '旧工程'
        first = orders[0].items[0]
        first.contract_no, first.project_name = 'C-001', '一号工程'
        wms.db.session.add(wms.InOrderItem(
            in_order_id=orders[0].id, material_id=first.material_id,
            quantity=2, price=10, amount=20, contract_no='C-002', project_name='二号工程'))
        orders[1].items[0].contract_no = ''
        orders[1].items[0].project_name = ''
        other = wms.Warehouse(code='WH002', name='二号仓库', status='active')
        wms.db.session.add(other)
        orders[2].warehouse = other.name
        wms.db.session.commit()
        wh_id = wms.Warehouse.query.filter_by(code='WH001').one().id
        other_id = other.id
    return client, wh_id, other_id


def test_columns_and_filter_controls(report_case):
    client, wh, _ = report_case
    html = client.get('/report/view/in_detail').get_data(as_text=True)
    assert 'name="contract_no"' in html
    assert 'name="project_name"' in html
    data = client.get('/report/api/in_detail', query_string={'warehouse_id': wh}).get_json()
    assert {'contract_no', 'project_name'} <= {c['field'] for c in data['columns']}
    rows = {r['contract_no']: r for r in data['data']}
    assert rows['C-001']['project_name'] == '一号工程'
    assert rows['']['project_name'] == ''  # 显式清空不能回退表头


@pytest.mark.parametrize('filters,expected', [
    ({'contract_no': ' C-001 '}, ['C-001']),
    ({'project_name': '二号'}, ['C-002']),
    ({'contract_no': 'C-001', 'project_name': '二号'}, []),
    ({'contract_no': 'HEADER'}, []),
])
def test_line_filters_and_totals(report_case, filters, expected):
    client, wh, _ = report_case
    data = client.get('/report/api/in_detail', query_string={
        'warehouse_id': wh, **filters}).get_json()
    assert [r['contract_no'] for r in data['data']] == expected
    assert data['total'] == len(expected)
    assert data['summary']['quantity'] == sum(r['quantity'] for r in data['data'])
    assert data['summary']['amount'] == sum(r['amount'] for r in data['data'])


def test_legacy_header_fallback_and_warehouse(report_case):
    client, wh, other = report_case
    query = {'contract_no': 'HEADER', 'project_name': '旧工程'}
    assert client.get('/report/api/in_detail', query_string={
        'warehouse_id': wh, **query}).get_json()['total'] == 0
    data = client.get('/report/api/in_detail', query_string={
        'warehouse_id': other, **query}).get_json()
    assert data['total'] == 1
    assert data['data'][0]['contract_no'] == 'HEADER'
    assert data['data'][0]['project_name'] == '旧工程'


def test_export_print_and_pagination_use_same_filters(report_case):
    client, wh, _ = report_case
    query = {'warehouse_id': wh, 'contract_no': 'C-', 'page_size': 1,
             'sort_field': 'contract_no', 'sort_order': 'asc'}
    data = client.get('/report/api/in_detail', query_string=query).get_json()
    assert data['total'] == 2 and len(data['data']) == 1
    assert data['data'][0]['contract_no'] == 'C-001'
    assert data['summary']['quantity'] == 3
    response = client.get('/report/api/in_detail', query_string={**query, 'export': 'excel'})
    assert response.status_code == 200
    rows = list(load_workbook(io.BytesIO(response.data)).active.values)
    header = rows[0]
    contract = header.index('合同编号')
    project = header.index('工程名称')
    assert [(r[contract], r[project]) for r in rows[1:]] == [
        ('C-001', '一号工程'), ('C-002', '二号工程')]
    with wms.app.test_request_context('/report/api/in_detail', query_string=query):
        filters = wms._build_report_filters()
        rows = wms._collect_in_detail_rows(filters)
        assert {r['contract_no'] for r in rows} == {'C-001', 'C-002'}
