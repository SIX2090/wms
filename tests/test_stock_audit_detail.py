import json

import app as wms
from tests.test_document_create_number_conflicts import case


def record(target_type, target_name, *, before=None, after=None):
    row = wms.OperationAudit(
        target_type=target_type, target_name=target_name, target_id=2,
        username='audit-poster', operation='complete_in_order', status='success',
        reason='完成入库单', old_data=before, new_data=after,
    )
    wms.db.session.add(row)
    wms.db.session.flush()
    return row.id


def test_stock_audit_detail_keeps_filters_and_displays_only_selected_record(case):
    clients, ids = case
    with wms.app.app_context():
        mid = ids['mats'][0]
        first = record('in_order', 'IN-AUDIT-50', before='{"status":"pending"}',
                       after=json.dumps({
                           'status': 'completed', 'warehouse': ids['names'][0],
                           'items': [{'material_id': mid, 'quantity': 3}],
                           'movements': [
                               {'material_id': mid, 'warehouse_id': ids['a'], 'quantity': 3},
                               {'material_id': mid, 'warehouse_id': 999, 'quantity': -0.0123,
                                'location': '<script>unsafe()</script>'},
                           ],
                           'password': 'private-field-marker',
                       }))
        other = record('out_order', 'OUT-AUDIT-51', after='{"warehouse":"other-record-marker"}')
        wms.db.session.commit()

    client = clients[0]
    params = {'search': 'IN-AUDIT-50', 'source': 'operation_audit', 'embedded': '1'}
    listing = client.get('/operation_audit', query_string=params).get_data(as_text=True)
    assert f'audit_detail={first}#audit-{first}' in listing
    assert 'IN-AUDIT-50' in listing and 'audit-poster' in listing
    assert 'other-record-marker' not in listing and '本次库存流水' not in listing

    opened = client.get('/operation_audit', query_string={**params, 'audit_detail': first})
    page = opened.get_data(as_text=True)
    assert opened.status_code == 200
    assert '收起变动明细' in page and 'search=IN-AUDIT-50' in page and 'embedded=1' in page
    assert '变更前' in page and '草稿' in page and '变更后' in page and '已完成' in page
    assert '本次库存流水' in page and 'DC-M1' in page and ids['names'][0] in page
    assert '>+3</td>' in page and '>-0.0123</td>' in page and '仓库 #999' in page
    assert '&lt;script&gt;unsafe()&lt;/script&gt;' in page
    assert '<script>unsafe()</script>' not in page and 'private-field-marker' not in page

    hidden = client.get('/operation_audit', query_string={**params, 'audit_detail': other})
    assert 'other-record-marker' not in hidden.get_data(as_text=True)


def test_stock_audit_detail_accepts_legacy_changes_and_rejects_unrelated_payloads(case):
    clients, ids = case
    with wms.app.app_context():
        old_items = json.dumps({'items': {'41': {'material_id': ids['mats'][0], 'qty': 2}}})
        legacy = record('in_order', 'IN-LEGACY', before=old_items, after='malformed JSON')
        bad = record('adjustment', 'ADJ-LEGACY', after='["non-object"]')
        unrelated = record('user', 'OTHER-AUDIT', after='{"warehouse":"unrelated-marker"}')
        warehouse = wms.User(username='warehouse-audit-read', role='warehouse',
                             password_hash='unused', must_change_password=False)
        wms.db.session.add(warehouse)
        wms.db.session.flush()
        warehouse_id = warehouse.id
        wms.db.session.commit()

    client, restricted = clients
    page = client.get('/operation_audit', query_string={'audit_detail': legacy}).get_data(as_text=True)
    assert '单据明细' in page and 'DC-M1' in page and '>2</td>' in page
    damaged = client.get('/operation_audit', query_string={'audit_detail': bad}).get_data(as_text=True)
    assert '这条审计记录没有可展示的库存明细' in damaged
    other = client.get('/operation_audit', query_string={'audit_detail': unrelated}).get_data(as_text=True)
    assert 'unrelated-marker' not in other and f'audit_detail={unrelated}#' not in other

    with restricted.session_transaction() as session:
        session['_user_id'] = str(warehouse_id)
    rejected = restricted.get('/operation_audit', query_string={'audit_detail': legacy})
    assert rejected.status_code in (302, 403)
    assert 'IN-LEGACY' not in rejected.get_data(as_text=True)
