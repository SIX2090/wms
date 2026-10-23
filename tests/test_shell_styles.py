"""Public shell styling stays identical while moving to a cacheable asset."""
import hashlib
import re
from pathlib import Path

import app as app_module

ROOT = Path(__file__).resolve().parents[1]


def test_shell_loads_versioned_styles_in_original_cascade_position():
    source = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    assert source.count("filename='css/shell.css'") == 1
    assert "filename='css/shell.css') }}?v={{ config.get('STATIC_VERSION', '1.0.0') }}" in source
    assert source.index('css/custom.css') < source.index('css/shell.css') < source.index('{% block extra_css %}')
    assert not re.search(r'^\s*<style>', source, re.M)


def test_shell_styles_preserve_every_rule_and_order():
    css = (ROOT / 'app/static/css/shell.css').read_text(encoding='utf-8')
    normalized = re.sub(r'\s+', '', re.sub(r'/\*.*?\*/', '', css, flags=re.S))
    # Snapshot from the original base.html style block, excluding comments/spacing.
    assert hashlib.sha256(normalized.encode()).hexdigest() == '04b9a0c0f13a44ec6336fa374a107c1f56a03596c709a60aad0291d9fe4bad23'
    assert '{{' not in css and '{%' not in css
    assert 'url(' not in css  # No relative resource paths to change meaning after extraction.


def test_shell_asset_is_served_with_cache_and_conditional_response():
    client = app_module.app.test_client()
    response = client.get('/static/css/shell.css?v=fixture')
    assert response.status_code == 200
    assert response.mimetype == 'text/css'
    assert response.data == (ROOT / 'app/static/css/shell.css').read_bytes()
    assert response.cache_control.public and response.cache_control.max_age == 31536000
    assert response.headers.get('ETag')
    cached = client.get('/static/css/shell.css?v=fixture', headers={'If-None-Match': response.headers['ETag']})
    assert cached.status_code == 304
