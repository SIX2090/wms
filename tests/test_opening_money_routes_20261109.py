"""Actual WMS opening routes on the already verified owned LPAC/memory fixture."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from tests.test_money_route_synthetic_20261109 import money_case
from tests.document_revision_client import document_post


def seed(case, enabled, quantity=1, price=5, amount=7.77):
    w = case.w
    if price is None or amount is None:
        # Only this new, proven memory DB models the older nullable schema.
        # Current model's NOT NULL constraints must not be weakened in production.
        from sqlalchemy import MetaData
        from sqlalchemy.schema import CreateTable, DropTable
        assert w.db.engine.url.database == ':memory:'
        legacy = w.OpeningStock.__table__.to_metadata(MetaData())
        # Foreign-key targets remain the actual synthetic metadata tables.
        for table in w.db.metadata.sorted_tables:
            if table.name != legacy.name:
                table.to_metadata(legacy.metadata)
        legacy.c.price.nullable = True
        legacy.c.amount.nullable = True
        assert w.OpeningStock.query.count() == 0
        w.db.session.remove()
        with w.db.engine.begin() as connection:
            connection.execute(DropTable(w.OpeningStock.__table__))
            connection.execute(CreateTable(legacy))
    w.set_system_setting('location_management_enabled', '1' if enabled else '0')
    docs = [w.OpeningStockDoc(doc_no='S-HISTORY-' + str(index), date=date.today(),
                              warehouse_id=warehouse, status='active', operator_id=case.ids['user'])
            for index, warehouse in enumerate((case.wh1, case.wh2), 1)]
    w.db.session.add_all(docs)
    w.db.session.flush()
    lines = [w.OpeningStock(doc_id=docs[0].id, material_id=case.ids['material'], warehouse_id=case.wh1,
                            date=date.today(), quantity=quantity, price=price, amount=amount,
                            location=case.warehouse if enabled else '', operator_id=case.ids['user']),
             w.OpeningStock(doc_id=docs[1].id, material_id=case.ids['material'], warehouse_id=case.wh2,
                            date=date.today(), quantity=2, price=5, amount=0,
                            location=w.db.session.get(w.Warehouse, case.wh2).name if enabled else '',
                            operator_id=case.ids['user'])]
    w.db.session.add_all(lines)
    w.db.session.flush()
    if price is None:
        lines[0].price = None
    if amount is None:
        lines[0].amount = None
    w.db.session.flush()
    w.db.session.get(w.Material, case.ids['material']).stock = quantity + 2
    for line in lines:
        w.LocationInventory.query.filter_by(warehouse_id=line.warehouse_id).one().quantity = line.quantity
        txn = w.StockTransaction.query.filter_by(warehouse_id=line.warehouse_id).one()
        txn.quantity = line.quantity
        txn.transaction_type = 'opening'
        txn.reference_type = 'opening_stock'
        txn.reference_id = line.id
    w.db.session.commit()
    return SimpleNamespace(doc=docs[0].id, line=lines[0].id, other_line=lines[1].id, enabled=enabled)


def state(case):
    w = case.w
    return (w.db.session.get(w.Material, case.ids['material']).stock,
            w.db.session.query(w.LocationInventory.warehouse_id, w.LocationInventory.quantity).order_by(w.LocationInventory.warehouse_id).all(),
            w.db.session.query(w.StockTransaction.warehouse_id, w.StockTransaction.quantity).order_by(w.StockTransaction.id).all(),
            w.db.session.query(w.OpeningStock.id, w.OpeningStock.quantity, w.OpeningStock.price, w.OpeningStock.amount).order_by(w.OpeningStock.id).all())


def payload(case, ident, **changes):
    line = case.w.db.session.get(case.w.OpeningStock, ident.line)
    row = {'line_id': ident.line, 'material_id': case.ids['material'], 'warehouse_id': case.wh1,
           'quantity': case.w.normalize_stock_quantity(line.quantity or 0),
           'price': case.w.round_to_2_decimals(line.price or 0), 'remark': '只改合成备注',
           'location': case.warehouse if ident.enabled else ''}
    row.update(changes)
    return {'doc_id': ident.doc, 'date': date.today().isoformat(), 'warehouse_id': case.wh1,
            'remark': '合成表头备注', 'items': [row]}


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('quantity,price,amount', [(1, 5, 7.77), (1, 5, 0), (1.2345, 1.235, 7.77), (1, None, 7.77)])
@pytest.mark.parametrize('endpoint', ['/opening_stock/save', '/opening_stock/batch_save'])
def test_document_metadata_save_preserves_all_existing_financial_values(money_case, enabled, quantity, price, amount, endpoint):
    c = money_case
    ident = seed(c, enabled, quantity, price, amount)
    before = state(c)
    response = document_post(c.client, endpoint, json=payload(c, ident))
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    c.w.db.session.remove()
    assert state(c) == before
    assert c.w.db.session.get(c.w.OpeningStock, ident.line).remark == '只改合成备注'


@pytest.mark.parametrize('enabled', [False, True])
def test_changed_values_use_decimal_amount_and_only_change_the_owning_warehouse(money_case, enabled):
    c = money_case
    ident = seed(c, enabled)
    response = document_post(c.client, '/opening_stock/save', json=payload(c, ident, quantity=1.15, price=3.5))
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    c.w.db.session.remove()
    line = c.w.db.session.get(c.w.OpeningStock, ident.line)
    assert (line.quantity, line.price, Decimal(str(line.amount))) == (1.15, 3.5, Decimal('4.03'))
    assert c.w.db.session.get(c.w.Material, c.ids['material']).stock == pytest.approx(3.15)
    assert c.w.get_warehouse_stock_quantities(c.w.db.session.get(c.w.Warehouse, c.wh1))[c.ids['material']] == 1.15
    assert c.w.get_warehouse_stock_quantities(c.w.db.session.get(c.w.Warehouse, c.wh2))[c.ids['material']] == 2
    other = c.w.db.session.get(c.w.OpeningStock, ident.other_line)
    assert (other.quantity, other.price, other.amount) == (2, 5, 0)


@pytest.mark.parametrize('enabled', [False, True])
def test_foreign_line_id_cannot_be_silently_reinterpreted(money_case, enabled):
    c = money_case
    ident = seed(c, enabled)
    before = state(c)
    response = document_post(c.client, '/opening_stock/save', json=payload(c, ident, line_id=ident.other_line))
    assert response.status_code == 400, response.json
    c.w.db.session.remove()
    assert state(c) == before


@pytest.mark.parametrize('enabled', [False, True])
def test_client_saved_amount_is_not_authoritative(money_case, enabled):
    c = money_case
    ident = seed(c, enabled)
    before = state(c)
    response = document_post(c.client, '/opening_stock/save',
                             json=payload(c, ident, saved_amount=999999, saved_quantity=888, saved_price=777))
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    c.w.db.session.remove()
    assert state(c) == before


@pytest.mark.parametrize('enabled', [False, True])
def test_single_row_form_metadata_save_preserves_history(money_case, enabled):
    c = money_case
    ident = seed(c, enabled)
    before = state(c)
    response = document_post(c.client, '/opening_stock/edit/' + str(ident.line), data={
        'material_id': c.ids['material'], 'warehouse_id': c.wh1, 'quantity': '1', 'price': '5',
        'date': date.today().isoformat(), 'location': c.warehouse if enabled else '', 'remark': '只改合成备注'})
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    c.w.db.session.remove()
    assert state(c) == before


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('quantity,price', [(1, 5), (1.2345, 1.235)])
def test_absent_amount_is_derived_without_rounding_away_stored_components(money_case, enabled, quantity, price):
    c = money_case
    ident = seed(c, enabled, quantity, price, None)
    before = state(c)
    response = document_post(c.client, '/opening_stock/save', json=payload(c, ident))
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    c.w.db.session.remove()
    after = state(c)
    assert after[:3] == before[:3]
    line = c.w.db.session.get(c.w.OpeningStock, ident.line)
    assert (line.quantity, line.price) == (quantity, price)
    assert line.amount == c.w.round_money_product(quantity, price)
    other = c.w.db.session.get(c.w.OpeningStock, ident.other_line)
    assert (other.quantity, other.price, other.amount) == (2, 5, 0)


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('quantity,price', [(1, 5), (1.2345, 1.235)])
def test_native_remark_only_edit_preserves_history_with_real_bearer_and_revision(money_case, enabled, quantity, price):
    c = money_case
    ident = seed(c, enabled, quantity, price, 7.77)
    response = c.client.post('/api/login', json={'username': 'bom-audit', 'password': 'fixture-only'})
    assert response.status_code == 200, response.json
    headers = {'Authorization': 'Bearer ' + response.json['data']['token']}
    response = c.client.get('/api/opening_stock', query_string={'warehouse_id': c.wh1}, headers=headers)
    assert response.status_code == 200, response.json
    listed = next(row for row in response.json['data']['items'] if row['id'] == ident.line)
    before = state(c)
    response = c.client.post('/api/opening_stock/' + str(ident.line),
                             json={'remark': '只改合成手机备注', 'revision': listed['revision']}, headers=headers)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    c.w.db.session.remove()
    assert state(c) == before
    assert c.w.db.session.get(c.w.OpeningStock, ident.line).remark == '只改合成手机备注'


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('bad', [{'quantity': 'nan'}, {'price': 'nan'}, {'quantity': '1e100'}, {'price': '1e100'}])
def test_invalid_form_numbers_are_rejected_before_any_balance_change(money_case, enabled, bad):
    c = money_case
    ident = seed(c, enabled)
    before = state(c)
    values = {'material_id': c.ids['material'], 'warehouse_id': c.wh1, 'quantity': '1', 'price': '5',
              'date': date.today().isoformat(), 'location': c.warehouse if enabled else '', 'remark': '坏数值不保存'}
    values.update(bad)
    response = document_post(c.client, '/opening_stock/edit/' + str(ident.line), data=values)
    assert response.status_code == 400, response.json
    c.w.db.session.remove()
    assert state(c) == before


@pytest.mark.parametrize('enabled', [False, True])
def test_legacy_replace_without_line_id_retains_explicit_recalculation(money_case, enabled):
    c = money_case
    ident = seed(c, enabled)
    before = state(c)
    response = document_post(c.client, '/opening_stock/save', json=payload(c, ident, line_id=None))
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    c.w.db.session.remove()
    assert state(c)[:3] == before[:3]
    line = c.w.db.session.get(c.w.OpeningStock, ident.line)
    assert (line.quantity, line.price, line.amount) == (1, 5, 5)


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('bad', [{'quantity': 'nan'}, {'price': 'nan'}, {'quantity': '1e100'}, {'price': '1e100'},
                                 {'quantity': -1}, {'price': -1}])
def test_native_invalid_numbers_leave_every_stock_view_unchanged(money_case, enabled, bad):
    c = money_case
    ident = seed(c, enabled)
    response = c.client.post('/api/login', json={'username': 'bom-audit', 'password': 'fixture-only'})
    assert response.status_code == 200, response.json
    headers = {'Authorization': 'Bearer ' + response.json['data']['token']}
    response = c.client.get('/api/opening_stock', query_string={'warehouse_id': c.wh1}, headers=headers)
    assert response.status_code == 200, response.json
    listed = next(row for row in response.json['data']['items'] if row['id'] == ident.line)
    before = state(c)
    response = c.client.post('/api/opening_stock/' + str(ident.line),
                             json=dict(bad, revision=listed['revision']), headers=headers)
    assert response.status_code == 400, response.json
    c.w.db.session.remove()
    assert state(c) == before


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('bad', [{'quantity': 'nan'}, {'price': 'nan'}, {'quantity': '1e100'}, {'price': '1e100'},
                                 {'quantity': -1}, {'price': -1}])
def test_native_create_invalid_numbers_roll_back_the_entire_request(money_case, enabled, bad):
    c = money_case
    ident = seed(c, enabled)
    response = c.client.post('/api/login', json={'username': 'bom-audit', 'password': 'fixture-only'})
    assert response.status_code == 200, response.json
    headers = {'Authorization': 'Bearer ' + response.json['data']['token']}
    before = state(c)
    doc_count = c.w.OpeningStockDoc.query.count()
    code = c.w.db.session.get(c.w.Material, c.ids['material']).code
    body = {'warehouse_code': c.w.db.session.get(c.w.Warehouse, c.wh1).code,
            'date': date.today().isoformat(),
            'lines': [dict({'material_code': code, 'quantity': 1, 'price': 5}, **bad)]}
    response = c.client.post('/api/opening_stock', json=body, headers=headers)
    assert response.status_code == 400, response.json
    c.w.db.session.remove()
    assert state(c) == before
    assert c.w.OpeningStockDoc.query.count() == doc_count


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('quantity,price,changes,expected', [
    (1.2345, 5, {'price': 6}, (1.2345, 6, 7.41)),
    (1, 1.235, {'quantity': 2}, (2, 1.235, 2.47))])
def test_editing_one_component_preserves_the_other_stored_component(money_case, enabled, quantity, price, changes, expected):
    c = money_case
    ident = seed(c, enabled, quantity, price)
    before = state(c)
    response = document_post(c.client, '/opening_stock/save', json=payload(c, ident, **changes))
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    c.w.db.session.remove()
    line = c.w.db.session.get(c.w.OpeningStock, ident.line)
    assert (line.quantity, line.price, line.amount) == expected
    if 'quantity' not in changes:
        assert state(c)[:3] == before[:3]
    else:
        assert c.w.db.session.get(c.w.Material, c.ids['material']).stock == 4
        assert c.w.get_warehouse_stock_quantities(c.w.db.session.get(c.w.Warehouse, c.wh1))[c.ids['material']] == 2
        assert c.w.get_warehouse_stock_quantities(c.w.db.session.get(c.w.Warehouse, c.wh2))[c.ids['material']] == 2
