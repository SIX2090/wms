"""库存周转率页面、按仓按月归集、分类、边界及全量输出。"""
from contextlib import contextmanager
from datetime import date, datetime
from io import BytesIO

import pytest
from openpyxl import load_workbook

import app as m
from services.material_movement_report import warehouse_material_balances
from tests.test_bug_2026_10_26_003_monthly_report import monthly


@contextmanager
def load_workbook_context(response):
    wb = load_workbook(BytesIO(response.data), read_only=True)
    try:
        yield wb.active
    finally:
        wb.close()


def params(case, **changes):
    return {'warehouse_id': case['a'], 'start_month': '2026-09', 'end_month': '2026-10', **changes}


def query(case, **changes):
    result = case['client'].get('/report/api/inventory_turnover', query_string=params(case, **changes))
    assert result.status_code == 200, result.get_json()
    return result.get_json()


def test_build_inventory_turnover_report(monthly):
    payload = query(monthly, standard_days='60')
    rows = {r['material_code']: r for r in payload['data']}
    a = rows['MONTH-A']
    assert [a[k] for k in ('opening_quantity', 'closing_quantity', 'average_quantity', 'out_quantity')] == [100, 85, 92.5, 40]
    assert a['turnover_rate'] == round(40 / 92.5, 4)
    assert a['turnover_days'] == round(61 * 92.5 / 40, 2)
    assert a['difference_days'] == round(61 * 92.5 / 40 - 60, 2)
    assert rows['MONTH-CARRY']['turnover_rate'] == 0
    assert rows['MONTH-CARRY']['turnover_days'] is None
    assert rows['MONTH-ZERO']['turnover_rate'] is None
    assert rows['MONTH-ZERO']['difference_days'] is None
    assert rows['MONTH-LEGACY']['closing_quantity'] == 5
    assert 'MONTH-FUTURE' not in rows and 'MONTH-B' not in rows
    assert query(monthly, warehouse_id=monthly['empty'])['total'] == 0
    assert [r['material_code'] for r in query(monthly, warehouse_id=monthly['b'])['data']] == ['MONTH-B']
    assert query(monthly, material_code='MONTH-A')['data'][0]['difference_days'] is None
    pages = query(monthly, page_size=1, page=2)
    assert pages['summary'] == payload['summary'] and len(pages['data']) == 1


def test_turnover_adjustments_category_price_and_outputs(monthly):
    with m.app.app_context():
        parent = m.MaterialCategory(code='P', name='测试分类')
        child = m.MaterialCategory(code='C', name='测试子类', parent=parent)
        m.db.session.add_all([parent, child])
        mat = m.db.session.get(m.Material, monthly['mats']['A'])
        mat.category = child
        for kind, qty in [('transfer_out', -3), ('adjustment_out', -2)]:
            m.db.session.add(m.StockTransaction(material_id=mat.id, warehouse_id=monthly['a'],
                quantity=qty, transaction_type=kind, created_at=datetime(2026, 10, 2)))
        m.set_system_setting('price_dimension_enabled', '0')
        m.db.session.commit()
        cat = parent.id
    filters = params(monthly, category_id=cat, standard_days='30.25')
    data = query(monthly, **filters)['data']
    assert len(data) == 1
    assert data[0]['category'] == '测试子类' and data[0]['out_quantity'] == 45
    assert 'inventory_amount' not in data[0]
    assert all(r['category'] == '未分类' for r in query(monthly, category_id='uncategorized')['data'])
    first_print = monthly['client'].get('/report/inventory_turnover/print_excel', query_string=filters)
    assert first_print.status_code == 200
    with load_workbook_context(first_print) as sheet:
        assert not any('期末库存金额（参考）' in cells for cells in sheet.values)
    with m.app.app_context():
        m.set_system_setting('price_dimension_enabled', '1')
        m.db.session.commit()
    row = query(monthly, **filters)['data'][0]
    assert row['inventory_amount'] == 80 * 99
    for url in ('/report/api/inventory_turnover', '/report/inventory_turnover/print_excel'):
        response = monthly['client'].get(url, query_string={**filters, 'export': 'excel', 'page_size': 1})
        assert response.status_code == 200
        with load_workbook_context(response) as sheet:
            values = list(sheet.values)
            assert any('期末库存金额（参考）' in cells for cells in values)
            item = next(v for v in values if 'MONTH-A' in v)
            assert 30.25 in item and row['difference_days'] in item
            assert not any('MONTH-METRE' in v for v in values)


def test_turnover_filters(monthly):
    client = monthly['client']
    for path in ('/report', '/report/view/inventory_turnover'):
        response = client.get(path)
        assert response.status_code == 200
        assert '库存周转率报表' in response.get_data(as_text=True)
    for name in ('start_month', 'end_month', 'standard_days', 'category_id'):
        assert f'name="{name}"' in response.get_data(as_text=True)
    for changes in ({'standard_days':'-1'}, {'standard_days':'NaN'}, {'category_id':'x'},
                    {'end_month':'2026-08'}, {'start_month':'xxxx-99'}, {'warehouse_id':'999999'}):
        assert client.get('/report/api/inventory_turnover', query_string=params(monthly, **changes)).status_code == 400


def test_warehouse_material_balances(monthly):
    with m.app.app_context():
        start, end = date(2026, 9, 1), date(2026, 10, 31)
        scope = dict(warehouse_id=monthly['a'], start_date=start, end_date=end, material_code='MONTH-A')
        warehouse, materials, balances = warehouse_material_balances(scope)
        mid = monthly['mats']['A']
        assert warehouse.id == monthly['a'] and set(materials) == {mid}
        assert balances[mid] == [100, 25, 40]
        with pytest.raises(ValueError, match='结束日期不能早于开始日期'):
            warehouse_material_balances(dict(scope, start_date=end, end_date=start))
