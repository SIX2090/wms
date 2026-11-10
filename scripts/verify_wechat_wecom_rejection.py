"""BUG-2026-11-10-012 offline regression lock.

企业微信 webhook 返回 HTTP 200 + errcode!=0 时，_wechat_share_send_wecom 给出动态码
wecom_<errcode>（app/app.py），属服务端结构化明确拒绝：消息未被接受，可安全普通重试。
修复前该动态码命中不了固定白名单 SAFE_FAILURE_CODES，被 execute_share 一律改判
uncertain，禁止普通重发。本锁验证归一化后的三处消费点一致性：

  A. execute_share 新结果判定   -> status 'failed'，message 带固定码
  B. 历史 failed 日志导入去重    -> 不再当作「不可安全重试」
  C. cleanup._preserve_claims    -> 不再补建 uncertain 保护占位

严格边界：传输层/重定向失败（wecom_offline/timeout/error/redirect_refused）以及
helper_* / http_* 等「可能已送达」的码必须继续 uncertain，绝不因本修复被放宽。

只读取源码并用合成 sqlite:///:memory: 执行真实函数；不导入 WMS 应用、不连生产库、
不访问现役服务、不发 HTTP、不写产品文件。
"""
import ast
import json
import sys
import types
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app' / 'services' / 'wechat_share_dispatch.py'
CLEANUP = ROOT / 'app' / 'services' / 'wechat_share_cleanup.py'
APP_PY = ROOT / 'app' / 'app.py'

UNCERTAIN_MESSAGE = '发送结果待确认；普通执行不会再次发送。请先核对接收端，确需重发时使用强制重发（可能重复）。'


def _tree(path):
    return ast.parse(path.read_text(encoding='utf-8-sig'))


def _safe_codes(tree):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'SAFE_FAILURE_CODES' for t in node.targets):
            return frozenset(ast.literal_eval(node.value.args[0]))
    raise AssertionError('SAFE_FAILURE_CODES assignment not found')


def _func(tree, name):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f'function {name} not found')


def _assigns_string_literal(func, value):
    """The real execute_share body must contain `code = <value>`."""
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'code' for t in node.targets):
            if isinstance(node.value, ast.Constant) and node.value.value == value:
                return True
    return False


def _build_runtime():
    """Compile the real dispatch functions into an isolated namespace over a fresh DB."""
    from sqlalchemy import Column, Date, DateTime, Integer, String, create_engine, update
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
    tree = _tree(SOURCE)
    names = ('_commit', '_view', '_claim', '_record', '_uncertain', 'execute_share')
    funcs = [_func(tree, n) for n in names]
    env = {
        'datetime': datetime, 'timedelta': timedelta, 'uuid4': uuid4,
        'LEASE_SECONDS': 300, 'UNCERTAIN_MESSAGE': UNCERTAIN_MESSAGE,
        'db': types.SimpleNamespace(
            engine=engine,
            session=types.SimpleNamespace(new=[], dirty=[], deleted=[])),
        'Session': Session, 'Dispatch': Dispatch, 'Log': Log, 'update': update,
        'IntegrityError': IntegrityError, 'SQLAlchemyError': SQLAlchemyError,
        'SAFE_FAILURE_CODES': _safe_codes(tree),
        'current_app': types.SimpleNamespace(
            logger=types.SimpleNamespace(error=lambda *_a, **_k: None)),
        'DispatchUnavailable': type('DispatchUnavailable', (RuntimeError,), {}),
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])),
                 '<synthetic-real-dispatch>', 'exec'), env)
    return engine, Session, Log, Dispatch, env


def _run_delivery(status, code, message):
    """Drive the real execute_share with a synthetic deliver() outcome."""
    engine, Session, Log, Dispatch, env = _build_runtime()
    key = {'module_key': 'in_order', 'order_id': 1, 'share_date': date(2026, 11, 11)}
    metadata = {'config_id': 1, 'order_no': 'QA-WECOM-012', 'trigger_type': 'manual',
                 'image_path': 'synthetic.png', 'image_size': 1,
                 'receiver_name': 'qa', 'receiver_wechat_id': 'qa'}
    result = env['execute_share'](
        key, metadata,
        lambda: ({'image_path': 'synthetic.png', 'image_size': 1}, None),
        lambda _data: (status, code, message), force=False)
    with Session(engine) as session:
        row = session.query(Log).order_by(Log.id.desc()).first()
        claim = session.get(Dispatch, tuple(key.values()))
        return {'result_status': result['status'],
                'log_status': row.status if row else None,
                'log_message': row.message if row else None,
                'claim_state': claim.state if claim else None}


def _history_needs_conservative_skip(codes, message):
    """Mirror of dispatch.py execute_share legacy-log predicate."""
    return not any(f'（错误码：{code}）' in (message or '') for code in codes)


def _cleanup_marks_unsafe(codes, message):
    """Mirror of cleanup.py _preserve_claims unsafe predicate for one failed log."""
    return not any(f'（错误码：{code}）' in (message or '') for code in codes)


def run_checks(source_path=None):
    source = Path(source_path) if source_path else SOURCE
    tree = _tree(source)
    execute_share = _func(tree, 'execute_share')
    codes = _safe_codes(tree)
    checks = {}

    checks['whitelist_has_wecom_rejected'] = 'wecom_rejected' in codes
    checks['whitelist_still_has_existing_safe_codes'] = {
        'invalid_helper_url', 'token_not_configured', 'auth_failed',
        'invalid_wecom_webhook', 'no_receiver', 'clipboard_failed',
        'wechat_window_not_found', 'open_contact_failed'} <= set(codes)
    checks['no_transport_code_in_whitelist'] = not ({
        'wecom_offline', 'wecom_timeout', 'wecom_error', 'wecom_redirect_refused',
        'helper_offline', 'helper_timeout', 'send_error', 'http_500',
        'helper_redirect_refused'} & set(codes))
    checks['execute_share_normalizes_to_fixed_code'] = _assigns_string_literal(
        execute_share, 'wecom_rejected')
    checks['normalization_is_inside_deliver_guard'] = any(
        isinstance(n, ast.If) and 'wecom_rejected' in ast.unparse(n)
        for n in ast.walk(execute_share))

    # The producer still emits the dynamic code (app/app.py must stay untouched).
    app_text = APP_PY.read_text(encoding='utf-8-sig')
    checks['producer_still_emits_dynamic_errcode'] = "f'wecom_{errcode}'" in app_text
    checks['app_py_unchanged_by_this_fix'] = 'wecom_rejected' not in app_text

    # Both downstream consumers must keep iterating SAFE_FAILURE_CODES so the
    # normalized message is recognized everywhere without touching those files.
    cleanup_text = CLEANUP.read_text(encoding='utf-8-sig')
    checks['cleanup_imports_shared_whitelist'] = (
        'from services.wechat_share_dispatch import SAFE_FAILURE_CODES' in cleanup_text)
    checks['cleanup_uses_whitelist_for_unsafe'] = (
        'for code in SAFE_FAILURE_CODES' in cleanup_text)
    checks['dispatch_history_uses_whitelist'] = (
        'for code in SAFE_FAILURE_CODES' in ast.unparse(execute_share))

    # End-to-end: explicit structured rejection is retryable, transport stays uncertain.
    reject = _run_delivery('failed', 'wecom_93000', '企业微信机器人返回错误：invalid webhook（errcode=93000）')
    checks['wecom_errcode_becomes_failed'] = (
        reject['result_status'] == 'failed' and reject['log_status'] == 'failed')
    checks['wecom_errcode_logs_fixed_code'] = '（错误码：wecom_rejected）' in (reject['log_message'] or '')
    checks['wecom_errcode_claim_not_uncertain'] = reject['claim_state'] == 'failed'
    checks['history_allows_normal_retry'] = not _history_needs_conservative_skip(
        codes, reject['log_message'])
    checks['cleanup_does_not_mark_unsafe'] = not _cleanup_marks_unsafe(
        codes, reject['log_message'])

    for other in (45009, 40058, 1):
        r = _run_delivery('failed', f'wecom_{other}', 'structured rejection')
        checks[f'wecom_numeric_{other}_becomes_failed'] = (
            r['result_status'] == 'failed' and r['log_status'] == 'failed')

    for code in ('wecom_offline', 'wecom_timeout', 'wecom_error',
                 'wecom_redirect_refused', 'wecom_None', 'wecom_93000abc',
                 'helper_offline', 'helper_timeout', 'send_error', 'http_500',
                 'helper_redirect_refused'):
        r = _run_delivery('failed', code, 'possible external effect')
        checks[f'transport_{code}_stays_uncertain'] = (
            r['result_status'] == 'uncertain' and r['log_status'] == 'uncertain')
        checks[f'transport_{code}_not_normalized'] = (
            '（错误码：wecom_rejected）' not in (r['log_message'] or ''))

    for code in ('auth_failed', 'invalid_wecom_webhook', 'token_not_configured'):
        r = _run_delivery('failed', code, 'preflight rejection')
        checks[f'existing_safe_{code}_still_failed'] = (
            r['result_status'] == 'failed' and r['log_status'] == 'failed')

    ok = _run_delivery('sent', 'ok', '已推送到企业微信群')
    checks['sent_outcome_unchanged'] = ok['result_status'] == 'sent' and ok['log_status'] == 'sent'
    pending = _run_delivery('pending', 'helper_not_configured', '待发送')
    checks['pending_queue_for_helper_unchanged'] = pending['result_status'] == 'pending'

    return checks


def main():
    checks = run_checks()
    passed = sum(bool(v) for v in checks.values())
    failed = [k for k, v in checks.items() if not v]
    if '--json' in sys.argv:
        print(json.dumps({'passed': passed, 'total': len(checks), 'failed': failed},
                         ensure_ascii=False, indent=2))
    else:
        for name, ok in checks.items():
            print(('PASS ' if ok else 'FAIL ') + name)
        print(f'\n{passed}/{len(checks)} passed')
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
