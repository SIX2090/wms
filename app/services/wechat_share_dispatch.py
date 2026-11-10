"""Durable delivery claims. No external delivery runs inside a DB transaction.

Receiver protocols currently have no idempotency/receipt lookup contract. A
timeout, process death while sending, or receipt persistence failure is UNKNOWN,
never an automatically retryable failure. Only explicit force accepts that risk.
Tests: tests/test_wechat_share_dispatch.py (HTTP, two OS workers, commit faults).
"""
from datetime import datetime, timedelta
from uuid import uuid4

from flask import current_app
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from db import db
from models.wechat import WechatShareDispatch as Dispatch, WechatShareLog as Log

LEASE_SECONDS = 300
UNCERTAIN_MESSAGE = '发送结果待确认；普通执行不会再次发送。请先核对接收端，确需重发时使用强制重发（可能重复）。'
SAFE_FAILURE_CODES = frozenset({'invalid_helper_url', 'token_not_configured', 'auth_failed',
    'invalid_wecom_webhook', 'wecom_rejected', 'no_receiver', 'clipboard_failed', 'wechat_window_not_found',
    'open_contact_failed'})


class DispatchUnavailable(RuntimeError):
    """A safe, human-readable failure; never contains transport credentials."""


def _commit(session):
    """Keep rejected flushes distinct from an ambiguous actual commit failure."""
    # Unique-claim conflicts fail before COMMIT. Let the caller roll them back
    # without invalidating a healthy connection (StaticPool may share it).
    session.flush()
    try:
        session.commit()
    except Exception:
        # Commit may fail before or after the driver's COMMIT. Discarding this
        # connection prevents an uncommitted receipt from being read/reused by
        # recovery; the next session observes only durable state.
        session.invalidate()
        raise


def _view(row, action='skipped'):
    return {'action': action, 'log_id': row.log_id, 'status': row.state,
            'message': UNCERTAIN_MESSAGE if row.state == 'uncertain' else '该单据今日已处理或正在处理'}


def _claim(key, force):
    """Unique insert / token CAS, committed before rendering or network effects."""
    now = datetime.now()
    token = uuid4().hex
    values = dict(token=token, state='preparing', lease_until=now + timedelta(seconds=LEASE_SECONDS),
                  updated_at=now, log_id=None)
    with Session(db.engine, expire_on_commit=False) as session:
        if session.bind.dialect.name != 'sqlite':
            raise DispatchUnavailable('当前数据库暂不支持安全领取，请人工核对')
        from sqlalchemy import text
        session.execute(text('BEGIN IMMEDIATE'))
        active = session.query(Log).filter_by(**key).filter(Log.status.in_(('queued_v2', 'sending', 'delivery_started'))).first()
        if active is not None:
            return None, {'action': 'skipped', 'log_id': active.id, 'status': 'uncertain',
                          'message': '轮询任务正在等待或执行，不能同时直推；请先核对'}
        row = Dispatch(**key, **values)
        session.add(row)
        try:
            _commit(session)
            return token, None
        except IntegrityError:
            session.rollback()
        session.execute(text('BEGIN IMMEDIATE'))
        row = session.get(Dispatch, tuple(key.values()))
        if row is None:
            raise DispatchUnavailable('分享任务领取冲突，请稍后重试；尚未发送')
        active_log = session.get(Log, row.log_id) if row.log_id else None
        if active_log is not None and active_log.status in ('queued_v2', 'sending', 'delivery_started'):
            return None, {'action': 'skipped', 'log_id': row.log_id, 'status': 'uncertain',
                          'message': '轮询任务正在等待或执行，不能同时直推；请先核对'}
        if row.state in ('preparing', 'sending') and row.lease_until > now:
            return None, _view(row)
        if row.state == 'sending' and not force:
            # Expired sender may already have caused an external effect.
            session.execute(update(Dispatch).where(
                *(getattr(Dispatch, k) == v for k, v in key.items()),
                Dispatch.token == row.token, Dispatch.state == 'sending',
            ).values(state='uncertain', updated_at=now))
            if row.log_id:
                session.execute(update(Log).where(Log.id == row.log_id, Log.status == 'sending')
                                .values(status='uncertain', message=UNCERTAIN_MESSAGE))
            _commit(session)
            row.state = 'uncertain'
            return None, _view(row)
        if not force and row.state in ('pending', 'sent', 'uncertain'):
            return None, _view(row)
        # Only a safe pre-send failure / expired preparation recovers normally.
        changed = session.execute(update(Dispatch).where(
            *(getattr(Dispatch, k) == v for k, v in key.items()),
            Dispatch.token == row.token, Dispatch.state == row.state,
        ).values(**values)).rowcount
        _commit(session)
        if not changed:
            return None, {'action': 'skipped', 'log_id': None, 'status': 'preparing',
                          'message': '另一执行进程已领取此任务'}
        return token, None


def _record(key, token, state, message, metadata=None, queue_for_helper=False):
    """CAS receipt and log together; stale workers cannot overwrite a new attempt."""
    with Session(db.engine, expire_on_commit=False) as session:
        row = session.get(Dispatch, tuple(key.values()))
        if row is None or row.token != token:
            raise DispatchUnavailable('分享任务已由其他执行进程接手，已停止本次发送')
        expected = row.state
        log_id = row.log_id
        if metadata is not None:
            log = Log(**metadata, **key, status=state, message=message)
            session.add(log)
            session.flush()
            log_id = log.id
        changed = session.execute(update(Dispatch).where(
            *(getattr(Dispatch, k) == v for k, v in key.items()),
            Dispatch.token == token, Dispatch.state == expected,
        ).values(state=state, log_id=log_id, updated_at=datetime.now(),
                 lease_until=datetime.now() + timedelta(seconds=LEASE_SECONDS))).rowcount
        if not changed:
            session.rollback()
            raise DispatchUnavailable('分享任务状态已变化，本次未重复发送')
        if metadata is None and log_id:
            session.execute(update(Log).where(Log.id == log_id).values(
                status='queued_v2' if queue_for_helper else state, message=message[:500],
                sent_at=datetime.now() if state == 'sent' else None))
        _commit(session)
        return {'action': 'created', 'log_id': log_id, 'status': state, 'message': message}


def _uncertain(key, token):
    """Best-effort safety marker; persisted sending also blocks normal replay."""
    try:
        with Session(db.engine) as session:
            row = session.get(Dispatch, tuple(key.values()))
            if row and row.token == token and row.state == 'sending':
                changed = session.execute(update(Dispatch).where(
                    *(getattr(Dispatch, k) == v for k, v in key.items()),
                    Dispatch.token == token, Dispatch.state == 'sending',
                ).values(state='uncertain', updated_at=datetime.now())).rowcount
                if changed and row.log_id:
                    session.execute(update(Log).where(Log.id == row.log_id).values(
                        status='uncertain', message=UNCERTAIN_MESSAGE))
                _commit(session)
    except SQLAlchemyError:
        current_app.logger.error('分享结果待确认标记暂未落库；保留已持久化的发送占位')


def execute_share(key, metadata, prepare, deliver, force=False):
    """No uncommitted caller writes, no auto replay after a possible send.

    prepare returns (log metadata additions, opaque delivery input). For a
    forced resend a NEW attempt log preserves the original receiver/history.
    """
    if db.session.new or db.session.dirty or db.session.deleted:
        raise DispatchUnavailable('请先保存当前业务变更，再执行分享；尚未发送')
    try:
        token, skipped = _claim(key, force)
        if skipped:
            return skipped
        # Import old successful/pending logs only after owning the durable key.
        if not force:
            with Session(db.engine) as session:
                previous = next((log for log in session.query(Log).filter_by(**key).order_by(Log.id.desc())
                    if log.status in ('pending', 'queued_v2', 'sent', 'sending', 'delivery_started', 'uncertain') or
                    (log.status == 'failed' and not any(
                        f'（错误码：{code}）' in (log.message or '') for code in SAFE_FAILURE_CODES))), None)
                if previous:
                    state = 'pending' if previous.status == 'queued_v2' else previous.status if previous.status in ('sent', 'pending') else 'uncertain'
                    session.execute(update(Dispatch).where(
                        *(getattr(Dispatch, k) == v for k, v in key.items()), Dispatch.token == token,
                    ).values(state=state, log_id=previous.id))
                    _commit(session)
                    return {'action': 'skipped', 'log_id': previous.id, 'status': state,
                            'message': UNCERTAIN_MESSAGE if state == 'uncertain' else '今日已有分享记录'}
        try:
            additions, data = prepare()
        except Exception:
            _record(key, token, 'failed', '图片生成失败，尚未发送，可重试')
            raise DispatchUnavailable('图片生成失败，尚未发送，可重试') from None
        _record(key, token, 'sending', '正在发送；若执行中断请先核对接收端', {**metadata, **additions})
        try:
            status, code, message = deliver(data)
            # BUG-2026-11-10-012：企业微信 webhook 返回 HTTP 200 + errcode≠0 是服务端
            # 结构化明确拒绝（消息未被接受），属可安全普通重试的确定性失败。原码是
            # 动态 wecom_<errcode>，命中不了固定白名单，会被一律改判 uncertain；归一为
            # 固定码后，新结果判定、历史 failed 日志导入去重、清理 claim 保全三处共享
            # 同一语义。仅纯数字 errcode 命中；wecom_offline/timeout/error/
            # redirect_refused 等传输层或重定向失败可能已送达，仍保持 uncertain。
            if (status == 'failed' and isinstance(code, str) and code.startswith('wecom_')
                    and code[6:].isdigit()):
                code = 'wecom_rejected'
            if status == 'pending' and code != 'helper_not_configured':
                status = 'uncertain'
                message = str(message or '') + '；发送情况请人工核对'
            # Only explicit rejection/preflight errors are safe for normal retry.
            safe = code in SAFE_FAILURE_CODES
            if status not in ('sent', 'pending'):
                status = 'failed' if status == 'failed' and safe else 'uncertain'
            if status == 'uncertain':
                message = UNCERTAIN_MESSAGE
                if isinstance(code, str) and 0 < len(code) <= 64 and all(ch in 'abcdefghijklmnopqrstuvwxyz0123456789_' for ch in code):
                    message += f'（错误码：{code}）'
            elif status == 'failed' and code not in ('ok', ''):
                message = f'{message}（错误码：{code}）'
            return _record(key, token, status, message,
                           queue_for_helper=status == 'pending' and code == 'helper_not_configured')
        except Exception:
            _uncertain(key, token)
            raise DispatchUnavailable(UNCERTAIN_MESSAGE) from None
    except SQLAlchemyError:
        raise DispatchUnavailable('分享状态暂时无法保存，请稍后核对记录；本次不会自动重发。若尚未升级，请先初始化 wechat_share_dispatch 表。') from None
