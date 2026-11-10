"""Actual Flask headers and rendered script hashes; only synthetic memory DB."""
import base64
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess

import pytest
import app as w


@pytest.fixture
def material_client(monkeypatch):
    # BUG-2026-11-10-006：CI 隔离容器是 FLASK_ENV=testing，TestingConfig 不带
    # SECURITY_HEADERS，after_request 只写出 material_form_policy 追加的一条严格 CSP，
    # 于是「迁移页 2 条 / 未迁移页 1 条」的断言全部落空。这里显式注入生产安全头，
    # 使被测前提在任意 FLASK_ENV 下一致（与 test_phase05_material_pages、
    # test_f27_security_headers 同一做法）；断言本身一条都不放宽。
    from config import ProductionConfig
    monkeypatch.setitem(w.app.config, 'SECURITY_HEADERS', dict(ProductionConfig.SECURITY_HEADERS))
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    with w.app.app_context():
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.session.remove(); w.db.drop_all(); w.db.create_all()
        user = w.User(username='csp-synthetic', password_hash='unused', role='admin', must_change_password=False)
        w.db.session.add_all([user, w.Unit(code='CSP-U', name='合成单位')]); w.db.session.commit()
        identity = user.id
    client = w.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(identity); session['_fresh'] = True
    yield client
    with w.app.app_context():
        w.db.session.remove(); w.db.drop_all()


def executable_hashes(html):
    found = []
    for attributes, body in re.findall(r'<script\b([^>]*)>([\s\S]*?)</script>', html):
        if re.search(r'\bsrc\s*=', attributes) or 'application/json' in attributes:
            continue
        if body.strip():
            found.append(base64.b64encode(hashlib.sha256(body.encode()).digest()).decode())
    return found


def test_apply_material_script_policy(material_client):
    response = material_client.get('/material/add?embedded=1')
    assert response.status_code == 200
    policies = response.headers.getlist('Content-Security-Policy')
    assert len(policies) == 2
    assert "script-src 'self' 'unsafe-inline'" in policies[0]
    assert "'unsafe-inline'" not in policies[1] and "'unsafe-eval'" not in policies[1]
    assert "script-src-attr 'none'" in policies[1]
    from services.material_form_policy import SHARED_SCRIPT_HASHES
    actual = executable_hashes(response.get_data(as_text=True))
    assert actual == list(SHARED_SCRIPT_HASHES)
    assert all("'sha256-" + value + "'" in policies[1] for value in actual)
    html = response.get_data(as_text=True)
    assert not re.search(r'<[^>]*\son[a-z]+\s*=', html, re.I)
    assert 'id="appSidebar"' in html and 'id="wmsBreadcrumb"' in html


@pytest.mark.parametrize('url', ['/supplier', '/supplier?embedded=0', '/login?embedded=1', '/customer?embedded=1'])
def test_unmigrated_pages_keep_original_policy(material_client, url):
    response = material_client.get(url)
    assert response.status_code == (302 if url.startswith('/login') else 200)
    assert len(response.headers.getlist('Content-Security-Policy')) == 1


@pytest.mark.parametrize(('url', 'inline_actions'), [
    ('/material/add?embedded=1', False), ('/material/add?embedded=0', False),
    ('/material/add', False), ('/material?embedded=1', False),
    ('/in_order/add?type=product&embedded=1', True), ('/in_order/add?type=product', True),
])
def test_shell_inline_handler_scope_matches_migrated_pages(material_client, url, inline_actions):
    response = material_client.get(url)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert ('onclick="toggleMobileSidebar()"' in html) is inline_actions
    assert ('onclick="toggleModuleMenu(this)"' in html) is inline_actions
    assert 'id="appSidebar"' in html and 'id="wmsBreadcrumb"' in html
    assert len(response.headers.getlist('Content-Security-Policy')) == (1 if inline_actions else 2)


def test_existing_stricter_policy_is_not_replaced(material_client, monkeypatch):
    headers = dict(w.app.config['SECURITY_HEADERS'])
    headers['Content-Security-Policy'] = "default-src 'none'; script-src 'none'"
    monkeypatch.setitem(w.app.config, 'SECURITY_HEADERS', headers)
    policies = material_client.get('/material/add?embedded=1').headers.getlist('Content-Security-Policy')
    assert policies[0] == "default-src 'none'; script-src 'none'" and len(policies) == 2


def test_relation_json_is_inert_and_entry_waits_for_asset(material_client):
    marker = '</script><script>window.syntheticInjected=true</script>'
    with w.app.app_context():
        w.db.session.add(w.Unit(code='CSP-X', name=marker)); w.db.session.commit()
    html = material_client.get('/material/add?embedded=1').get_data(as_text=True)
    config = re.search(r'<script type="application/json" id="material-add-data">([\s\S]*?)</script>', html)
    assert config and any(row['name'] == marker for row in json.loads(config.group(1))['units'])
    assert '<script>window.syntheticInjected' not in html
    assert 'js/pages/material-add.js' in html and 'wms-no-global-actionbar' in html
    assert re.search(r'<button[^>]*id="materialSaveButton"[^>]*data-wms-save[^>]*disabled', html)
    assert 'onclick="showAddUnitModal()"' not in html


def test_redirect_and_post_do_not_gain_page_policy(material_client):
    anonymous = w.app.test_client().get('/material/add?embedded=1')
    assert anonymous.status_code == 302
    assert len(anonymous.headers.getlist('Content-Security-Policy')) == 1
    html = material_client.get('/material/add?embedded=1').get_data(as_text=True)
    token = re.search(r'<meta name="csrf-token" content="([^"]+)"', html).group(1)
    response = material_client.post('/material/add?embedded=1', data={'csrf_token': token},
                                    headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'})
    assert response.status_code == 400
    assert len(response.headers.getlist('Content-Security-Policy')) == 1


def test_browser_timing_samples_obey_material_identity_validation(material_client):
    source = (Path(__file__).resolve().parents[1] / 'tests/material_browser_check.cjs').read_text(encoding='utf-8')
    helper = re.search(r'function benchmarkName\(index\)\{[^\n]+\}', source).group()
    result = subprocess.run([shutil.which('node'), '-e', helper +
                             ';process.stdout.write(JSON.stringify([0,1,2].map(benchmarkName)))'],
                            capture_output=True, text=True, encoding='utf-8', timeout=10)
    assert result.returncode == 0, result.stderr
    names = json.loads(result.stdout)
    assert len(set(names)) == 3
    html = material_client.get('/material/add?embedded=1').get_data(as_text=True)
    token = re.search(r'<meta name="csrf-token" content="([^"]+)"', html).group(1)
    headers = {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}
    for index, name in enumerate(names):
        response = material_client.post('/material/add', data={
            'csrf_token': token, 'code': 'BENCH-GUARD-' + str(index), 'name': name,
            'stock': '0', 'price': '0'}, headers=headers)
        assert response.status_code == 200 and response.json['status'] == 'success'
    duplicate = material_client.post('/material/add', data={
        'csrf_token': token, 'code': 'BENCH-EQUIVALENT', 'name': names[0],
        'stock': '0', 'price': '0'}, headers=headers)
    assert duplicate.status_code == 400 and '不能同时重复' in duplicate.json['msg']
    with w.app.app_context():
        assert w.Material.query.count() == 3
        assert w.Material.query.filter_by(code='BENCH-EQUIVALENT').first() is None
