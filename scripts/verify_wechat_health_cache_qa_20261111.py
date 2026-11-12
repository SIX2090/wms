"""QA offline replica of tests/verify_bug_2026_08_11_012_helper_health_cache.py T1-T4.

The original file does `import app as app_module` at module level, so local
pytest is blocked by tests/conftest.py's LPAC guard (expected, never bypassed).
Here the REAL test methods are AST-extracted and run against a synthetic
`app_module` module whose __dict__ is also the __globals__ of the REAL
_wechat_share_get_helper_health / _wechat_share_helper_health_url extracted
from app/app.py. No WMS app import, no DB, no HTTP.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import copy
import datetime as dt
import json
import os
from pathlib import Path
import sys
import types
from urllib.parse import urlparse

ROOT = Path(r'C:\wms')
APP_PY = ROOT / 'app' / 'app.py'
CACHE_TEST = ROOT / 'tests' / 'verify_bug_2026_08_11_012_helper_health_cache.py'
NO_PROXY = {'http': None, 'https': None}

TEST_NAMES = (
    'test_t1_second_call_within_30s_hits_cache',
    'test_t2_cache_expires_after_30s',
    'test_t3_url_change_bypasses_cache',
    'test_t4_unconfigured_clears_cache_and_skips_request',
)


class _StripImports(ast.NodeTransformer):
    def visit_Import(self, node):
        return None

    def visit_ImportFrom(self, node):
        return None


class _Logger:
    def warning(self, *a, **k):
        pass

    def exception(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass


def _synthetic_app_module():
    import requests  # real module: monkeypatch.setattr("requests.get", ...) works

    app_module = types.ModuleType('qa_synth_app_module')
    cache = {'url': '', 'at': None, 'health': None}

    class _App:
        config = {'WECHAT_HELPER_TOKEN': 'tok-cache'}

        def app_context(self):
            return contextlib.nullcontext()

    app_module.__dict__.update({
        '__builtins__': __builtins__,
        'os': types.SimpleNamespace(environ={}, path=os.path),
        'urlparse': urlparse,
        'datetime': dt.datetime,
        'requests': requests,
        'app': types.SimpleNamespace(logger=_Logger(), config=_App.config),
        'external_operations_paused': lambda: False,
        '_wechat_share_helper_url_allowed': lambda url: True,
        '_WECHAT_SHARE_HEALTH_CACHE': cache,
        '_WECHAT_SHARE_HEALTH_CACHE_TTL_SECONDS': 30,
        '_LOOPBACK_NO_PROXY': NO_PROXY,
        'app_obj': _App(),
    })
    app_module.app_context = _App().app_context  # not used by health fn
    # `app_module.app` must expose app_context() for the test methods.
    app_module.app = _App()

    tree = ast.parse(APP_PY.read_text(encoding='utf-8-sig'))
    wanted = {'_wechat_share_get_helper_health', '_wechat_share_helper_health_url'}
    health_nodes = copy.deepcopy(
        [n for n in tree.body
         if isinstance(n, ast.FunctionDef) and n.name in wanted])
    for n in health_nodes:
        n.decorator_list = []
        _StripImports().visit(n)
    exec(compile(ast.fix_missing_locations(
        ast.Module(body=health_nodes, type_ignores=[])),
        '<qa-health-cache:app.py>', 'exec'), app_module.__dict__)
    return app_module


def main() -> int:
    import pytest

    tree = ast.parse(CACHE_TEST.read_text(encoding='utf-8-sig'))
    wanted = {'_make_config', '_FakeResponse', '_reset_cache', '_freeze_time',
              '_real_datetime', 'TestHelperHealthCache'}
    nodes = copy.deepcopy(
        [n for n in tree.body
         if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in wanted])
    for n in nodes:
        if hasattr(n, 'decorator_list'):
            n.decorator_list = []
        _StripImports().visit(n)

    app_module = _synthetic_app_module()
    glb = {
        '__builtins__': __builtins__,
        'dt': dt, 'os': os, 'sys': sys, 'types': types, 'Path': Path,
        'ROOT': ROOT, 'app_module': app_module, 'pytest': pytest,
    }
    exec(compile(ast.fix_missing_locations(
        ast.Module(body=nodes, type_ignores=[])),
        '<qa-health-cache:tests>', 'exec'), glb)

    results = {}
    cls = glb['TestHelperHealthCache']
    for name in TEST_NAMES:
        mp = pytest.MonkeyPatch()
        try:
            getattr(cls(), name)(mp)
            results[name] = True
        except Exception as exc:
            results[name] = False
            print(f'  [FAIL] {name}: {type(exc).__name__}: {exc}', file=sys.stderr)
        finally:
            mp.undo()

    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    failed = [n for n, ok in results.items() if not ok]
    if args.json:
        print(json.dumps({'total': len(results),
                          'passed': len(results) - len(failed),
                          'failed': failed, 'success': not failed},
                         ensure_ascii=False, indent=2))
    else:
        for n, ok in results.items():
            print(('  PASS  ' if ok else '  FAIL  ') + n)
        print(f'\n  {len(results) - len(failed)}/{len(results)} real test methods passed')
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
