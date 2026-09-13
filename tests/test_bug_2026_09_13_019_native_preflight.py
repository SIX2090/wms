from datetime import datetime, timedelta
from pathlib import Path

import pytest
import app as wms
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene, _stock


def _headers():
    user = wms.User.query.filter_by(username="reviewer").one()
    wms.db.session.add(wms.ApiToken(token="preflight-test", user_id=user.id,
        expires_at=datetime.now() + timedelta(hours=1)))
    wms.db.session.commit()
    return {"Authorization": "Bearer preflight-test"}


@pytest.mark.parametrize("endpoint", ["/api/outbound/preflight", "/api/outbound"])
def test_cumulative_warehouse_demand_before_writes(scene, monkeypatch, endpoint):
    client, source, other, material = scene
    _stock(material, source, 10, legacy=True)
    headers = _headers()
    calls = []
    monkeypatch.setattr(wms, "deduct_stock", lambda *args, **kwargs: calls.append(args))
    response = client.post(endpoint, headers=headers, json={
        "warehouse_code": source.code,
        "lines": [{"material_code": material.code, "quantity": 6}] * 2})
    assert response.status_code == 400
    message = response.get_json()["msg"]
    assert "本仓可用 10" in message and "本次 12" in message
    assert calls == []
    assert wms.OutOrder.query.count() == 0
    assert wms.StockTransaction.query.count() == 2


@pytest.mark.parametrize("available,quantity,expected", [(0, 1, 400), (10, 10, 200)])
def test_native_api_outbound_preflight(scene, available, quantity, expected):
    client, source, other, material = scene
    _stock(material, source, available, legacy=True)
    response = client.post("/api/outbound/preflight", headers=_headers(), json={
        "warehouse_code": source.code,
        "lines": [{"material_code": material.code, "quantity": quantity}]})
    assert response.status_code == expected, response.get_json()
    assert wms.OutOrder.query.count() == 0
    assert wms.MobileApiRequest.query.count() == 0
    assert wms.StockTransaction.query.count() == 2
    assert wms.get_warehouse_stock_quantities(other)[material.id] == 100
    assert material.stock == available + 100


@pytest.mark.parametrize("payload", [[], {"lines": []}, {"lines": [{"material_code": 12, "quantity": 1}]}])
def test_preflight_invalid_payload(scene, payload):
    client, *_ = scene
    response = client.post("/api/outbound/preflight", headers=_headers(), json=payload)
    assert response.status_code == 400


def test_preflight_requires_bearer(scene):
    client, *_ = scene
    assert client.post("/api/outbound/preflight", json={}).status_code == 401


def test_preflight_inactive_warehouse(scene):
    client, source, other, material = scene
    other.status = 'inactive'
    response = client.post('/api/outbound/preflight', headers=_headers(), json={
        'warehouse_code': other.code,
        'lines': [{'material_code': material.code, 'quantity': 1}]})
    assert response.status_code == 400
    assert '停用' in response.get_json()['msg']


def test_preflight_preserves_negative_stock_policy(scene):
    client, source, other, material = scene
    wms.set_system_setting('allow_negative_stock', '1')
    response = client.post('/api/outbound/preflight', headers=_headers(), json={
        'warehouse_code': source.code,
        'lines': [{'material_code': material.code, 'quantity': 1}]})
    assert response.status_code == 200
    assert wms.OutOrder.query.count() == 0


def test_android_preflight_before_submit_inside_offline_boundary():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'app/android-native-wms/app/src/main/java/com/factory/wms/data/repository/WmsRepository.kt').read_text(encoding='utf-8')
    method = source.split('suspend fun submitOutbound(', 1)[1].split('suspend fun submitStocktake(', 1)[0]
    assert method.index('submitWithOfflineFallback(') < method.index('api.preflightOutbound(request)')
    assert method.index('getOrThrow()') < method.index('api.submitOutbound(requestId, request)')
