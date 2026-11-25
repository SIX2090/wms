import json
from datetime import datetime, timedelta

import pytest

import app as wms
from tests.document_revision_client import document_post
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene


@pytest.mark.parametrize("same_warehouse", [False, True])
def test_frozen_check_keeps_warehouse_identity(scene, same_warehouse):
    client, source, other, material = scene
    check = wms.InventoryCheck(check_no="CK-FREEZE", warehouse=source.name,
                               status="pending", frozen_at=datetime.now())
    wms.db.session.add(check)
    wms.db.session.flush()
    row = wms.InventoryCheckItem(inventory_check_id=check.id, material_id=material.id,
                                 system_stock=60, actual_stock=58, difference=-2)
    wms.db.session.add(row)
    wms.db.session.commit()
    result = document_post(client,"/check/save_table", json={
        "order_id": check.id, "order_no": check.check_no,
        "header": {"warehouse": source.code if same_warehouse else other.name},
        "items": [{"material_id": material.id, "actual_stock": 18}],
    }).get_json()
    assert result["status"] == ("success" if same_warehouse else "error"), result
    wms.db.session.expire_all()
    assert check.warehouse == source.name
    assert row.system_stock == 60
    assert row.actual_stock == (18 if same_warehouse else 58)
    assert row.difference == (-42 if same_warehouse else -2)


def test_empty_check_can_choose_another_warehouse(scene):
    client, source, other, material = scene
    check = wms.InventoryCheck(check_no="CK-EMPTY", warehouse=source.name, status="pending")
    wms.db.session.add(check)
    wms.db.session.commit()
    result = document_post(client,"/check/save_table", json={
        "order_id": check.id, "order_no": check.check_no,
        "header": {"warehouse": other.name},
        "items": [{"material_id": material.id, "actual_stock": 98}],
    }).get_json()
    assert result["status"] == "success", result
    wms.db.session.expire_all()
    assert check.warehouse == other.name
    assert check.items[0].system_stock == 100
    assert check.items[0].difference == -2


def test_confirmed_draft_warehouse_correction_refreezes_target_stock(scene):
    client, source, other, material = scene
    counted_at = datetime.now() - timedelta(days=1)
    operator = wms.User.query.filter_by(username='reviewer').one()
    check = wms.InventoryCheck(check_no='CK-WAREHOUSE-CHANGE', warehouse=source.code,
                               status='pending', frozen_at=counted_at, operator_id=operator.id)
    wms.db.session.add(check)
    wms.db.session.flush()
    first = wms.InventoryCheckItem(inventory_check_id=check.id, material_id=material.id,
                                  actual_stock=58, system_stock=60, difference=-2,
                                  counted_by=operator.id, counted_at=counted_at)
    zero = wms.InventoryCheckItem(inventory_check_id=check.id, material_id=material.id,
                                 actual_stock=0, system_stock=60, difference=-60,
                                 counted_by=operator.id, counted_at=counted_at)
    blank = wms.InventoryCheckItem(inventory_check_id=check.id, material_id=material.id,
                                  actual_stock=60, system_stock=60, difference=0)
    withdrawn = wms.AdjustmentOrder(adjustment_no='ADJ-OLD-WAREHOUSE', adjustment_type='stocktake',
                                    warehouse=source.name, source_type='check', source_id=check.id,
                                    status='cancelled')
    wms.db.session.add_all([first, zero, blank, withdrawn])
    wms.db.session.commit()
    movement_count = wms.StockTransaction.query.count()

    page = client.get(f'/check/{check.id}').get_data(as_text=True)
    payload = {
        'order_id': check.id,
        'header': {'warehouse_id': other.id, 'warehouse_change_from_id': source.id},
        'items': [
            {'line_id': row.id, 'material_id': material.id, 'actual_stock': actual}
            for row, actual in ((first, 58), (zero, 0), (blank, None))
        ],
    }
    result = document_post(client, '/check/save_table', json=payload).get_json()
    assert result['status'] == 'success', result
    wms.db.session.expire_all()
    assert check.warehouse == other.name and check.frozen_at > counted_at
    assert result['line_ids'] == [first.id, zero.id, blank.id]
    assert [row.system_stock for row in (first, zero, blank)] == [100, 100, 100]
    assert [row.actual_stock for row in (first, zero, blank)] == [58, 0, 100]
    assert [row.difference for row in (first, zero, blank)] == [-42, -100, 0]
    assert [row.has_actual_count for row in (first, zero, blank)] == [True, True, False]
    assert first.counted_at == zero.counted_at == counted_at
    assert withdrawn.status == 'cancelled' and withdrawn.warehouse == source.name
    assert wms.StockTransaction.query.count() == movement_count and material.stock == 100
    audit = wms.OperationAudit.query.filter_by(operation='change_check_warehouse', target_id=check.id).one()
    assert json.loads(audit.old_data)['warehouse'] == source.code
    assert json.loads(audit.new_data)['warehouse'] == other.name
    assert '更换仓库后' in page and f'data-saved-warehouse-id="{source.id}"' in page

    refrozen_at = check.frozen_at
    del payload['header']['warehouse_change_from_id']
    payload['items'][-1]['actual_stock'] = 10
    saved = document_post(client, '/check/save_table', json=payload).get_json()
    assert saved['status'] == 'success', saved
    completed = document_post(client, f'/check/{check.id}/complete', json={}).get_json()
    assert completed['status'] == 'success', completed
    wms.db.session.expire_all()
    adjustment = wms.AdjustmentOrder.query.filter_by(source_type='check', source_id=check.id,
                                                     status='pending').one()
    assert check.frozen_at == refrozen_at
    assert adjustment.warehouse == other.name
    assert [item.quantity for item in adjustment.items] == [-32]
    assert withdrawn.status == 'cancelled' and withdrawn.warehouse == source.name
    assert wms.StockTransaction.query.count() == movement_count and material.stock == 100


@pytest.mark.parametrize('blocker', ['scan', 'adjustment', 'stale_source'])
def test_confirmed_warehouse_correction_rejects_unresolved_links_or_stale_source(scene, blocker):
    client, source, other, material = scene
    check = wms.InventoryCheck(check_no='CK-WAREHOUSE-BLOCKED', warehouse=source.name,
                               status='pending', frozen_at=datetime(2026, 11, 20))
    wms.db.session.add(check)
    wms.db.session.flush()
    row = wms.InventoryCheckItem(inventory_check_id=check.id, material_id=material.id,
                               system_stock=60, actual_stock=58, difference=-2)
    wms.db.session.add(row)
    if blocker == 'scan':
        wms.db.session.add(wms.InventoryCheckScan(check_no='SCAN-BLOCKED', check_id=check.id,
                                                 status='completed', warehouse=source.name))
    if blocker == 'adjustment':
        wms.db.session.add(wms.AdjustmentOrder(adjustment_no='ADJ-BLOCKED', adjustment_type='stocktake',
                                              warehouse=source.name, source_type='check', source_id=check.id,
                                              status='pending'))
    wms.db.session.commit()

    result = document_post(client, '/check/save_table', json={
        'order_id': check.id,
        'header': {'warehouse_id': other.id, 'warehouse_change_from_id': other.id if blocker == 'stale_source' else source.id},
        'items': [{'line_id': row.id, 'material_id': material.id, 'actual_stock': 58}],
    }).get_json()
    assert result['status'] == 'error', result
    assert {'scan': '扫码', 'adjustment': '调整单', 'stale_source': '仓库已变化'}[blocker] in result['msg']
    wms.db.session.expire_all()
    assert check.warehouse == source.name and row.system_stock == 60
    assert wms.OperationAudit.query.filter_by(operation='change_check_warehouse').count() == 0
