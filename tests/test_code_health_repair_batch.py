"""Runtime regressions for report BUG-1/2/3/4; synthetic data only."""
import pytest
from sqlalchemy import event
import app as w


@pytest.fixture()
def mobile_case(monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    monkeypatch.setitem(w.app.config, 'PROPAGATE_EXCEPTIONS', False)
    monkeypatch.setattr('routes.print_queue.enqueue_auto_print_job', lambda *a, **k: None)
    with w.app.app_context():
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.session.remove(); w.db.drop_all(); w.db.create_all()
        user = w.User(username='health-test', role='admin', password_hash='unused', must_change_password=False)
        wh = w.Warehouse(code='HEALTH', name='验证仓', status='active', is_default=True)
        other = w.Warehouse(code='OTHER', name='另一仓', status='active')
        mat = w.Material(code='HEALTH', name='合成物料', stock=0, price=0)
        w.db.session.add_all([user, wh, other, mat]); w.db.session.commit()
        uid = user.id
    client = w.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(uid); session['_fresh'] = True
    yield client, {'mode': 'in', 'code': 'HEALTH', 'quantity': 5, 'warehouse': '验证仓', 'request_id': 'one'}
    with w.app.app_context():
        w.db.session.remove()


def test_after_sale_edit_renders(mobile_case):
    client, _ = mobile_case
    with w.app.app_context():
        order = w.AfterSaleOutOrder(order_no='HEALTH-AS', warehouse='验证仓', operator_id=w.User.query.one().id, status='pending')
        w.db.session.add(order); w.db.session.commit(); oid = order.id
    assert client.get(f'/after_sale_out/{oid}/edit').status_code == 200


def test_batch_error_keeps_original_exception(mobile_case, monkeypatch, caplog):
    client, _ = mobile_case
    def fail():
        raise RuntimeError('synthetic-storage-fault')
    monkeypatch.setattr(w.db.session, 'flush', fail)
    response = client.post('/mobile/api/scan_batch_draft', json={'mode': 'in', 'warehouse': '验证仓', 'lines': [{'material_code': 'HEALTH', 'quantity': 1}]})
    assert response.status_code == 500
    assert response.json['msg'] == '生成草稿失败，请稍后重试'
    assert 'synthetic-storage-fault' in caplog.text
    assert 'NameError' not in caplog.text


def test_navigation_catalog(mobile_case):
    from ai.tools.registry import list_ai_tool_specs
    client, _ = mobile_case
    response = client.get('/api/ai/v2/tools/navigation/skills')
    assert response.status_code == 200
    assert response.json['data'] == [{'name': s.name, 'description': s.description, 'category': s.audit_category} for s in list_ai_tool_specs()]
    for path in ('apis', 'help'):
        assert client.get('/api/ai/v2/tools/navigation/' + path).status_code == 200
        assert w.app.test_client().get('/api/ai/v2/tools/navigation/' + path).status_code in (302, 401)


def test_mobile_document_idempotent(mobile_case):
    client, body = mobile_case
    replies = [client.post('/mobile/api/scan_submit', json=body) for _ in range(3)]
    assert [r.status_code for r in replies] == [200] * 3
    assert replies[0].json == replies[1].json == replies[2].json
    with w.app.app_context():
        assert w.InOrder.query.count() == 1
        assert w.Material.query.one().stock == 5
        assert w.StockTransaction.query.count() == 1
        assert w.MobileApiRequest.query.count() == 1
    for i in range(3):
        assert client.post('/mobile/api/scan_submit', json=dict(body, quantity=1, request_id=f'new-{i}')).status_code == 200
    with w.app.app_context():
        assert w.InOrder.query.count() == 4
        assert w.Material.query.one().stock == 8
        assert sum(w.get_warehouse_stock_quantities(w.Warehouse.query.filter_by(code='OTHER').one()).values()) == 0


def test_mobile_conflict_and_validation_retry(mobile_case):
    client, body = mobile_case
    assert client.post('/mobile/api/scan_submit', json=dict(body, quantity=0)).status_code == 400
    assert client.post('/mobile/api/scan_submit', json=body).status_code == 200
    assert client.post('/mobile/api/scan_submit', json=dict(body, quantity=2)).status_code == 409
    assert w.app.test_client().post('/mobile/api/scan_submit', json=body).status_code == 401


def test_mobile_outbound_replays_without_double_deduction(mobile_case):
    client, body = mobile_case
    assert client.post('/mobile/api/scan_submit', json=body).status_code == 200
    outbound = dict(body, mode='out', quantity=2, request_id='out')
    one = client.post('/mobile/api/scan_submit', json=outbound)
    two = client.post('/mobile/api/scan_submit', json=outbound)
    assert one.status_code == two.status_code == 200
    assert one.json == two.json
    with w.app.app_context():
        assert w.OutOrder.query.count() == 1
        assert w.Material.query.one().stock == 3


def test_mobile_batch_and_confirmation_replay(mobile_case):
    client, _ = mobile_case
    body = {'mode': 'in', 'warehouse': '验证仓', 'request_id': 'batch', 'lines': [{'material_code': 'HEALTH', 'quantity': 2}]}
    first = client.post('/mobile/api/scan_batch_draft', json=body)
    again = client.post('/mobile/api/scan_batch_draft', json=body)
    assert first.status_code == again.status_code == 200
    assert first.json == again.json
    oid = first.json['data']['order_id']
    confirm = {'order_type': 'in', 'request_id': 'confirm'}
    first = client.post(f'/mobile/api/scan_draft_confirm/{oid}', json=confirm)
    again = client.post(f'/mobile/api/scan_draft_confirm/{oid}', json=confirm)
    assert first.status_code == again.status_code == 200
    assert first.json == again.json
    assert client.post(f'/mobile/api/scan_draft_confirm/{oid}', json=dict(confirm, request_id='other')).status_code == 400
    with w.app.app_context():
        assert w.InOrder.query.count() == 1
        assert w.Material.query.one().stock == 2


def test_mobile_commit_failure_releases_claim(mobile_case):
    client, body = mobile_case
    with w.app.app_context():
        engine = w.db.engine
    def fail(connection):
        raise RuntimeError('synthetic-commit-fault')
    event.listen(engine, 'commit', fail)
    try:
        assert client.post('/mobile/api/scan_submit', json=body).status_code == 500
    finally:
        event.remove(engine, 'commit', fail)
    with w.app.app_context():
        assert w.InOrder.query.count() == w.MobileApiRequest.query.count() == 0
        assert w.Material.query.one().stock == 0
    assert client.post('/mobile/api/scan_submit', json=body).status_code == 200


def test_mobile_stocktake_replays_and_preserves_inventory(mobile_case):
    client, body = mobile_case
    with w.app.app_context():
        check = w.InventoryCheck(check_no='CHECK-HEALTH', warehouse='验证仓', status='pending')
        w.db.session.add(check); w.db.session.commit(); oid = check.id
    payload = dict(body, mode='check', actual_stock=3, check_id=oid)
    first = client.post('/mobile/api/scan_submit', json=payload)
    again = client.post('/mobile/api/scan_submit', json=payload)
    assert first.status_code == again.status_code == 200
    assert first.json == again.json
    with w.app.app_context():
        assert w.InventoryCheckScan.query.count() == 1
        assert w.Material.query.one().stock == 0


def test_mobile_bearer_replay_and_csrf_boundary(mobile_case, monkeypatch):
    client, body = mobile_case
    from types import SimpleNamespace
    with w.app.app_context():
        uid = w.User.query.one().id
    monkeypatch.setattr(w, 'get_bearer_user', lambda: SimpleNamespace(id=uid, role='warehouse'))
    bearer = w.app.test_client()
    one = bearer.post('/mobile/api/scan_submit', json=body)
    two = bearer.post('/mobile/api/scan_submit', json=body)
    assert one.status_code == two.status_code == 200
    assert one.json == two.json
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', True)
    assert client.post('/mobile/api/scan_submit', json=body).status_code == 400
