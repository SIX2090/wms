"""Purchase order pages, exports and print views use the list's read policy."""

from io import BytesIO
from urllib.parse import urlsplit

import pytest
from openpyxl import load_workbook

import app as wms
from tests.test_document_print_flow import print_case


READ_URLS = (
    '/purchase_order',
    '/purchase_order/add',
    '/purchase_order/{id}',
    '/purchase_order/{id}/edit',
    '/purchase_order/export',
    '/purchase_order/{id}/print',
    '/purchase_order/{id}/print_options',
    '/purchase_order/{id}/print_preview',
    '/purchase_order/{id}/print_file',
    '/purchase_order/{id}/print_excel',
    '/api/purchase_order/todo_summary',
    '/api/purchase_order/selectable',
)
WORKBOOK_URLS = {
    '/purchase_order/export',
    '/purchase_order/{id}/print_file',
    '/purchase_order/{id}/print_excel',
}


def sign_in(client, role):
    with wms.app.app_context():
        user = wms.User(username=f'purchase-access-{role}', role=role,
                        password_hash='unused-test-value', must_change_password=False)
        wms.db.session.add(user)
        wms.db.session.commit()
        user_id = user.id
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True


@pytest.mark.parametrize('role', ['production', 'sales', 'user', 'viewer'])
@pytest.mark.parametrize('path', READ_URLS)
def test_roles_without_purchase_order_access_are_denied(print_case, role, path):
    client, documents, _ = print_case
    sign_in(client, role)
    response = client.get(path.format(id=documents['purchase_order']),
                          headers={'Accept': 'application/json'})
    assert response.status_code == 403
    assert response.json['status'] == 'error'
    assert '没有权限' in response.json['msg']


@pytest.mark.parametrize('role', ['admin', 'warehouse', 'purchase', 'finance'])
def test_authorized_roles_can_read_purchase_order(print_case, role):
    client, documents, _ = print_case
    sign_in(client, role)
    order_id = documents['purchase_order']
    with wms.app.app_context():
        order_no = wms.db.session.get(wms.PurchaseOrder, order_id).order_no

    for path in READ_URLS:
        response = client.get(path.format(id=order_id))
        assert response.status_code == 200, (role, path)
        if path in WORKBOOK_URLS:
            with BytesIO(response.data) as data:
                workbook = load_workbook(data, read_only=True)
                try:
                    assert any(order_no in str(cell) for row in workbook.active.values for cell in row), path
                finally:
                    workbook.close()
        elif path.startswith('/api/'):
            assert any(order['order_no'] == order_no for order in response.json['orders'])
        elif path != '/purchase_order/add':
            assert order_no in response.get_data(as_text=True), path


def test_purchase_order_browser_denial_and_finance_write_boundary(print_case):
    _, documents, _ = print_case
    client = wms.app.test_client()
    path = f"/purchase_order/{documents['purchase_order']}/print_options"
    anonymous = client.get(path)
    assert anonymous.status_code == 302 and urlsplit(anonymous.location).path == '/login'
    sign_in(client, 'viewer')
    denied = client.get(path)
    assert denied.status_code == 302 and urlsplit(denied.location).path == '/'

    sign_in(client, 'finance')
    assert client.get(path).status_code == 200
    denied_write = client.post('/purchase_order/save', json={})
    assert denied_write.status_code == 403
    assert '只读' in denied_write.json['msg']
