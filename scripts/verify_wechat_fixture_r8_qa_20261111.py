"""QA independent verification of the one out-of-scope file edit:
tests/verify_bug_2026_09_14_034_loopback_no_proxy.py (fake_get fixture).

Proves:
  A. No existing assertion was deleted or weakened (AST comparison of the
     pre-fix baseline commit vs worktree, for BOTH fake_get and fake_post and
     the enclosing test methods).
  B. The change is a genuine STRENGTHENING: the real TestHealthNoProxy T2
     (executed offline with a synthetic app_module) passes on the current
     app/app.py and FAILS on the pre-fix baseline app.py, because that version
     never passes allow_redirects=False.
  C. The added parameter has a default (non-breaking) and fake_post's
     equivalent assertion is untouched.

No WMS app import, no DB, no HTTP, no product file modification.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import copy
import datetime as _dt
import json
import os
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(r'C:\wms')
FIXTURE = ROOT / 'tests' / 'verify_bug_2026_09_14_034_loopback_no_proxy.py'
APP_PY = ROOT / 'app' / 'app.py'
HEAD_APP_OUT = ROOT / 'output' / 'qa_head_app.py'
NO_PROXY = {'http': None, 'https': None}

# 本批次起点（修复前基线）。固定基线而非 HEAD，使取证脚本在本批次提交前后
# 都可复跑：提交后 HEAD 已含修复，若仍拿 HEAD 当「修复前」会令 A/B 全部失效。
BASELINE_SHA = '95d85da32717045700e32d5fb1517f193aba2ab2'

RESULTS: dict[str, bool] = {}


def _check(name, fn):
    try:
        RESULTS[name] = bool(fn())
    except Exception as exc:
        print(f'  [check error] {name}: {type(exc).__name__}: {exc}', file=sys.stderr)
        RESULTS[name] = False


def _git_show_head(rel: str) -> str:
    """读取修复前基线版本（函数名沿用，语义为 BASELINE_SHA 而非当前 HEAD）。"""
    r = subprocess.run(['git', 'show', f'{BASELINE_SHA}:{rel}'], cwd=ROOT,
                       capture_output=True, check=True)
    return r.stdout.decode('utf-8')


def _assert_dumps(text: str, scope: str) -> list[str]:
    """All assert statements inside a named class/method or nested fake_* func."""
    tree = ast.parse(text)
    out = []
    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef):
            continue
        for fn in cls.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            if scope == 'all' or fn.name == scope or cls.name == scope:
                out.extend(ast.dump(n) for n in ast.walk(fn)
                           if isinstance(n, ast.Assert))
    return out


def check_A():
    head = _git_show_head(
        'tests/verify_bug_2026_09_14_034_loopback_no_proxy.py')
    work = FIXTURE.read_text(encoding='utf-8-sig')

    head_all = _assert_dumps(head, 'all')
    work_all = _assert_dumps(work, 'all')
    _check('A1_all_HEAD_asserts_preserved_verbatim',
           lambda: all(a in work_all for a in head_all))
    _check('A2_worktree_has_more_asserts_than_HEAD',
           lambda: len(work_all) > len(head_all))

    def new_asserts():
        remaining = list(work_all)
        for a in head_all:
            remaining.remove(a)
        return remaining
    _check('A3_exactly_one_new_assert_added',
           lambda: len(new_asserts()) == 1)
    _check('A4_new_assert_is_allow_redirects_is_False',
           lambda: 'allow_redirects' in new_asserts()[0]
           and 'Is()' in new_asserts()[0]
           and 'Constant(value=False)' in new_asserts()[0])

    def t2_asserts(text):
        tree = ast.parse(text)
        cls = next(n for n in tree.body
                   if isinstance(n, ast.ClassDef) and n.name == 'TestHealthNoProxy')
        fn = next(n for n in cls.body
                  if isinstance(n, ast.FunctionDef)
                  and n.name == 'test_t2_health_passes_no_proxy')
        return [ast.dump(n) for n in ast.walk(fn) if isinstance(n, ast.Assert)]
    _check('A5_T2_HEAD_asserts_all_preserved',
           lambda: all(a in t2_asserts(work) for a in t2_asserts(head)))

    def fake_get_sig(text):
        tree = ast.parse(text)
        cls = next(n for n in tree.body
                   if isinstance(n, ast.ClassDef) and n.name == 'TestHealthNoProxy')
        fn = next(n for n in cls.body
                  if isinstance(n, ast.FunctionDef)
                  and n.name == 'test_t2_health_passes_no_proxy')
        inner = next(n for n in ast.walk(fn)
                     if isinstance(n, ast.FunctionDef) and n.name == 'fake_get')
        return [a.arg for a in inner.args.args], [d for d in inner.args.defaults]
    _check('A6_fake_get_added_param_has_default_nonbreaking',
           lambda: fake_get_sig(work)[0][-1] == 'allow_redirects'
           and fake_get_sig(work)[0][:-1] == fake_get_sig(head)[0]
           and len(fake_get_sig(work)[1]) == len(fake_get_sig(work)[0]) - 1)
    _check('A7_fake_post_allow_redirects_assert_unchanged',
           lambda: head.count('assert allow_redirects is False') == 1
           and work.count('assert allow_redirects is False') == 2)
    _check('A8_only_one_diff_hunk_in_fixture',
           lambda: sum(1 for line in subprocess.run(
               ['git', 'diff', BASELINE_SHA, '--',
                'tests/verify_bug_2026_09_14_034_loopback_no_proxy.py'],
               cwd=ROOT, capture_output=True, check=True).stdout.decode().splitlines()
               if line.startswith('@@ ')) == 1)


class _StripImports(ast.NodeTransformer):
    def visit_Import(self, node):
        return None

    def visit_ImportFrom(self, node):
        return None


def _extract_health(app_path: Path, cache: dict, logger):
    import requests  # real module, so monkeypatch.setattr("requests.get", ...) works
    from urllib.parse import urlparse
    text = app_path.read_text(encoding='utf-8-sig')
    tree = ast.parse(text)
    wanted = {'_wechat_share_get_helper_health', '_wechat_share_helper_health_url'}
    nodes = copy.deepcopy([n for n in tree.body
                           if isinstance(n, ast.FunctionDef) and n.name in wanted])
    for n in nodes:
        n.decorator_list = []
        _StripImports().visit(n)
    fake_os = types.SimpleNamespace(environ={}, path=os.path)
    glb = {
        '__builtins__': __builtins__,
        'os': fake_os,
        'urlparse': urlparse,
        'datetime': _dt.datetime,
        'requests': requests,
        'app': types.SimpleNamespace(logger=logger),
        'external_operations_paused': lambda: False,
        '_wechat_share_helper_url_allowed': lambda url: True,
        '_WECHAT_SHARE_HEALTH_CACHE': cache,
        '_WECHAT_SHARE_HEALTH_CACHE_TTL_SECONDS': 30,
        '_LOOPBACK_NO_PROXY': NO_PROXY,
    }
    # Single namespace: functions defined here must see each other via
    # __globals__ (separate globals/locals would hide sibling defs).
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 f'<qa-fixture:{app_path.name}>', 'exec'), glb)
    return glb


class _Logger:
    def warning(self, *a, **k):
        pass

    def exception(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass


def _run_t2(app_path: Path):
    """Execute the REAL TestHealthNoProxy T2 offline with a synthetic app_module."""
    import pytest
    fixture_text = FIXTURE.read_text(encoding='utf-8-sig')
    tree = ast.parse(fixture_text)
    cls = copy.deepcopy(next(n for n in tree.body
                             if isinstance(n, ast.ClassDef)
                             and n.name == 'TestHealthNoProxy'))
    helpers = copy.deepcopy([
        n for n in tree.body
        if (isinstance(n, ast.FunctionDef) and n.name in ('_make_config',))
        or (isinstance(n, ast.ClassDef) and n.name == '_HealthResponse')
    ])
    _StripImports().visit(cls)
    for n in helpers:
        if hasattr(n, 'decorator_list'):
            n.decorator_list = []
        _StripImports().visit(n)

    cache = {'url': '', 'at': None, 'health': None}
    health_ns = _extract_health(app_path, cache, _Logger())

    class _App:
        config = {'WECHAT_HELPER_TOKEN': 'tok-034'}

        def app_context(self):
            return contextlib.nullcontext()

    app_module = types.SimpleNamespace(
        app=_App(),
        _WECHAT_SHARE_HEALTH_CACHE=cache,
        _LOOPBACK_NO_PROXY=NO_PROXY,
        _wechat_share_get_helper_health=health_ns['_wechat_share_get_helper_health'],
        _wechat_share_helper_health_url=health_ns['_wechat_share_helper_health_url'],
    )
    glb = {
        '__builtins__': __builtins__,
        'types': types,
        'os': os,
        'pytest': pytest,
        'NO_PROXY': NO_PROXY,
        'app_module': app_module,
    }
    # Single namespace as well: class methods resolve _make_config / NO_PROXY
    # through __globals__.
    exec(compile(ast.fix_missing_locations(
        ast.Module(body=helpers + [cls], type_ignores=[])),
        '<qa-fixture-test>', 'exec'), glb)
    mp = pytest.MonkeyPatch()
    try:
        glb['TestHealthNoProxy']().test_t2_health_passes_no_proxy(mp)
        return True, None
    except Exception as exc:
        return False, f'{type(exc).__name__}: {exc}'
    finally:
        mp.undo()


def check_B():
    ok_work, err_work = _run_t2(APP_PY)
    RESULTS['B1_real_T2_passes_on_workspace'] = ok_work
    if not ok_work:
        print(f'  [B1 error] {err_work}', file=sys.stderr)

    HEAD_APP_OUT.write_text(_git_show_head('app/app.py'), encoding='utf-8', newline='')
    ok_head, err_head = _run_t2(HEAD_APP_OUT)
    RESULTS['B2_real_T2_fails_on_HEAD_app_py'] = (not ok_head)
    print(f'  [B2 evidence] HEAD app.py -> ok={ok_head}, error={err_head}')
    RESULTS['B3_HEAD_failure_is_the_new_allow_redirects_assertion'] = (
        not ok_head and err_head is not None
        and ('AssertionError' in err_head or 'allow_redirects' in (err_head or '')))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    check_A()
    check_B()
    failed = [n for n, ok in RESULTS.items() if not ok]
    passed = len(RESULTS) - len(failed)
    if args.json:
        print(json.dumps({'total': len(RESULTS), 'passed': passed,
                          'failed': failed, 'success': not failed},
                         ensure_ascii=False, indent=2))
    else:
        for n, ok in RESULTS.items():
            print(('  PASS  ' if ok else '  FAIL  ') + n)
        print(f'\n  {passed}/{len(RESULTS)} checks passed')
        if failed:
            print('  FAILED: ' + ', '.join(failed))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
