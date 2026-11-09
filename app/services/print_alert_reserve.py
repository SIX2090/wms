"""Reserve print alerts before delivery using isolated short SQLite transactions."""
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool, SingletonThreadPool


def reserve_alert(db, Log, metadata, interval_minutes):
    if db.engine.dialect.name != 'sqlite' or isinstance(db.engine.pool, (StaticPool, SingletonThreadPool)):
        raise ValueError('无法确认独立 SQLite 写入连接')
    with Session(db.engine, expire_on_commit=False) as session:
        session.execute(text('BEGIN IMMEDIATE'))
        cutoff = datetime.now() - timedelta(minutes=interval_minutes)
        if session.query(Log).filter(Log.module_key == 'print_alert', Log.order_id == 0,
                Log.status.in_(('pending', 'queued_v2', 'sending', 'delivery_started', 'uncertain'))).first():
            return None
        if session.query(Log).filter(Log.module_key == 'print_alert', Log.order_id == metadata['order_id'],
                Log.order_no == metadata['order_no'],
                Log.status.in_(('pending', 'queued_v2', 'sending', 'delivery_started', 'uncertain'))).first():
            return None
        if session.query(Log).filter(Log.module_key == 'print_alert', Log.created_at >= cutoff).first():
            return None
        log = Log(**metadata, status='sending', message='告警正在发送，结果待核对')
        session.add(log)
        session.flush()
        ident = log.id
        try:
            session.commit()
        except Exception:
            session.invalidate()
            raise
        return ident


def attach_alert_image(db, Log, log_id, image_path, image_size):
    with Session(db.engine) as session:
        session.execute(text('BEGIN IMMEDIATE'))
        changed = session.query(Log).filter_by(id=log_id, status='sending').update(
            {'image_path': image_path, 'image_size': image_size}, synchronize_session=False)
        if changed != 1:
            session.rollback()
            return False
        session.flush()
        try:
            session.commit()
        except Exception:
            session.invalidate()
            raise
        return True


def finish_alert(db, Log, log_id, state, message):
    if state not in ('sent', 'failed', 'queued_v2', 'uncertain'):
        raise ValueError('无效结果')
    with Session(db.engine) as session:
        session.execute(text('BEGIN IMMEDIATE'))
        changed = session.query(Log).filter_by(id=log_id, status='sending').update(
            {'status': state, 'message': message[:500],
             'sent_at': datetime.now() if state == 'sent' else None}, synchronize_session=False)
        if changed != 1:
            session.rollback()
            return False
        session.flush()
        try:
            session.commit()
        except Exception:
            session.invalidate()
            raise
        return True
