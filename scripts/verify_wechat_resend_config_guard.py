"""Offline regression lock for BUG-2026-11-11-002.

The real ``resend_wechat_share_log`` route is extracted from
``app/routes/wechat_share.py`` with the AST, all module imports and decorators
are stripped, and only that single function is executed in a synthetic
namespace.  Nothing imports the WMS application, opens a database, writes a
product file or issues an HTTP request.  The temporary PNG lives in the OS
temp directory and is removed on exit.
"""
from __future__ import annotations

import argparse
import ast
import copy
import datetime as _dt
import json
import os
from pathlib import Path
import tempfile
import types
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / 'app' / 'routes' / 'wechat_share.py'
ROUTE_NAME = 'resend_wechat_share_log'
FORBIDDEN = '_wechat_share_default_config'


class _StripModuleImports(ast.NodeTransformer):
    """Remove ``from app/flask/services... import`` only.

    ``import types as _types`` is stdlib, so it is deliberately kept.
    """

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        return None


class _Json:
    def __init__(self, payload: dict):
        self.payload = payload

    def get_json(self) -> dict:
        return self.payload


class DispatchUnavailable(Exception):
    pass


def _find_route(source: Path) -> ast.FunctionDef:
    tree = ast.parse(source.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == ROUTE_NAME:
            return node
    raise AssertionError('缺少待验证的路由函数：' + ROUTE_NAME)


def _compile_route(found: ast.FunctionDef, source: Path):
    fn = copy.deepcopy(found)
    fn.decorator_list = []
    _StripModuleImports().visit(fn)
    ast.fix_missing_locations(fn)
    module = ast.Module(body=[fn], type_ignores=[])
    return compile(module, str(source), 'exec')


def _config(oid: int = 9) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        id=oid, helper_url='http://127.0.0.1:8765/send', sender_name='sender',
        sender_wechat_id='', receiver_name='receiver', receiver_wechat_id='',
        receiver_search_key='receiver', receiver_type='person', auto_send=False,
    )


def _env(code, image_dir: str, image_path: str, config, module_key='in_order',
         execute_impl=None, log_overrides=None):
    """Build one isolated synthetic namespace; returns (namespace, calls, route)."""
    calls: list = []
    captured: dict = {}
    log = types.SimpleNamespace(
        id=3, config=config, module_key=module_key, image_path=image_path,
        image_size=15, order_no='RK-SYNTH-1', order_id=1,
        share_date=_dt.date.today(), receiver_name='', receiver_wechat_id='',
    )
    for key, value in (log_overrides or {}).items():
        setattr(log, key, value)

    class _Query:
        def get_or_404(self, log_id):
            captured['log_id'] = log_id
            return log

    class _Session:
        def add(self, *args):
            calls.append('db.session.add')

        def commit(self):
            calls.append('db.session.commit')

        def rollback(self):
            calls.append('db.session.rollback')

    def default_config():
        calls.append('default_config')
        return None  # old code then fails on config.id, but must not crash the verifier

    def execute_share(*args, **kwargs):
        calls.append('execute_share')
        captured['args'] = args
        captured['kwargs'] = kwargs
        if execute_impl is not None:
            return execute_impl(*args, **kwargs)
        return {'status': 'sent', 'message': 'ok', 'log_id': 7}

    def send_image(send_config, path):
        calls.append('send_image')
        captured['send_config'] = send_config
        return 'sent', 'ok', '已发送'

    def send_wecom(*args, **kwargs):
        calls.append('send_wecom')
        return 'sent', 'ok', '已发送'

    def log_operation(*args, **kwargs):
        calls.append('log_operation')

    ns: dict = {
        'WechatShareLog': types.SimpleNamespace(query=_Query()),
        '_wechat_share_output_dir': lambda: image_dir,
        '_wechat_share_send_image': send_image,
        '_wechat_share_send_wecom': send_wecom,
        '_wechat_share_wecom_webhook': lambda: '',
        FORBIDDEN: default_config,
        'datetime': _dt,
        'db': types.SimpleNamespace(session=_Session()),
        'jsonify': lambda payload: _Json(payload),
        'log_operation': log_operation,
        'os': os,
        'request': types.SimpleNamespace(form={}, args={}),
        'current_app': types.SimpleNamespace(
            logger=types.SimpleNamespace(exception=lambda *a, **k: None)),
        'DispatchUnavailable': DispatchUnavailable,
        'execute_share': execute_share,
    }
    exec(code, ns)
    return ns, calls, captured, ns[ROUTE_NAME]


def _call(route, log_id=3):
    result = route(log_id)
    if isinstance(result, tuple):
        return result[0].get_json(), result[1]
    return result.get_json(), 200


def _static_checks(found: ast.FunctionDef, source: Path) -> dict:
    results: dict = {}
    names = {n.id for n in ast.walk(found) if isinstance(n, ast.Name)}
    aliases = {a.name for n in ast.walk(found) if isinstance(n, (ast.Import, ast.ImportFrom))
               for a in n.names}
    results['route_never_names_default_config'] = FORBIDDEN not in names | aliases

    assigns = [n for n in ast.walk(found) if isinstance(n, ast.Assign)]
    results['config_read_directly_from_log'] = any(
        isinstance(a.value, ast.Attribute) and a.value.attr == 'config'
        and isinstance(a.value.value, ast.Name) and a.value.value.id == 'log'
        and any(isinstance(t, ast.Name) and t.id == 'config' for t in a.targets)
        for a in assigns)
    results['config_never_falls_back_with_or'] = not any(
        isinstance(a.value, ast.BoolOp) and isinstance(a.value.op, ast.Or)
        and any(isinstance(t, ast.Name) and t.id == 'config' for t in a.targets)
        for a in assigns)

    guards = [n for n in ast.walk(found) if isinstance(n, ast.If)
              and isinstance(n.test, ast.Compare)
              and isinstance(n.test.left, ast.Name) and n.test.left.id == 'config'
              and any(isinstance(o, ast.Is) for o in n.test.ops)
              and any(isinstance(c, ast.Constant) and c.value is None
                      for c in n.test.comparators)]
    results['explicit_none_guard_present'] = len(guards) == 1
    guard = guards[0] if guards else None
    execute_calls = [n for n in ast.walk(found) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == 'execute_share']
    results['guard_precedes_any_send'] = bool(
        guard is not None and execute_calls
        and guard.lineno < min(c.lineno for c in execute_calls))

    def _return_payload(node):
        for sub in ast.walk(node):
            if isinstance(sub, ast.Return) and sub.value is not None:
                call = sub.value.func if isinstance(sub.value, ast.Call) else None
                target = sub.value.elts[0] if isinstance(sub.value, ast.Tuple) else sub.value
                if isinstance(target, ast.Call):
                    call = target
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) \
                        and call.func.id == 'jsonify' and call.args \
                        and isinstance(call.args[0], ast.Dict):
                    keys = [k.value for k in call.args[0].keys if isinstance(k, ast.Constant)]
                    vals = [v.value for v in call.args[0].values if isinstance(v, ast.Constant)]
                    payload = dict(zip(keys, vals))
                    code = sub.value.elts[1].value if isinstance(sub.value, ast.Tuple) \
                        and isinstance(sub.value.elts[1], ast.Constant) else None
                    return payload, code
        return {}, None

    guard_payload, guard_code = _return_payload(guard) if guard is not None else ({}, None)
    results['guard_returns_error_status'] = guard_payload.get('status') == 'error'
    results['guard_returns_409'] = guard_code == 409
    results['guard_msg_explains_missing_config'] = (
        '配置' in str(guard_payload.get('msg', ''))
        and '停止重发' in str(guard_payload.get('msg', '')))

    source_text = source.read_text(encoding='utf-8')
    results['module_key_check_preserved'] = "if log.module_key != 'in_order':" in source_text
    results['image_path_check_preserved'] = 'if not log.image_path:' in source_text
    results['image_exists_check_preserved'] = 'os.path.exists(image_path)' in source_text
    results['frozen_receiver_preserved'] = '_types.SimpleNamespace(' in source_text \
        and 'used_frozen_receiver' in source_text
    results['force_true_preserved'] = 'force=True' in source_text
    results['config_id_still_from_log_config'] = "'config_id': config.id" in source_text
    results['dispatch_unavailable_503_preserved'] = 'except DispatchUnavailable as exc:' in source_text
    results['generic_exception_500_preserved'] = 'except Exception as exc:' in source_text
    results['log_operation_preserved'] = "log_operation('重发微信分享'" in source_text
    results['other_routes_keep_default_config'] = (
        source_text.count(FORBIDDEN) >= 2
        and 'config = _wechat_share_default_config()' in source_text)
    results['route_decorators_preserved'] = bool(found.decorator_list) and any(
        isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
        and d.func.attr == 'route' for d in found.decorator_list)

    # R6: the other consumers of the current-config helper are untouched by this batch.
    app_py = (ROOT / 'app' / 'app.py').read_text(encoding='utf-8')
    print_alerts = (ROOT / 'app' / 'routes' / 'print_alerts.py').read_text(encoding='utf-8')
    results['app_py_default_config_untouched'] = 'config = config or _wechat_share_default_config()' in app_py
    results['print_alert_default_config_untouched'] = 'config = _wechat_share_default_config()' in print_alerts
    return results


def run_checks(source: Path = DEFAULT_SOURCE) -> dict:
    found = _find_route(source)
    code = _compile_route(found, source)
    results = _static_checks(found, source)

    with tempfile.TemporaryDirectory(prefix='wms-resend-guard-') as tmp:
        image_path = os.path.join(tmp, 'synth.png')
        Path(image_path).write_bytes(b'\x89PNG\r\n\x1a\nsynthetic')

        # ---- primary regression: config missing must fail closed ----
        _ns, calls, captured, route = _env(code, tmp, image_path, None)
        payload, status = _call(route)
        results['missing_config_status_409'] = status == 409
        results['missing_config_error_envelope'] = payload.get('status') == 'error'
        results['missing_config_msg_actionable'] = (
            '配置' in payload.get('msg', '') and '重新生成' in payload.get('msg', ''))
        results['missing_config_never_creates_default'] = 'default_config' not in calls
        results['missing_config_never_dispatches'] = 'execute_share' not in calls
        results['missing_config_never_sends'] = not any(
            c in calls for c in ('send_image', 'send_wecom'))
        results['missing_config_never_writes_db'] = not any(
            c in calls for c in ('db.session.add', 'db.session.commit'))
        results['missing_config_never_logs_operation'] = 'log_operation' not in calls

        # ---- normal resend path is byte-for-byte equivalent in behaviour ----
        cfg = _config()
        _ns, calls, captured, route = _env(code, tmp, image_path, cfg)
        payload, status = _call(route)
        results['valid_config_success_200'] = status == 200 and payload.get('status') == 'success'
        results['valid_config_keeps_log_status'] = payload.get('log_status') == 'sent'
        results['valid_config_keeps_log_id'] = payload.get('log_id') == 7
        results['valid_config_never_creates_default'] = 'default_config' not in calls
        results['valid_config_dispatches_once'] = calls.count('execute_share') == 1
        args = captured.get('args', ())
        results['valid_config_uses_log_config_id'] = bool(
            len(args) >= 2 and args[1].get('config_id') == 9)
        results['valid_config_keeps_manual_resend_trigger'] = bool(
            len(args) >= 2 and args[1].get('trigger_type') == 'manual_resend')
        results['valid_config_force_remains_true'] = captured.get('kwargs', {}).get('force') is True
        results['valid_config_logged'] = 'log_operation' in calls

        # frozen receiver still wins over the current config (BUG-2026-08-11-014)
        def _delivering_execute(*args, **kwargs):
            captured['deliver'] = args[3]
            args[3](None)
            return {'status': 'sent', 'message': 'ok', 'log_id': 7}
        _ns, calls, captured, route = _env(
            code, tmp, image_path, cfg, execute_impl=_delivering_execute,
            log_overrides={'receiver_name': '历史张三', 'receiver_wechat_id': ''})
        payload, status = _call(route)
        results['frozen_receiver_still_used'] = (
            captured.get('send_config') is not None
            and captured['send_config'].receiver_name == '历史张三')
        results['frozen_receiver_still_sends_image'] = 'send_image' in calls
        results['frozen_receiver_still_success'] = status == 200 and payload.get('status') == 'success'

        # ---- all pre-existing short-circuit branches stay unchanged ----
        _ns, calls, captured, route = _env(code, tmp, image_path, cfg, module_key='print_alert')
        payload, status = _call(route)
        results['non_in_order_still_400'] = status == 400 and '入库单' in payload.get('msg', '')
        results['non_in_order_never_dispatches'] = 'execute_share' not in calls

        _ns, calls, captured, route = _env(code, tmp, image_path, cfg,
                                            log_overrides={'image_path': None})
        payload, status = _call(route)
        results['no_image_still_400'] = status == 400 and '图片' in payload.get('msg', '')

        _ns, calls, captured, route = _env(code, tmp, image_path, cfg,
                                            log_overrides={'image_path': os.path.join(tmp, 'gone.png')})
        payload, status = _call(route)
        results['missing_image_still_404'] = status == 404 and '重新生成' in payload.get('msg', '')
        results['missing_image_never_dispatches'] = 'execute_share' not in calls

        def _unavailable(*args, **kwargs):
            calls.append('execute_share')
            raise DispatchUnavailable('领取失败')
        _ns, calls, captured, route = _env(code, tmp, image_path, cfg, execute_impl=_unavailable)
        payload, status = _call(route)
        results['dispatch_unavailable_still_503'] = status == 503 and payload.get('msg') == '领取失败'
        results['dispatch_unavailable_still_rolls_back'] = 'db.session.rollback' in calls

        def _boom(*args, **kwargs):
            calls.append('execute_share')
            raise RuntimeError('synthetic fault')
        _ns, calls, captured, route = _env(code, tmp, image_path, cfg, execute_impl=_boom)
        payload, status = _call(route)
        results['generic_exception_still_500'] = status == 500 and '执行失败' not in payload.get('msg', '')
        results['generic_exception_still_rolls_back'] = 'db.session.rollback' in calls

    return results


def main() -> int:
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
            print(('  PASS  ' if ok else '  FAIL  ') + name)
        print('\n  %d/%d checks passed' % (len(results) - len(failed), len(results)))
    return 0 if not failed else 1


if __name__ == '__main__':
    raise SystemExit(main())
