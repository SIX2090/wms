"""Render business pages with isolated users and compare controls with permissions."""
from datetime import date
from html.parser import HTMLParser

import pytest

from app import app, db, User, PurchaseRequest
from ai.policies import AI_USE_ROLES

ROLES = ['admin', 'warehouse', 'purchase', 'production', 'sales', 'viewer', 'finance', 'user']


class Controls(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.nodes = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


@pytest.fixture
def role_page(monkeypatch):
    monkeypatch.setitem(app.config, 'TESTING', True)
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', False)
    with app.app_context():
        assert db.engine.url.database in (None, ':memory:')
        db.drop_all()
        db.create_all()
        user = User(username='toolbar-role', role='admin', password_hash='fixture-only',
                    must_change_password=False)
        db.session.add(user)
        orders = [PurchaseRequest(request_no='ROLE-'+status, date=date.today(),
                    status=status, applicant='测试')
                  for status in ['pending', 'approved', 'completed', 'rejected']]
        db.session.add_all(orders)
        db.session.commit()
        uid = user.id
        ids = {order.status: order.id for order in orders}
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(uid)
        session['_fresh'] = True

    def get(role, path):
        with app.app_context():
            db.session.get(User, uid).role = role
            db.session.commit()
        return client.get(path, headers={'Accept': 'application/json'})

    yield get, ids
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()


@pytest.mark.parametrize('role', ROLES)
def test_import_page_only_shows_authorized_forms(role_page, role):
    get, _ = role_page
    response = get(role, '/batch_import')
    if role not in ['admin', 'warehouse', 'purchase', 'production']:
        assert response.status_code == 403
        return
    assert response.status_code == 200
    controls = Controls(response.get_data(as_text=True))
    urls = {a['data-url'] for tag, a in controls.nodes if tag == 'form' and 'data-url' in a}
    all_urls = {'/material/import', '/import/in_order', '/import/out_order', '/category/import',
        '/opening_stock/import', '/unit/import', '/supplier/import', '/employee/import',
        '/bom/import', '/warehouse/import', '/department/import', '/customer/import'}
    expected = all_urls if role == 'admin' else (
        all_urls - {'/employee/import', '/bom/import'} if role == 'warehouse' else
        {'/import/in_order', '/import/out_order'} if role == 'purchase' else {'/bom/import'})
    assert urls == expected
    adapter = app.url_map.bind('example.test')
    for url in urls:
        endpoint, _ = adapter.match(url, method='POST')
        assert role == 'admin' or role in app.view_functions[endpoint]._required_roles


@pytest.mark.parametrize('role', ROLES)
def test_navigation_and_ai_suggestions_follow_role(role_page, role):
    get, _ = role_page
    response = get(role, '/purchase_request')
    assert response.status_code == 200
    controls = Controls(response.get_data(as_text=True))
    assert any(tag == 'a' and a.get('href', '').startswith('/purchase_request/export?')
               for tag, a in controls.nodes)
    suggestions = [a for tag, a in controls.nodes if 'ai-suggestion' in a.get('class', '').split()]
    if role not in AI_USE_ROLES:
        assert not suggestions
        assert not any(a.get('id') == 'aiAssistantButton' for _, a in controls.nodes)
    else:
        assert suggestions
        assert all(role == 'admin' or a['data-role'] in ['all', role] for a in suggestions)
        if role == 'admin':
            assert len(suggestions) == 30
    if role == 'viewer':
        assert not any(tag == 'a' and a.get('href') == '/batch_import' for tag, a in controls.nodes)
    if role not in ['admin', 'purchase']:
        assert not any(tag == 'a' and a.get('href') == '/purchase_request/add' for tag, a in controls.nodes)


@pytest.mark.parametrize('role', ROLES)
@pytest.mark.parametrize('status', ['pending', 'approved', 'completed', 'rejected'])
def test_purchase_request_actions_follow_role_in_list_and_detail(role_page, role, status):
    get, ids = role_page
    paths = ['/purchase_request', '/purchase_request/'+str(ids[status])]
    for path in paths + [path+'?embedded=1' for path in paths]:
        response = get(role, path)
        assert response.status_code == 200
        nodes = Controls(response.get_data(as_text=True)).nodes
        actions = [a for tag, a in nodes if tag == 'button' and any(
            name+'(' in a.get('onclick', '') for name in
            ['approveOrder', 'rejectOrder', 'revertOrder', 'completeOrder', 'deleteOrder', 'createPurchaseOrder'])]
        if role not in ['admin', 'purchase']:
            assert any(tag == 'body' and 'wms-no-global-actionbar' in a.get('class', '').split()
                       for tag, a in nodes)
            assert not actions
            assert not any(tag == 'a' and '/purchase_request/' in a.get('href', '') and
                           a['href'].endswith('/edit') for tag, a in nodes)
        elif status != 'rejected':
            assert actions
