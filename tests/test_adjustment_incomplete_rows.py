"""库存调整保留未录完的行，粘贴不得覆盖人工输入。"""
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.document_revision_client import document_post
from tests.test_document_validation_feedback import function
from tests.test_requisition_location_flow_integration import scene, wms


def test_adjustment_partial_rows_are_neither_submitted_nor_reused_by_paste():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    source = (Path(__file__).resolve().parents[1] / 'app/templates/adjustment_add.html').read_text('utf8')
    functions = '\n'.join(function(source, name) for name in ('adjustmentRowHasDetails', 'collectItems', 'findEmptyRow'))
    harness = """
const assert = require('node:assert/strict');
function row(code, quantity, location, reason) {
    const values = {'.material-code':code, '.adjust-qty':quantity, '.adjust-location':location, '.adjust-reason':reason};
    const fields = Object.fromEntries(Object.entries(values).map(([key,value]) => [key,{value,style:{}}]));
    return {querySelector: key => fields[key]};
}
const empty = row('', '', ' ', '');
const rows = [row('M','2','',''), row('','0','',''), row('','','B',''), row('','','','待查'), empty];
const document = {querySelectorAll: () => rows};
const WMS = {normalizeDecimalInput() {}};
const findMaterialByCode = code => ({id:1, code});
const result = collectItems();
assert.deepEqual(result.items.map(item => item.quantity), [2]);
assert.deepEqual(result.invalidRows.map(message => message.match(/第 (\\d+) 行/)[1]), ['2','3','4']);
assert.equal(findEmptyRow(), empty);
assert.equal(rows[3].querySelector('.adjust-reason').value, '待查');
"""
    subprocess.run([node, '-e', functions + harness], check=True, timeout=20)


def test_adjustment_mixed_submission_preserves_saved_rows(scene):
    client, _, warehouse_id, _, _ = scene
    wms.User.query.filter_by(username='u1-integration').one().role = 'warehouse'
    wms.db.session.commit()
    header = dict(adjustment_type='surplus', date='2026-11-22', warehouse_id=warehouse_id)
    line = dict(code='U1-M', quantity=3, location='Rack-1')
    saved = client.post('/adjustment/add', json={**header, 'items':[line]}).get_json()
    assert saved['status'] == 'success'
    header['order_id'] = saved['id']
    invalid = document_post(client, '/adjustment/add', json={**header, 'items':[{**line, 'quantity':9}, {'quantity':2}]})
    assert invalid.status_code == 400 and '第 2 行' in invalid.get_json()['msg']
    invalid_form = document_post(client, '/adjustment/add', data={**header, 'reason':'待补物料'})
    assert invalid_form.status_code == 400 and '第 1 行' in invalid_form.get_json()['msg']
    wms.db.session.expire_all()
    order = wms.db.session.get(wms.AdjustmentOrder, saved['id'])
    assert order.status == 'pending'
    assert [item.quantity for item in order.items] == [3]
