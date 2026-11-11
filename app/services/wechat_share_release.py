"""Human exit for share logs stranded in ``queued_v2``.

A ``queued_v2`` log has been queued for the local helper but not yet claimed:
``claim_log`` is the only writer that moves it to ``sending``.  If the helper
never polls (stopped, wrong token, network fault), the record is dead-locked:

* ``_claim`` refuses even a forced resend while an active log exists;
* the page disables the resend button for ``queued_v2``;
* history cleanup protects ``queued_v2`` from deletion.

Releasing it is therefore safe: no claim exists and no external delivery has
started.  The log becomes an ordinary *deterministic* failure whose error code
is a member of ``SAFE_FAILURE_CODES``, so normal replay, forced resend and
history cleanup all keep their existing semantics.  A record that has already
been claimed (``sending``/``delivery_started``) is never touched: it may already
have produced an external effect and must stay under human review.

BUG-2026-11-11-004.  No WMS application import, no HTTP, no image writes.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

RELEASED_CODE = 'released_queued_v2'
RELEASE_MESSAGE = (
    '人工撤销待助手领取的排队；该记录尚未被助手领取，确认未发送，可重新分享或强制重发'
    f'（错误码：{RELEASED_CODE}）'
)


def release_queued_share(db, Log, log_id):
    """CAS one unclaimed ``queued_v2`` log into a safely retryable failure.

    Returns ``(ok, reason)``.  Uses its own short transaction so the caller's
    Flask session stays clean for ``execute_share``'s uncommitted-write guard.
    """
    if db.engine.dialect.name != 'sqlite':
        return False, '当前数据库暂不支持撤销排队'
    with Session(db.engine, expire_on_commit=False) as session:
        session.execute(text('BEGIN IMMEDIATE'))
        row = session.query(Log).filter_by(id=log_id).first()
        if row is None:
            session.rollback()
            return False, '分享记录不存在'
        if row.status != 'queued_v2':
            session.rollback()
            return False, '当前状态不是待助手领取，无需撤销'
        changed = session.query(Log).filter_by(
            id=log_id, status='queued_v2', message=row.message).update(
                {'status': 'failed', 'message': RELEASE_MESSAGE},
                synchronize_session=False)
        if changed != 1:
            session.rollback()
            return False, '记录状态已变化，请刷新后重试'
        session.commit()
        return True, ''
