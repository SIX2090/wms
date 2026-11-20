import json
from datetime import datetime

import pytest

import app as wms
from tests.test_document_create_number_conflicts import case, rows, snapshot
from tests.test_web_stock_posting_audit import fail_audit, posting_actors


@pytest.mark.parametrize('action', ['complete', 'revert'])
def test_stage_inventory_check_audit_tracks_draft_and_rolls_back_with_check(posting_actors, action):
    creator, poster, ids = posting_actors
    with wms.app.app_context():
        check = wms.InventoryCheck(check_no='CHECK-AUDIT', status='pending', warehouse=ids['names'][0],
                                   frozen_at=datetime.now(), operator_id=ids['user'])
        wms.db.session.add(check)
        wms.db.session.flush()
        check_id = check.id
        wms.db.session.add(wms.InventoryCheckItem(
            inventory_check_id=check_id, material_id=ids['mats'][0], system_stock=20, actual_stock=18,
            difference=-2, counted_by=ids['user'], counted_at=datetime.now(), area='',
        ))
        wms.db.session.commit()

    if action == 'revert':
        prepared = creator.post(f'/check/{check_id}/complete', json={})
        assert prepared.json['status'] == 'success', prepared.json
    with wms.app.app_context():
        before = (snapshot(wms.InventoryCheck), snapshot(wms.AdjustmentOrder),
                  rows(wms.OperationAudit), rows(wms.OperationLog))

    operation = f'{action}_check'
    url = f'/check/{check_id}/{action}'
    with fail_audit(operation, check_id) as attempted:
        failure = poster.post(url, json={})
    assert failure.json['status'] == 'error', failure.json
    assert attempted == [check_id]
    with wms.app.app_context():
        assert (snapshot(wms.InventoryCheck), snapshot(wms.AdjustmentOrder),
                rows(wms.OperationAudit), rows(wms.OperationLog)) == before

    accepted = poster.post(url, json={})
    assert accepted.json['status'] == 'success', accepted.json
    completing = action == 'complete'
    with wms.app.app_context():
        audit = wms.OperationAudit.query.filter_by(operation=operation, target_type='check', target_id=check_id).one()
        audit_id = audit.id
        assert audit.user_id == ids['poster'] and audit.username == 'web-stock-poster'
        assert audit.target_name == 'CHECK-AUDIT'
        old, new = json.loads(audit.old_data), json.loads(audit.new_data)
        assert old['status'] == ('pending' if completing else 'completed')
        assert new['status'] == ('completed' if completing else 'pending')
        assert new['moves_inventory'] is False
        line = new['items'][0]
        assert line['counted_by'] == ids['user'] and line['difference'] == -2
        assert (line['system_stock'], line['actual_stock']) == (20, 18)
        drafts = (new if completing else old)['adjustments']
        assert len(drafts) == 1
        draft = drafts[0]
        assert draft['warehouse'] == ids['names'][0]
        assert draft['items'][0]['quantity'] == -2 and draft['items'][0]['material_id'] == ids['mats'][0]
        draft_in_db = wms.db.session.get(wms.AdjustmentOrder, draft['id'])
        if completing:
            assert draft_in_db.adjustment_no == draft['number'] and draft_in_db.status == 'pending'
        else:
            assert draft_in_db is None
        assert wms.db.session.get(wms.Material, ids['mats'][0]).stock == 30
        assert rows(wms.StockTransaction) == before[0]['transactions']

    response = creator.get('/operation_audit', query_string={'search': 'CHECK-AUDIT', 'audit_detail': audit_id})
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    label = '生成的调整草稿' if completing else '撤回的调整草稿'
    assert label in page and draft['number'] in page and 'web-stock-poster' in page
    assert '本次盘点操作未改动库存' in page and '>-2</td>' in page
