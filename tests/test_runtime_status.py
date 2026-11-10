"""Runtime identity and explicit paused operations; only synthetic Flask apps."""
import importlib.util
import json
from pathlib import Path
import sys

from flask import Flask
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'app'))
from services import runtime_status as runtime


@pytest.fixture
def sample_app(monkeypatch, tmp_path):
    for key in ['WMS_RELEASE_MANIFEST', 'WMS_RELEASE_STATE_ROOT', 'WMS_EXTERNAL_OPERATIONS_PAUSED']:
        monkeypatch.delenv(key, raising=False)
    directory = tmp_path/'app'
    directory.mkdir()
    app = Flask('runtime-synthetic', root_path=str(directory))
    app.config.update(SECRET_KEY='synthetic-only', TESTING=True, SESSION_COOKIE_SECURE=True,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
    return app


@pytest.mark.parametrize('path,method', [
    ('/print_queue/jobs', 'POST'), ('/print_queue/api/v1/claim', 'POST'),
    ('/print_queue/next', 'GET'), ('/print_queue/workstations/2/next', 'GET'),
    ('/print_agent/heartbeat', 'POST'), ('/wechat_share/save', 'POST'),
    ('/wechat_share/run', 'POST'), ('/wechat_share/run_now', 'POST'), ('/wechat_share/log/3/resend', 'POST'),
    ('/wechat_share/logs/clear', 'POST'), ('/wechat_share/logs/cleanup', 'POST'),
])
def test_initialize_runtime_status(sample_app, monkeypatch, path, method):
    monkeypatch.setenv('WMS_EXTERNAL_OPERATIONS_PAUSED', '1')
    effects = []
    runtime.initialize_runtime_status(sample_app)
    sample_app.add_url_rule(path, view_func=lambda: effects.append('write') or 'unexpected', methods=[method])
    response = sample_app.test_client().open(path, method=method)
    assert response.status_code == 503
    assert '当前部署已暂停' in response.get_json()['msg']
    assert effects == []


@pytest.mark.parametrize('path,method', [('/print_queue/stats', 'GET'),
    ('/print_queue/station', 'GET'), ('/print_routing', 'GET'), ('/wechat_share', 'GET'),
    ('/wechat_share/logs/cleanup_preview', 'GET'),
    ('/in_order/add', 'POST'), ('/in_order/7/print', 'GET')])
def test_paused_runtime_keeps_reading_and_core_business_entry(sample_app, monkeypatch, path, method):
    monkeypatch.setenv('WMS_EXTERNAL_OPERATIONS_PAUSED', '1')
    runtime.initialize_runtime_status(sample_app)
    sample_app.add_url_rule(path, view_func=lambda: 'unchanged', methods=[method])
    assert sample_app.test_client().open(path, method=method).data == b'unchanged'


@pytest.mark.parametrize('endpoint', ['clear_wechat_share_logs', 'cleanup_wechat_share_history'])
def test_paused_runtime_blocks_share_cleanup_endpoint_names(sample_app, monkeypatch, endpoint):
    monkeypatch.setenv('WMS_EXTERNAL_OPERATIONS_PAUSED', '1')
    effects = []
    runtime.initialize_runtime_status(sample_app)
    path = '/synthetic/' + endpoint
    sample_app.add_url_rule(path, endpoint=endpoint,
                            view_func=lambda: effects.append('write') or 'unexpected', methods=['POST'])
    response = sample_app.test_client().post(path)
    assert response.status_code == 503
    assert effects == []


def test_standard_runtime_does_not_pause_an_existing_route(sample_app):
    runtime.initialize_runtime_status(sample_app)
    sample_app.add_url_rule('/print_queue/jobs', view_func=lambda: 'normal', methods=['POST'])
    assert sample_app.test_client().post('/print_queue/jobs').data == b'normal'
    with sample_app.app_context():
        status = runtime.get_runtime_status()
        assert status['registered'] is False
        assert status['external_operations_paused'] is False


def test_external_operations_paused(sample_app, monkeypatch):
    monkeypatch.setenv('WMS_RELEASE_STATE_ROOT', str(Path(sample_app.root_path).parent/'synthetic-state'))
    monkeypatch.setenv('WMS_EXTERNAL_OPERATIONS_PAUSED', '0')
    runtime.initialize_runtime_status(sample_app)
    assert runtime.external_operations_paused(sample_app) is True


def test_get_runtime_status(sample_app, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-secret-not-for-output')
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///private-warehouse-path.db')
    runtime.initialize_runtime_status(sample_app)
    with sample_app.app_context():
        before = runtime.get_runtime_status()
        sample_app.config['SESSION_COOKIE_SECURE'] = False
        after = runtime.get_runtime_status()
    assert before['config_fingerprint'] != after['config_fingerprint']
    rendered = json.dumps(after)
    assert 'synthetic-secret' not in rendered and 'private-warehouse-path' not in rendered
    assert str(sample_app.root_path) not in rendered


def test_preflight_runtime_identity(sample_app, monkeypatch):
    monkeypatch.setenv('WMS_RELEASE_MANIFEST', str(Path(sample_app.root_path).parent/'missing.json'))
    with pytest.raises((OSError, ValueError)):
        runtime.preflight_runtime_identity(sample_app.root_path)


def test_initialize_runtime_status_bad_boolean_refuses(sample_app, monkeypatch):
    monkeypatch.setenv('WMS_EXTERNAL_OPERATIONS_PAUSED', 'maybe')
    with pytest.raises(ValueError):
        runtime.initialize_runtime_status(sample_app)


def test_registered_manifest_reports_complete_identity_and_current_interpreter(sample_app, monkeypatch):
    from services.release_manifest import build_release_manifest
    directory = Path(sample_app.root_path)
    (directory/'app.py').write_text('# synthetic', encoding='utf-8')
    report = {'success': True, 'python_version': sys.version.split()[0], 'packages': [], 'failures': []}
    manifest = build_release_manifest(directory.parent, source_sha='a'*40, ui_sha='b'*40,
        includes=['app'], application_root='app', overlay_roots=[], runtime_report=report,
        external_operations_paused=True)
    (directory.parent/'wms-release.json').write_text(json.dumps(manifest), encoding='utf-8')
    runtime.initialize_runtime_status(sample_app)
    with sample_app.app_context():
        status = runtime.get_runtime_status()
    assert status['registered'] and status['artifact_id'] == manifest['artifact_id']
    assert status['source_sha'] == 'a'*40 and status['ui_sha'] == 'b'*40
    assert status['external_operations_paused'] is True
    assert status['runtime_verified'] is True


def test_preflight_runtime_identity_rejects_wrong_application_root(sample_app, monkeypatch):
    from services.release_manifest import build_release_manifest
    directory = Path(sample_app.root_path)
    (directory/'app.py').write_text('# synthetic', encoding='utf-8')
    report = {'success': True, 'python_version': sys.version.split()[0], 'packages': [], 'failures': []}
    manifest = build_release_manifest(directory.parent, source_sha='a'*40, ui_sha='a'*40,
        includes=['app'], application_root='app', overlay_roots=[], runtime_report=report,
        external_operations_paused=False)
    (directory.parent/'wms-release.json').write_text(json.dumps(manifest), encoding='utf-8')
    other = directory.parent/'other-app'
    other.mkdir()
    monkeypatch.setenv('WMS_RELEASE_MANIFEST', str(directory.parent/'wms-release.json'))
    with pytest.raises(ValueError):
        runtime.preflight_runtime_identity(other)
