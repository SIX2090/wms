"""BUG-2026-11-06-001: no production traffic, even on collection or redirect."""
import importlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import subprocess
from types import SimpleNamespace

import pytest
import requests
from requests.adapters import BaseAdapter

from scripts.smoke_isolation import IsolatedSession, read_identity, validate_base_url
from scripts import run_smoke_in_ci as runner

ROOT = Path(__file__).resolve().parents[1]
NONCE = 'a' * 64
BASE = 'http://127.0.0.1:49199'


@pytest.mark.parametrize('script', ['full_smoke_test.py', 'run_smoke_in_ci.py'])
def test_import_has_no_network_or_process_side_effect(script, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Import attempted a request or started a server')
    monkeypatch.setattr(requests.Session, 'request', forbidden)
    monkeypatch.setattr(runner.subprocess, 'Popen', forbidden)
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    namespace = runpy.run_path(str(ROOT / 'scripts' / script), run_name='import_only')
    assert callable(namespace['main'])


def test_missing_explicit_identity_refuses_before_network(monkeypatch):
    module = importlib.import_module('scripts.full_smoke_test')
    with pytest.raises(SystemExit) as error:
        module.main([])
    assert error.value.code == 2


def test_isolated_interpreter_can_load_smoke_helpers():
    result = subprocess.run([sys.executable, '-I', '-B',
                             str(ROOT / 'scripts/full_smoke_test.py'), '--help'],
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    assert '--isolation-file' in result.stdout


@pytest.mark.parametrize('url', [
    'http://127.0.0.1:8080', 'http://127.0.0.1:5000', 'http://127.0.0.1:80',
    'https://gd2026.top', 'http://gd2026.top:49199', 'http://localhost:49199',
    'http://0.0.0.0:49199', 'http://[::1]:49199', 'https://127.0.0.1:49199',
    'http://user:pass@127.0.0.1:49199', BASE + '/login', BASE + '?x=1',
    BASE + '#fragment', 'http://127.0.0.1:65536', 'http://127.0.0.1',
])
def test_unsafe_address_refused_without_connecting(url):
    with pytest.raises(ValueError):
        validate_base_url(url)


def test_owned_loopback_url_is_canonical():
    assert validate_base_url(BASE + '/') == BASE


def identity(root):
    return dict(schema=1, pid=os.getpid(), nonce=NONCE,
                base_url=BASE, database=str(root / 'synthetic.db'))


@pytest.mark.parametrize('field,value', [
    ('schema', 2), ('pid', False), ('pid', 0), ('nonce', 'short'),
    ('database', 'inventory.db'), ('base_url', 'http://127.0.0.1:8080'),
])
def test_invalid_receipt_rejected(field, value):
    with tempfile.TemporaryDirectory(prefix='wms-isolated-smoke-') as directory:
        root = Path(directory).resolve()
        receipt = identity(root)
        receipt[field] = value
        path = root / 'ready.json'
        path.write_text(json.dumps(receipt), encoding='utf-8')
        with pytest.raises(ValueError):
            read_identity(path)


def test_valid_receipt_matches_owned_database():
    with tempfile.TemporaryDirectory(prefix='wms-isolated-smoke-') as directory:
        root = Path(directory).resolve()
        path = root / 'ready.json'
        path.write_text(json.dumps(identity(root)), encoding='utf-8')
        assert read_identity(path) == identity(root)


class OfflineAdapter(BaseAdapter):
    """Return responses in memory; unsafe URLs are never opened in these tests."""

    def __init__(self, headers, status=200):
        self.calls = []
        self.headers = headers
        self.status = status

    def send(self, request, **kwargs):
        self.calls.append(request.url)
        response = requests.Response()
        response.status_code = self.status
        response.headers.update(self.headers)
        response.url = request.url
        response.request = request
        response.raw = io.BytesIO(b'{}')
        return response

    def close(self):
        pass


def session_with_adapter(headers, status=200):
    session = IsolatedSession(dict(base_url=BASE, nonce=NONCE))
    adapter = OfflineAdapter(headers, status)
    session.mount('http://', adapter)
    return session, adapter


def test_wrong_origin_rejected_before_adapter():
    session, adapter = session_with_adapter({'X-WMS-Isolated-Smoke': NONCE})
    with pytest.raises(ValueError, match='outside'):
        session.post('http://127.0.0.1:8080/login', data={'username': 'synthetic'})
    assert adapter.calls == []


@pytest.mark.parametrize('headers', [{}, {'X-WMS-Isolated-Smoke': 'wrong'}])
def test_missing_or_wrong_server_identity_stops_on_first_response(headers):
    session, adapter = session_with_adapter(headers)
    with pytest.raises(ValueError, match='identity mismatch'):
        session.get(BASE + '/login')
    assert adapter.calls == [BASE + '/login']


def test_redirect_to_production_is_refused_before_second_request():
    session, adapter = session_with_adapter({
        'X-WMS-Isolated-Smoke': NONCE, 'Location': 'http://127.0.0.1:8080/login'}, 302)
    with pytest.raises(ValueError, match='outside'):
        session.get(BASE + '/login')
    assert adapter.calls == [BASE + '/login']


def test_unidentified_redirect_is_not_followed_even_to_same_origin():
    session, adapter = session_with_adapter({'Location': BASE + '/login'}, 302)
    with pytest.raises(ValueError, match='identity mismatch'):
        session.get(BASE + '/')
    assert adapter.calls == [BASE + '/']


def test_valid_child_identity_allows_request():
    session, adapter = session_with_adapter({'X-WMS-Isolated-Smoke': NONCE})
    assert session.get(BASE + '/login').status_code == 200
    assert session.trust_env is False
    assert adapter.calls == [BASE + '/login']


def test_csrf_redirect_to_login_is_never_login_success(monkeypatch):
    module = importlib.import_module('scripts.full_smoke_test')
    calls = []
    fake = SimpleNamespace(
        get=lambda url: SimpleNamespace(status_code=200, text='<input name="csrf_token" value="synthetic">'),
        post=lambda *args, **kwargs: calls.append(args[0]) or SimpleNamespace(
            status_code=302, headers={'Location': '/login'}))
    monkeypatch.setattr(module, 's', fake)
    monkeypatch.setattr(module, 'BASE', BASE)
    assert module.try_login('synthetic', 'synthetic') is False
    assert calls == [BASE + '/login']


def test_environment_discards_production_database_and_services(monkeypatch, tmp_path):
    for key in ('DATABASE_URL', 'WMS_RELEASE_STATE_ROOT', 'WMS_RELEASE_MANIFEST',
                'WMS_PORT', 'WECHAT_HELPER_TOKEN', 'SESSION_COOKIE_SECURE',
                'UPLOAD_FOLDER', 'LOG_FILE', 'PYTHONPATH', 'SECRET_KEY'):
        monkeypatch.setenv(key, 'PRODUCTION_SENTINEL')
    env = runner.clean_environment(tmp_path)
    assert env['DATABASE_URL'] == 'sqlite:///' + (tmp_path / 'synthetic.db').as_posix()
    assert all(value != 'PRODUCTION_SENTINEL' for value in env.values())
    assert 'WMS_RELEASE_STATE_ROOT' not in env and 'WMS_RELEASE_MANIFEST' not in env
    assert env['AUTO_BACKUP_ENABLED'] == 'false'
    assert env['WMS_EXTERNAL_OPERATIONS_PAUSED'] == '1'
    assert env['WMS_ALLOW_INSECURE_COOKIE'] == '1'


def test_server_uses_current_interpreter_and_owned_environment(monkeypatch, tmp_path):
    captured = {}
    def popen(command, **kwargs):
        captured.update(command=command, **kwargs)
        return 'owned-child'
    monkeypatch.setattr(runner.subprocess, 'Popen', popen)
    assert runner.start_server(tmp_path, io.StringIO()) == 'owned-child'
    assert captured['command'][0] == sys.executable
    assert captured['command'][-2:] == ['--serve', str(tmp_path)]
    assert captured['env']['DATABASE_URL'].endswith('/synthetic.db')


def test_ready_receipt_must_match_child_pid():
    with tempfile.TemporaryDirectory(prefix='wms-isolated-smoke-') as directory:
        root = Path(directory).resolve()
        (root / 'ready.json').write_text(json.dumps(identity(root)), encoding='utf-8')
        child = SimpleNamespace(pid=os.getpid() + 1, poll=lambda: None)
        with pytest.raises(ValueError, match='another process'):
            runner.wait_ready(child, root, timeout=1)


def test_dead_child_never_probes_http(tmp_path):
    child = SimpleNamespace(pid=123, poll=lambda: 1)
    with pytest.raises(RuntimeError, match='did not become ready'):
        runner.wait_ready(child, tmp_path, timeout=1)


def test_existing_database_is_refused_before_application_import(monkeypatch):
    with tempfile.TemporaryDirectory(prefix='wms-isolated-smoke-') as directory:
        root = Path(directory).resolve()
        database = root / 'synthetic.db'
        database.write_bytes(b'untouched sentinel')
        monkeypatch.setenv('DATABASE_URL', 'sqlite:///' + database.as_posix())
        with pytest.raises(ValueError, match='unowned smoke state'):
            runner.serve_isolated(root)
        assert database.read_bytes() == b'untouched sentinel'
        assert not (root / 'program').exists()


def test_stop_only_owned_child():
    actions = []
    child = SimpleNamespace(poll=lambda: None, terminate=lambda: actions.append('terminate'),
                            wait=lambda timeout: actions.append(('wait', timeout)))
    runner.stop_server(child)
    assert actions == ['terminate', ('wait', 5)]
