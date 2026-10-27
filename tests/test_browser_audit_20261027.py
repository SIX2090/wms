"""Browser audit regressions; all database operations use pytest's isolated database."""
from datetime import datetime, timedelta
import csv
import io

import pytest
import app as wms


@pytest.fixture
def case(monkeypatch):
    monkeypatch.setitem(wms.app.config, 'TESTING', True)
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', False)
    monkeypatch.setattr(wms, '_ai_capability_allowed', lambda *a: True)
    with wms.app.app_context():
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()
        user = wms.User(username='audit-fixture', role='admin', password_hash='unused', must_change_password=False)
        wms.db.session.add(user)
        for i in range(505):
            wms.db.session.add(wms.Material(code=f'AUD-{i:04}', name=f'测试{i}', stock=0, min_stock=10))
        wms.db.session.commit()
        client = wms.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user.id)
            session['_fresh'] = True
        yield client
        wms.db.session.remove()


def test_health_average_independent_of_limit_and_filter(case):
    full = wms._ai_inventory_health_report(limit=None)
    limited = wms._ai_inventory_health_report(limit=2)
    assert len(full['rows']) == 505
    expected = sum(r['health_score'] for r in full['rows']) / 505
    assert limited['summary']['avg_health_score'] == round(expected, 2)
    assert limited['summary']['total'] == 505
    filtered = wms._ai_inventory_health_report(limit=2, risk_filter='healthy')
    assert filtered['summary']['avg_health_score'] == limited['summary']['avg_health_score']


@pytest.mark.parametrize('path', ['/ai/inventory_health', '/ai/replenishment_smart'])
def test_full_csv_and_last_page(case, path):
    response = case.get(path + '?risk=all&export=csv')
    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.data.decode('utf-8-sig'))))
    assert len(rows) == 506
    page = case.get(path + '?risk=all&page=3')
    assert page.status_code == 200
    assert '共 505 条'.encode() in page.data
    assert b'AUD-0504' in page.data
    assert b'AUD-0000' not in page.data
    first = case.get(path + '?risk=all&embedded=1')
    from bs4 import BeautifulSoup
    from urllib.parse import parse_qs, urlsplit
    nav = BeautifulSoup(first.data, 'html.parser').find('nav', attrs={'aria-label': '分析明细分页'})
    assert parse_qs(urlsplit(nav.find('a')['href']).query)['embedded'] == ['1']


def test_replenishment_precision_and_summary(case, monkeypatch):
    mid = wms.Material.query.order_by(wms.Material.code).first().id
    monkeypatch.setattr(wms, '_ai_replenishment_out_qty_by_material', lambda days: {mid: 1000})
    report = wms._ai_smart_replenishment_report(days=30, coverage_days=30, limit=1)
    assert report['summary']['total'] == 505
    assert report['rows'][0]['coverage_stock'] == 1000
    assert report['rows'][0]['suggested_qty'] == 1000
    assert report['rows'][0]['avg_daily'] == 33.33


def test_prelaunch_instance_db(case, tmp_path, monkeypatch):
    (tmp_path / 'audit.db').write_bytes(b'fixture')
    monkeypatch.setattr(wms.app, 'instance_path', str(tmp_path))
    monkeypatch.setitem(wms.app.config, 'SQLALCHEMY_DATABASE_URI', 'sqlite:///audit.db')
    with wms.app.test_request_context():
        report = wms._ai_prelaunch_checks()
    assert next(c for c in report['checks'] if c['code'] == 'DB-ACCESS')['status'] == 'pass'


def test_daily_backup_visible_to_prelaunch(case, tmp_path, monkeypatch):
    import backup_catalog
    daily = tmp_path / 'auto_daily_fixture.db'
    daily.write_bytes(b'fixture')
    monkeypatch.setattr(backup_catalog, 'get_backup_sources', lambda manual: {
        'daily': {'directory': tmp_path, 'label': '每日自动备份', 'retention': '', 'auto_only': False}})
    with wms.app.test_request_context():
        report = wms._ai_prelaunch_checks()
    check = next(c for c in report['checks'] if c['code'] == 'BACKUP-READY')
    assert check['status'] == 'pass'
    assert daily.name in check['detail']


def test_workstation_stale_heartbeat_display(case):
    wms.db.session.add(wms.PrintWorkstation(code='STALE', name='STALE', device_id='fixture-stale', status='online', enabled=True,
                                          last_heartbeat=datetime.now() - timedelta(days=1)))
    wms.db.session.commit()
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(case.get('/print_routing').data, 'html.parser')
    header = soup.find('b', string='STALE').parent.parent
    assert '离线' in header.get_text()
    assert '在线' not in header.get_text()


def test_purchase_link_filter(case):
    from bs4 import BeautifulSoup
    from urllib.parse import parse_qs, urlsplit
    soup = BeautifulSoup(case.get('/purchase_report').data, 'html.parser')
    link = next(a for a in soup.find_all('a') if '查看采购入库明细' in a.get_text())
    assert parse_qs(urlsplit(link['href']).query)['business_type'] == ['采购入库']


def test_local_printer_unicode_output():
    import local_print_agent as agent
    if agent.os.name != 'nt':
        pytest.skip('Windows PowerShell encoding integration')
    ok, output = agent._run_powershell_status("Write-Output 'Fax (已重定向 2)'")
    assert ok
    assert output == 'Fax (已重定向 2)'


@pytest.mark.parametrize('filename', ['app/local_print_agent.py', 'tools/print_agent/wms_print_agent.py'])
def test_printer_pipe_encoding_contract(filename, monkeypatch):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace
    path = Path(__file__).resolve().parents[1] / filename
    spec = importlib.util.spec_from_file_location('audit_printer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'os', SimpleNamespace(name='nt'))
    def run(args, **kwargs):
        assert '[Console]::OutputEncoding' in args[-1]
        assert 'UTF8Encoding' in args[-1]
        assert kwargs['encoding'] == 'utf-8'
        return SimpleNamespace(returncode=0, stdout='打印机（重定向）', stderr='')
    monkeypatch.setattr(module.subprocess, 'run', run)
    assert module._run_powershell_status('Get-Printer') == (True, '打印机（重定向）')


@pytest.mark.parametrize('path', ['/ai/replenishment', '/ai/replenishment_live', '/ai/replenishment_smart'])
def test_replenishment_label_and_pagination(case, path):
    response = case.get(path + '?risk=all&page=3')
    assert response.status_code == 200
    assert '中风险物料数'.encode() in response.data
    assert '共 505 条'.encode() in response.data
    assert b'AUD-0504' in response.data
