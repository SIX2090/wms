"""Quantity display never exposes binary-float tails or writes inventory."""
from decimal import Decimal
import json
from pathlib import Path
import re
from types import SimpleNamespace as NS

import pytest
from sqlalchemy import event

import app as wms
import utils
from app import app, db, Material, StockTransaction, User, Warehouse


@pytest.mark.parametrize('value,expected', [
    (1.2 - .3 - .5, '0.4'), (.1 + .2, '0.3'),
    (1.2345, '1.2345'), (Decimal('2.3400'), '2.34'),
    (0.0001, '0.0001'), (-.00000000000001, '0'),
    (.1 + .2 - .3, '0'), (99999999.99, '99999999.99'),
    (0, '0'), (12.0, '12'), (-1.2 + .3 + .5, '-0.4'),
    (None, ''), ('', ''), (float('nan'), ''), (float('inf'), ''),
])
def test_format_quantity(value, expected):
    formatter = getattr(utils, 'format_quantity', None)
    assert callable(formatter), 'a shared display formatter is required'
    assert formatter(value) == expected


@pytest.fixture()
def quantity_case(monkeypatch, tmp_path):
    monkeypatch.setitem(app.config, 'TESTING', True)
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', False)
    monkeypatch.setattr(app, 'static_folder', str(tmp_path))
    with app.app_context():
        assert str(db.engine.url) == 'sqlite:///:memory:'
        db.session.remove(); db.drop_all(); db.create_all()
        user = User(username='quantity-fixture', role='admin', password_hash='unused', must_change_password=False)
        a = Warehouse(code='Q-A', name='数量甲仓', is_default=True, status='active')
        b = Warehouse(code='Q-B', name='数量乙仓', status='active')
        material = Material(code='207005', name='浮点展示测试', stock=1.2 - .3 - .5, min_stock=0)
        other = Material(code='Q-OTHER', name='另一仓物料', stock=.1 + .2)
        db.session.add_all([user, a, b, material, other]); db.session.flush()
        for value in [1.2, -.3, -.5]:
            db.session.add(StockTransaction(material_id=material.id, warehouse_id=a.id, location=a.name,
                                           quantity=value, transaction_type='in' if value > 0 else 'out'))
        for value in [.1, .2]:
            db.session.add(StockTransaction(material_id=other.id, warehouse_id=None, location=b.name,
                                           quantity=value, transaction_type='in'))
        db.session.commit()
        ids = dict(uid=user.id, mid=material.id, other=other.id, a=a.id, b=b.id)
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'], session['_fresh'] = str(ids['uid']), True
    yield client, ids
    with app.app_context():
        db.session.remove(); db.drop_all()


def test_material_page_renders_clean_stock_without_mutating_ledgers(quantity_case):
    client, ids = quantity_case
    with app.app_context():
        before = db.session.get(Material, ids['mid']).stock
        engine = db.engine
    writes = []
    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().split()[0].upper() in {'INSERT', 'UPDATE', 'DELETE', 'ALTER', 'CREATE', 'DROP'}:
            writes.append(statement)
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        response = client.get('/material?search=207005')
        assert response.status_code == 200
        cell = re.search(r'<td data-column-key="stock"[^>]*>(.*?)</td>', response.text, re.S)[1].strip()
        assert cell == '0.4'
        assert not writes
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    with app.app_context():
        assert db.session.get(Material, ids['mid']).stock == before
        assert StockTransaction.query.count() == 5


def test_query_payloads_clean_tails_keep_numbers_and_warehouse_boundaries(quantity_case):
    client, ids = quantity_case
    with app.app_context():
        material = db.session.get(Material, ids['mid'])
        for serializer in [utils.serialize_material, utils.serialize_material_legacy, wms.api_material_payload]:
            payload = serializer(material)
            assert payload['stock'] == .4
            assert isinstance(payload['stock'], (int, float))
        assert wms.api_material_payload(material, warehouse=db.session.get(Warehouse, ids['a']))['stock'] == .4
        assert wms.api_material_payload(material, warehouse=db.session.get(Warehouse, ids['b']))['stock'] == 0
    for code, warehouse, expected in [('207005','Q-A',.4), ('207005','Q-B',0), ('Q-OTHER','Q-B',.3)]:
        response = client.get('/api/material/info', query_string={'code':code,'warehouse':warehouse})
        assert response.status_code == 200 and response.json['data']['stock'] == expected
    # Label identity and real stock fields use the same clean number; no print job is created.
    response = client.get('/label/batch_print', query_string={'ids':ids['mid']})
    materials = json.loads(re.search(r'var MATERIALS\s*=\s*(.*?);', response.text)[1])
    assert materials[0]['stock'] == '0.4'
    from routes.print_queue import _material_label_data
    with app.app_context():
        assert _material_label_data(db.session.get(Material, ids['mid']))['stock'] == '0.4'


def test_excel_general_hides_binary_tails_without_changing_currency_or_formula_behavior():
    from openpyxl import Workbook
    from services.report_print_preview import _display_value
    book = Workbook()
    cell = book.active['A1']
    cell.value = 1.2 - .3 - .5
    assert _display_value(cell) == '0.4'
    cell.value = 1.2345
    assert _display_value(cell) == '1.2345'
    cell.number_format = '0.00'
    assert _display_value(cell) == '1.23'
    book.close()


@pytest.mark.parametrize('template,expression', [
    ('material.html','mat.stock'), ('material.html','mat.min_stock'),
    ('alert.html','material.stock'), ('alert.html','material.min_stock'),
    ('alert.html','material.safety_stock'), ('print_label.html','material.stock'),
    ('stock_query.html','material.min_stock'), ('ai_inventory_health.html','row.current_stock'),
    ('ai_replenishment.html','row.current_stock'), ('ai_replenishment_smart.html','row.current_stock'),
    ('print_in.html','item.quantity'), ('print_out.html','item.quantity'),
    ('after_sale_out_detail.html','item.quantity'), ('sales_order_detail.html','item.quantity'),
    ('ai_document_job_detail.html','item.quantity'),
    ('sales_report.html','it.quantity'), ('sales_execution_report.html','row.quantity'),
    ('sales_price_analysis.html','row.quantity'), ('sales_reconciliation_report.html','row.shipped_qty'),
    ('purchase_request_detail.html','item.quantity'), ('subcontract_receive.html','receive.total_quantity'),
])
def test_real_template_quantity_cells_never_render_raw_float(template, expression):
    source = (Path(__file__).resolve().parents[1] / 'app/templates' / template).read_text(encoding='utf-8')
    actual_expression = re.search(r'\{\{\s*\(?' + re.escape(expression) + r'\b[^{}]*\}\}', source)[0]
    name, attribute = expression.split('.')
    with app.app_context():
        rendered = app.jinja_env.from_string(actual_expression).render(**{name:NS(**{attribute:1.2 - .3 - .5})})
    assert rendered == '0.4'
