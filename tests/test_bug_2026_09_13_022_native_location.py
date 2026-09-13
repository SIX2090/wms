import pytest
import app as wms
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene
from tests.test_bug_2026_09_13_019_native_preflight import _headers


def _payload(warehouse, material, locations):
    return {'warehouse_code': warehouse.code, 'lines': [
        {'material_code': material.code, 'quantity': 2, 'location_code': location}
        for location in locations]}


@pytest.mark.parametrize('endpoint', ['/api/inbound', '/api/outbound', '/api/outbound/preflight'])
def test_mixed_locations_rejected_before_writes(scene, endpoint):
    client, source, other, material = scene
    wms.set_system_setting('location_management_enabled', '1')
    response = client.post(endpoint, headers=_headers(), json=_payload(other, material, ['L1', 'L2']))
    assert response.status_code == 400
    assert '分单' in response.get_json()['msg']
    assert wms.OutOrder.query.count() == wms.InOrder.query.count() == 0


@pytest.mark.parametrize('endpoint,model', [('/api/inbound', wms.InOrder), ('/api/outbound', wms.OutOrder)])
def test_document_preserves_location(scene, monkeypatch, endpoint, model):
    client, source, other, material = scene
    wms.set_system_setting('location_management_enabled', '1')
    wms.db.session.add(wms.LocationInventory(material_id=material.id, warehouse_id=other.id, location='L1', quantity=100))
    wms.db.session.commit()
    monkeypatch.setattr('routes.print_queue.enqueue_auto_print_job', lambda *args, **kwargs: None)
    response = client.post(endpoint, headers=_headers(), json=_payload(other, material, ['L1']))
    assert response.status_code == 200, response.get_json()
    assert model.query.one().location == 'L1'
    assert wms.get_warehouse_stock_quantities(other)[material.id] == material.stock


def test_inbound_disabled_does_not_create_hidden_location(scene, monkeypatch):
    client, source, other, material = scene
    monkeypatch.setattr('routes.print_queue.enqueue_auto_print_job', lambda *args, **kwargs: None)
    response = client.post('/api/inbound', headers=_headers(), json=_payload(other, material, ['L1']))
    assert response.status_code == 200
    assert wms.LocationInventory.query.count() == 0


def test_preflight_location_does_not_borrow_another_bin(scene):
    client, source, other, material = scene
    wms.set_system_setting('location_management_enabled', '1')
    wms.db.session.add(wms.LocationInventory(material_id=material.id, warehouse_id=other.id, location='L2', quantity=100))
    wms.db.session.commit()
    response = client.post('/api/outbound/preflight', headers=_headers(), json=_payload(other, material, ['L1']))
    assert response.status_code == 400
    assert 'L1' in response.get_json()['msg']
    assert wms.OutOrder.query.count() == 0
