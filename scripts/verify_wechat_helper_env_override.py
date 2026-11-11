"""Offline regression lock for BUG-2026-11-11-003.

``WMS_WECHAT_HELPER_URL`` was dead configuration: the save route and the
first-run default config always persisted ``http://127.0.0.1:8765/send``,
and both consumers read the database value *before* the environment, so the
operator override could never win.

The real functions are extracted from ``app/app.py`` and
``app/routes/wechat_share.py`` with the AST, decorators/module imports are
stripped, and only those definitions execute in a synthetic namespace.
Nothing imports the WMS application, opens a database, writes a product file
or issues a real HTTP request. The synthetic PNG lives in the OS temp dir.
"""
from __future__ import annotations

import argparse
import ast
import copy
import datetime as _dt
from functools import lru_cache
import json
import os
from pathlib import Path
import tempfile
import types
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = ROOT / 'app' / 'app.py'
ROUTE_SOURCE = ROOT / 'app' / 'routes' / 'wechat_share.py'
APP_FUNCTIONS = ('_wechat_share_helper_url_allowed', '_wechat_share_send_image',
                '_wechat_share_helper_health_url')
ROUTE_NAME = 'save_wechat_share_config'
ENV_KEY = 'WMS_WECHAT_HELPER_URL'
LEGACY_DEFAULT = 'http://127.0.0.1:8765/send'
LINE_ANCHOR = 'def backfill_stock_txn_warehouse_id('
LINE_ANCHOR_EXPECTED = 30413


class _StripModuleImports(ast.NodeTransformer):
    """Remove ``from app/flask/services... import`` only; keep stdlib imports."""

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        return None


class _Json:
    def __init__(self, payload: dict):
        self.payload = payload

    def get_json(self) -> dict:
        return self.payload


class _ConnError(Exception):
    pass


class _Timeout(Exception):
    pass


@lru_cache(maxsize=16)
def _parse_tree(path_str: str, mtime_ns: int, size: int):
    return ast.parse(Path(path_str).read_text(encoding='utf-8'))


@lru_cache(maxsize=16)
def _read_text(path_str: str, mtime_ns: int, size: int) -> str:
    return Path(path_str).read_text(encoding='utf-8')


def _tree(source: Path):
    stat = source.stat()
    return _parse_tree(str(source), stat.st_mtime_ns, stat.st_size)


def _source_text(source: Path) -> str:
    stat = source.stat()
    return _read_text(str(source), stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=16)
def _find_route_node(path_str: str, mtime_ns: int, size: int):
    tree = _parse_tree(path_str, mtime_ns, size)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == ROUTE_NAME:
            return node
    raise AssertionError('缺少待验证的路由函数：' + ROUTE_NAME)


def _find_defs(source: Path, wanted) -> dict:
    found = {node.name: node for node in _tree(source).body
             if isinstance(node, ast.FunctionDef) and node.name in wanted}
    missing = [name for name in wanted if name not in found]
    if missing:
        raise AssertionError('缺少待验证的函数定义：' + ', '.join(missing))
    return found


def _find_route(source: Path) -> ast.FunctionDef:
    stat = source.stat()
    return _find_route_node(str(source), stat.st_mtime_ns, stat.st_size)


def _compile_route(found: ast.FunctionDef, source: Path):
    fn = copy.deepcopy(found)
    fn.decorator_list = []
    _StripModuleImports().visit(fn)
    ast.fix_missing_locations(fn)
    return compile(ast.Module(body=[fn], type_ignores=[]), str(source), 'exec')


def _with_env(value, fn):
    previous = os.environ.get(ENV_KEY)
    try:
        if value is None:
            os.environ.pop(ENV_KEY, None)
        else:
            os.environ[ENV_KEY] = value
        return fn()
    finally:
        if previous is None:
            os.environ.pop(ENV_KEY, None)
        else:
            os.environ[ENV_KEY] = previous


def _config(helper_url=LEGACY_DEFAULT):
    return types.SimpleNamespace(
        id=9, helper_url=helper_url, sender_name='sender', sender_wechat_id='',
        receiver_name='receiver', receiver_wechat_id='', receiver_search_key='receiver',
        receiver_type='person', auto_send=False, share_time='15:30',
    )


def _build_app_ns(app_source: Path, *, token='synthetic-token', post_result=None):
    """Compile the three real app.py helpers into a fully synthetic namespace."""
    defs = _find_defs(app_source, APP_FUNCTIONS)
    calls: list = []
    captured: dict = {}

    class _Response:
        def __init__(self, status_code=200, payload=None):
            self.status_code = status_code
            self.ok = 200 <= status_code < 300
            self._payload = payload or {'status': 'sent', 'code': 'ok', 'msg': '已发送'}

        def json(self):
            return self._payload

    def fake_post(url, **kwargs):
        calls.append('requests.post')
        captured['url'] = url
        captured['kwargs'] = kwargs
        if post_result is not None:
            result = post_result
            if isinstance(result, Exception):
                raise result
            return result
        return _Response()

    requests = types.SimpleNamespace(
        post=fake_post,
        exceptions=types.SimpleNamespace(ConnectionError=_ConnError, Timeout=_Timeout),
    )
    app = types.SimpleNamespace(
        config={'WECHAT_HELPER_TOKEN': token},
        logger=types.SimpleNamespace(
            warning=lambda *a, **k: None, error=lambda *a, **k: None,
            exception=lambda *a, **k: None),
    )
    ns: dict = {
        'os': os, 'urlparse': urlparse, 'app': app, 'requests': requests,
        '_LOOPBACK_NO_PROXY': {'http': None, 'https': None},
    }
    for name in APP_FUNCTIONS:
        module = ast.Module(body=[defs[name]], type_ignores=[])
        exec(compile(module, str(app_source), 'exec'), ns)
    return ns, calls, captured


def _build_route_ns(code, form: dict, allowed_fn):
    """Compile the real save route into a synthetic namespace."""
    calls: list = []
    captured: dict = {}
    config = _config()

    def default_config():
        calls.append('default_config')
        captured['config'] = config
        return config

    class _Session:
        def commit(self):
            calls.append('db.session.commit')

        def rollback(self):
            calls.append('db.session.rollback')

    def api_error(msg):
        return _Json({'status': 'error', 'msg': msg}), 400

    ns: dict = {
        'os': os,
        'current_app': types.SimpleNamespace(
            logger=types.SimpleNamespace(error=lambda *a, **k: None)),
        '_wechat_share_default_config': default_config,
        '_wechat_share_helper_url_allowed': allowed_fn,
        '_wechat_share_time_is_valid': lambda v: bool(v) and len(str(v)) == 5,
        '_wechat_share_wecom_webhook_allowed': lambda url: True,
        'api_error': api_error,
        'datetime': _dt.datetime,
        'db': types.SimpleNamespace(session=_Session()),
        'jsonify': lambda payload: _Json(payload),
        'log_operation': lambda *a, **k: calls.append('log_operation'),
        'request': types.SimpleNamespace(form=form, args={}),
        'set_system_setting': lambda *a, **k: calls.append('set_system_setting'),
    }
    exec(code, ns)
    return ns, calls, captured, config, ns[ROUTE_NAME]


def _call_route(route):
    result = route()
    if isinstance(result, tuple):
        return result[0].get_json(), result[1]
    return result.get_json(), 200


def _helper_assign(fn: ast.FunctionDef):
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'helper_url' for t in node.targets):
            if isinstance(node.value, ast.BoolOp) and isinstance(node.value.op, ast.Or):
                return node.value.values
    return []


def _static_checks(app_source: Path, route_source: Path) -> dict:
    results: dict = {}
    app_defs = _find_defs(app_source, APP_FUNCTIONS)
    route = _find_route(route_source)
    app_text = _source_text(app_source)
    route_text = _source_text(route_source)

    for name in ('_wechat_share_send_image', '_wechat_share_helper_health_url'):
        values = _helper_assign(app_defs[name])
        first = ast.dump(values[0]) if values else ''
        second = ast.dump(values[1]) if len(values) > 1 else ''
        results[f'{name}_env_is_first_operand'] = (
            ENV_KEY in first and 'config' not in first)
        results[f'{name}_config_is_fallback_operand'] = (
            'config' in second and ENV_KEY not in second)
        results[f'{name}_still_uses_strip'] = (
            'strip' in first and 'strip' in second)

    results['line_anchor_unchanged_30413'] = any(
        i == LINE_ANCHOR_EXPECTED and line.startswith(LINE_ANCHOR)
        for i, line in enumerate(app_text.splitlines(), 1))
    results['send_image_keeps_loopback_whitelist'] = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == '_wechat_share_helper_url_allowed'
        for n in ast.walk(app_defs['_wechat_share_send_image']))
    results['health_url_keeps_loopback_whitelist'] = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == '_wechat_share_helper_url_allowed'
        for n in ast.walk(app_defs['_wechat_share_helper_health_url']))
    send_calls = [n for n in ast.walk(app_defs['_wechat_share_send_image'])
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr == 'post']
    keywords = {k.arg: k.value for c in send_calls for k in c.keywords}
    results['send_image_keeps_no_proxy'] = 'proxies' in keywords
    results['send_image_keeps_no_redirects'] = (
        'allow_redirects' in keywords
        and isinstance(keywords['allow_redirects'], ast.Constant)
        and keywords['allow_redirects'].value is False)
    results['send_image_keeps_timeout_10'] = (
        'timeout' in keywords and isinstance(keywords['timeout'], ast.Constant)
        and keywords['timeout'].value == 10)
    results['send_image_keeps_helper_token_header'] = (
        'WECHAT_HELPER_TOKEN' in app_text and 'X-Wechat-Helper-Token' in app_text)

    results['save_route_has_no_hardcoded_default'] = (
        "or 'http://127.0.0.1:8765/send'" not in route_text)
    guards = [n for n in ast.walk(route) if isinstance(n, ast.If)
              and isinstance(n.test, ast.BoolOp) and isinstance(n.test.op, ast.And)
              and any(isinstance(v, ast.Name) and v.id == 'helper_url'
                      for v in n.test.values)
              and any(isinstance(v, ast.UnaryOp) and isinstance(v.op, ast.Not)
                      and isinstance(v.operand, ast.Call)
                      and isinstance(v.operand.func, ast.Name)
                      and v.operand.func.id == '_wechat_share_helper_url_allowed'
                      for v in n.test.values)]
    results['save_route_empty_allowed_but_nonempty_validated'] = len(guards) == 1
    results['save_route_still_assigns_helper_url'] = any(
        isinstance(n, ast.Assign) and isinstance(n.value, ast.Name)
        and n.value.id == 'helper_url'
        and any(isinstance(t, ast.Attribute) and t.attr == 'helper_url'
                for t in n.targets) for n in ast.walk(route))
    results['save_route_decorators_preserved'] = bool(route.decorator_list) and any(
        isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
        and d.func.attr == 'route' for d in route.decorator_list)
    print_alerts_text = _source_text(ROOT / 'app' / 'routes' / 'print_alerts.py')
    results['other_default_config_callers_preserved'] = (
        route_text.count('_wechat_share_default_config') >= 4
        and 'config = config or _wechat_share_default_config()' in app_text
        and '    _wechat_share_default_config()' in app_text
        and 'config = _wechat_share_default_config()' in print_alerts_text)
    results['helper_configured_flag_untouched'] = (
        "bool((config.helper_url or '').strip() or os.environ.get('WMS_WECHAT_HELPER_URL', '').strip())"
        in route_text)
    return results


def run_checks(app_source: Path = APP_SOURCE, route_source: Path = ROUTE_SOURCE) -> dict:
    results = _static_checks(app_source, route_source)
    allowed_fn = _build_app_ns(app_source)[0]['_wechat_share_helper_url_allowed']

    with tempfile.TemporaryDirectory(prefix='wms-helper-env-') as tmp:
        image_path = os.path.join(tmp, 'synth.png')
        Path(image_path).write_bytes(b'\x89PNG\r\n\x1a\nsynthetic')

        def send(env_value, cfg_url=LEGACY_DEFAULT, **kw):
            ns, calls, captured = _build_app_ns(app_source, **kw)
            return _with_env(
                env_value,
                lambda: (ns['_wechat_share_send_image'](_config(cfg_url), image_path),
                         calls, captured)), ns

        # ---- core regression: operator env override must win ----
        (result, calls, captured), _ = send('http://127.0.0.1:18765/send')
        results['env_override_wins_over_persisted_default'] = (
            captured.get('url') == 'http://127.0.0.1:18765/send')
        results['env_override_still_posts'] = calls.count('requests.post') == 1
        results['env_override_returns_sent'] = result[0] == 'sent'
        results['env_override_keeps_token_header'] = (
            captured.get('kwargs', {}).get('headers', {}).get('X-Wechat-Helper-Token')
            == 'synthetic-token')
        results['env_override_keeps_no_proxy'] = (
            captured.get('kwargs', {}).get('proxies') == {'http': None, 'https': None})
        results['env_override_keeps_timeout'] = (
            captured.get('kwargs', {}).get('timeout') == 10)
        results['env_override_forbids_redirects'] = (
            captured.get('kwargs', {}).get('allow_redirects') is False)

        # ---- existing behaviour with no env must be byte-equivalent ----
        (result, calls, captured), _ = send(None)
        results['no_env_falls_back_to_config'] = captured.get('url') == LEGACY_DEFAULT
        results['no_env_still_sends'] = result[0] == 'sent'
        (result, calls, captured), _ = send('')
        results['blank_env_falls_back_to_config'] = captured.get('url') == LEGACY_DEFAULT
        (result, calls, captured), _ = send('   ')
        results['whitespace_only_env_falls_back'] = captured.get('url') == LEGACY_DEFAULT
        (result, calls, captured), _ = send('  http://localhost:18765/send  ')
        results['env_value_is_stripped'] = captured.get('url') == 'http://localhost:18765/send'

        # ---- fail-closed guards survive ----
        (result, calls, captured), _ = send('https://evil.example.com/send')
        results['external_env_rejected'] = (
            result[0] == 'failed' and result[1] == 'invalid_helper_url'
            and calls == [])
        (result, calls, captured), _ = send('http://user:pw@127.0.0.1:8765/send')
        results['env_with_userinfo_rejected'] = (
            result[0] == 'failed' and result[1] == 'invalid_helper_url'
            and calls == [])
        (result, calls, captured), _ = send(None, cfg_url='')
        results['no_url_anywhere_pending'] = (
            result[0] == 'pending' and result[1] == 'helper_not_configured'
            and calls == [])
        (result, calls, captured), _ = send('http://127.0.0.1:18765/send', token='')
        results['missing_token_still_fails_closed'] = (
            result[0] == 'failed' and result[1] == 'token_not_configured'
            and calls == [])

        # ---- transport result mapping untouched ----
        (result, calls, captured), _ = send('http://127.0.0.1:18765/send',
                                            post_result=_ConnError('synthetic'))
        results['connection_error_still_offline'] = (
            result[1] == 'helper_offline' and calls.count('requests.post') == 1)
        (result, calls, captured), _ = send('http://127.0.0.1:18765/send',
                                            post_result=_Timeout('synthetic'))
        results['timeout_still_no_retry'] = (
            result[1] == 'helper_timeout' and calls.count('requests.post') == 1)

        # ---- health URL consumer uses the same precedence ----
        def health(env_value, cfg_url=LEGACY_DEFAULT):
            ns, _, _ = _build_app_ns(app_source)
            return _with_env(
                env_value, lambda: ns['_wechat_share_helper_health_url'](_config(cfg_url)))

        results['health_env_override_wins'] = (
            health('http://127.0.0.1:18765/send') == 'http://127.0.0.1:18765/health')
        results['health_no_env_falls_back'] = health(None) == 'http://127.0.0.1:8765/health'
        results['health_env_without_send_path'] = (
            health('http://localhost:18765') == 'http://localhost:18765/health')
        results['health_external_env_rejected'] = (
            health('https://evil.example.com/send') == '')
        results['health_both_empty_returns_empty'] = health(None, cfg_url='') == ''
        results['loopback_whitelist_empty_still_false'] = (
            _build_app_ns(app_source)[0]['_wechat_share_helper_url_allowed']('') is False)

        # ---- save route no longer pins a default address ----
        code = _compile_route(_find_route(route_source), route_source)

        def save(form, env_value=None):
            def run():
                ns, calls, captured, config, route = _build_route_ns(code, form, allowed_fn)
                payload, status = _call_route(route)
                return payload, status, calls, config
            return _with_env(env_value, run)

        payload, status, calls, config = save({
            'share_time': '15:30', 'receiver_name': '张三', 'helper_url': ''})
        results['save_blank_helper_url_succeeds'] = (
            status == 200 and payload.get('status') == 'success')
        results['save_blank_stores_empty_string'] = config.helper_url == ''
        results['save_blank_never_writes_legacy_default'] = (
            LEGACY_DEFAULT not in str(config.helper_url))
        results['save_blank_still_commits'] = 'db.session.commit' in calls
        results['save_blank_still_logs_operation'] = 'log_operation' in calls
        results['save_blank_still_reuses_current_config'] = 'default_config' in calls

        payload, status, calls, config = save({
            'share_time': '15:30', 'receiver_name': '张三', 'helper_url': ''},
            env_value='http://127.0.0.1:18765/send')
        results['save_blank_does_not_persist_env_value'] = config.helper_url == ''

        payload, status, calls, config = save({
            'share_time': '15:30', 'receiver_name': '张三',
            'helper_url': 'http://192.168.1.100:8765/send'})
        results['save_rejects_external_url'] = (
            status == 400 and payload.get('status') == 'error'
            and '回环' in payload.get('msg', ''))
        results['save_reject_does_not_commit'] = 'db.session.commit' not in calls

        payload, status, calls, config = save({
            'share_time': '15:30', 'receiver_name': '张三',
            'helper_url': '  http://localhost:18765/send  '})
        results['save_valid_url_stripped_and_stored'] = (
            status == 200 and config.helper_url == 'http://localhost:18765/send')

        payload, status, calls, config = save({'share_time': '15:30', 'helper_url': ''})
        results['save_still_requires_receiver'] = (
            status == 400 and '接收人' in payload.get('msg', ''))

    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--app-source', default=str(APP_SOURCE))
    parser.add_argument('--route-source', default=str(ROUTE_SOURCE))
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    results = run_checks(Path(args.app_source), Path(args.route_source))
    failed = [name for name, ok in results.items() if not ok]
    if args.json:
        print(json.dumps({'total': len(results), 'passed': len(results) - len(failed),
                          'failed': failed, 'success': not failed}, ensure_ascii=False))
    else:
        for name, ok in results.items():
            print(('  PASS  ' if ok else '  FAIL  ') + name)
        print('\n  %d/%d checks passed' % (len(results) - len(failed), len(results)))
    return 0 if not failed else 1


if __name__ == '__main__':
    raise SystemExit(main())
