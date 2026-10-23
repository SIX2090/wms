"""Real GET/Jinja requisition location context, isolated from production records."""
from html.parser import HTMLParser

from flask import template_rendered
import pytest

import app as wms


class Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.inputs = []
        self.bad_images = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input':
            self.inputs.append(attrs)
        if tag == 'img' and attrs.get('src') == 'fixture-attack':
            self.bad_images.append(attrs)


@pytest.fixture()
def client():
    wms.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with wms.app.app_context():
        wms.db.drop_all()
        wms.db.create_all()
        wms.db.session.add_all([
            wms.User(username='location-render-fixture', password_hash='synthetic-unused',
                     role='admin', must_change_password=False),
            wms.Warehouse(code='A', name='warehouse A', status='active', is_default=True),
            wms.Warehouse(code='B', name='warehouse B', status='active'),
        ])
        wms.db.session.commit()
        uid = wms.User.query.filter_by(username='location-render-fixture').one().id
    c = wms.app.test_client()
    with c.session_transaction() as session:
        session['_user_id'] = str(uid)
        session['_fresh'] = True
    yield c


def get_render(client, path, enabled, query):
    with wms.app.app_context():
        wms.set_system_setting('location_management_enabled', '1' if enabled else '0')
        wms.db.session.commit()
        before = wms.ProductionRequisition.query.count()
    rendered = []

    def capture(sender, template, context, **extra):
        if template.name == 'document_table_form.html':
            rendered.append(context)

    with template_rendered.connected_to(capture, wms.app):
        response = client.get(path, query_string=query)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert len(rendered) == 1
    context = rendered[0]
    assert context['location_management_enabled'] is enabled
    assert context['doc_type'] == 'requisition'
    with wms.app.app_context():
        assert wms.ProductionRequisition.query.count() == before, 'GET must never create a draft'
    return context, response.get_data(as_text=True)


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('raw', ['', '   ', '  B-02  ', '库' * 130, '\"><img src=fixture-attack onerror=attack()>'])
def test_new_location_prefill_is_bounded_and_escaped(client, enabled, raw):
    context, html = get_render(client, '/requisition/add', enabled, {
        'location': raw, 'warehouse_id': '2', 'order_id': '999', 'status': 'completed',
        'date': '2000-01-01', 'readonly': '1',
    })
    expected = raw.strip()[:100]
    assert context['header']['location'] == expected
    assert context['header']['warehouse_id'] == 2
    assert context['order_id'] == ''
    assert context['readonly'] is False
    assert context['status'] == 'pending'
    assert context['date_value'] != '2000-01-01'
    parsed = Inputs(html)
    assert not parsed.bad_images, 'location text must not become active HTML'
    location = [attrs for attrs in parsed.inputs if attrs.get('name') == 'location']
    assert len(location) == 1
    assert location[0].get('value', '') == expected
    assert ('required' in location[0]) is enabled
    if not enabled:
        assert location[0]['type'] == 'hidden'


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('status', ['pending', 'completed'])
@pytest.mark.parametrize('location', ['B-02', ''])
def test_existing_location_ignores_query_and_preserves_readonly(client, enabled, status, location):
    with wms.app.app_context():
        order = wms.ProductionRequisition(req_no='REQ-RENDER-EXISTING', warehouse='warehouse B',
                                         location=location, status=status, picker='original picker')
        wms.db.session.add(order)
        wms.db.session.commit()
        order_id = order.id
    context, html = get_render(client, f'/requisition/{order_id}', enabled, {
        'location': 'A-99\"><img src=fixture-attack onerror=attack()>',
        'warehouse_id': '1', 'warehouse': 'warehouse A', 'picker': 'injected picker',
        'readonly': '0', 'status': 'pending',
    })
    assert context['header']['location'] == location
    assert context['header']['warehouse'] == 'warehouse B'
    assert context['header']['warehouse_id'] == ''
    assert context['header']['picker'] == 'original picker'
    assert context['readonly'] is (status == 'completed')
    assert context['status'] == status
    parsed = Inputs(html)
    assert not parsed.bad_images
    field = next(attrs for attrs in parsed.inputs if attrs.get('name') == 'location')
    assert field.get('value', '') == (location or '')
    if enabled:
        assert ('readonly' in field) is (status == 'completed')
    else:
        assert field['type'] == 'hidden'
    with wms.app.app_context():
        persisted = wms.db.session.get(wms.ProductionRequisition, order_id)
        assert (persisted.location, persisted.warehouse, persisted.picker, persisted.status) == (
            location, 'warehouse B', 'original picker', status)


@pytest.mark.parametrize('enabled', [False, True])
def test_new_form_has_no_invented_default_location(client, enabled):
    context, html = get_render(client, '/production_requisition', enabled, {})
    assert context['header']['location'] == ''
    assert context['header']['warehouse_id'] == ''
    field = next(attrs for attrs in Inputs(html).inputs if attrs.get('name') == 'location')
    assert field.get('value', '') == ''
