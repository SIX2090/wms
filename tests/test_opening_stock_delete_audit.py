import json
from types import SimpleNamespace

import pytest

import app as wms
from routes.opening_stock import OPENING_STOCK_PURGE_PHRASE
from tests.document_revision_client import document_post
from tests.test_document_create_number_conflicts import case, rows
from tests.test_web_stock_posting_audit import fail_audit, posting_actors


@pytest.mark.parametrize('scope, operation', [
    ('document', 'delete_opening_stock_doc'),
    ('lines', 'delete_opening_stock_lines'),
    ('all', 'purge_opening_stock'),
])
def test_opening_stock_delete_audit_rolls_back_deletion_and_stock(posting_actors, scope, operation):
    creator, poster, ids = posting_actors
    doc_ids = []
    for warehouse_id, material_id, quantity in zip((ids['a'], ids['b']), ids['mats'], (3, 7)):
        response = creator.post('/opening_stock/save', json={
            'warehouse_id': warehouse_id, 'date': '2026-11-01',
            'items': [{'material_id': material_id, 'warehouse_id': warehouse_id, 'quantity': quantity, 'price': 1}],
        })
        assert response.status_code == 200 and response.json['status'] == 'success', response.json
        doc_ids.append(response.json['doc_id'])

    models = (wms.OpeningStockDoc, wms.OpeningStock, wms.Material, wms.StockTransaction,
              wms.LocationInventory, wms.OperationAudit, wms.OperationLog)
    doc_id = doc_ids[0]
    with wms.app.app_context():
        doc_number = wms.db.session.get(wms.OpeningStockDoc, doc_id).doc_no
        line_id = wms.OpeningStock.query.filter_by(doc_id=doc_id).one().id
        before = [rows(model) for model in models]

    urls = {'document': f'/opening_stock/{doc_id}/delete',
            'lines': f'/opening_stock/{doc_id}/lines/delete', 'all': '/opening_stock/delete_all'}
    payloads = {'document': {}, 'lines': {'line_ids': [line_id]},
                'all': {'confirm': True, 'confirm_phrase': OPENING_STOCK_PURGE_PHRASE}}
    with fail_audit(operation) as attempted:
        failed = document_post(poster, urls[scope], json=payloads[scope])
    assert failed.json['status'] == 'error', failed.json
    assert attempted == [None if scope == 'all' else doc_id]
    with wms.app.app_context():
        assert [rows(model) for model in models] == before

    saved = document_post(poster, urls[scope], json=payloads[scope])
    assert saved.json['status'] == 'success', saved.json
    count = 2 if scope == 'all' else 1
    with wms.app.app_context():
        audit = wms.OperationAudit.query.filter_by(operation=operation, target_type='opening_stock').one()
        audit_id, target_name = audit.id, audit.target_name
        assert audit.username == 'web-stock-poster' and audit.user_id == ids['poster']
        assert audit.target_id == (None if scope == 'all' else doc_id)
        assert target_name == ('全部期初库存' if scope == 'all' else doc_number)
        old, new = json.loads(audit.old_data), json.loads(audit.new_data)
        assert old['line_count'] == new['reversed_lines'] == count
        assert old['items_truncated'] == 0 and len(old['items']) == count
        assert old['items'][0] == {
            'id': line_id, 'doc_id': doc_id, 'material_id': ids['mats'][0],
            'warehouse_id': ids['a'], 'quantity': 3,
        }
        assert wms.OpeningStock.query.count() == 2 - count
        assert wms.OpeningStockDoc.query.count() == {'document': 1, 'lines': 2, 'all': 0}[scope]
        assert wms.db.session.get(wms.Material, ids['mats'][0]).stock == 30
        assert wms.db.session.get(wms.Material, ids['mats'][1]).stock == (30 if scope == 'all' else 37)

    detail = creator.get('/operation_audit', query_string={'search': target_name, 'audit_detail': audit_id})
    assert detail.status_code == 200
    page = detail.get_data(as_text=True)
    assert f'影响 {count} 行' in page and f'已回冲 {count} 行' in page
    assert 'web-stock-poster' in page and 'DC-M1' in page and ids['names'][0] in page


def test_opening_stock_deleted_lines_audit_marks_truncated_sample():
    from routes.opening_stock import _opening_stock_deleted_lines_audit

    lines = [SimpleNamespace(id=index, doc_id=None, material_id=1, warehouse_id=None, quantity=1)
             for index in range(53)]
    audit = _opening_stock_deleted_lines_audit(lines)
    assert audit['line_count'] == 53 and audit['items_truncated'] == 3
    assert [item['id'] for item in audit['items']] == list(range(50))
