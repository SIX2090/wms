"""Full WMS HTTP/ORM cases, only through the existing owned memory fixture."""
import math

import pytest
from sqlalchemy import event

from tests.test_money_route_synthetic_20261109 import money_case


DEFINITIONS = {
    'requisition': ('ProductionRequisition', 'req_no', 'ProductionRequisitionItem', 'requisition_id',
                    'requisition', 'requisition', -1, '/requisition/{id}/revert'),
    'aftersale': ('AfterSaleOutOrder', 'order_no', 'AfterSaleOutOrderItem', 'after_sale_out_order_id',
                 'after_sale_out_order', 'after_sale_out', -1, '/after_sale_out/{id}/revert'),
    'issue': ('SubcontractIssue', 'issue_no', 'SubcontractIssueItem', 'issue_id',
              'subcontract_issue', 'subcontract_issue', -1, '/subcontract/issue/{id}/revert'),
    'receive': ('SubcontractReceive', 'receive_no', 'SubcontractReceiveItem', 'receive_id',
                'subcontract_receive', 'subcontract_receive', 1, '/subcontract/receive/{id}/revert'),
}


def seed(c, domain, location_on, mode):
    w = c.w
    model, number, item_model, fk, reference, stage, sign, path = DEFINITIONS[domain]
    w.set_system_setting('location_management_enabled', '1' if location_on else '0')
    if domain in ('issue', 'receive'):
        source = w.SubcontractOrder(order_no='SYN-FOUR-PARENT', status='processing',
                                    warehouse=c.warehouse, total_amount=77.77, remark='原父单')
        source_key = 'subcontract_order_id'
    elif domain == 'requisition':
        source = w.db.session.get(w.BOM, c.ids['bom'])
        source_key = 'bom_id'
    else:
        source = w.OutOrder(order_no='SYN-FOUR-SOURCE', status='completed', warehouse=c.warehouse,
                             total_amount=88.88, remark='原来源单')
        source_key = 'source_out_order_id'
    w.db.session.add(source)
    w.db.session.flush()
    source_snapshot = {col.key: getattr(source, col.key) for col in source.__table__.columns}
    fields = {number: 'SYN-FOUR-HISTORY', 'status': 'completed', 'warehouse': c.warehouse,
              'location': c.warehouse, source_key: source.id}
    if domain == 'aftersale': fields.update(total_amount=123.45, customer='合成客户', reason='原售后原因')
    order = getattr(w, model)(**fields)
    w.db.session.add(order)
    w.db.session.flush()
    quantity = 1.01 if mode == 'ordinary' else 1.005
    fields = {fk: order.id, 'material_id': c.ids['material'], 'quantity': quantity}
    if domain == 'aftersale': fields.update(price=3.5, amount=7.77, contract_no='合成行合同', project_name='原行工程')
    row = getattr(w, item_model)(**fields)
    w.db.session.add(row)
    delta = sign * (1.01 if mode in ('ordinary', 'normalized') else 1.005)
    recorded = w.StockTransaction(material_id=c.ids['material'], warehouse_id=c.wh1,
                                   quantity=delta, reference_type=reference, reference_id=order.id,
                                   transaction_type=stage, location=c.warehouse)
    w.db.session.add(recorded)
    material = w.db.session.get(w.Material, c.ids['material'])
    material.stock = 10 + delta
    if location_on:
        w.LocationInventory.query.filter_by(material_id=material.id, warehouse_id=c.wh1).one().quantity = 5 + delta
    w.db.session.commit()
    return order.id, path.format(id=order.id), source, source_snapshot, source_key


def inventory(c):
    w = c.w
    w.db.session.remove()
    return (w.db.session.get(w.Material, c.ids['material']).stock,
            [(r.id, r.quantity, r.transaction_type, r.reference_type, r.reference_id, r.warehouse_id)
             for r in w.StockTransaction.query.order_by(w.StockTransaction.id)],
            [(r.id, r.quantity, r.warehouse_id, r.location)
             for r in w.LocationInventory.query.order_by(w.LocationInventory.id)])


@pytest.mark.parametrize('domain', list(DEFINITIONS))
@pytest.mark.parametrize('location_on', [False, True])
@pytest.mark.parametrize('mode', ['raw', 'normalized', 'ordinary'])
def test_four_domain_reverse_uses_proven_quantity_and_preserves_other_business(money_case, domain, location_on, mode):
    c = money_case
    ident, path, source, before, source_key = seed(c, domain, location_on, mode)
    source_cls, source_id = type(source), source.id
    response = c.client.post(path)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    w = c.w
    w.db.session.remove()
    order = w.db.session.get(getattr(w, DEFINITIONS[domain][0]), ident)
    assert order.status == 'pending' and getattr(order, source_key) == source_id
    assert w.db.session.get(w.Material, c.ids['material']).stock == pytest.approx(10, abs=1e-12)
    ledger = w.StockTransaction.query.filter_by(material_id=c.ids['material']).all()
    assert math.fsum(r.quantity for r in ledger) == pytest.approx(10, abs=1e-12)
    assert math.fsum(r.quantity for r in ledger if r.warehouse_id == c.wh1) == pytest.approx(5, abs=1e-12)
    assert math.fsum(r.quantity for r in ledger if r.warehouse_id == c.wh2) == 5
    assert len(ledger) == 4
    assert math.fsum(r.quantity for r in ledger if r.reference_type == DEFINITIONS[domain][4] and r.reference_id == ident) == pytest.approx(0, abs=1e-12)
    assert [r.quantity for r in w.LocationInventory.query.order_by(w.LocationInventory.warehouse_id)] == [5, 5]
    source = w.db.session.get(source_cls, source_id)
    assert {col.key: getattr(source, col.key) for col in source.__table__.columns} == before
    assert w.DocumentPushLine.query.count() == 0
    if domain == 'aftersale':
        assert order.total_amount == 123.45 and order.reason == '原售后原因'
        assert [(r.quantity, r.price, r.amount, r.contract_no, r.project_name) for r in order.items] == [
            (1.01 if mode == 'ordinary' else 1.005, 3.5, 7.77, '合成行合同', '原行工程')]
    snapshot = inventory(c)
    repeat = c.client.post(path)
    assert repeat.status_code in (400, 409), repeat.json
    assert repeat.json['status'] == 'error' and inventory(c) == snapshot


@pytest.mark.parametrize('domain', list(DEFINITIONS))
@pytest.mark.parametrize('location_on', [False, True])
def test_four_domain_reverse_rolls_back_middle_dml_failure(money_case, domain, location_on):
    c = money_case
    ident, path, *_ = seed(c, domain, location_on, 'raw')
    before = inventory(c)
    hit = []
    target = 'UPDATE LOCATION_INVENTORY' if location_on else 'UPDATE MATERIAL'
    def fail(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith(target):
            hit.append(True)
            raise RuntimeError('owned synthetic four-domain DML failure')
    event.listen(c.w.db.engine, 'before_cursor_execute', fail)
    try:
        response = c.client.post(path)
    finally:
        event.remove(c.w.db.engine, 'before_cursor_execute', fail)
    assert hit == [True]
    assert response.status_code in (400, 409) and response.json['status'] == 'error', response.json
    assert inventory(c) == before
    assert c.w.db.session.get(getattr(c.w, DEFINITIONS[domain][0]), ident).status == 'completed'


@pytest.mark.parametrize('domain', list(DEFINITIONS))
@pytest.mark.parametrize('location_on', [False, True])
def test_four_domain_unknown_original_fk_is_not_inferred_from_header(money_case, domain, location_on):
    c = money_case
    ident, path, *_ = seed(c, domain, location_on, 'raw')
    row = c.w.StockTransaction.query.filter_by(reference_type=DEFINITIONS[domain][4], reference_id=ident).one()
    row.warehouse_id = None
    c.w.db.session.commit()
    before = inventory(c)
    response = c.client.post(path)
    assert response.status_code == 400 and response.json['status'] == 'error', response.json
    assert '原仓归属' in response.json['msg']
    assert inventory(c) == before
    assert c.w.db.session.get(getattr(c.w, DEFINITIONS[domain][0]), ident).status == 'completed'
