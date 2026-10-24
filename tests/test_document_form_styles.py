"""Keep document styling identical while making extracted assets cacheable."""
import ast
import hashlib
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def normalized(css):
    return re.sub(r'\s+', '', re.sub(r'/\*.*?\*/', '', css, flags=re.S))


@pytest.mark.parametrize('page', ['in_order_add', 'sales_order_add'])
def test_document_styles_load_shared_sheet_before_page_overrides(page):
    source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
    assert source.count("filename='css/document-form.css'") == 1
    assert "?v={{ config.get('STATIC_VERSION', '1.0.0') }}" in source
    inline = '\n'.join(re.findall(r'<style>(.*?)</style>', source, re.S))
    assert '.page-header {' not in inline
    assert '#materialTable thead th {' not in inline
    if page == 'in_order_add':
        assert source.index('document-form.css') < source.index('<style>')
        assert '-webkit-appearance: none;' in inline
        assert 'appearance: textfield;' in inline
    else:
        assert not inline.strip()


def test_shared_css_preserves_pre_refactor_rules_exactly():
    # Snapshot of the original sales page's full CSS, excluding comments/spacing.
    # The original inbound page differs only in its retained quantity spinner override.
    css = (ROOT / 'app/static/css/document-form.css').read_text(encoding='utf-8')
    assert hashlib.sha256(normalized(css).encode()).hexdigest() == 'd7b2b0d78d0be4d49fdb3cffbcfc2836c317314612eae6b251781feb96f160f2'
    assert 'spin-button' not in css


def version_function(tmp_path):
    tree = ast.parse((ROOT / 'app/app.py').read_text(encoding='utf-8'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_compute_static_version')
    ns = {'os': os, '__file__': str(tmp_path / 'app.py'), '_STATIC_VERSION_EXCLUDE': ('xlsx.full.min.js',)}
    exec(compile(ast.Module(body=[function], type_ignores=[]), 'static_version', 'exec'), ns)
    return ns['_compute_static_version']


@pytest.mark.parametrize('asset', ['css/document-form.css', 'js/pages/department.js', 'css/pages/material.css', 'css/shell.css', 'js/pages/shell-navigation.js', 'js/pages/ai-assistant.js', 'js/select-refresh.js', 'js/material-cache.js', 'js/list-cache.js'])
def test_extracted_assets_change_version_on_add_update_remove(tmp_path, asset):
    compute = version_function(tmp_path)
    before = compute()
    path = tmp_path / 'static' / asset
    path.parent.mkdir(parents=True)
    path.write_text('fixture', encoding='utf-8')
    added = compute()
    assert added != before
    os.utime(path, (9999999999, 9999999999))
    updated = compute()
    assert updated != added
    assert '9999999999' in updated
    path.unlink()
    assert compute() == before


def test_vendor_xlsx_stays_out_of_cache_version(tmp_path):
    compute = version_function(tmp_path)
    before = compute()
    path = tmp_path / 'static/js/xlsx.full.min.js'
    path.parent.mkdir(parents=True)
    path.write_text('fixture', encoding='utf-8')
    assert compute() == before
