"""Actual adjustment HTTP/ORM/report matrix, only in verified owned memory."""
from datetime import date
from decimal import Decimal
import math

from scripts.verify_db_guard import require_isolated_test_runtime

require_isolated_test_runtime()

import pytest  # noqa: E402
from sqlalchemy import event  # noqa: E402
import app as w  # noqa: E402
from tests.test_opening_reference_ownership_runtime_20261113 import source_scene  # noqa: E402


COMMON = ('raw', 'normalized', 'ordinary', 'same_raw', 'same_norm', 'aggregate',
          'multi_bin', 'mixed_raw', 'mixed_norm', 'phase_bad', 'phase_sign',
          'unknown_fk', 'header_conflict', 'missing_source', 'renamed', 'closed_cycle',
          'closed_residue', 'global_mismatch', 'global_shortage', 'wh_shortage',
          'allow_negative', 'dml_failure', 'ordinary_prefix', 'cumulative_float')
PLAN = [(sign, on, mode) for sign in (1, -1) for on in (False, True) for mode in COMMON]
PLAN += [(sign, True, mode) for sign in (1, -1)
         for mode in ('missing_bin', 'bin_mismatch', 'missing_position', 'bin_shortage')]
assert len(PLAN) == 104 and len(set(PLAN)) == 104


def _txn(material, warehouse, quantity, reference, ident, stage):
    row = w.StockTransaction(material_id=material.id, warehouse_id=warehouse.id,
        quantity=quantity, reference_type=reference, reference_id=ident,
        transaction_type=stage, location=warehouse.name)
    w.db.session.add(row)
    return row


def _seed(scene, sign, on, mode):
    client, a, b = scene
    for name, value in (('location_management_enabled', on), ('allow_negative_stock', False),
                        ('allow_negative_location_stock', False)):
        w.set_system_setting(name, '1' if value else '0')
    values = ([sign*1.005]*100 if mode == 'cumulative_float' else [sign*1.005, sign*2.005] if mode in ('same_raw', 'aggregate', 'multi_bin', 'dml_failure') else
              [sign*1.005, sign*1.005] if mode == 'same_norm' else
              [sign*1.005, -sign*1.005] if mode in ('mixed_raw', 'mixed_norm') else
              [sign*1.01, -sign*1.01] if mode == 'ordinary_prefix' else
              [sign*1.01] if mode == 'ordinary' else [sign*1.005])
    recorded = ([sign*1.01] if mode == 'normalized' else [sign*1.01, sign*1.01] if mode == 'same_norm' else
                [sign*3.01] if mode == 'aggregate' else [sign*1.01, -sign*1.01] if mode == 'mixed_norm' else values)
    material = w.Material(code='SYN-ADJUSTMENT', name='合成调整物料', price=2.5, stock=20+math.fsum(recorded))
    order = w.AdjustmentOrder(adjustment_no='SYN-ADJUSTMENT', date=date.today(),
        adjustment_type='surplus' if sign > 0 else 'loss', warehouse=a.name,
        status='completed', source_type='manual', remark='原调整备注')
    w.db.session.add_all([material, order]); w.db.session.flush()
    for index, quantity in enumerate(values):
        w.db.session.add(w.AdjustmentOrderItem(adjustment_order_id=order.id, material_id=material.id,
            quantity=quantity, location='OTHER' if mode == 'multi_bin' and index else 'SAME', reason='原调整原因'))
    _txn(material, a, 10, 'material_initial', material.id, 'initial')
    _txn(material, b, 10, 'material_initial', material.id, 'initial')
    if mode in ('closed_cycle', 'closed_residue'):
        _txn(material, a, sign*2.005, 'adjustment', order.id, 'adjustment_in' if sign > 0 else 'adjustment_out')
        _txn(material, a, -sign*(1.005 if mode == 'closed_residue' else 2.005), 'adjustment', order.id,
             'revert_adjustment_in' if sign > 0 else 'revert_adjustment_out')
        material.stock += sign if mode == 'closed_residue' else 0
    rows = [_txn(material, a, q, 'adjustment', order.id, 'adjustment_in' if q > 0 else 'adjustment_out') for q in recorded]
    if on:
        if mode == 'multi_bin':
            for position, quantity in (('SAME', 10+recorded[0]), ('OTHER', recorded[1])):
                w.db.session.add(w.LocationInventory(material_id=material.id, warehouse_id=a.id,
                    location=position, quantity=quantity))
        else:
            w.db.session.add(w.LocationInventory(material_id=material.id, warehouse_id=a.id, location='SAME',
                quantity=material.stock-10))
        w.db.session.add(w.LocationInventory(material_id=material.id, warehouse_id=b.id, location='SAME', quantity=10))
    w.db.session.flush()
    target = w.LocationInventory.query.filter_by(material_id=material.id, warehouse_id=a.id).first() if on else None
    if mode == 'phase_bad': rows[0].transaction_type = 'unproved-stage'
    elif mode == 'phase_sign': rows[0].transaction_type = 'adjustment_out' if sign > 0 else 'adjustment_in'
    elif mode == 'unknown_fk': rows[0].warehouse_id = None
    elif mode == 'header_conflict': order.warehouse = b.name
    elif mode == 'missing_source': w.db.session.delete(rows[0])
    elif mode == 'renamed': order.warehouse = 'SYN-HISTORICAL-NAME'
    elif mode == 'global_mismatch': material.stock += .005
    elif mode in ('global_shortage', 'wh_shortage', 'allow_negative'):
        warehouse = b if mode == 'global_shortage' else a
        extra = -30 if mode == 'global_shortage' else -11 if sign > 0 else -9
        _txn(material, warehouse, extra, 'synthetic-consumption', 99, 'out')
        material.stock += extra
        if on: w.LocationInventory.query.filter_by(material_id=material.id, warehouse_id=warehouse.id).one().quantity += extra
        if mode == 'allow_negative':
            w.set_system_setting('allow_negative_stock', '1')
            w.set_system_setting('allow_negative_location_stock', '1')
    elif mode == 'missing_bin': order.items[0].location = ''
    elif mode == 'bin_mismatch': target.quantity += .005
    elif mode == 'missing_position': target.location = 'OTHER'
    elif mode == 'bin_shortage':
        target.quantity = .5 if sign > 0 else -5
        w.db.session.add(w.LocationInventory(material_id=material.id, warehouse_id=a.id, location='OTHER',
            quantity=10+sign*1.005-target.quantity))
    elif mode == 'ordinary_prefix':
        _txn(material, a, -10, 'synthetic-balance', 98, 'out')
        _txn(material, b, 10, 'synthetic-balance', 99, 'in')
        if on:
            target.quantity = 0
            w.LocationInventory.query.filter_by(material_id=material.id, warehouse_id=b.id).one().quantity = 20
    w.db.session.commit()
    return client, a.id, b.id, material.id, order.id


def _state():
    w.db.session.expire_all()
    tables = (w.Material, w.StockTransaction, w.LocationInventory, w.AdjustmentOrder, w.AdjustmentOrderItem)
    return tuple([tuple(getattr(row, c.key) for c in model.__table__.columns)
                  for row in model.query.order_by(model.id)] for model in tables)


def _reports(warehouse_ids, material_id):
    material = w.db.session.get(w.Material, material_id)
    month = date.today().strftime('%Y-%m')
    return [w._build_warehouse_monthly_report(dict(warehouse_id=ident, material_code=material.code,
        start_month=month, end_month=month)) for ident in warehouse_ids]


@pytest.mark.parametrize('sign,on,mode', PLAN)
def test_actual_adjustment_reversal_preserves_each_signed_flow(source_scene, sign, on, mode):
    client, a, b, mid, ident = _seed(source_scene, sign, on, mode)
    before, reports = _state(), _reports((a, b), mid)
    prior = w.StockTransaction.query.filter_by(reference_type='adjustment', reference_id=ident).order_by(w.StockTransaction.id).all()
    last = max((r.id for r in prior if r.transaction_type.startswith('revert_')), default=0)
    original = [(r.quantity, r.transaction_type) for r in prior if r.id > last]
    items = [(r.id, r.quantity, r.material_id, r.location, r.reason, r.unit_id)
             for r in w.db.session.get(w.AdjustmentOrder, ident).items]
    head = {c.key: getattr(w.db.session.get(w.AdjustmentOrder, ident), c.key) for c in w.AdjustmentOrder.__table__.columns if c.key != 'status'}
    hit = []
    prefix = 'UPDATE LOCATION_INVENTORY' if on else 'UPDATE MATERIAL'
    def fail(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith(prefix):
            hit.append(True)
            if len(hit) == 2: raise RuntimeError('owned synthetic second adjustment DML failure')
    if mode == 'dml_failure': event.listen(w.db.engine, 'before_cursor_execute', fail)
    try: response = client.post(f'/adjustment/{ident}/revert')
    finally:
        if mode == 'dml_failure': event.remove(w.db.engine, 'before_cursor_execute', fail)
    refused = mode in ('aggregate', 'mixed_raw', 'mixed_norm', 'phase_bad', 'phase_sign', 'unknown_fk',
        'header_conflict', 'missing_source', 'closed_residue', 'global_mismatch', 'dml_failure',
        'missing_bin', 'bin_mismatch', 'missing_position') or (mode == 'cumulative_float' and (sign > 0 or on)) or (on and mode in ('multi_bin', 'closed_cycle')) or (
        sign > 0 and mode in ('global_shortage', 'wh_shortage', 'bin_shortage', 'ordinary_prefix'))
    if refused:
        assert response.status_code in (400, 409) and response.json['status'] == 'error', response.json
        assert _state() == before and _reports((a, b), mid) == reports
        if mode == 'dml_failure': assert hit == [True, True]
        return
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    w.db.session.expire_all()
    order = w.db.session.get(w.AdjustmentOrder, ident)
    assert order.status == 'pending'
    assert {c.key: getattr(order, c.key) for c in order.__table__.columns if c.key != 'status'} == head
    assert [(r.id, r.quantity, r.material_id, r.location, r.reason, r.unit_id) for r in order.items] == items
    material = w.db.session.get(w.Material, mid)
    ledger = w.StockTransaction.query.filter_by(material_id=mid).all()
    assert material.price == 2.5
    assert material.stock == pytest.approx(math.fsum(r.quantity for r in ledger), abs=1e-12)
    assert math.fsum(r.quantity for r in ledger if r.reference_type == 'adjustment' and r.reference_id == ident) == pytest.approx(0, abs=1e-12)
    if on:
        for wid in (a, b):
            assert math.fsum(r.quantity for r in w.LocationInventory.query.filter_by(material_id=mid, warehouse_id=wid)) == pytest.approx(
                math.fsum(r.quantity for r in ledger if r.warehouse_id == wid), abs=1e-12)
    after = _reports((a, b), mid)
    assert after[1] == reports[1]
    assert len(after[0][1]) == len(reports[0][1]) == 1
    old, new = reports[0][1][0], after[0][1][0]
    for direction, factor in (('in', -1), ('out', 1)):
        added = sum((Decimal(str(abs(q))) for q, _ in original if q*factor > 0), Decimal(0))
        assert new[direction+'_quantity'] == pytest.approx(old[direction+'_quantity']+float(added), abs=1e-12)
        assert new[direction+'_amount'] == pytest.approx(old[direction+'_amount']+float(added*Decimal('2.5')), abs=1e-12)
    assert new['transaction_count'] == old['transaction_count']+len(original)
    assert new['ending_quantity'] == pytest.approx(old['ending_quantity']-math.fsum(q for q, _ in original), abs=1e-12)
    snapshot = _state()
    repeated = client.post(f'/adjustment/{ident}/revert')
    assert repeated.status_code in (400, 409) and repeated.json['status'] == 'error'
    assert _state() == snapshot


@pytest.mark.parametrize('sign', [1, -1])
@pytest.mark.parametrize('on', [False, True])
@pytest.mark.parametrize('quantity', [1.005, 1.01])
def test_actual_completion_uses_existing_per_line_normalization(source_scene, sign, on, quantity):
    client, a, b, mid, ident = _seed(source_scene, sign, on, 'ordinary')
    # A fresh pending synthetic adjustment has no own ledger; ordinary completion
    # remains authoritative for newly completed legacy high-precision rows.
    w.StockTransaction.query.filter_by(reference_type='adjustment', reference_id=ident).delete()
    order = w.db.session.get(w.AdjustmentOrder, ident)
    order.status = 'pending'; order.items[0].quantity = sign*quantity
    material = w.db.session.get(w.Material, mid); material.stock = 20
    if on: w.LocationInventory.query.filter_by(material_id=mid, warehouse_id=a).one().quantity = 10
    w.db.session.commit()
    complete = client.post(f'/adjustment/{ident}/complete')
    assert complete.status_code == 200 and complete.json['status'] == 'success', complete.json
    recorded = w.StockTransaction.query.filter_by(reference_type='adjustment', reference_id=ident).one()
    assert recorded.quantity == sign*1.01
    assert w.db.session.get(w.AdjustmentOrder, ident).status == 'completed'
    inverse = client.post(f'/adjustment/{ident}/revert')
    assert inverse.status_code == 200 and inverse.json['status'] == 'success', inverse.json
    assert w.db.session.get(w.Material, mid).stock == pytest.approx(20, abs=1e-12)
    assert w.db.session.get(w.AdjustmentOrder, ident).items[0].quantity == sign*quantity


assert len(PLAN)+2*2*2 == 112, 'HTTP plan must remain explicit and nonempty'
