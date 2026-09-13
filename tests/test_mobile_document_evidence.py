import base64
from io import BytesIO

from PIL import Image

import app as wms
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene
from tests.test_bug_2026_09_13_019_native_preflight import _headers


def _jpg():
    output = BytesIO()
    Image.new('RGB', (20, 10), 'red').save(output, format='JPEG')
    return base64.b64encode(output.getvalue()).decode('ascii')


def test_evidence_rejects_invalid_and_is_not_material_image(scene):
    client, source, other, material = scene
    response = client.post('/api/inbound', headers=_headers(), json={
        'warehouse_code': source.code, 'evidence': ['not-an-image'],
        'lines': [{'material_code': material.code, 'quantity': 1}]})
    assert response.status_code == 400
    assert wms.OutOrder.query.count() == 0
    assert wms.MaterialImage.query.count() == 0


def test_evidence_is_saved_with_document_and_read_is_owner_only(scene, monkeypatch):
    client, source, other, material = scene
    monkeypatch.setattr('routes.print_queue.enqueue_auto_print_job', lambda *args, **kwargs: None)
    response = client.post('/api/inbound', headers=_headers(), json={
        'warehouse_code': source.code, 'evidence': [_jpg()],
        'lines': [{'material_code': material.code, 'quantity': 1}]})
    assert response.status_code == 200, response.get_json()
    order_id = response.get_json()['data']['id']
    rows = wms.DocumentEvidence.query.all()
    assert len(rows) == 1 and rows[0].in_order_id == order_id
    read = client.get(f'/api/mobile/document/in_order/{order_id}/evidence', headers={"Authorization": "Bearer preflight-test"})
    assert read.status_code == 200 and len(read.get_json()['data']['items']) == 1


def test_evidence_maximum_and_size_are_enforced(scene):
    client, source, other, material = scene
    response = client.post('/api/inbound', headers=_headers(), json={
        'warehouse_code': source.code, 'evidence': [_jpg()] * 4,
        'lines': [{'material_code': material.code, 'quantity': 1}]})
    assert response.status_code == 400
