"""05-A: real synthetic page output, script restrictions and field relationships."""
import base64
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
import app as w

ROOT = Path(__file__).resolve().parents[1]


class PageNodes(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.nodes = []
        self.form = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.form = attrs.get('id', 'filter')
        self.nodes.append((tag, attrs, self.form))

    def handle_endtag(self, tag):
        if tag == 'form':
            self.form = None


@pytest.fixture
def page_client(monkeypatch):
    # BUG-2026-11-10-001：CI 隔离容器是 FLASK_ENV=testing，TestingConfig 不带
    # SECURITY_HEADERS，after_request 只写出 material_form_policy 追加的一条严格 CSP，
    # 于是 assert len(policies) == 2 失败。这里显式注入生产安全头，使被测前提在
    # 任意 FLASK_ENV 下一致；断言本身（含严格策略的 hash 校验）一条都不放宽。
    from config import ProductionConfig
    monkeypatch.setitem(w.app.config, 'SECURITY_HEADERS', dict(ProductionConfig.SECURITY_HEADERS))
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    with w.app.app_context():
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.session.remove(); w.db.drop_all(); w.db.create_all()
        admin = w.User(username='phase05-synthetic', password_hash='unused', role='admin', must_change_password=False)
        unit = w.Unit(code='P5-U', name='合成单位')
        category = w.MaterialCategory(code='P5-C', name='合成分类')
        warehouse = w.Warehouse(code='P5-W', name='合成仓', is_default=True)
        w.db.session.add_all([admin, unit, category, warehouse]); w.db.session.flush()
        material = w.Material(code='P5-M', name='合成物料', unit_id=unit.id, category_id=category.id, stock=0)
        w.db.session.add(material); w.db.session.commit()
        identity, material_id = admin.id, material.id
    client = w.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(identity); session['_fresh'] = True
    yield client, material_id
    with w.app.app_context():
        w.db.session.remove(); w.db.drop_all()


PAGES = ['/material', '/material/add', '/category', '/unit',
         '/mobile/material?code=P5-M&warehouse=P5-W', '/material_archive/{id}/print?autoprint=1&copies=2']


def test_material_page_uses_strict_scripts():
    from services.material_form_policy import material_page_uses_strict_scripts
    for url in PAGES:
        with w.app.test_request_context(url.format(id=1), method='GET'):
            assert material_page_uses_strict_scripts()
        with w.app.test_request_context(url.format(id=1), method='POST'):
            assert not material_page_uses_strict_scripts()
    with w.app.test_request_context('/in_order/add?type=product&embedded=1'):
        assert not material_page_uses_strict_scripts()


@pytest.mark.parametrize('url', PAGES)
@pytest.mark.parametrize('embedded', [False, True])
def test_material_page_script_policy_covers_real_entry_modes(page_client, url, embedded):
    client, identity = page_client
    url = url.format(id=identity)
    if embedded:
        url += ('&' if '?' in url else '?') + 'embedded=1'
    response = client.get(url)
    assert response.status_code == 200
    policies = response.headers.getlist('Content-Security-Policy')
    assert len(policies) == 2
    assert "'unsafe-inline'" not in policies[1] and "'unsafe-eval'" not in policies[1]
    assert "script-src-attr 'none'" in policies[1]
    html = response.get_data(as_text=True)
    nodes = PageNodes(html).nodes
    assert not [(tag, key) for tag, attrs, _ in nodes for key in attrs if re.fullmatch('on[a-z]+', key)]
    assert not [attrs['href'] for _, attrs, _ in nodes if attrs.get('href', '').lower().startswith('javascript:')]
    for attributes, body in re.findall(r'<script\b([^>]*)>([\s\S]*?)</script>', html):
        if re.search(r'\bsrc\s*=', attributes) or 'application/json' in attributes or not body.strip():
            continue
        value = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
        assert "'sha256-" + value + "'" in policies[1]


@pytest.mark.parametrize('url', ['/material', '/material/add', '/category', '/unit'])
def test_material_business_controls_have_associated_labels(page_client, url):
    response = page_client[0].get(url + '?embedded=1')
    assert response.status_code == 200
    nodes = PageNodes(response.get_data(as_text=True)).nodes
    labels = {attrs.get('for') for tag, attrs, _ in nodes if tag == 'label' and attrs.get('for')}
    missing = []
    for tag, attrs, form in nodes:
        if not form or tag not in {'input', 'select', 'textarea'}:
            continue
        if attrs.get('type') in {'hidden', 'submit', 'button', 'checkbox', 'radio'}:
            continue
        if attrs.get('id') not in labels and not attrs.get('aria-label') and not attrs.get('aria-labelledby'):
            missing.append((form, attrs.get('id'), attrs.get('name')))
    assert not missing, missing


def test_material_relations_are_inert_json_after_asset_extraction(page_client):
    marker = '</script><script>window.phase05Injected=true</script>'
    with w.app.app_context():
        w.db.session.add(w.Unit(code='P5-X', name=marker)); w.db.session.commit()
    html = page_client[0].get('/material?embedded=1').get_data(as_text=True)
    match = re.search(r'<script type="application/json" id="material-list-data">([\s\S]*?)</script>', html)
    assert match
    data = json.loads(match.group(1))
    assert any(row['name'] == marker for row in data['relations']['unit'])
    assert '<script>window.phase05Injected' not in html
    assert data['urls']['printBatch'] == '/label/batch_print'
    assert 'js/pages/material-list.js' in html


def test_material_page_modules_parse_without_template_execution():
    for filename in ['material-list.js', 'material-category.js', 'material-unit.js',
                     'material-archive.js', 'material-shell-actions.js']:
        path = ROOT / 'app/static/js/pages' / filename
        assert path.is_file()
        source = path.read_text(encoding='utf-8')
        assert '{{' not in source and '{%' not in source
        assert not re.search(r'\bon(?:click|change|input|error)\s*=\s*["\']', source)
        result = subprocess.run([shutil.which('node'), '--check', str(path)], capture_output=True,
                                text=True, encoding='utf-8', timeout=15)
        assert result.returncode == 0, result.stderr


def test_legacy_delete_all_materials_remains_a_notification_without_any_write():
    source = (ROOT / 'app/static/js/pages/material-list.js').read_text(encoding='utf-8')
    handler = re.search(r'window\.deleteAllMaterials = function\(\) \{[\s\S]*?\n    \};', source)
    assert handler
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),fs=require('node:fs');
const messages=[],fail=()=>assert.fail('disabled legacy control must never send a request');
const ctx={window:{},showToast:(...args)=>messages.push(args),fetch:fail,WMS:{api:{post:fail,postRaw:fail}},alert:()=>assert.fail('use the existing Chinese notification')};
vm.runInNewContext(fs.readFileSync(0,'utf8'),ctx);ctx.window.deleteAllMaterials();
assert.equal(messages.length,1);assert.equal(messages[0][1],'warning');assert(messages[0][0].includes('已禁用删除全部物料'));
'''
    result = subprocess.run([shutil.which('node'), '-e', program], input=handler[0],
                            capture_output=True, text=True, encoding='utf-8', timeout=10)
    assert result.returncode == 0, result.stderr
