"""R2-ISSUE-006: only equal documents merit the duplicate warning."""
from datetime import date
from decimal import Decimal

import pytest

from tests.test_feat_2026_10_03_001_anomaly_duplicate_only import (
    wms_env, _make_in_order, _make_out_order, _mat, _sup, _login_client,
)


@pytest.fixture(params=['in', 'out'])
def pair(wms_env, request):
    w = wms_env
    if request.param == 'in':
        material = _mat(w)
        make = lambda number: _make_in_order(w, number, date.today(), .1, 2, material, supplier=_sup(w))
        detector = w._check_in_order_anomalies
        row_model = w.InOrderItem
        fk = 'in_order_id'
    else:
        material = _mat(w, 'FEAT1003001-OM')
        make = lambda number: _make_out_order(w, number, date.today(), .1, 2, material)
        detector = w._check_out_order_anomalies
        row_model = w.OutOrderItem
        fk = 'out_order_id'
    existing, candidate = make('EXACT-OLD'), make('EXACT-NEW')
    return w, existing, candidate, detector, row_model, fk


def check(pair):
    w, _, candidate, detector, _, _ = pair
    with w.db.session.no_autoflush:
        return detector(candidate)


@pytest.mark.parametrize('field,value', [
    ('quantity', .2), ('quantity', .005), ('quantity', 1.005),
    ('price', 3), ('amount', .3), ('contract_id', 99),
    ('contract_no', 'OTHER'), ('project_name', 'OTHER'),
    ('source_sales_order_item_id', 99),
])
def test_changed_line_does_not_warn(pair, field, value):
    setattr(pair[2].items[0], field, value)
    assert check(pair) == []


@pytest.mark.parametrize('field,value', [
    ('business_type', 'OTHER'), ('warehouse', '另一仓库'), ('location', '另一库位'),
    ('contract_id', 99), ('contract_no', 'OTHER'), ('project_name', 'OTHER'),
    ('source_sales_order_id', 99), ('purpose', 'OTHER'),
])
def test_changed_header_does_not_warn(pair, field, value):
    setattr(pair[2], field, value)
    assert check(pair) == []


@pytest.mark.parametrize('side', ['existing', 'candidate'])
def test_extra_line_even_same_material_is_not_an_equal_document(pair, side):
    w, old, new, _, model, fk = pair
    order = old if side == 'existing' else new
    row = model(**{fk: order.id}, material_id=order.items[0].material_id,
                quantity=.1, price=2, amount=.2)
    w.db.session.add(row)
    w.db.session.commit()
    assert check(pair) == []


def test_equal_lines_ignore_order_but_preserve_multiplicity(pair):
    w, old, new, _, model, fk = pair
    for order in (old, new):
        w.db.session.add(model(**{fk: order.id}, material_id=order.items[0].material_id,
                               quantity=.2, price=3, amount=.6))
    w.db.session.commit()
    new.items.reverse()
    result = check(pair)
    assert len(result) == 1
    assert result[0]['existing_order'] == old.order_no
    assert '2' in result[0]['msg']
    new.items[0].quantity = .1
    new.items[0].price = 2
    new.items[0].amount = .2
    assert check(pair) == []


def test_decimal_equivalence_and_notes_are_not_new_business_content(pair):
    pair[2].items[0].quantity = Decimal('0.10')
    pair[2].remark = '备注不同'
    pair[2].items[0].remark = '备注不同'
    assert len(check(pair)) == 1


def test_detector_does_not_change_inventory_or_transactions(pair):
    w = pair[0]
    before = ([(m.id, m.stock) for m in w.Material.query.all()], w.StockTransaction.query.count())
    assert len(check(pair)) == 1
    assert ([(m.id, m.stock) for m in w.Material.query.all()], w.StockTransaction.query.count()) == before


@pytest.mark.parametrize('field,value', [('batch_no', 'B2'), ('expiry_date', date(2030, 1, 1)),
                                       ('is_customer_supplied', True), ('source_purchase_order_item_id', 99)])
def test_inbound_traceability_is_part_of_the_comparison(pair, field, value):
    if pair[5] != 'in_order_id':
        pytest.skip('Inbound-specific columns')
    setattr(pair[2].items[0], field, value)
    assert check(pair) == []


def test_documents_match_for_duplicate_warning(pair):
    from services.document_duplicate import documents_match_for_duplicate_warning
    assert documents_match_for_duplicate_warning(pair[1], pair[2])
    pair[2].items[0].quantity = .2
    assert not documents_match_for_duplicate_warning(pair[1], pair[2])


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), None])
def test_invalid_number_is_never_labelled_an_equal_document(pair, bad):
    pair[2].items[0].quantity = bad
    assert check(pair) == []


def test_different_quantity_completes_without_force_and_keeps_warehouse_boundary(pair):
    from services.warehouse_stock_service import apply_stock_delta
    w, _, candidate, _, _, fk = pair
    material = candidate.items[0].material
    main_warehouse = w.Warehouse.query.filter_by(name='主仓库').one()
    second = w.Warehouse(code='EXACT-SECOND', name='另一仓库', status='active')
    w.db.session.add(second)
    w.db.session.flush()
    with w.app.test_request_context():
        for warehouse in (main_warehouse, second):
            ok, message = apply_stock_delta(material, 2, transaction_type='in',
                                            reference_type='duplicate_test', reference_id=0,
                                            warehouse=warehouse.name)
            assert ok, message
    candidate.items[0].quantity = .2
    candidate.items[0].amount = .4
    w.db.session.commit()
    direction = 'in' if fk == 'in_order_id' else 'out'
    reference = direction + '_order'
    client = _login_client(w)
    from flask import g
    g.pop('_login_user', None)  # The stock-seeding request cached AnonymousUser in this fixture's app context.
    response = client.post(f'/{reference}/{candidate.id}/complete')
    assert response.status_code == 200, response.get_data(as_text=True)
    result = response.get_json()
    assert result['status'] == 'success', result
    assert candidate.status == 'completed'
    transactions = w.StockTransaction.query.filter_by(reference_type=reference, reference_id=candidate.id).all()
    assert len(transactions) == 1
    expected = .2 if direction == 'in' else -.2
    assert transactions[0].quantity == pytest.approx(expected)
    assert transactions[0].warehouse_id == main_warehouse.id
    assert material.stock == pytest.approx(4 + expected)
    assert w.get_warehouse_stock_quantities(second)[material.id] == pytest.approx(2)
    repeated = client.post(f'/{reference}/{candidate.id}/complete').get_json()
    assert repeated['status'] == 'error'
    assert w.StockTransaction.query.filter_by(reference_type=reference, reference_id=candidate.id).count() == 1
