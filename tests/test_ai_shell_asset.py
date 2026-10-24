"""AI shell loading, cache contracts, and unchanged rendering/image semantics."""
import hashlib
from pathlib import Path
import re

import app as app_module
import pytest
from tests.test_shell_navigation_asset import render_shell

ROOT = Path(__file__).resolve().parents[1]
ASSET = 'js/pages/ai-assistant.js'


@pytest.mark.parametrize('role,count', [('admin', 1), ('warehouse', 1), ('purchase', 1), ('production', 1), ('sales', 1), ('viewer', 0), ('finance', 0), ('user', 0)])
def test_real_template_keeps_role_visibility_and_load_order(role, count):
    html = render_shell(role)
    assert html.count('/static/' + ASSET + '?v=nav-test-v1') == count
    assert 'function sendAssistantMessage' not in html
    if count:
        assert html.index('js/api.js') < html.index('js/app.js') < html.index(ASSET)
        tag = next(tag for tag in re.findall(r'<script\b[^>]*>', html) if ASSET in tag)
        assert 'async' not in tag and 'defer' not in tag
        assert html.index('id="aiAssistantForm"') < html.index(ASSET)


def test_assistant_asset_is_served_with_conditional_cache():
    response = app_module.app.test_client().get('/static/' + ASSET)
    assert response.status_code == 200
    assert response.mimetype in {'text/javascript', 'application/javascript'}
    assert response.data == (ROOT / 'app/static' / ASSET).read_bytes()
    assert response.cache_control.public and response.cache_control.max_age == 31536000
    assert app_module.app.test_client().get('/static/' + ASSET, headers={'If-None-Match': response.headers['ETag']}).status_code == 304


@pytest.mark.parametrize('name,digest', [
    ('renderMarkdown', 'f5c9631e39dce6987b7ae48b5e23a0a5017a770373c4a0b9ab3bcd89de3f569f'),
    ('renderCards', 'd74f4e34fcf48469efe83ef24fe2e9f7d1bf6c9a357124c1ec8380593d09a98c'),
    ('renderActions', '261ea210591c513f338317804d55388a584ee6060cabbd08945683cf617f21b9'),
    ('prepareImageAttachment', '760f6c885bfd2c0d62e98efc9874beb5d15fe83ce103a7c4a060dbff7cf5df4a'),
    ('sendAssistantMessage', '8753ad0727f9dcdd509ebf44d2e1429b8c74b0dbfdeaa353c4c89b2f074cd752'),
])
def test_nontransport_functions_keep_original_bytes(name, digest):
    source = (ROOT / 'app/static' / ASSET).read_text(encoding='utf-8')
    start = source.index('        function ' + name + '(')
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if not depth:
            assert hashlib.sha256(source[start:end + 1].encode()).hexdigest() == digest
            break
    else:
        pytest.fail('unterminated function ' + name)


def test_assistant_has_no_native_transport_or_server_interpolation():
    source = (ROOT / 'app/static' / ASSET).read_text(encoding='utf-8')
    assert 'fetch(' not in source and 'csrfFetch(' not in source
    assert '{{' not in source and '{%' not in source
    assert "WMS.api.postResponse('/api/ai/chat/stream'" in source
    assert 'window.fixtureAssistant' not in source
