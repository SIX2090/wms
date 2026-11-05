"""Explicit fresh-page transport for business tests that edit existing documents.

Conflict/protocol tests use the raw Flask client. This helper performs a real
page read, never disables the server guard, and never retries a rejected write.
"""
import re
from urllib.parse import urlsplit


def document_post(client, path, **kwargs):
    import app as w
    from services.document_edit_guard import EDIT_ENDPOINTS, _family, _identity
    from werkzeug.exceptions import HTTPException
    try:
        endpoint, _ = w.app.url_map.bind('localhost').match(urlsplit(path).path, method='POST')
    except HTTPException:
        return client.post(path, **kwargs)
    if endpoint not in EDIT_ENDPOINTS:
        return client.post(path, **kwargs)
    headers = dict(kwargs.get('headers') or {})
    data = kwargs.get('data') or {}
    if 'X-WMS-Document-Revision' in headers or (isinstance(data, dict) and data.get('document_revision')):
        return client.post(path, **kwargs)
    # Build identity-only form data; a Flask request context closes file streams
    # on teardown, so it must never borrow the actual upload being tested.
    if kwargs.get('json') is not None:
        context = {'json': kwargs['json']}
    else:
        context = {'data': {key: data.get(key) for key in
                   ('id', 'order_id', 'doc_id', 'request_id', 'header') if key in data}}
    with w.app.test_request_context(path, method='POST', **context):
        from flask import request
        family = _family()
        identity = _identity(family) if family and request.endpoint in EDIT_ENDPOINTS else None
        line_id = (request.view_args or {}).get('id')
    if identity == -2:
        with w.app.app_context():
            row = w.db.session.get(w.OpeningStock, line_id)
            warehouse_id = row.warehouse_id
        assert warehouse_id, 'Unattributed rows need a separate validation test'
        page_number = 1
        while True:
            response = client.get('/api/opening_stock', query_string={
                'warehouse_id': warehouse_id, 'page': page_number, 'page_size': 100})
            assert response.status_code == 200, response.json
            listing = response.json['data']
            row = next((item for item in listing['items'] if item['id'] == line_id), None)
            if row:
                headers['X-WMS-Document-Revision'] = row['revision']
                kwargs['headers'] = headers
                return client.post(path, **kwargs)
            assert page_number < listing['total_pages'], 'Target row must be discoverable'
            page_number += 1
    if identity and identity > 0:
        page = '/' + family.replace('subcontract_', 'subcontract/') + '/' + str(identity)
        response = client.get(page)
        if response.status_code in (302, 401, 403, 404):
            return client.post(path, **kwargs)
        assert response.status_code == 200, (page, response.status_code)
        match = re.search(r'<meta name="document-revision" content="([^"]+)"', response.get_data(as_text=True))
        token = match.group(1) if match else response.headers.get('X-WMS-Document-Read-Revision')
        assert token, page
        headers['X-WMS-Document-Revision'] = token
        kwargs['headers'] = headers
    return client.post(path, **kwargs)
