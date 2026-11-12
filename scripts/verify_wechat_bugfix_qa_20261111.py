"""QA independent offline regression lock — WeChat bugfix batch 2026-11-11.

Verifies the 7 implemented fixes (1/2/3/4/5/6/8) behaviourally, not by grep:

  1  paste_image_and_optionally_send() clipboard moved next to Ctrl+V,
     finally/error mapping preserved
  2  open_contact() key-sequence groups de-duplicated
  3  _wechat_helper_authorized() rejects non-ASCII headers without TypeError
  4  _wechat_share_get_helper_health() 3xx not absorbed, allow_redirects=False,
     exception text not echoed
  5  _wechat_share_cleanup_old_images_daily() only marks date after success
  6  wechat_share.html helper_url input has no hardcoded default
  8  four exception-text desensitisation sites (app.py + 3 routes)

The REAL functions are extracted with the AST from app/app.py,
app/wechat_helper.py and app/routes/wechat_share.py, decorators/module imports
are stripped, and only those definitions run in synthetic namespaces. The
template is rendered with Jinja2 over an isolated string. Nothing imports the
WMS application, opens a product database, writes a product file, issues an
HTTP request, or touches the running service.

Run:  py -3.11 -B -X utf8 scripts/verify_wechat_bugfix_qa_20261111.py [--json]
rc=0 iff every check passes. Every check is deliberately mutation-sensitive:
reverting any product file to `git show HEAD:<file>` makes at least one check fail.
"""
from __future__ import annotations

import argparse
import ast
import copy
import datetime as _dt
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[1]
APP_PY = ROOT / 'app' / 'app.py'
HELPER_PY = ROOT / 'app' / 'wechat_helper.py'
ROUTES_PY = ROOT / 'app' / 'routes' / 'wechat_share.py'
TEMPLATE = ROOT / 'app' / 'templates' / 'wechat_share.html'

NO_PROXY = {'http': None, 'https': None}
HEALTH_URL = 'http://127.0.0.1:8765/health'
SEND_URL = 'http://127.0.0.1:8765/send'
SECRET = 'synthetic-secret-127.0.0.1:8765/send-should-never-leak'

RESULTS: dict[str, bool] = {}


def _check(name: str, fn):
    try:
        ok = bool(fn())
    except Exception as exc:  # a crashing check is a failed check, never a crash
        RESULTS[name] = False
        RESULTS.setdefault('__errors__', {})
        print(f'  [check error] {name}: {type(exc).__name__}: {exc}', file=sys.stderr)
        return
    RESULTS[name] = ok


_TEXT_CACHE: dict[Path, str] = {}
_TREE_CACHE: dict[Path, ast.Module] = {}


def _text(path: Path) -> str:
    if path not in _TEXT_CACHE:
        _TEXT_CACHE[path] = path.read_text(encoding='utf-8-sig')
    return _TEXT_CACHE[path]


def _tree(path: Path) -> ast.Module:
    if path not in _TREE_CACHE:
        _TREE_CACHE[path] = ast.parse(_text(path))
    return _TREE_CACHE[path]


class _StripImports(ast.NodeTransformer):
    """Remove every import statement inside extracted function bodies."""

    def visit_Import(self, node):
        return None

    def visit_ImportFrom(self, node):
        return None


def _extract(path: Path, names: set[str], glb: dict) -> dict:
    tree = _tree(path)
    nodes = [n for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
             and n.name in names]
    missing = names - {n.name for n in nodes}
    if missing:
        raise AssertionError(f'{path.name}: missing defs {sorted(missing)}')
    nodes = copy.deepcopy(nodes)
    for n in nodes:
        if hasattr(n, 'decorator_list'):
            n.decorator_list = []
        _StripImports().visit(n)
    env = {'__builtins__': __builtins__}
    env.update(glb)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 f'<qa-synth:{path.name}>', 'exec'), env)
    return env


def _extract_nested(path: Path, name: str, glb: dict) -> dict:
    tree = _tree(path)
    node = next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == name), None)
    if node is None:
        raise AssertionError(f'{path.name}: missing nested def {name}')
    node = copy.deepcopy(node)
    node.decorator_list = []
    _StripImports().visit(node)
    env = {'__builtins__': __builtins__}
    env.update(glb)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 f'<qa-synth:{path.name}:{name}>', 'exec'), env)
    return env


def _func_node(path: Path, name: str) -> ast.FunctionDef:
    tree = _tree(path)
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == name)


class _Json:
    def __init__(self, payload):
        self.payload = payload

    def get_json(self):
        return self.payload


class _Logger:
    def __init__(self):
        self.warnings = []
        self.exceptions = []

    def warning(self, *args, **kwargs):
        self.warnings.append(args)

    def exception(self, *args, **kwargs):
        self.exceptions.append(args)

    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


# ---------------------------------------------------------------------------
# Fix 3: _wechat_helper_authorized
# ---------------------------------------------------------------------------
def _auth_env():
    logger = _Logger()
    app = types.SimpleNamespace(config={'WECHAT_HELPER_TOKEN': 'tok-034'},
                                logger=logger)
    request = types.SimpleNamespace(headers={})
    return _extract(APP_PY, {'_wechat_helper_authorized'},
                    {'app': app, 'request': request, 'secrets': secrets}), app, request


def _auth(expected, provided) -> bool:
    env, app, request = _auth_env()
    app.config['WECHAT_HELPER_TOKEN'] = expected
    request.headers = {'X-Wechat-Helper-Token': provided}
    return env['_wechat_helper_authorized']()


def check_fix3():
    _check('fix3_auth_ascii_correct_token_still_passes',
           lambda: _auth('tok-034', 'tok-034') is True)
    _check('fix3_auth_ascii_wrong_token_rejected',
           lambda: _auth('tok-034', 'wrong') is False)
    _check('fix3_auth_missing_header_rejected',
           lambda: _auth('tok-034', '') is False)
    _check('fix3_auth_missing_expected_rejected',
           lambda: _auth('', 'tok-034') is False)
    _check('fix3_auth_nonascii_provided_returns_false_no_typeerror',
           lambda: _auth('tok-034', '令牌非ASCII') is False)
    _check('fix3_auth_nonascii_expected_returns_false_no_typeerror',
           lambda: _auth('令牌非ASCII', '令牌非ASCII') is False)
    _check('fix3_auth_nonascii_expected_ascii_provided_returns_false',
           lambda: _auth('令牌非ASCII', 'tok-034') is False)
    _check('fix3_auth_compare_digest_still_used',
           lambda: 'secrets.compare_digest' in ast.get_source_segment(
               _text(APP_PY), _func_node(APP_PY, '_wechat_helper_authorized')))
    _check('fix3_auth_isascii_guard_present',
           lambda: 'expected.isascii()' in ast.get_source_segment(
               _text(APP_PY), _func_node(APP_PY, '_wechat_helper_authorized'))
           and 'provided.isascii()' in ast.get_source_segment(
               _text(APP_PY), _func_node(APP_PY, '_wechat_helper_authorized')))


# ---------------------------------------------------------------------------
# Fix 4: _wechat_share_get_helper_health
# ---------------------------------------------------------------------------
class _Resp:
    def __init__(self, status_code=200, ok=True, payload=None, json_forbidden=False):
        self.status_code = status_code
        self.ok = ok
        self.payload = payload or {}
        self.json_forbidden = json_forbidden
        self.json_calls = 0

    def json(self):
        self.json_calls += 1
        if self.json_forbidden:
            raise AssertionError('3xx response JSON must NOT be consumed')
        return self.payload


class _FakeRequests:
    exceptions = types.SimpleNamespace(
        ConnectionError=type('ConnectionError', (Exception,), {}),
        Timeout=type('Timeout', (Exception,), {}),
    )

    def __init__(self, resp=None, exc=None):
        self.resp = resp
        self.exc = exc
        self.captured = {}

    def get(self, url, **kwargs):
        self.captured = {'url': url, **kwargs}
        if self.exc is not None:
            raise self.exc
        return self.resp

    def post(self, url, **kwargs):
        self.captured = {'url': url, **kwargs}
        if self.exc is not None:
            raise self.exc
        return self.resp


def _health_env(req, resp=None, exc=None):
    logger = _Logger()
    cache = {'url': '', 'at': None, 'health': None}
    fake_os = types.SimpleNamespace(environ={}, path=os.path)
    req.resp = resp
    req.exc = exc
    glb = {
        'os': fake_os,
        'datetime': _dt.datetime,
        'app': types.SimpleNamespace(logger=logger),
        'requests': req,
        'external_operations_paused': lambda: False,
        '_wechat_share_helper_health_url': lambda config: HEALTH_URL,
        '_WECHAT_SHARE_HEALTH_CACHE': cache,
        '_WECHAT_SHARE_HEALTH_CACHE_TTL_SECONDS': 30,
        '_LOOPBACK_NO_PROXY': NO_PROXY,
    }
    env = _extract(APP_PY, {'_wechat_share_get_helper_health'}, glb)
    return env, cache, logger, req


def _health(req, resp=None, exc=None, config_url=SEND_URL):
    env, cache, logger, req = _health_env(req, resp, exc)
    config = types.SimpleNamespace(helper_url=config_url)
    return env['_wechat_share_get_helper_health'](config), cache, logger, req, resp


def check_fix4():
    # 302: no JSON absorbed, online stays False, message is the redirect hint.
    def t_302():
        resp = _Resp(status_code=302, ok=False,
                     payload={'status': 'ok', 'wechat_window_found': True},
                     json_forbidden=True)
        h, cache, logger, req, _ = _health(_FakeRequests(), resp=resp)
        return (h['online'] is False
                and h['message'] == '微信发送助手返回重定向，请核对本机助手地址'
                and resp.json_calls == 0
                and h.get('wechat_window_found') is False
                and h.get('wms_base_url') == '')
    _check('fix4_health_302_not_absorbed_online_false', t_302)

    def t_302_kwargs():
        h, cache, logger, req, _ = _health(
            _FakeRequests(), resp=_Resp(status_code=302, ok=False))
        return (req.captured.get('allow_redirects') is False
                and req.captured.get('proxies') == NO_PROXY
                and req.captured.get('timeout') == 1.5
                and req.captured.get('url') == HEALTH_URL)
    _check('fix4_health_get_passes_allow_redirects_false_and_no_proxy', t_302_kwargs)

    def t_500():
        h, *_ = _health(_FakeRequests(), resp=_Resp(status_code=500, ok=False))
        return h['online'] is False and h['message'] == '助手返回 HTTP 500'
    _check('fix4_health_non_ok_http_message_unchanged', t_500)

    def t_200():
        payload = {'status': 'ok', 'wechat_window_found': True,
                   'poll_enabled': False, 'wms_base_url': 'http://127.0.0.1:8080'}
        h, *_ = _health(_FakeRequests(), resp=_Resp(200, True, payload))
        return (h['online'] is True and h['wechat_window_found'] is True
                and h['message'] == '助手在线')
    _check('fix4_health_200_ok_path_unchanged', t_200)

    def t_exc():
        h, cache, logger, req, _ = _health(
            _FakeRequests(), exc=RuntimeError(SECRET))
        logged = ' '.join(str(a) for call in logger.warnings for a in call)
        return (h['online'] is False
                and h['message'] == '助手不可用，请检查本机微信发送助手状态'
                and SECRET not in h['message']
                and SECRET not in logged
                and any('RuntimeError' in str(a) for call in logger.warnings for a in call))
    _check('fix4_health_exception_text_not_echoed_logs_type_only', t_exc)

    src = ast.get_source_segment(_text(APP_PY),
                                 _func_node(APP_PY, '_wechat_share_get_helper_health'))
    _check('fix4_health_3xx_branch_present',
           lambda: '300 <= response.status_code < 400' in src)
    _check('fix4_health_no_fstring_exc_in_source',
           lambda: not any(isinstance(n, ast.JoinedStr)
                           and any(isinstance(v, ast.FormattedValue)
                                   and isinstance(v.value, ast.Name)
                                   and v.value.id == 'exc'
                                   for v in n.values)
                           for n in ast.walk(_func_node(APP_PY, '_wechat_share_get_helper_health'))))


# ---------------------------------------------------------------------------
# Fix 5: _wechat_share_cleanup_old_images_daily
# ---------------------------------------------------------------------------
def _cleanup_env(impl, paused=False):
    logger = _Logger()
    state = {'last_run_date': None}
    calls = []

    def cleanup():
        calls.append(1)
        return impl()

    glb = {
        'date': _dt.date,
        'app': types.SimpleNamespace(logger=logger),
        '_WECHAT_SHARE_CLEANUP_STATE': state,
        '_wechat_share_cleanup_old_images': cleanup,
        'external_operations_paused': lambda: paused,
    }
    env = _extract(APP_PY, {'_wechat_share_cleanup_old_images_daily'}, glb)
    return env, state, calls, logger


def check_fix5():
    def t_success_marks_and_idempotent():
        env, state, calls, _ = _cleanup_env(lambda: 3)
        first = env['_wechat_share_cleanup_old_images_daily']()
        second = env['_wechat_share_cleanup_old_images_daily']()
        return (first == 3 and second == 0 and len(calls) == 1
                and state['last_run_date'] == _dt.date.today())
    _check('fix5_cleanup_success_marks_date_once_per_day', t_success_marks_and_idempotent)

    def t_failure_not_marked_retry_next_tick():
        boom = [True]

        def impl():
            if boom[0]:
                boom[0] = False
                raise RuntimeError('synthetic cleanup failure')
            return 2

        env, state, calls, logger = _cleanup_env(impl)
        first = env['_wechat_share_cleanup_old_images_daily']()
        marked_after_failure = state['last_run_date']
        second = env['_wechat_share_cleanup_old_images_daily']()
        return (first == 0 and marked_after_failure is None
                and second == 2 and len(calls) == 2
                and state['last_run_date'] == _dt.date.today()
                and len(logger.exceptions) == 1)
    _check('fix5_cleanup_failure_day_not_marked_and_retried', t_failure_not_marked_retry_next_tick)

    def t_paused():
        env, state, calls, _ = _cleanup_env(lambda: 9, paused=True)
        return (env['_wechat_share_cleanup_old_images_daily']() == 0
                and len(calls) == 0 and state['last_run_date'] is None)
    _check('fix5_cleanup_paused_short_circuit_unchanged', t_paused)

    def t_mark_after_try():
        fn = _func_node(APP_PY, '_wechat_share_cleanup_old_images_daily')
        assign_lines = [n.lineno for n in ast.walk(fn)
                        if isinstance(n, ast.Assign)
                        and isinstance(n.targets[0], ast.Subscript)
                        and isinstance(n.targets[0].slice, ast.Constant)
                        and n.targets[0].slice.value == 'last_run_date']
        handler_lines = [n.lineno for n in ast.walk(fn) if isinstance(n, ast.ExceptHandler)]
        return bool(assign_lines and handler_lines
                    and min(assign_lines) > min(handler_lines))
    _check('fix5_cleanup_mark_assignment_is_after_except_handler', t_mark_after_try)


# ---------------------------------------------------------------------------
# Fix 6: template helper_url input (real Jinja render)
# ---------------------------------------------------------------------------
def check_fix6():
    try:
        from jinja2 import Environment
    except ImportError:
        RESULTS['fix6_template_jinja2_available'] = False
        return
    text = _text(TEMPLATE)
    _check('fix6_template_full_jinja_parses',
           lambda: bool(Environment().parse(text)) or True)
    tag = re.search(r'<input[^>]*name="helper_url"[^>]*>', text)
    _check('fix6_template_helper_url_input_found', lambda: tag is not None)
    if tag is None:
        return
    tag_html = tag.group(0)

    def value_of(rendered):
        m = re.search(r'value="([^"]*)"', rendered)
        return m.group(1) if m else None

    def render(helper_url):
        return Environment().from_string(tag_html).render(
            share_config=types.SimpleNamespace(helper_url=helper_url))

    _check('fix6_template_unconfigured_value_is_empty',
           lambda: value_of(render(None)) == '')
    _check('fix6_template_blank_value_is_empty',
           lambda: value_of(render('')) == '')
    _check('fix6_template_configured_value_preserved',
           lambda: value_of(render('http://127.0.0.1:9/send')) == 'http://127.0.0.1:9/send')
    _check('fix6_template_placeholder_preserved',
           lambda: 'placeholder="http://127.0.0.1:8765/send"' in tag_html)
    _check('fix6_template_no_hardcoded_default_in_value_expr',
           lambda: '127.0.0.1:8765/send' not in
           re.search(r'value="([^"]*)"', tag_html).group(1))


# ---------------------------------------------------------------------------
# Fix 1 + 2: wechat_helper.py paste order / open_contact groups
# ---------------------------------------------------------------------------
def _paste_env(clipboard_exc=None, hotkey_exc=None, auto_send=False):
    calls = []

    def activate_wechat():
        calls.append('activate')
        return 1, 'normal'

    def ensure(hwnd):
        calls.append('ensure_foreground')

    def open_contact(name, hwnd=None):
        calls.append('open_contact')

    def set_clipboard(data):
        calls.append('set_clipboard_dib')
        if clipboard_exc:
            raise clipboard_exc

    def hotkey(*args):
        calls.append('hotkey')
        if hotkey_exc:
            raise hotkey_exc

    def press_key(key):
        calls.append('press_key')

    def restore(hwnd, state):
        calls.append('restore')

    glb = {
        'activate_wechat': activate_wechat,
        '_ensure_foreground': ensure,
        'open_contact': open_contact,
        'set_clipboard_dib': set_clipboard,
        'hotkey': hotkey,
        'press_key': press_key,
        'restore_window_state': restore,
        'time': types.SimpleNamespace(sleep=lambda _s: None),
        'VK_CONTROL': 17, 'VK_V': 86, 'VK_RETURN': 13,
    }
    env = _extract(HELPER_PY,
                   {'_SendError', 'paste_image_and_optionally_send'}, glb)
    return env, calls


def check_fix1():
    def t_order():
        env, calls = _paste_env()
        result = env['paste_image_and_optionally_send'](b'png', 'receiver', False)
        ensure_idx = [i for i, c in enumerate(calls) if c == 'ensure_foreground']
        clip_idx = calls.index('set_clipboard_dib')
        hotkey_idx = calls.index('hotkey')
        return (result == 'ready'
                and calls[0] == 'activate'
                and len(ensure_idx) >= 2
                and clip_idx > ensure_idx[1]
                and clip_idx == hotkey_idx - 1
                and calls[-1] == 'restore')
    _check('fix1_paste_clipboard_after_2nd_foreground_immediately_before_ctrl_v', t_order)

    def t_no_receiver_first():
        env, calls = _paste_env()
        try:
            env['paste_image_and_optionally_send'](b'png', '  ', False)
            return False
        except Exception as exc:
            return (getattr(exc, 'code', None) == 'no_receiver' and calls == [])
    _check('fix1_paste_no_receiver_check_precedes_all_ui_side_effects', t_no_receiver_first)

    def t_clipboard_failure():
        env, calls = _paste_env(clipboard_exc=RuntimeError('synthetic clipboard denied'))
        try:
            env['paste_image_and_optionally_send'](b'png', 'receiver', False)
            return False
        except Exception as exc:
            return (getattr(exc, 'code', None) == 'clipboard_failed'
                    and '写入剪贴板失败' in str(exc)
                    and 'hotkey' not in calls
                    and calls[-1] == 'restore')
    _check('fix1_paste_clipboard_failure_maps_code_and_finally_restores', t_clipboard_failure)

    def t_paste_failure():
        env, calls = _paste_env(hotkey_exc=RuntimeError('synthetic partial key'))
        try:
            env['paste_image_and_optionally_send'](b'png', 'receiver', False)
            return False
        except Exception as exc:
            return getattr(exc, 'code', None) == 'paste_failed' and calls[-1] == 'restore'
    _check('fix1_paste_hotkey_failure_maps_paste_failed_and_restores', t_paste_failure)

    def t_auto_send():
        env, calls = _paste_env(auto_send=True)
        result = env['paste_image_and_optionally_send'](b'png', 'receiver', True)
        return (result == 'sent' and 'press_key' in calls
                and calls[-1] == 'restore')
    _check('fix1_paste_auto_send_path_preserved', t_auto_send)

    src = ast.get_source_segment(_text(HELPER_PY),
                                 _func_node(HELPER_PY, 'paste_image_and_optionally_send'))
    _check('fix1_paste_finally_restore_window_state_unchanged',
           lambda: 'finally:' in src and 'restore_window_state(hwnd, prior_state)' in src)


def check_fix2():
    def t_groups():
        fn = _func_node(HELPER_PY, 'open_contact')
        groups = None
        for n in ast.walk(fn):
            if isinstance(n, ast.For) and isinstance(n.iter, ast.Tuple):
                if all(isinstance(e, ast.Tuple) for e in n.iter.elts):
                    groups = [ast.dump(e) for e in n.iter.elts]
                    break
        return groups is not None and len(groups) == 3 and len(set(groups)) == 3
    _check('fix2_open_contact_three_unique_key_groups', t_groups)


# ---------------------------------------------------------------------------
# Fix 8: four exception-text desensitisation sites
# ---------------------------------------------------------------------------
def _send_image_generic_exception():
    """Force the generic `except Exception` branch of _wechat_share_send_image."""
    logger = _Logger()
    req = _FakeRequests(exc=RuntimeError(SECRET))
    fake_os = types.SimpleNamespace(environ={}, path=os.path)
    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    try:
        tmp.write(b'\x89PNG\r\n\x1a\nqa-synthetic')
        tmp.close()
        config = types.SimpleNamespace(
            helper_url=SEND_URL, sender_name='s', sender_wechat_id='',
            receiver_name='r', receiver_wechat_id='', receiver_search_key='r',
            receiver_type='person', auto_send=False)
        glb = {
            'os': fake_os,
            'urlparse': __import__('urllib.parse', fromlist=['urlparse']).urlparse,
            'requests': req,
            'app': types.SimpleNamespace(
                config={'WECHAT_HELPER_TOKEN': 'synthetic-token'}, logger=logger),
            '_wechat_share_helper_url_allowed': lambda url: True,
            '_LOOPBACK_NO_PROXY': NO_PROXY,
        }
        env = _extract(APP_PY, {'_wechat_share_send_image'}, glb)
        return env['_wechat_share_send_image'](config, tmp.name), logger
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def check_fix8():
    def t_send_image():
        result, logger = _send_image_generic_exception()
        logged = ' '.join(str(a) for call in logger.warnings for a in call)
        return (result[0] == 'failed' and result[1] == 'send_error'
                and result[2] == '微信发送助手调用失败，请检查本机助手状态与配置'
                and SECRET not in result[2] and SECRET not in logged
                and any('RuntimeError' in str(a) for call in logger.warnings for a in call))
    _check('fix8_send_image_exception_fixed_message_no_echo', t_send_image)

    # Route-level generic exception handlers, executed from real AST-extracted views.
    def t_run_now():
        calls = []
        env = _extract_nested(ROUTES_PY, 'run_wechat_share_now', {
            'jsonify': lambda p: _Json(p),
            'db': types.SimpleNamespace(
                session=types.SimpleNamespace(rollback=lambda: calls.append('rollback'))),
            'log_operation': lambda *a, **k: None,
            'request': types.SimpleNamespace(form={}),
            'current_app': types.SimpleNamespace(logger=_Logger()),
            'DispatchUnavailable': type('DispatchUnavailable', (Exception,), {}),
            'run_wechat_share_for_today': lambda **kw: (_ for _ in ()).throw(
                RuntimeError(SECRET)),
        })
        payload, status = env['run_wechat_share_now']()
        return (status == 500
                and payload.get_json()['msg'] == '执行失败，请稍后重试或联系管理员'
                and SECRET not in payload.get_json()['msg']
                and 'rollback' in calls)
    _check('fix8_run_now_exception_fixed_message_no_echo', t_run_now)

    def t_clear():
        calls = []
        env = _extract_nested(ROUTES_PY, 'clear_wechat_share_logs', {
            'jsonify': lambda p: _Json(p),
            'db': types.SimpleNamespace(
                session=types.SimpleNamespace(rollback=lambda: calls.append('rollback'))),
            'log_operation': lambda *a, **k: None,
            'request': types.SimpleNamespace(form={'status': 'failed'}),
            'current_app': types.SimpleNamespace(logger=_Logger()),
            'current_user': types.SimpleNamespace(id=1),
            '_wechat_share_log_status_label': lambda s: s,
            'cleanup_share_history': lambda *a, **k: (_ for _ in ()).throw(
                RuntimeError(SECRET)),
        })
        payload, status = env['clear_wechat_share_logs']()
        return (status == 500
                and payload.get_json()['msg'] == '清理失败，请稍后重试或联系管理员'
                and SECRET not in payload.get_json()['msg']
                and 'rollback' in calls)
    _check('fix8_clear_logs_exception_fixed_message_no_echo', t_clear)

    def t_resend():
        # Reuse the existing, purpose-built synthetic namespace of the
        # resend_config_guard regression lock (which already passed 50/50).
        spec = importlib.util.spec_from_file_location(
            'qa_resend_guard', ROOT / 'scripts' / 'verify_wechat_resend_config_guard.py')
        guard = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(guard)
        found = guard._find_route(ROUTES_PY)
        code = guard._compile_route(found, ROUTES_PY)
        with tempfile.TemporaryDirectory(prefix='wms-qa-resend-') as tmp:
            image_path = os.path.join(tmp, 'synth.png')
            Path(image_path).write_bytes(b'\x89PNG\r\n\x1a\nsynthetic')
            cfg = guard._config()
            _ns, calls, _captured, route = guard._env(
                code, tmp, image_path, cfg,
                execute_impl=lambda *a, **k: (_ for _ in ()).throw(RuntimeError(SECRET)))
            payload, status = guard._call(route)
        return (status == 500
                and payload.get('msg') == '重发失败，请稍后重试或联系管理员'
                and '执行失败' not in payload.get('msg', '')
                and SECRET not in payload.get('msg', '')
                and 'db.session.rollback' in calls)
    _check('fix8_resend_exception_fixed_message_no_echo_and_no_execute_failure', t_resend)

    # Static: no f-string interpolating exc in any of the four handlers.
    def t_no_exc_fstring():
        for path, name in ((APP_PY, '_wechat_share_send_image'),
                           (ROUTES_PY, 'run_wechat_share_now'),
                           (ROUTES_PY, 'resend_wechat_share_log'),
                           (ROUTES_PY, 'clear_wechat_share_logs')):
            fn = _func_node(path, name)
            for n in ast.walk(fn):
                if isinstance(n, ast.JoinedStr):
                    for v in n.values:
                        if (isinstance(v, ast.FormattedValue)
                                and isinstance(v.value, ast.Name)
                                and v.value.id == 'exc'):
                            return False
        return True
    _check('fix8_no_fstring_interpolates_exc_in_four_handlers', t_no_exc_fstring)

    route_text = _text(ROUTES_PY)
    _check('fix8_three_logger_exception_calls_preserved',
           lambda: route_text.count('current_app.logger.exception(') >= 3)
    _check('fix8_exact_fixed_messages_present',
           lambda: all(s in _text(APP_PY) + route_text for s in (
               '微信发送助手调用失败，请检查本机助手状态与配置',
               '执行失败，请稍后重试或联系管理员',
               '重发失败，请稍后重试或联系管理员',
               '清理失败，请稍后重试或联系管理员')))


# ---------------------------------------------------------------------------
# Fix 7 (deliberately abandoned): line 379 must keep the original Qt heuristic
# ---------------------------------------------------------------------------
# CI 的工作区 /opt/wms 是 checkout 产物、不带 git 历史，不能用
# `git show HEAD:app/wechat_helper.py` 与工作区比对（本机有 .git 能过，CI 必红）。
# 改为直接锁定期望文本，断言强度不变：既要求整行逐字相同，也要求过宽匹配
# 仍在、且未加进程名条件。
EXPECTED_QT_LINE = ('        has_wechat_class = "WeChat" in class_text or "Weixin" '
                    'in class_text or class_text.startswith("Qt")')


def check_fix7_abandoned():
    def t():
        work_line = _text(HELPER_PY).splitlines()[378]
        return (work_line == EXPECTED_QT_LINE
                and 'class_text.startswith("Qt")' in work_line
                and 'and is_wechat_process' not in work_line)
    _check('fix7_abandoned_line379_unchanged_qt_check_kept', t)


def run_checks() -> dict[str, bool]:
    """Run every check fresh and return a copy of the results (CI-wrapper API)."""
    RESULTS.clear()
    check_fix1()
    check_fix2()
    check_fix3()
    check_fix4()
    check_fix5()
    check_fix6()
    check_fix7_abandoned()
    check_fix8()
    RESULTS.pop('__errors__', None)
    return dict(RESULTS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    RESULTS.clear()
    run_checks()
    failed = [name for name, ok in RESULTS.items() if not ok]
    passed = len(RESULTS) - len(failed)
    if args.json:
        print(json.dumps({'total': len(RESULTS), 'passed': passed,
                          'failed': failed, 'success': not failed},
                         ensure_ascii=False, indent=2))
    else:
        for name, ok in RESULTS.items():
            print(('  PASS  ' if ok else '  FAIL  ') + name)
        print(f'\n  {passed}/{len(RESULTS)} checks passed')
        if failed:
            print('  FAILED: ' + ', '.join(failed))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
