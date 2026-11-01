"""BUG-2026-11-01-028: the default browser icon works without auth or a DB."""
import xml.etree.ElementTree as ET

import app as wms
from tests.test_document_create_number_conflicts import case  # noqa: F401


def test_default_browser_favicon_is_available_without_login():
    client = wms.app.test_client()
    response = client.get('/favicon.ico')
    assert response.status_code == 200
    assert response.mimetype == 'image/svg+xml'
    root = ET.fromstring(response.data)
    assert root.tag == '{http://www.w3.org/2000/svg}svg'
    assert root.attrib.get('viewBox') == '0 0 32 32'
    assert response.cache_control.no_store
    static = client.get('/static/favicon.svg')
    assert static.status_code == 200 and static.data == response.data


def test_shared_layout_declares_favicon(case):
    response = case[0][0].get('/check')
    assert response.status_code == 200
    assert 'rel="icon"' in response.get_data(as_text=True)
