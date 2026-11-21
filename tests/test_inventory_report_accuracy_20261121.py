"""End-to-end reporting contracts on an isolated, two-warehouse database."""
from datetime import date, datetime
from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy import event
from werkzeug.security import generate_password_hash

import app as m


@pytest.fixture
def reports(monkeypatch):
    monkeypatch.setitem(m.app.config, 'TESTING', True)
    monkeypatch.setitem(m.app.config, 'WTF_CSRF_ENABLED', False)
    with m.app.app_context():
        assert m.db.engine.url.get_backend_name() == 'sqlite'
        assert m.db.engine.url.database in (None, '', ':memory:')
        m.db.session.remove()
        m.db.drop_all()
        m.db.create_all()
        a = m.Warehouse(name='甲仓', code='WA', status='active', is_default=True)
        b = m.Warehouse(name='乙仓', code='WB', status='active')
        ea, meter = m.Unit(code='EA', name='件'), m.Unit(code='M', name='米')
        user = m.User(username='report-reader', role='warehouse', must_change_password=False,
                      password_hash=generate_password_hash('fixture'))
        m.db.session.add_all([a, b, ea, meter, user])
        m.db.session.flush()
        x = m.Material(code='M01', name='件料', unit_id=ea.id)
        y = m.Material(code='M010', name='米料', unit_id=meter.id)
        m.db.session.add_all([x, y])
        m.db.session.flush()
        def document(header, number, status, kind, **fields):
            order = header(order_no=number, date=date(2026, 9, 2), status=status,
                           business_type=kind, warehouse=a.name, remark='单头', **fields)
            m.db.session.add(order)
            m.db.session.flush()
            return order

        receipt = document(m.InOrder, 'IN1', 'completed', '采购入库')
        draft = document(m.InOrder, 'IN2', 'pending', '产品入库')
        issue = document(m.OutOrder, 'OUT1', 'completed', '领料单', customer='Z')
        other = document(m.OutOrder, 'OUT2', 'pending', '领料单', customer='A')
        for order, material, quantity, contract in [
            (receipt, x, 8, 'HA'), (receipt, x, 2, 'HB'), (draft, y, 4, ''),
            (issue, x, 3, ''), (other, y, 4, ''),
        ]:
            item = (m.InOrderItem(in_order_id=order.id) if isinstance(order, m.InOrder)
                    else m.OutOrderItem(out_order_id=order.id))
            item.material_id, item.quantity, item.price, item.amount = material.id, quantity, 2, quantity * 2
            item.remark, item.contract_no = '行备注', contract
            m.db.session.add(item)
        for mat, ref, number, qty, day in [
            (x, 'in_order', receipt.id, 8, 3), (x, 'in_order', receipt.id, 2, 3),
            (x, 'out_order', issue.id, -3, 9), (y, None, None, 5, 3),
        ]:
            m.db.session.add(m.StockTransaction(material_id=mat.id, quantity=qty, warehouse_id=a.id,
                                               transaction_type='in' if qty > 0 else 'out',
                                               reference_type=ref, reference_id=number,
                                               created_at=datetime(2026, 9, day)))
        m.db.session.commit()
        ids = dict(warehouse_id=a.id, material_id=x.id)
    client = m.app.test_client()
    assert client.post('/login', data={'username': 'report-reader', 'password': 'fixture'}).status_code == 302
    return client, ids


def test_single_material_count_contract_and_backdated_order(reports):
    client, ids = reports
    base = dict(start_date='2026-09-01', end_date='2026-09-02', warehouse_id=ids['warehouse_id'])
    for identity in ({'material_code': 'M01'}, {'material_id': ids['material_id']}):
        data = client.get('/report/api/ledger', query_string={**base, **identity}).get_json()
        assert data['summary'] == {'count': 3, 'quantity': 13, 'amount': 7}
        rows = data['data']
        assert {row['material_code'] for row in rows} == {'M01'}
        assert rows[-1]['reference_type'] == '本期合计'
        assert [r['balance_quantity'] for r in rows] == [0, 8, 10, 7, 7]
        assert all('多合同' in r['contract_no'] for r in rows if r['reference_no'] == 'IN1')
    assert client.get('/report/api/ledger', query_string={**ids, 'material_code': 'M010'}).status_code == 400
    for invalid_id in ('bad', '0', '99999999999999999999'):
        assert client.get('/report/api/ledger', query_string={**ids, 'material_id': invalid_id, 'material_code': 'M01'}).status_code == 400


def test_prior_history_is_complete_even_above_detail_limit(reports, monkeypatch):
    client, ids = reports
    monkeypatch.setattr(m, 'LEDGER_ROW_LIMIT', 1)
    data = client.get('/report/api/ledger', query_string={**ids, 'start_date': '2026-09-03'}).get_json()
    assert data['summary'] == {'count': 0, 'quantity': 0, 'amount': 7}
    assert [r['balance_quantity'] for r in data['data']] == [7, 7]
    for url in ('/report/api/ledger', '/report/ledger/print_excel', '/report/ledger/print_preview'):
        assert client.get(url, query_string=ids).status_code == 400


@pytest.mark.parametrize(('kind', 'quantity'), [('in_detail', 10), ('out_detail', 3)])
def test_posted_by_default_all_units_and_row_remarks(reports, kind, quantity):
    client, ids = reports
    url = '/report/api/' + kind
    posted = client.get(url, query_string={'warehouse_id': ids['warehouse_id']}).get_json()
    assert posted['summary']['quantity'] == quantity
    assert {r['status'] for r in posted['data']} == {'completed'}
    assert all((r['remark'], r['item_remark']) == ('单头', '行备注') for r in posted['data'])
    all_rows = client.get(url, query_string={'warehouse_id': ids['warehouse_id'], 'status': 'all', 'sort_field': 'customer'}).get_json()
    assert all_rows['summary']['quantity'] is None
    assert {r['unit']: r['quantity'] for r in all_rows['summary']['unit_totals']} == {'件': quantity, '米': 4}
    if kind == 'out_detail':
        assert [r['customer'] for r in all_rows['data']] == ['A', 'Z']
    for params in [{'warehouse_id': 'abc'}, {'warehouse_id': '+1'}, {'warehouse_id': -1},
                   {'warehouse_id': ids['warehouse_id'], 'start_date': '2026-10-01', 'end_date': '2026-09-01'}]:
        for endpoint in (url, '/report/' + kind + '/print_excel', '/report/' + kind + '/print_preview'):
            assert client.get(endpoint, query_string=params).status_code == 400


def test_legacy_transfer_and_subcontract_receipts_share_warehouse_ownership(reports):
    client, ids = reports
    with m.app.app_context():
        t = m.TransferOrder(transfer_no='T1', date=date(2026, 10, 2), from_warehouse='甲仓', to_warehouse='乙仓',
                            from_location='', to_location='')
        issue = m.SubcontractIssue(issue_no='SI', warehouse='甲仓', date=t.date, status='completed')
        receipt = m.SubcontractReceive(receive_no='SR', warehouse='甲仓', date=t.date, status='completed')
        m.db.session.add_all([t, issue, receipt])
        m.db.session.flush()
        for qty, ref, doc, memo in [(-5, 'transfer', t, '调拨到 乙仓'), (5, 'transfer', t, '来自 甲仓'),
                                    (-5, 'transfer', t, '反提交调拨 T1'), (5, 'transfer', t, '反提交调拨 T1'),
                                    (-4, 'subcontract_issue', issue, ''), (11, 'subcontract_receive', receipt, '')]:
            kind = ('transfer_out' if qty < 0 else 'transfer_in') if ref == 'transfer' else ref
            m.db.session.add(m.StockTransaction(material_id=ids['material_id'], transaction_type=kind,
                                               quantity=qty, remark=memo, reference_type=ref, reference_id=doc.id))
        m.db.session.commit()
        t_id = t.id
        wid_b = m.Warehouse.query.filter_by(code='WB').one().id
    with m.app.app_context():
        unresolved = m.StockTransaction(material_id=ids['material_id'], transaction_type='transfer_out',
                                        reference_type='transfer', reference_id=t_id, quantity=-1)
        m.db.session.add(unresolved)
        m.db.session.commit()
        response = client.get('/report/api/ledger', query_string=ids)
        assert response.status_code == 400 and '归属待核' in response.get_json()['msg']
        unresolved.reference_id = None
        m.db.session.commit()
        orphan = client.get('/report/api/ledger', query_string=ids)
        assert orphan.status_code == 400 and '归属待核' in orphan.get_json()['msg']
        m.db.session.delete(unresolved)
        m.db.session.commit()
    for wid, expected in [(ids['warehouse_id'], (4, 25, 14)), (wid_b, (2, 10, 0))]:
        data = client.get('/report/api/ledger', query_string={**ids, 'warehouse_id': wid, 'start_date': '2026-10-01'}).get_json()
        summary = data['summary']
        assert (summary['count'], summary['quantity'], summary['amount']) == expected


def test_historical_name_code_collision_rejects_ambiguous_document_scope(reports):
    client, ids = reports
    with m.app.app_context():
        b = m.Warehouse.query.filter_by(code='WB').one()
        m.db.session.execute(m.Warehouse.__table__.update().where(m.Warehouse.id == b.id).values(code='甲仓'))
        m.db.session.commit()
        other_id = b.id
    for wid in (ids['warehouse_id'], other_id):
        for kind in ('in_detail', 'out_detail', 'purchase_order_execution', 'supplier_purchase_summary', 'material_purchase_summary'):
            response = client.get('/report/api/'+kind, query_string={'warehouse_id': wid})
            assert response.status_code == 400 and '归属待核' in response.get_json()['msg']


def test_source_numbers_loaded_in_batches(reports):
    client, ids = reports
    with m.app.app_context():
        for index in range(32):
            order = m.InOrder(order_no=f'BATCH-{index}', date=date(2026, 9, 2), warehouse='甲仓', status='completed')
            m.db.session.add(order)
            m.db.session.flush()
            m.db.session.add(m.StockTransaction(material_id=ids['material_id'], warehouse_id=ids['warehouse_id'],
                reference_type='in_order', reference_id=order.id, transaction_type='in', quantity=1))
        m.db.session.commit()
        selects = []
        def count(conn, cursor, statement, params, context, executemany):
            if 'FROM in_order ' in statement and 'WHERE in_order.id = ?' in statement:
                selects.append(params)
        event.listen(m.db.engine, 'before_cursor_execute', count)
        try:
            rows = client.get('/report/api/ledger', query_string={**ids, 'material_code': 'M01', 'page_size': 100}).get_json()['data']
            assert [r['reference_no'] for r in rows].count('IN1') == 2
            assert len({r['reference_no'] for r in rows if r['reference_no'].startswith('BATCH-')}) == 32
            assert selects == []
        finally:
            event.remove(m.db.engine, 'before_cursor_execute', count)


@pytest.mark.parametrize('kind', ['in_detail', 'out_detail'])
def test_print_preview_and_template_download_use_same_status_and_prices(reports, kind):
    client, ids = reports
    for enabled in (False, True):
        with m.app.app_context():
            m.set_system_setting('price_dimension_enabled', '1' if enabled else '0')
            m.db.session.commit()
        args = {'warehouse_id': ids['warehouse_id'], 'status': 'all'}
        preview = client.get('/report/'+kind+'/print_preview', query_string=args)
        download = client.get('/report/'+kind+'/print_excel', query_string=args)
        assert preview.status_code == download.status_code == 200
        rows = list(load_workbook(BytesIO(download.data)).active.values)
        assert any('已完成' in row for row in rows) and any('待处理' in row for row in rows)
        assert '已完成' in preview.get_data(as_text=True) and '待处理' in preview.get_data(as_text=True)
        headers = next(row for row in rows if '物料编码' in row)
        assert '明细备注' in headers
        assert ('单价' in headers) is enabled

@pytest.mark.parametrize(('kind', 'pieces'), [('in_detail', 10), ('out_detail', 3)])
def test_resolve_report_print_layout(reports, tmp_path, monkeypatch, kind, pieces):
    client, ids = reports
    monkeypatch.setattr(m.app, 'static_folder', str(tmp_path))
    template_path = tmp_path / 'uploads' / 'print_templates' / 'custom.xlsx'
    template_path.parent.mkdir(parents=True)
    workbook = Workbook()
    workbook.active.append(['{item.material_code}', '{item.quantity}', '{item.status}', '{item.unit}'])
    workbook.active.append(['{total_quantity}', '{total_amount}'])
    workbook.save(template_path)
    with m.app.app_context():
        template = m.ExcelPrintTemplate(name='自定义合计', target_type='report',
            target_code='report_' + kind, template_type='excel',
            excel_template_path='/static/uploads/print_templates/custom.xlsx')
        m.db.session.add(template)
        m.db.session.commit()
        tid = template.id
    args = {'warehouse_id': ids['warehouse_id'], 'status': 'all', 'template_id': tid}
    for enabled in (False, True):
        with m.app.app_context():
            m.set_system_setting('price_dimension_enabled', '1' if enabled else '0')
            m.db.session.commit()
        preview = client.get(f'/report/{kind}/print_preview', query_string=args)
        download = client.get(f'/report/{kind}/print_excel', query_string=args)
        assert download.status_code == preview.status_code == 200
        totals = list(load_workbook(BytesIO(download.data)).active.values)[-1]
        expected = f'{pieces} 件 / 4 米'
        assert totals[0] == expected and expected in preview.get_data(as_text=True)
        assert totals[1] == ((pieces + 4) * 2 if enabled else None)
        if enabled:
            assert f'>{(pieces + 4) * 2}</td>' in preview.get_data(as_text=True)
    for wrong in ('abc', 999999):
        for kind_of_output in ('print_preview', 'print_excel'):
            assert client.get(f'/report/{kind}/{kind_of_output}', query_string={'warehouse_id': ids['warehouse_id'], 'template_id': wrong}).status_code == 400

def test_fractional_ledger_movements_match_stored_quantities(reports):
    client, ids = reports
    with m.app.app_context():
        m.db.session.add(m.StockTransaction(material_id=ids['material_id'], warehouse_id=ids['warehouse_id'],
                                          quantity=0.0001, transaction_type='in'))
        m.db.session.commit()
    data = client.get('/report/api/ledger', query_string=ids).get_json()
    assert data['summary'] == {'count': 4, 'quantity': 13.0001, 'amount': 7.0001}
    assert data['data'][-1]['in_quantity'] == 10.0001


@pytest.mark.parametrize('kind', ['in_detail', 'out_detail', 'ledger'])
def test_default_warehouse_must_be_submitted_by_caller(reports, kind):
    client, _ = reports
    for path, options in ((f'/report/api/{kind}', {}), (f'/report/api/{kind}', {'export': 'excel'}),
                          (f'/report/{kind}/print_excel', {}), (f'/report/{kind}/print_preview', {})):
        for params in ({}, {'warehouse_id': ''}, {'warehouse_id': '  '}):
            response = client.get(path, query_string={'material_code': 'M01', **options, **params})
            assert response.status_code == 400
            error = response.get_json()['msg'] if response.is_json else response.get_data(as_text=True)
            assert '请选择仓库' in error
