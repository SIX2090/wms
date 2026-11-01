"""Preview-consent boundary through real HTTP; execution is a nonmutating sentinel."""
import pytest
import app as m
from tests.test_round26_input_http import http_case

@pytest.fixture
def consent_case(http_case, monkeypatch):
    clients, ids, state = http_case
    with m.app.app_context():
        target = m.db.session.get(m.Material, ids['material'])
        source = m.Material(code='QA30-SOURCE', name=target.name, unit_id=target.unit_id, stock=0)
        other = m.Material(code='QA30-OTHER', name=target.name, unit_id=target.unit_id, stock=0)
        m.db.session.add_all([source, other]); m.db.session.commit()
        ids['source'], ids['other'] = source.id, other.id
    calls = []
    def stop_before_irreversible(target, source, **options):
        calls.append((target, source))
        raise ValueError('QA30_STOP_BEFORE_IRREVERSIBLE_EXECUTION')
    monkeypatch.setattr(m, 'merge_material_duplicates', stop_before_irreversible)
    yield clients, ids, state, calls

def preview(c, ids, target='QA27-M', keep_alias=True):
    response = c.post('/material/merge_preview', json={
        'source_code':'QA30-SOURCE', 'target_code':target, 'manual_review':True, 'keep_alias':keep_alias})
    assert response.status_code == 200, response.json
    return response.json['data']

def execute(c, ids, token='', target='QA27-M', keep_alias=True):
    return c.post(f"/material/{ids['source']}/merge", json={
        'target_code':target, 'confirm':True, 'identity_confirmed':True,
        'keep_alias':keep_alias, 'preview_token':token})

def test_execution_without_prior_preview_never_reaches_merge(consent_case):
    clients, ids, state, calls = consent_case
    before = state()
    response = execute(clients(),ids)
    assert response.status_code == 409, response.json
    assert calls == []
    assert state() == before

@pytest.mark.parametrize('change', ['target', 'identity', 'stock', 'references', 'reference_contents', 'options', 'tamper'])
def test_changed_or_forged_preview_never_reaches_merge(consent_case, change):
    clients, ids, state, calls = consent_case
    c = clients()
    plan = preview(c, ids)
    token = plan.get('preview_token', 'OLD_NO_TOKEN')
    target, alias = 'QA27-M', True
    with m.app.app_context():
        if change == 'identity':
            m.db.session.get(m.Material, ids['source']).spec = 'Changed after preview'
        elif change == 'stock':
            m.db.session.get(m.Material, ids['source']).stock = 1
        elif change == 'references':
            m.db.session.add(m.StockTransaction(material_id=ids['source'],warehouse_id=ids['a'],quantity=0,transaction_type='in'))
        elif change == 'reference_contents':
            m.StockTransaction.query.filter_by(material_id=ids['material']).first().remark = 'Changed without changing row count'
        m.db.session.commit()
    if change == 'target': target = 'QA30-OTHER'
    if change == 'options': alias = False
    if change == 'tamper': token = token+'x'
    before = state()
    response = execute(c,ids,token,target,alias)
    assert response.status_code == 409, response.json
    assert calls == []
    assert state() == before

@pytest.mark.parametrize('keep_alias', [True, False])
def test_valid_preview_reaches_only_nonmutating_execution_sentinel(consent_case, keep_alias):
    clients, ids, state, calls = consent_case
    c = clients()
    plan = preview(c, ids, keep_alias=keep_alias)
    assert isinstance(plan.get('preview_token'),str) and plan['preview_token']
    before = state()
    response = execute(c,ids,plan['preview_token'],keep_alias=keep_alias)
    assert response.status_code == 400 and response.json['msg'] == 'QA30_STOP_BEFORE_IRREVERSIBLE_EXECUTION'
    assert calls == [(ids['material'],ids['source'])]
    assert state() == before

@pytest.mark.parametrize('role,csrf,expected', [(None,True,401),('finance',True,403),('admin',False,400)])
def test_consent_endpoint_keeps_auth_role_csrf(consent_case, role, csrf, expected):
    clients, ids, _, calls = consent_case
    response = execute(clients(role,csrf),ids)
    assert response.status_code == expected
    assert calls == []

def test_issue_merge_preview(consent_case, monkeypatch):
    from itsdangerous import TimestampSigner
    clients, ids, state, calls = consent_case
    plan = preview(clients(), ids)
    token = plan['preview_token']
    before = state()
    assert execute(clients('warehouse'), ids, token).status_code == 409
    original_clock = TimestampSigner.get_timestamp
    monkeypatch.setattr(TimestampSigner, 'get_timestamp', lambda self: original_clock(self)+301)
    assert execute(clients(), ids, token).status_code == 409
    assert calls == [] and state() == before

def test_require_merge_preview(consent_case, monkeypatch):
    clients, ids, _, calls = consent_case
    c = clients()
    plan = preview(c, ids)
    existing = m.merge_material_duplicates
    def check_lock(*a, **k):
        raw = m.db.session.connection().connection.driver_connection
        assert raw.in_transaction is True
        return existing(*a, **k)
    monkeypatch.setattr(m, 'merge_material_duplicates', check_lock)
    response = execute(c, ids, plan['preview_token'])
    assert response.status_code == 400 and calls == [(ids['material'], ids['source'])]

def test_require_merge_preview_busy_is_controlled_503(consent_case, monkeypatch):
    from sqlalchemy.exc import OperationalError
    clients, ids, _, calls = consent_case
    c = clients()
    plan = preview(c, ids)
    def busy(*a, **k):
        raise OperationalError('BEGIN IMMEDIATE', {}, Exception('database is locked'))
    monkeypatch.setattr(m.db.session, 'connection', busy)
    response = execute(c, ids, plan['preview_token'])
    assert response.status_code == 503 and '重新预览' in response.json['msg']
    assert calls == []
