"""Offline regression lock for BUG-2026-11-10-005.

Loads an arbitrary copy of runtime_status.py (so the same assertions can be
replayed against the pre-fix source) plus the wechat_share template, using only
synthetic Flask apps. Never imports the WMS application, opens a database or
issues an HTTP request.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

from flask import Flask
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / 'app' / 'services' / 'runtime_status.py'
DEFAULT_TEMPLATE = ROOT / 'app' / 'templates' / 'wechat_share.html'

BLOCKED = [
    ('/print_queue/jobs', 'POST'), ('/print_queue/api/v1/claim', 'POST'),
    ('/print_queue/next', 'GET'), ('/print_queue/workstations/2/next', 'GET'),
    ('/print_agent/heartbeat', 'POST'), ('/wechat_share/save', 'POST'),
    ('/wechat_share/run', 'POST'), ('/wechat_share/run_now', 'POST'),
    ('/wechat_share/log/3/resend', 'POST'),
    ('/wechat_share/logs/clear', 'POST'), ('/wechat_share/logs/cleanup', 'POST'),
]
ALLOWED = [
    ('/print_queue/stats', 'GET'), ('/print_queue/station', 'GET'),
    ('/print_routing', 'GET'), ('/wechat_share', 'GET'),
    ('/wechat_share/logs/cleanup_preview', 'GET'),
    ('/in_order/add', 'POST'), ('/in_order/7/print', 'GET'),
]
CLEANUP_ENDPOINTS = ['clear_wechat_share_logs', 'cleanup_wechat_share_history']
TEMPLATE_MARKERS = [
    "onclick=\"clearWechatShareLogs('failed')\"",
    'onclick="openWechatShareCleanup()"',
    'onclick="previewWechatShareCleanup()"',
    'id="wechatCleanupConfirm"',
]
PAUSE_TITLE = '当前部署暂停清理'


def load_runtime(source: Path):
    sys.path.insert(0, str(ROOT / 'app'))
    spec = importlib.util.spec_from_file_location('wms_runtime_status_under_test', source)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build_app(module, paused: bool):
    for key in ('WMS_RELEASE_MANIFEST', 'WMS_RELEASE_STATE_ROOT'):
        os.environ.pop(key, None)
    if paused:
        os.environ['WMS_EXTERNAL_OPERATIONS_PAUSED'] = '1'
    else:
        os.environ.pop('WMS_EXTERNAL_OPERATIONS_PAUSED', None)
    root = Path(tempfile.mkdtemp(prefix='wms-pause-guard-')) / 'app'
    root.mkdir()
    app = Flask('runtime-synthetic', root_path=str(root))
    app.config.update(SECRET_KEY='synthetic-only', TESTING=True,
                      SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Lax')
    module.initialize_runtime_status(app)
    return app


def check_blocked(module, path: str, method: str) -> bool:
    app = build_app(module, True)
    effects = []
    app.add_url_rule(path, view_func=lambda: effects.append('write') or 'unexpected',
                     methods=[method])
    response = app.test_client().open(path, method=method)
    return (response.status_code == 503 and '当前部署已暂停' in response.get_json()['msg']
            and effects == [])


def check_allowed(module, path: str, method: str) -> bool:
    app = build_app(module, True)
    app.add_url_rule(path, view_func=lambda: 'unchanged', methods=[method])
    return app.test_client().open(path, method=method).data == b'unchanged'


def check_endpoint(module, endpoint: str) -> bool:
    app = build_app(module, True)
    effects = []
    path = '/synthetic/' + endpoint
    app.add_url_rule(path, endpoint=endpoint,
                     view_func=lambda: effects.append('write') or 'unexpected',
                     methods=['POST'])
    response = app.test_client().post(path)
    return response.status_code == 503 and effects == []


def check_unpaused(module) -> bool:
    app = build_app(module, False)
    for path in ('/wechat_share/logs/clear', '/wechat_share/logs/cleanup'):
        app.add_url_rule(path, endpoint='synthetic_' + path.rsplit('/', 1)[-1],
                         view_func=lambda: 'normal', methods=['POST'])
    return all(app.test_client().post(path).data == b'normal'
               for path in ('/wechat_share/logs/clear', '/wechat_share/logs/cleanup'))


def check_template(path: Path) -> dict:
    text = path.read_text(encoding='utf-8')
    env = Environment()
    env.parse(text)  # syntax only; the parent template is never loaded
    lines = text.splitlines()
    results = {}
    for marker in TEMPLATE_MARKERS:
        line = next((candidate for candidate in lines if marker in candidate), '')
        if not line:
            results['template ' + marker] = False
            continue
        off = env.from_string(line).render(runtime_external_paused=False)
        on = env.from_string(line).render(runtime_external_paused=True)
        results['template off ' + marker] = PAUSE_TITLE not in off
        results['template on ' + marker] = PAUSE_TITLE in on
    results['template confirm stays disabled while paused'] = (
        'cleanupPaused || !wechatCleanupPlan' in text
        and 'meta[name="wms-external-operations"]' in text)
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(DEFAULT_SOURCE))
    parser.add_argument('--template', default=str(DEFAULT_TEMPLATE))
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    module = load_runtime(Path(args.source))
    results = {}
    for path, method in BLOCKED:
        results['blocked %s %s' % (method, path)] = check_blocked(module, path, method)
    for path, method in ALLOWED:
        results['allowed %s %s' % (method, path)] = check_allowed(module, path, method)
    for endpoint in CLEANUP_ENDPOINTS:
        results['endpoint ' + endpoint] = check_endpoint(module, endpoint)
    results['unpaused cleanup posts'] = check_unpaused(module)
    results.update(check_template(Path(args.template)))
    failed = [name for name, ok in results.items() if not ok]
    if args.json:
        print(json.dumps({'total': len(results), 'passed': len(results) - len(failed),
                          'failed': failed, 'success': not failed}, ensure_ascii=False))
    else:
        for name, ok in results.items():
            print(('PASS ' if ok else 'FAIL ') + name)
        print('%d/%d passed' % (len(results) - len(failed), len(results)))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
