"""BUG-2026-11-11-004 offline regression lock.

A share log left in ``queued_v2`` (queued for the local helper, never claimed)
is a dead end: ``_claim`` refuses even a forced resend while an active log
exists, the page disables the resend button, and history cleanup protects the
state.  ``claim_log`` is the only writer that moves ``queued_v2`` -> ``sending``,
so an unclaimed record is provably unsent and can safely be released.

This lock executes the REAL ``release_queued_share``, ``execute_share`` and
``resend_wechat_share_log`` functions extracted by AST, over a synthetic
``sqlite:///:memory:`` database / synthetic namespace.  It never imports the
WMS application, opens a product database, writes a product file, issues an
HTTP request or touches the running service.
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
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
RELEASE_SRC = ROOT / 'app' / 'services' / 'wechat_share_release.py'
DISPATCH_SRC = ROOT / 'app' / 'services' / 'wechat_share_dispatch.py'
CLEANUP_SRC = ROOT / 'app' / 'services' / 'wechat_share_cleanup.py'
ROUTE_SRC = ROOT / 'app' / 'routes' / 'wechat_share.py'
TEMPLATE_SRC = ROOT / 'app' / 'templates' / 'wechat_share.html'
APP_PY = ROOT / 'app' / 'app.py'
DOC = ROOT / 'INVENTORY_TRUTH.md'
PAUSE_SRC = ROOT / 'app' / 'services' / 'runtime_status.py'
ROUTE_NAME = 'resend_wechat_share_log'

UNCERTAIN_MESSAGE = '发送结果待确认；普通执行不会再次发送。请先核对接收端，确需重发时使用强制重发（可能重复）。'


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8-sig')
    except OSError:
        return ''


def _tree(path: Path) -> ast.Module:
    return ast.parse(_text(path) or ' ')


def _func(tree: ast.Module, name: str):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _safe_codes(tree: ast.Module) -> frozenset:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'SAFE_FAILURE_CODES' for t in node.targets):
            return frozenset(ast.literal_eval(node.value.args[0]))
    return frozenset()


def _check(results: dict, name: str, predicate) -> None:
    try:
        results[name] = bool(predicate())
    except Exception:
        results[name] = False


# --------------------------------------------------------------------------
# Static structure of the four product files (and the contracts they must not
# disturb).
# --------------------------------------------------------------------------
def _static_checks() -> dict:
    r: dict = {}
    rel_text = _text(RELEASE_SRC)
    rel_tree = _tree(RELEASE_SRC)
    rel_fn = _func(rel_tree, 'release_queued_share')
    rel_ast = ast.unparse(rel_fn) if rel_fn else ''

    _check(r, 'release_module_exists', lambda: bool(rel_text))
    _check(r, 'release_function_exists', lambda: rel_fn is not None)
    _check(r, 'release_docstring_explains_unclaimed_semantics',
           lambda: 'queued_v2' in (ast.get_docstring(rel_tree) or '')
           and 'claim_log' in (ast.get_docstring(rel_tree) or '')
           and 'sending' in (ast.get_docstring(rel_tree) or ''))
    _check(r, 'release_uses_own_session', lambda: 'Session(db.engine, expire_on_commit=False)' in rel_ast)
    _check(r, 'release_takes_sqlite_write_lock', lambda: "text('BEGIN IMMEDIATE')" in rel_ast)
    _check(r, 'release_rejects_non_sqlite', lambda: "db.engine.dialect.name != 'sqlite'" in rel_ast)
    _check(r, 'release_rejects_other_status', lambda: "row.status != 'queued_v2'" in rel_ast)
    _check(r, 'release_cas_on_status_and_message',
           lambda: "status='queued_v2'" in rel_ast and 'message=row.message' in rel_ast
           and 'synchronize_session=False' in rel_ast)
    _check(r, 'release_writes_only_status_and_message',
           lambda: "'status': 'failed'" in rel_ast and "'message': RELEASE_MESSAGE" in rel_ast
           and rel_ast.count("'status':") == 1)
    _check(r, 'release_rejects_concurrent_change', lambda: 'changed != 1' in rel_ast)
    _check(r, 'release_commits_only_on_success', lambda: 'session.commit()' in rel_ast)
    _check(r, 'release_rolls_back_on_refusal', lambda: rel_ast.count('session.rollback()') >= 3)
    _check(r, 'release_returns_reason_tuple',
           lambda: any(isinstance(n, ast.Return) and isinstance(n.value, ast.Tuple)
                       for n in ast.walk(rel_fn)) if rel_fn else False)

    rel_env = _release_namespace()
    code = rel_env.get('RELEASED_CODE') if rel_env else None
    message = rel_env.get('RELEASE_MESSAGE') if rel_env else None
    _check(r, 'released_code_value', lambda: code == 'released_queued_v2')
    _check(r, 'release_message_carries_safe_code',
           lambda: isinstance(message, str) and '（错误码：released_queued_v2）' in message)
    _check(r, 'release_message_within_column_limit',
           lambda: isinstance(message, str) and len(message) <= 500)
    _check(r, 'release_message_is_not_uncertain',
           lambda: isinstance(message, str) and '结果待确认' not in message and message != UNCERTAIN_MESSAGE)
    _check(r, 'release_message_states_unsent',
           lambda: isinstance(message, str) and '确认未发送' in message)

    d_tree = _tree(DISPATCH_SRC)
    codes = _safe_codes(d_tree)
    claim = _func(d_tree, '_claim')
    claim_ast = ast.unparse(claim) if claim else ''
    execute = _func(d_tree, 'execute_share')
    execute_ast = ast.unparse(execute) if execute else ''
    _check(r, 'safe_codes_still_frozenset',
           lambda: any(isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                       and isinstance(n.value.func, ast.Name) and n.value.func.id == 'frozenset'
                       for n in d_tree.body))
    _check(r, 'safe_codes_keeps_wecom_rejected', lambda: 'wecom_rejected' in codes)
    _check(r, 'safe_codes_has_released_queued_v2', lambda: 'released_queued_v2' in codes)
    _check(r, 'safe_codes_does_not_widen_transport_failures',
           lambda: not ({'send_error', 'http_500', 'helper_offline', 'helper_timeout',
                         'wecom_offline', 'wecom_timeout', 'paste_failed', 'focus_lost'} & set(codes)))
    _check(r, 'dedup_still_iterates_safe_codes', lambda: 'for code in SAFE_FAILURE_CODES' in execute_ast)
    _check(r, 'claim_active_states_unchanged',
           lambda: "'queued_v2', 'sending', 'delivery_started'" in claim_ast)
    cleanup_text = _text(CLEANUP_SRC)
    _check(r, 'cleanup_still_shares_safe_codes',
           lambda: 'from services.wechat_share_dispatch import SAFE_FAILURE_CODES' in cleanup_text
           and 'for code in SAFE_FAILURE_CODES' in cleanup_text)
    _check(r, 'cleanup_still_protects_queued_v2',
           lambda: "'queued_v2'" in cleanup_text and '_PROTECTED' in cleanup_text)

    route_fn = _func(_tree(ROUTE_SRC), ROUTE_NAME)
    route_ast = ast.unparse(route_fn) if route_fn else ''
    _check(r, 'route_guards_only_queued_v2', lambda: "log.status == 'queued_v2'" in route_ast)
    _check(r, 'route_calls_release_with_db_and_model',
           lambda: 'release_queued_share(db, WechatShareLog, log_id)' in route_ast)
    _check(r, 'route_fails_closed_on_release_refusal',
           lambda: 'if not released:' in route_ast and '409' in route_ast
           and 'db.session.rollback()' in route_ast)
    _check(r, 'route_release_precedes_execute_share', lambda: _release_before_execute(route_fn))
    _check(r, 'route_keeps_forced_resend', lambda: 'force=True' in route_ast)
    _check(r, 'route_keeps_frozen_receiver', lambda: 'frozen_name' in route_ast and 'used_frozen_receiver' in route_ast)
    _check(r, 'route_keeps_missing_config_409',
           lambda: 'if config is None:' in route_ast and "'该记录关联的分享配置已不存在" in route_ast)
    _check(r, 'route_keeps_503_and_500_handlers',
           lambda: 'except DispatchUnavailable' in route_ast and 'except Exception' in route_ast
           and '503' in route_ast and '500' in route_ast)
    _check(r, 'no_new_release_route_added', lambda: '/release' not in _text(ROUTE_SRC))

    template = _text(TEMPLATE_SRC)
    try:
        from jinja2 import Environment
        Environment().parse(template)
        jinja_ok = True
    except Exception:
        jinja_ok = False
    _check(r, 'template_jinja_parses', lambda: jinja_ok)
    _check(r, 'template_queued_v2_no_longer_disabled',
           lambda: "'sending', 'delivery_started', 'queued_v2'" not in template
           and "log.status in ('sending', 'delivery_started')" in template)
    _check(r, 'template_still_disables_in_flight',
           lambda: "log.status in ('sending', 'delivery_started')" in template
           and 'runtime_external_paused' in template)
    _check(r, 'template_confirmation_mentions_release',
           lambda: '撤销排队' in template and '确认未发送' in template)
    _check(r, 'template_still_posts_to_resend_path',
           lambda: "'/wechat_share/log/' + logId + '/resend'" in template)

    anchors = [node.lineno for node in _tree(APP_PY).body
               if isinstance(node, ast.FunctionDef) and node.name == 'backfill_stock_txn_warehouse_id']
    _check(r, 'app_py_source_anchor_is_unique', lambda: len(anchors) == 1)
    _check(r, 'inventory_truth_matches_current_source_anchor',
           lambda: len(anchors) == 1 and f'`app/app.py:{anchors[0]}`' in _text(DOC))
    pause = _text(PAUSE_SRC)
    _check(r, 'pause_guard_still_covers_resend_path',
           lambda: "r'/wechat_share/log/\\d+/resend'" in pause
           and 'resend_wechat_share_log' in pause)
    return r


def _release_before_execute(route_fn) -> bool:
    if route_fn is None:
        return False
    release_line = min((n.lineno for n in ast.walk(route_fn)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                        and n.func.id == 'release_queued_share'), default=10 ** 9)
    execute_line = min((n.lineno for n in ast.walk(route_fn)
                         if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                         and n.func.id == 'execute_share'), default=0)
    return release_line < execute_line


def _release_namespace() -> dict | None:
    """Compile the real release module constants + function in isolation."""
    try:
        from sqlalchemy import text
        from sqlalchemy.orm import Session
        tree = _tree(RELEASE_SRC)
        nodes = [n for n in tree.body if isinstance(n, ast.Assign)
                 or (isinstance(n, ast.FunctionDef) and n.name == 'release_queued_share')]
        env = {'text': text, 'Session': Session}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                     '<synthetic-release>', 'exec'), env)
        return env
    except Exception:
        return None


# --------------------------------------------------------------------------
# Behaviour: real release_queued_share over a synthetic in-memory database.
# --------------------------------------------------------------------------
def _build_db():
    from sqlalchemy import Column, Date, DateTime, Integer, String, create_engine, update, text
    from sqlalchemy.exc import IntegrityError, SQLAlchemyError
    from sqlalchemy.orm import Session, declarative_base

    engine = create_engine('sqlite:///:memory:')
    Base = declarative_base()

    class Log(Base):
        __tablename__ = 'wechat_share_log'
        id = Column(Integer, primary_key=True)
        module_key = Column(String)
        order_id = Column(Integer)
        share_date = Column(Date)
        config_id = Column(Integer)
        order_no = Column(String)
        trigger_type = Column(String)
        image_path = Column(String)
        image_size = Column(Integer)
        receiver_name = Column(String)
        receiver_wechat_id = Column(String)
        status = Column(String)
        message = Column(String)
        sent_at = Column(DateTime)
        created_at = Column(DateTime)

    class Dispatch(Base):
        __tablename__ = 'wechat_share_dispatch'
        module_key = Column(String, primary_key=True)
        order_id = Column(Integer, primary_key=True)
        share_date = Column(Date, primary_key=True)
        token = Column(String)
        state = Column(String)
        lease_until = Column(DateTime)
        updated_at = Column(DateTime)
        log_id = Column(Integer)

    Base.metadata.create_all(engine)

    d_tree = _tree(DISPATCH_SRC)
    names = ('_commit', '_view', '_claim', '_record', '_uncertain', 'execute_share')
    funcs = [_func(d_tree, n) for n in names]
    db = types.SimpleNamespace(engine=engine,
                               session=types.SimpleNamespace(new=[], dirty=[], deleted=[]))
    env = {
        'datetime': _dt.datetime, 'timedelta': _dt.timedelta, 'uuid4': uuid4,
        'LEASE_SECONDS': 300, 'UNCERTAIN_MESSAGE': UNCERTAIN_MESSAGE,
        'db': db, 'Session': Session, 'Dispatch': Dispatch, 'Log': Log, 'update': update,
        'IntegrityError': IntegrityError, 'SQLAlchemyError': SQLAlchemyError,
        'SAFE_FAILURE_CODES': _safe_codes(d_tree),
        'current_app': types.SimpleNamespace(
            logger=types.SimpleNamespace(error=lambda *_a, **_k: None)),
        'DispatchUnavailable': type('DispatchUnavailable', (RuntimeError,), {}),
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])),
                 '<synthetic-dispatch>', 'exec'), env)
    return engine, Session, Log, Dispatch, db, env


def _behaviour_checks() -> dict:
    r: dict = {}
    rel = _release_namespace() or {}
    release = rel.get('release_queued_share')
    message = rel.get('RELEASE_MESSAGE')
    engine, Session, Log, Dispatch, db, dispatch_env = _build_db()
    today = _dt.date(2026, 11, 11)

    def seed(status, msg, *, log_id=1):
        with Session(engine) as s:
            s.query(Log).delete()
            s.query(Dispatch).delete()
            s.add(Log(id=log_id, module_key='in_order', order_id=1, share_date=today,
                      status=status, message=msg, image_path='synthetic.png',
                      receiver_name='qa', order_no='QA-004'))
            s.commit()

    def row(log_id=1):
        with Session(engine) as s:
            found = s.query(Log).filter_by(id=log_id).first()
            return (found.status, found.message, found.image_path) if found else None

    def release_one(log_id=1):
        return release(db, Log, log_id)

    # Only an unclaimed queued_v2 record may be released.
    _check(r, 'behaviour_queued_v2_released', lambda: (
        seed('queued_v2', '等待助手领取'), release_one() == (True, ''),
        row()[0] == 'failed' and row()[1] == message))
    _check(r, 'behaviour_release_message_has_safe_code',
           lambda: (seed('queued_v2', '等待助手领取'), release_one(),
                    '（错误码：released_queued_v2）' in row()[1]))
    _check(r, 'behaviour_release_keeps_other_columns',
           lambda: row()[2] == 'synthetic.png')
    _check(r, 'behaviour_null_message_released', lambda: (
        seed('queued_v2', None), release_one() == (True, ''), row()[0] == 'failed'))
    _check(r, 'behaviour_long_message_replaced', lambda: (
        seed('queued_v2', 'x' * 490), release_one() == (True, ''), len(row()[1]) <= 500))
    _check(r, 'behaviour_second_release_refused', lambda: (
        release_one() == (False, '当前状态不是待助手领取，无需撤销'), row()[0] == 'failed'))

    for status in ('sent', 'failed', 'skipped', 'sending', 'delivery_started',
                   'uncertain', 'pending', 'preparing'):
        before = (status, '原始消息')
        _check(r, 'behaviour_refuses_' + status, lambda status=status, before=before: (
            seed(status, before[1]), release_one()[0] is False, row()[:2] == before))

    _check(r, 'behaviour_missing_id_refused', lambda: (
        seed('queued_v2', 'x'), release_one(999) == (False, '分享记录不存在'),
        row()[0] == 'queued_v2'))
    _check(r, 'behaviour_non_sqlite_refused', lambda: (
        release(types.SimpleNamespace(
            engine=types.SimpleNamespace(dialect=types.SimpleNamespace(name='postgresql'))),
            Log, 1)[0] is False))
    _check(r, 'behaviour_siblings_untouched', lambda: _siblings_untouched(
        engine, Session, Log, db, release))

    # End-to-end: deadlock before release, recovery through forced resend after.
    key = {'module_key': 'in_order', 'order_id': 1, 'share_date': today}
    metadata = {'config_id': 1, 'order_no': 'QA-004', 'trigger_type': 'manual_resend',
                'image_path': 'synthetic.png', 'image_size': 1,
                'receiver_name': 'qa', 'receiver_wechat_id': 'qa'}
    prepare = lambda: ({'image_path': 'synthetic.png', 'image_size': 1}, None)

    def seed_deadlock():
        with Session(engine) as s:
            s.query(Log).delete()
            s.query(Dispatch).delete()
            s.add(Log(id=1, **key, status='queued_v2', message='等待助手领取'))
            s.add(Dispatch(**key, token='old', state='pending',
                           lease_until=_dt.datetime.now() - _dt.timedelta(seconds=1),
                           updated_at=_dt.datetime.now(), log_id=1))
            s.commit()

    def forced_result(force):
        calls = []
        result = dispatch_env['execute_share'](
            key, metadata, prepare,
            lambda _data: calls.append('deliver') or ('sent', 'ok', 'synthetic'),
            force=force)
        return result, calls

    _check(r, 'behaviour_deadlock_blocks_even_force', lambda: (
        seed_deadlock(), forced_result(True)[0]['action'] == 'skipped',
        '轮询任务正在等待或执行' in forced_result(True)[0]['message']))
    _check(r, 'behaviour_release_unblocks_forced_resend', lambda: (
        seed_deadlock(), release_one() == (True, ''),
        forced_result(True)[0]['status'] == 'sent',
        forced_result(True)[1] == ['deliver']))
    _check(r, 'behaviour_normal_replay_still_conservative', lambda: (
        seed_deadlock(), release_one(), forced_result(False)[0]['action'] == 'skipped'))
    return r


def _siblings_untouched(engine, Session, Log, db, release) -> bool:
    today = _dt.date(2026, 11, 11)
    with Session(engine) as s:
        s.query(Log).delete()
        for i, status in enumerate(('queued_v2', 'sent', 'queued_v2'), start=1):
            s.add(Log(id=i, module_key='in_order', order_id=i, share_date=today,
                      status=status, message='m%d' % i))
        s.commit()
    ok = release(db, Log, 1) == (True, '')
    with Session(engine) as s:
        rows = {row.id: (row.status, row.message) for row in s.query(Log).all()}
    return ok and rows[1][0] == 'failed' and rows[2] == ('sent', 'm2') and rows[3] == ('queued_v2', 'm3')


# --------------------------------------------------------------------------
# Behaviour: the real resend route, with imports stripped, in a synthetic ns.
# --------------------------------------------------------------------------
class _StripModuleImports(ast.NodeTransformer):
    def visit_ImportFrom(self, node):
        return None


class _Json:
    def __init__(self, payload):
        self.payload = payload

    def get_json(self):
        return self.payload


class DispatchUnavailable(Exception):
    pass


def _compile_route():
    found = _func(_tree(ROUTE_SRC), ROUTE_NAME)
    if found is None:
        return None
    fn = copy.deepcopy(found)
    fn.decorator_list = []
    _StripModuleImports().visit(fn)
    ast.fix_missing_locations(fn)
    return compile(ast.Module(body=[fn], type_ignores=[]), str(ROUTE_SRC), 'exec')


def _route_env(code, image_dir, image_path, *, status='queued_v2', config_ok=True,
               module_key='in_order', image_ok=True, release_result=(True, '')):
    calls, captured = [], {}
    log = types.SimpleNamespace(
        id=3, config=types.SimpleNamespace(
            id=9, helper_url='http://127.0.0.1:8765/send', sender_name='s',
            sender_wechat_id='', receiver_name='r', receiver_wechat_id='',
            receiver_search_key='r', receiver_type='person', auto_send=False) if config_ok else None,
        module_key=module_key, image_path=image_path if image_ok else None,
        image_size=15, order_no='RK-QA-004', order_id=1,
        share_date=_dt.date.today(), receiver_name='', receiver_wechat_id='',
        status=status)

    class _Query:
        def get_or_404(self, log_id):
            return log

    class _Session:
        def rollback(self):
            calls.append('rollback')

        def commit(self):
            calls.append('commit')

    def release(*args):
        calls.append('release')
        captured['release_args'] = args
        return release_result

    def execute_share(*args, **kwargs):
        calls.append('execute_share')
        captured['kwargs'] = kwargs
        return {'status': 'sent', 'message': 'ok', 'log_id': 7}

    ns = {
        'WechatShareLog': types.SimpleNamespace(query=_Query()),
        '_wechat_share_output_dir': lambda: image_dir,
        '_wechat_share_send_image': lambda *_a: ('sent', 'ok', 'ok'),
        '_wechat_share_send_wecom': lambda *_a, **_k: ('sent', 'ok', 'ok'),
        '_wechat_share_wecom_webhook': lambda: '',
        'datetime': _dt,
        'db': types.SimpleNamespace(session=_Session()),
        'jsonify': lambda payload: _Json(payload),
        'log_operation': lambda *a, **k: calls.append('log_operation'),
        'os': os,
        'request': types.SimpleNamespace(form={}, args={}),
        'current_app': types.SimpleNamespace(
            logger=types.SimpleNamespace(exception=lambda *a, **k: None)),
        'DispatchUnavailable': DispatchUnavailable,
        'execute_share': execute_share,
        'release_queued_share': release,
    }
    exec(code, ns)
    return ns, calls, captured, ns[ROUTE_NAME]


def _call(route, log_id=3):
    result = route(log_id)
    if isinstance(result, tuple):
        return result[0].payload, result[1]
    return result.payload, 200


def _route_checks() -> dict:
    r: dict = {}
    code = _compile_route()
    with tempfile.TemporaryDirectory(prefix='wms-queued-release-') as tmp:
        image = os.path.join(tmp, 'share.png')
        Path(image).write_bytes(b'\x89PNG\r\n\x1a\n')

        def run(**kwargs):
            ns, calls, captured, route = _route_env(code, tmp, image, **kwargs)
            payload, status = _call(route)
            return payload, status, calls, captured

        _check(r, 'route_queued_v2_releases_then_resends', lambda: (
            lambda out: out[1] == 200 and out[0]['status'] == 'success'
            and out[2].count('release') == 1 and 'execute_share' in out[2]
            and out[3]['kwargs'].get('force') is True)(run()))
        _check(r, 'route_release_failure_returns_409_no_send', lambda: (
            lambda out: out[1] == 409 and out[0]['status'] == 'error'
            and 'execute_share' not in out[2] and 'rollback' in out[2])(
                run(release_result=(False, '记录状态已变化，请刷新后重试'))))
        _check(r, 'route_release_failure_msg_is_actionable', lambda: (
            lambda out: '记录状态已变化' in out[0]['msg'])(
                run(release_result=(False, '记录状态已变化，请刷新后重试'))))
        for status in ('failed', 'sent', 'skipped', 'sending', 'delivery_started', 'uncertain'):
            _check(r, 'route_does_not_release_' + status,
                   lambda status=status: 'release' not in run(status=status)[2])
        _check(r, 'route_missing_config_still_409_no_release', lambda: (
            lambda out: out[1] == 409 and 'release' not in out[2])(run(config_ok=False)))
        _check(r, 'route_other_module_still_400_no_release', lambda: (
            lambda out: out[1] == 400 and 'release' not in out[2])(run(module_key='out_order')))
        _check(r, 'route_missing_image_still_400_no_release', lambda: (
            lambda out: out[1] == 400 and 'release' not in out[2])(run(image_ok=False)))
        _check(r, 'route_normal_failed_resend_unchanged', lambda: (
            lambda out: out[1] == 200 and 'execute_share' in out[2])(run(status='failed')))
    return r


def run_checks() -> dict:
    results = {}
    results.update(_static_checks())
    results.update(_behaviour_checks())
    results.update(_route_checks())
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    results = run_checks()
    failed = [name for name, ok in results.items() if not ok]
    if args.json:
        print(json.dumps({'total': len(results), 'passed': len(results) - len(failed),
                          'failed': failed, 'success': not failed}, ensure_ascii=False))
    else:
        for name, ok in results.items():
            print(('  PASS  ' if ok else '  FAIL  ') + name)
        print(f'\n  {len(results) - len(failed)}/{len(results)} checks passed')
    return 0 if not failed else 1


if __name__ == '__main__':
    raise SystemExit(main())
