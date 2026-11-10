"""Offline regression lock for BUG-2026-11-10-006.

Extracts the two pure helper-URL functions from app/app.py with the AST and
executes only those definitions in an isolated namespace. Never imports the
WMS application, opens a database or issues an HTTP request.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import os
from types import SimpleNamespace
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / 'app' / 'app.py'
FUNCTIONS = ('_wechat_share_helper_url_allowed', '_wechat_share_helper_health_url')


def load_functions(source: Path) -> dict:
    tree = ast.parse(source.read_text(encoding='utf-8'))
    definitions = {node.name: node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS}
    missing = [name for name in FUNCTIONS if name not in definitions]
    if missing:
        raise AssertionError('缺少待验证的函数定义：' + ', '.join(missing))
    namespace = {'os': os, 'urlparse': urlparse}
    for name in FUNCTIONS:
        module = ast.Module(body=[definitions[name]], type_ignores=[])
        exec(compile(module, str(source), 'exec'), namespace)
    return namespace


def _health(namespace, helper_url: str = '', env_url: str | None = None) -> str:
    previous = os.environ.get('WMS_WECHAT_HELPER_URL')
    try:
        if env_url is None:
            os.environ.pop('WMS_WECHAT_HELPER_URL', None)
        else:
            os.environ['WMS_WECHAT_HELPER_URL'] = env_url
        return namespace['_wechat_share_helper_health_url'](
            SimpleNamespace(helper_url=helper_url))
    finally:
        if previous is None:
            os.environ.pop('WMS_WECHAT_HELPER_URL', None)
        else:
            os.environ['WMS_WECHAT_HELPER_URL'] = previous


def run_checks(source: Path = DEFAULT_SOURCE) -> dict:
    namespace = load_functions(source)
    results = {}
    results['loopback 127.0.0.1 /send'] = (
        _health(namespace, 'http://127.0.0.1:8765/send') == 'http://127.0.0.1:8765/health')
    results['loopback localhost without /send'] = (
        _health(namespace, 'http://localhost:8765') == 'http://localhost:8765/health')
    results['loopback ipv6 ::1 /send'] = (
        _health(namespace, 'http://[::1]:8765/send') == 'http://[::1]:8765/health')
    results['loopback env fallback'] = (
        _health(namespace, '', 'http://127.0.0.1:8765/send') == 'http://127.0.0.1:8765/health')
    results['empty configuration'] = _health(namespace) == ''
    results['malformed url'] = _health(namespace, 'not-a-url') == ''
    results['non-http scheme'] = _health(namespace, 'ftp://127.0.0.1:8765/send') == ''
    # The regression lock: a non-loopback address must never produce an outbound GET target.
    results['external https host rejected'] = _health(namespace, 'https://example.com/send') == ''
    results['lan host rejected'] = _health(namespace, 'http://192.168.1.10:8765/send') == ''
    results['external env rejected'] = _health(namespace, '', 'https://example.com/send') == ''
    source_text = source.read_text(encoding='utf-8')
    body = next(node for node in ast.parse(source_text).body
                if isinstance(node, ast.FunctionDef) and node.name == FUNCTIONS[1])
    results['health url explicitly reuses loopback whitelist'] = any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == FUNCTIONS[0] for node in ast.walk(body))
    return results


def main() -> int:
    import json
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(DEFAULT_SOURCE))
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    results = run_checks(Path(args.source))
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
    raise SystemExit(main())
