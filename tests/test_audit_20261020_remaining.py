"""A04–A08：真实鉴权、跨账号限流、仓库文本引用、期初账与 HTTPS 回归。"""
from datetime import date, datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

import app as wms
from app import db


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setitem(wms.app.config, 'TESTING', True)
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', False)
    monkeypatch.setitem(wms.app.config, 'TRUSTED_PROXIES', [])
    with wms.app.app_context():
        assert db.engine.url.database == ':memory:'
        db.session.remove()
        db.drop_all()
        db.create_all()
        db.session.add_all([
            wms.User(username='audit', role='admin', must_change_password=False,
                     password_hash=generate_password_hash('fixture-password')),
            wms.Warehouse(code='WA', name='仓A', status='active', is_default=True),
            wms.Warehouse(code='WB', name='仓B', status='active'),
            wms.Unit(code='U', name='个'),
        ])
        db.session.flush()
        db.session.add(wms.Material(code='M', name='物料', unit_id=1, stock=0))
        db.session.add(wms.ApiToken(token=wms.hash_access_token('fixture-bearer'),
                                   user_id=1, expires_at=datetime.now() + timedelta(days=1)))
        db.session.commit()
    client = wms.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = '1'
        session['_fresh'] = True
    yield client
    with wms.app.app_context():
        db.session.remove()


@pytest.mark.parametrize('path', [
    '/mobile/api/scan_submit', '/api/ai/document_ocr', '/api/ai/document_ocr_excel',
    '/print_queue/jobs',
])
@pytest.mark.parametrize('authorization', ['', 'Bearer forged'])
def test_session_writes_require_csrf_even_with_forged_bearer(client, monkeypatch, path, authorization):
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', True)
    response = client.post(path, json={}, headers={'Authorization': authorization})
    if path == '/print_queue/jobs' and authorization:
        assert response.status_code == 401
        return
    assert response.status_code == 400
    assert 'CSRF' in response.get_json()['msg']


@pytest.mark.parametrize('factory', ['mobile', 'mobile_role', 'app', 'app_role', 'excel'])
@pytest.mark.parametrize('channel', ['session_missing', 'session_valid', 'bearer', 'anonymous'])
def test_dual_auth_decorators(client, monkeypatch, factory, channel):
    from flask_login import login_user
    from flask_wtf.csrf import generate_csrf
    from routes import mobile, ai_excel
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', True)
    decorators = {
        'mobile': mobile._web_or_api_required,
        'mobile_role': mobile._web_or_api_role_required('warehouse'),
        'app': wms.web_or_api_required,
        'app_role': wms.web_or_api_role_required('warehouse'),
        'excel': ai_excel._web_or_api_role_required('warehouse'),
    }
    called = []
    @decorators[factory]
    def target():
        called.append(True)
        return 'allowed'
    headers = {'Authorization': 'Bearer fixture-bearer'} if channel == 'bearer' else {}
    with wms.app.test_request_context('/probe', method='POST', headers=headers):
        if channel.startswith('session'):
            login_user(db.session.get(wms.User, 1))
        if channel == 'session_valid':
            wms.request.environ['HTTP_X_CSRFTOKEN'] = generate_csrf()
        result = target()
        if channel == 'session_missing':
            assert not called
            assert result[1] == 400
        elif channel == 'anonymous':
            assert not called
            assert result[1] == 401
        else:
            assert result == 'allowed' and called


def test_api_login_limits_unknown_users_and_shares_web_bucket(client, monkeypatch):
    import rate_limit
    monkeypatch.setattr(wms, 'LOGIN_IP_RATE_LIMIT_PER_MINUTE', 3)
    anonymous = wms.app.test_client()
    for index in range(3):
        assert anonymous.post('/api/login', json={
            'username': f'unknown-{index}', 'password': 'wrong',
        }).status_code == 401
    assert anonymous.post('/api/login', json={
        'username': 'audit', 'password': 'fixture-password',
    }).status_code == 429
    assert anonymous.post('/login', data={
        'username': 'audit', 'password': 'fixture-password',
    }).status_code == 429
    assert anonymous.post('/api/login', json={
        'username': 'audit', 'password': 'fixture-password',
    }, environ_overrides={'REMOTE_ADDR': '192.0.2.9'}).status_code == 200
    # 过期即恢复；不是重启服务或改账号密码才能解锁。
    rate_limit.reset()
    rate_limit.record_failure('login_fail:127.0.0.1', 60, now=0)
    assert anonymous.post('/api/login', json={
        'username': 'audit', 'password': 'fixture-password',
    }).status_code == 200


def test_api_login_wrong_password_and_untrusted_forwarding(client, monkeypatch):
    monkeypatch.setattr(wms, 'LOGIN_IP_RATE_LIMIT_PER_MINUTE', 1)
    anonymous = wms.app.test_client()
    assert anonymous.post('/api/login', json={
        'username': 'audit', 'password': 'wrong',
    }, headers={'X-Forwarded-For': '192.0.2.10'}).status_code == 401
    assert anonymous.post('/api/login', json={
        'username': 'audit', 'password': 'fixture-password',
    }, headers={'X-Forwarded-For': '192.0.2.11'}).status_code == 429


@pytest.mark.parametrize('change_code', [False, True])
def test_warehouse_rename_all_text_columns(client, change_code):
    from models import documents
    models = [
        (documents.InventoryCheck, 'check_no'),
        (documents.InventoryCheckScan, 'check_no'),
        (documents.AdjustmentOrder, 'adjustment_no'),
        (documents.SubcontractIssue, 'issue_no'),
        (documents.SubcontractReceive, 'receive_no'),
    ]
    with wms.app.app_context():
        for model, key in models:
            for index, warehouse in enumerate(['仓A', 'WA', '仓B', '', '历史未知']):
                extra = {'adjustment_type': 'profit'} if model is documents.AdjustmentOrder else {}
                db.session.add(model(**{key: f'{model.__name__}-{index}',
                                        'date': date.today(), 'warehouse': warehouse, **extra}))
        db.session.commit()
    response = client.post('/warehouse/1/edit', data={
        'name': '仓A新', 'code': 'WA2' if change_code else 'WA', 'status': 'active',
    })
    assert response.status_code == 200
    with wms.app.app_context():
        for model, key in models:
            assert [row.warehouse for row in model.query.order_by(model.id)] == [
                '仓A新', 'WA2' if change_code else 'WA', '仓B', '', '历史未知',
            ]


@pytest.mark.parametrize('quantity', [10, 5, 15])
@pytest.mark.parametrize('location_on', [False, True])
def test_opening_location_change_is_rejected_without_any_mutation(client, quantity, location_on):
    with wms.app.test_request_context():
        wms.set_system_setting('location_management_enabled', '1' if location_on else '0')
        material = db.session.get(wms.Material, 1)
        warehouse = db.session.get(wms.Warehouse, 1)
        opening, _ = wms._apply_opening_stock_balance(
            None, material, 10, 1, 10, '', warehouse, date.today(), 'L-A')
        db.session.commit()
        opening_id = opening.id
        before = [(r.location, r.quantity) for r in wms.LocationInventory.query.all()]
        txn_count = wms.StockTransaction.query.count()
        with pytest.raises(ValueError, match='库位'):
            wms._apply_opening_stock_balance(
                opening, material, quantity, 1, quantity, 'changed',
                warehouse, date.today(), 'L-B')
        db.session.rollback()
        assert db.session.get(wms.OpeningStock, opening_id).location == 'L-A'
        assert db.session.get(wms.OpeningStock, opening_id).quantity == 10
        assert db.session.get(wms.Material, 1).stock == 10
        assert wms.StockTransaction.query.count() == txn_count
        assert [(r.location, r.quantity) for r in wms.LocationInventory.query.all()] == before


@pytest.mark.parametrize('env', [None, '0', '1'])
def test_external_ai_http_never_sends_credentials(monkeypatch, env):
    if env is None:
        monkeypatch.delenv('WMS_AI_REQUIRE_HTTPS', raising=False)
    else:
        monkeypatch.setenv('WMS_AI_REQUIRE_HTTPS', env)
    with pytest.raises(RuntimeError, match='HTTPS'):
        wms._ai_llm_endpoint({'ai_llm_base_url': 'http://example.com/v1'})
    assert wms._ai_llm_endpoint({'ai_llm_base_url': 'https://example.com/v1'}).startswith('https://')
    assert wms._ai_llm_endpoint({'ai_llm_base_url': 'http://127.0.0.1:8000/v1'}).startswith('http://127.0.0.1')


@pytest.mark.parametrize('channel', ['v2', 'asr'])
def test_ai_v2_and_asr_block_http_before_network(monkeypatch, channel):
    from ai import providers
    def forbidden(*args, **kwargs):
        pytest.fail('明文地址不得进入网络调用')
    monkeypatch.setattr(providers.requests, 'post', forbidden)
    config = providers.OpenAICompatibleConfig(
        enabled=True, endpoint='http://example.com/v1', model='fixture',
        api_key='synthetic-key', timeout_seconds=1, max_tokens=10,
    )
    if channel == 'v2':
        assert providers.call_llm(config, [{'role': 'user', 'content': 'fixture'}]) is None
        return
    monkeypatch.setattr(wms, '_ai_llm_configured', lambda: True)
    monkeypatch.setattr(wms, '_asr_tokenhub_endpoint', lambda: 'http://example.com/v1/asr')
    text, error = wms._asr_call_tokenhub(b'fixture-audio')
    assert text is None and 'HTTPS' in error


@pytest.mark.parametrize('path', ['/opening_stock/batch_save', '/opening_stock/save'])
def test_opening_batch_location_rejection_rolls_back_earlier_rows(client, path):
    with wms.app.app_context():
        wms.set_system_setting('location_management_enabled', '1')
        db.session.add(wms.Material(code='M2', name='物料2', unit_id=1, stock=0))
        db.session.commit()
    payload = {'warehouse_id': 1, 'date': '2026-10-20', 'items': [
        {'material_id': 1, 'warehouse_id': 1, 'quantity': 10, 'location': 'L-A'},
        {'material_id': 2, 'warehouse_id': 1, 'quantity': 20, 'location': 'L-A'},
    ]}
    response = client.post(path, json=payload)
    assert response.status_code == 200, response.get_json()
    payload['doc_id'] = response.get_json()['doc_id']
    payload['items'][0]['quantity'] = 12
    payload['items'][1]['location'] = 'L-B'
    response = client.post(path, json=payload)
    assert response.status_code == 400 and '库位' in response.get_json()['msg']
    with wms.app.app_context():
        assert [r.quantity for r in wms.OpeningStock.query.order_by(wms.OpeningStock.material_id)] == [10, 20]
        assert [r.stock for r in wms.Material.query.order_by(wms.Material.id)] == [10, 20]
        assert {r.location for r in wms.LocationInventory.query.all()} == {'L-A'}
        assert sum(r.quantity for r in wms.LocationInventory.query.all()) == 30
        assert wms.StockTransaction.query.count() == 2


def test_warehouse_rename_transaction_rolls_back(client, monkeypatch):
    from sqlalchemy.orm import Query
    with wms.app.app_context():
        db.session.add(wms.InventoryCheck(check_no='CHECK', warehouse='仓A'))
        db.session.commit()
    original = Query.update
    count = [0]
    def fail_midway(self, *args, **kwargs):
        count[0] += 1
        if count[0] == 9:
            raise RuntimeError('fixture forced failure')
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Query, 'update', fail_midway)
    assert client.post('/warehouse/1/edit', data={
        'name': '仓A新', 'code': 'WA2', 'status': 'active',
    }).status_code == 500
    with wms.app.app_context():
        assert db.session.get(wms.Warehouse, 1).name == '仓A'
        assert db.session.get(wms.Warehouse, 1).code == 'WA'
        assert wms.InventoryCheck.query.one().warehouse == '仓A'


def test_warehouse_cross_name_code_collision_rejected(client):
    response = client.post('/warehouse/1/edit', data={
        'name': 'WB', 'code': 'WA', 'status': 'active',
    })
    assert response.status_code == 400
    with wms.app.app_context():
        assert db.session.get(wms.Warehouse, 1).name == '仓A'
        assert db.session.get(wms.Warehouse, 2).name == '仓B'


def test_validate_session_write(client, monkeypatch):
    from flask_login import login_user
    from session_csrf import validate_session_write
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', True)
    with wms.app.test_request_context('/mobile/api/probe', method='GET'):
        login_user(db.session.get(wms.User, 1))
        assert validate_session_write() is None
