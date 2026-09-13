import app as wms
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene
from tests.test_bug_2026_09_13_019_native_preflight import _headers


def test_native_api_location_options(scene):
    client, source, other, material = scene
    wms.set_system_setting('location_management_enabled', '1')
    for warehouse, location in [(source, 'L1'), (source, 'L2'), (other, 'OTHER')]:
        wms.db.session.add(wms.LocationInventory(material_id=material.id,
            warehouse_id=warehouse.id, location=location, quantity=1))
    wms.db.session.commit()
    headers = _headers()
    response = client.get('/api/mobile/location/options', headers=headers,
        query_string={'warehouse_code': source.code, 'page_size': 1})
    first = response.get_json()['data']
    assert first['items'] == ['L1']
    assert (first['total'], first['page'], first['page_size'], first['total_pages']) == (2, 1, 1, 2)
    assert first['enabled'] is True and first['default_location'] is None
    second = client.get('/api/mobile/location/options', headers=headers,
        query_string={'warehouse_code': source.code, 'page_size': 1, 'page': 2}).get_json()['data']
    assert second['items'] == ['L2']
    assert wms.StockTransaction.query.count() == 1


def test_location_options_disabled_and_bad_warehouse(scene):
    client, source, other, material = scene
    headers = _headers()
    data = client.get('/api/mobile/location/options', headers=headers,
        query_string={'warehouse_code': source.code}).get_json()['data']
    assert data['enabled'] is False and data['items'] == []
    assert client.get('/api/mobile/location/options', headers=headers,
        query_string={'warehouse_code': 'not-found'}).status_code == 400
    assert client.get('/api/mobile/location/options').status_code == 401
