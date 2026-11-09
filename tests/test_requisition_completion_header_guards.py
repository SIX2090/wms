"""A07: valid headers and lock-time nonempty lines, without changing stock semantics."""
import pytest
from sqlalchemy import event

import app as w
from tests.document_revision_client import document_post
from tests.test_requisition_location_flow_integration import scene, snapshot, save  # noqa: F401


def post(client, url, **kwargs):
    return document_post(client, url, headers={'X-Requested-With': 'XMLHttpRequest'}, **kwargs)


def draft(scene, *, key=None):
    client, a, _, _, _ = scene
    data = dict(warehouse_id=str(a), location='Rack-1' if w.location_management_enabled() else '',
                purpose='original purpose', production_order='original job', picker='original picker')
    headers = {'X-Requested-With': 'XMLHttpRequest'}
    if key:
        headers['X-Idempotency-Key'] = key
    response = client.post('/requisition/add', data=data, headers=headers)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    return response.json['id'], data


def document_state(rid):
    w.db.session.expire_all()
    row = w.db.session.get(w.ProductionRequisition, rid)
    return (row.status, row.warehouse, row.location, row.production_order, row.purpose,
            row.picker, row.bom_id, row.remark,
            [(i.id, i.material_id, i.quantity, i.unit_id) for i in row.items])


@pytest.mark.parametrize('scene', [False, True], indirect=True)
@pytest.mark.parametrize('empty_by', ['create', 'single_delete', 'batch_delete'])
def test_empty_requisition_cannot_complete_after_last_line_disappears(scene, empty_by):
    client, _, _, mid, uid = scene
    rid, _ = draft(scene)
    if empty_by != 'create':
        line = w.ProductionRequisitionItem(requisition_id=rid, material_id=mid, unit_id=uid, quantity=5)
        w.db.session.add(line)
        w.db.session.commit()
        if empty_by == 'single_delete':
            deleted = post(client, f'/requisition/{rid}/item/{line.id}/delete')
        else:
            deleted = post(client, f'/requisition/{rid}/batch_delete_items', json={'ids': [line.id]})
        assert deleted.status_code == 200 and deleted.json['status'] == 'success'
    before_stock, before_doc = snapshot(mid), document_state(rid)
    assert not before_doc[-1]
    response = post(client, f'/requisition/{rid}/complete')
    assert response.status_code == 400 and response.json['status'] == 'error', response.json
    assert '明细' in response.json['msg']
    assert snapshot(mid) == before_stock and document_state(rid) == before_doc


def test_nonempty_check_uses_the_locked_reloaded_lines(scene, monkeypatch):
    client, _, _, mid, uid = scene
    rid, _ = draft(scene)
    w.db.session.add(w.ProductionRequisitionItem(requisition_id=rid, material_id=mid, unit_id=uid, quantity=5))
    w.db.session.commit()
    before_stock, before_doc = snapshot(mid), document_state(rid)
    original = w._acquire_order_write_lock
    observed = []
    def locked_without_lines(*args, **kwargs):
        row, ok = original(*args, **kwargs)
        if ok:
            w.ProductionRequisitionItem.query.filter_by(requisition_id=rid).delete(synchronize_session='fetch')
            w.db.session.flush()
            w.db.session.expire(row, ['items'])
            observed.append(len(row.items))
        return row, ok
    monkeypatch.setattr(w, '_acquire_order_write_lock', locked_without_lines)
    response = post(client, f'/requisition/{rid}/complete')
    assert observed == [0], 'injected real SQL deletion must occur after the lock'
    assert response.status_code == 400 and '明细' in response.json['msg'], response.json
    # The injected deletion is part of this rejected transaction and also rolls back.
    assert snapshot(mid) == before_stock and document_state(rid) == before_doc


@pytest.mark.parametrize('entry', ['add', 'update', 'table'])
@pytest.mark.parametrize('invalid', ['unknown_name', 'inactive_name', 'unknown_id', 'inactive_id', 'zero_id', 'malformed_id', 'missing_location'])
def test_all_requisition_header_entries_reject_invalid_effective_values(scene, entry, invalid):
    client, a, _, mid, uid = scene
    inactive = w.Warehouse(code='B7-OFF', name='B7停用仓', status='inactive')
    w.db.session.add(inactive)
    w.db.session.commit()
    rid, _ = draft(scene)
    data = dict(warehouse=w.db.session.get(w.Warehouse, a).name, location='Rack-1', purpose='must not save')
    if invalid == 'unknown_name':
        data['warehouse'] = 'B7不存在仓库'
    elif invalid == 'inactive_name':
        data['warehouse'] = inactive.name
    elif invalid == 'unknown_id':
        data['warehouse_id'] = '999999'
    elif invalid == 'inactive_id':
        data['warehouse_id'] = str(inactive.id)
    elif invalid == 'zero_id':
        data['warehouse_id'] = 0
    elif invalid == 'malformed_id':
        data['warehouse_id'] = 'not-an-id'
    else:
        data['location'] = ''
    before_stock, before_doc = snapshot(mid), document_state(rid)
    count = w.ProductionRequisition.query.count()
    if entry == 'table':
        response = save(client, mid, uid, data, order_id=rid)
    else:
        response = post(client, '/requisition/add' if entry == 'add' else f'/requisition/{rid}/update', data=data)
    assert response.status_code == 400 and response.json['status'] == 'error', response.json
    assert '库位' in response.json['msg'] if invalid == 'missing_location' else '仓库' in response.json['msg']
    assert snapshot(mid) == before_stock and document_state(rid) == before_doc
    assert w.ProductionRequisition.query.count() == count


@pytest.mark.parametrize('scene', [False], indirect=True)
@pytest.mark.parametrize('entry', ['add', 'update', 'table'])
def test_omitted_warehouse_uses_only_an_active_default_and_disabled_location_stays_optional(scene, entry):
    client, a, _, mid, uid = scene
    rid, _ = draft(scene)
    data = dict(purpose='valid omission', location='')
    before = snapshot(mid)
    if entry == 'table':
        response = save(client, mid, uid, data, order_id=rid)
    else:
        response = post(client, '/requisition/add' if entry == 'add' else f'/requisition/{rid}/update', data=data)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    target = rid if entry != 'add' else response.json['id']
    row = w.db.session.get(w.ProductionRequisition, target)
    assert row.warehouse == w.db.session.get(w.Warehouse, a).name and not row.location
    assert snapshot(mid) == before


@pytest.mark.parametrize('entry', ['add', 'update', 'table'])
def test_missing_default_cannot_create_or_modify_a_requisition(scene, entry):
    client, a, _, mid, uid = scene
    rid, _ = draft(scene)
    w.db.session.get(w.Warehouse, a).is_default = False
    w.db.session.commit()
    before_stock, before_doc = snapshot(mid), document_state(rid)
    count = w.ProductionRequisition.query.count()
    data = dict(purpose='must not save', location='Rack-1')
    response = save(client, mid, uid, data, order_id=rid) if entry == 'table' else post(
        client, '/requisition/add' if entry == 'add' else f'/requisition/{rid}/update', data=data)
    assert response.status_code == 400 and response.json['status'] == 'error', response.json
    assert snapshot(mid) == before_stock and document_state(rid) == before_doc
    assert w.ProductionRequisition.query.count() == count


@pytest.mark.parametrize('level', ['header', 'top'])
def test_explicit_zero_id_never_falls_back_to_the_default_warehouse(scene, level):
    client, _, _, mid, uid = scene
    rid, _ = draft(scene)
    before_stock, before_doc = snapshot(mid), document_state(rid)
    payload = dict(order_id=rid, order_no=w.db.session.get(w.ProductionRequisition, rid).req_no,
                   header=dict(location='Rack-1', purpose='must not save'),
                   items=[dict(material_id=mid, unit_id=uid, quantity=5)])
    (payload['header'] if level == 'header' else payload)['warehouse_id'] = 0
    response = post(client, '/requisition/save_table', json=payload)
    assert response.status_code == 400 and response.json['status'] == 'error', response.json
    assert '仓库' in response.json['msg']
    assert snapshot(mid) == before_stock and document_state(rid) == before_doc


@pytest.mark.parametrize('scene', [False, True], indirect=True)
def test_complete_and_existing_revert_keep_three_ledgers_and_other_warehouse(scene):
    client, a, b, mid, uid = scene
    location = 'Rack-1' if w.location_management_enabled() else ''
    result = save(client, mid, uid, dict(warehouse_id=a, location=location))
    assert result.status_code == 200 and result.json['status'] == 'success', result.json
    rid = result.json['id']
    total = w.db.session.get(w.Material, mid).stock
    other = w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse, b))[mid]
    before_locations = [(x.warehouse_id, x.location, x.quantity) for x in w.LocationInventory.query.order_by(w.LocationInventory.id)]
    completed = post(client, f'/requisition/{rid}/complete')
    assert completed.status_code == 200 and completed.json['status'] == 'success', completed.json
    w.db.session.expire_all()
    assert w.db.session.get(w.Material, mid).stock == total - 5
    assert w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse, b))[mid] == other
    reverted = post(client, f'/requisition/{rid}/revert')
    assert reverted.status_code == 200 and reverted.json['status'] == 'success', reverted.json
    w.db.session.expire_all()
    assert w.db.session.get(w.Material, mid).stock == total
    assert w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse, b))[mid] == other
    assert [(x.warehouse_id, x.location, x.quantity) for x in w.LocationInventory.query.order_by(w.LocationInventory.id)] == before_locations
    rows = w.StockTransaction.query.filter_by(reference_type='requisition', reference_id=rid).all()
    assert len(rows) == 2 and all(x.warehouse_id == a for x in rows)
    assert sum(x.quantity for x in rows) == 0
    assert w.db.session.get(w.ProductionRequisition, rid).status == 'pending'


def test_empty_draft_first_save_replay_does_not_allocate_another_number(scene):
    client, _, _, mid, _ = scene
    before = snapshot(mid)
    rid, data = draft(scene, key='b7-empty-first-save')
    response = client.post('/requisition/add', data=data, headers={'X-Idempotency-Key': 'b7-empty-first-save'})
    assert response.status_code == 200 and response.json['id'] == rid
    assert w.ProductionRequisition.query.count() == 1 and snapshot(mid) == before


def test_legacy_update_commit_failure_really_rolls_back_header_and_inventory(scene):
    client, a, _, mid, _ = scene
    rid, _ = draft(scene)
    before_stock, before_doc = snapshot(mid), document_state(rid)
    reached = []
    written = []
    def observe_write(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().lower().startswith('update production_requisition ') and 'must roll back' in parameters:
            written.append(True)
    def fail_commit(connection):
        if written:
            reached.append(True)
            raise RuntimeError('synthetic B7 commit failure')
    event.listen(w.db.engine, 'before_cursor_execute', observe_write)
    event.listen(w.db.engine, 'commit', fail_commit)
    try:
        response = post(client, f'/requisition/{rid}/update', data=dict(warehouse_id=a, location='Rack-1', purpose='must roll back'))
        assert response.json['status'] == 'error', response.json
    finally:
        event.remove(w.db.engine, 'commit', fail_commit)
        event.remove(w.db.engine, 'before_cursor_execute', observe_write)
    assert written and reached, 'must reach the real header write and its commit failure'
    assert snapshot(mid) == before_stock and document_state(rid) == before_doc
