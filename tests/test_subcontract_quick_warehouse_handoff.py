"""Quick issue and receipt inherit the parent warehouse at posting time."""
import pytest

import app as w
from tests.test_document_create_number_conflicts import case
from tests.test_transfer_account_handoff import file_accounts
from tests.test_web_stock_posting_audit import posting_actors


@pytest.mark.parametrize('legacy', [False, True], ids=['web', 'compat'])
@pytest.mark.parametrize('direction', ['issue', 'receive'])
@pytest.mark.parametrize('change', ['disable', 'switch', 'already_inactive'])
def test_quick_actions_use_current_parent_warehouse(file_accounts, monkeypatch, legacy, direction, change):
    client, _, ids = file_accounts
    mid = ids['mats'][0]
    with w.app.app_context():
        parent = w.SubcontractOrder(order_no='HANDOFF-QUICK', status='pending',
                                    warehouse=ids['names'][0], operator_id=ids['user'])
        w.db.session.add(parent)
        w.db.session.flush()
        oid = parent.id
        w.db.session.add(w.SubcontractItem(subcontract_order_id=oid, material_id=mid, quantity=1))
        if change == 'already_inactive':
            w.db.session.get(w.Warehouse, ids['a']).status = 'inactive'
        w.db.session.commit()
        code = w.db.session.get(w.Material, mid).code
        count = w.StockTransaction.query.count()

    locked = []
    original_lock = w._acquire_order_write_lock
    def change_then_lock(*args, **kwargs):
        table = w.Warehouse.__table__ if change == 'disable' else w.SubcontractOrder.__table__
        key = ids['a'] if change == 'disable' else oid
        values = {'status': 'inactive'} if change == 'disable' else {'warehouse': ids['names'][1]}
        with w.db.engine.begin() as other:
            locked.append(other.execute(table.update().where(table.c.id == key).values(**values)).rowcount)
        return original_lock(*args, **kwargs)

    if change != 'already_inactive':
        monkeypatch.setattr(w, '_acquire_order_write_lock', change_then_lock)
    if legacy:
        body = {'order_id': oid, 'material_id': mid, 'quantity': 1}
        if direction == 'issue':
            body = {'order_id': oid, 'items': [{'material_id': mid, 'quantity': 1}]}
        response = client.post('/api/subcontract/quick_' + direction, json=body)
    else:
        response = client.post(f'/subcontract/{oid}/{direction}', data={'material_code': code, 'quantity': 1})
    if change != 'already_inactive':
        assert locked == [1]
    success = change == 'switch'
    assert response.json['status'] == ('success' if success else 'error'), response.json
    with w.app.app_context():
        model = w.SubcontractIssue if direction == 'issue' else w.SubcontractReceive
        if success:
            posted = model.query.one()
            assert posted.warehouse == ids['names'][1]
            moved = w.StockTransaction.query.filter_by(reference_type='subcontract_' + direction,
                                                      reference_id=posted.id).one()
            assert moved.warehouse_id == ids['b']
            delta = -1 if direction == 'issue' else 1
            assert moved.quantity == delta
        else:
            assert model.query.count() == 0 and w.StockTransaction.query.count() == count
            assert w.db.session.get(w.SubcontractOrder, oid).status == 'pending'
            delta = 0
        assert w.db.session.get(w.Material, mid).stock == 30 + delta
        for wid, expected in [(ids['a'], 20), (ids['b'], 10 + delta)]:
            assert w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse, wid))[mid] == expected
