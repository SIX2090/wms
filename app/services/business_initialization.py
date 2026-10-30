"""BUG-2026-10-30-002: bind destructive initialization to a recoverable snapshot."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select

from db import db


class InitializationRefused(RuntimeError):
    """A failed precondition; no destructive changes may be committed."""


def initialization_enabled():
    """Enable only during an explicitly configured maintenance window."""
    return os.environ.get('WMS_ALLOW_BUSINESS_INIT', '0') == '1'


def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='wms-business-init-v1')


def _database_identity():
    return hashlib.sha256(str(db.engine.url).encode()).hexdigest()


def _snapshot_fingerprint(include_master):
    """Hash every affected row, including retained materials whose stock is zeroed."""
    import app as wms
    groups = [wms.INIT_BUSINESS_TABLES, wms.INIT_BUSINESS_ITEM_TABLES,
              wms.INIT_INVENTORY_TABLES, wms.INIT_LOG_TABLES, wms.INIT_AI_TABLES]
    if include_master:
        groups.append(wms.INIT_MASTER_TABLES)
    tables = {model.__table__.name: model.__table__ for group in groups for _, model in group}
    tables[wms.Material.__table__.name] = wms.Material.__table__
    digest = hashlib.sha256()
    for name, table in sorted(tables.items()):
        digest.update(name.encode())
        rows = db.session.execute(select(table).order_by(*table.primary_key.columns)).yield_per(500)
        for row in rows:
            payload = json.dumps(list(row), ensure_ascii=False, default=str, separators=(',', ':'))
            digest.update(payload.encode())
            digest.update(b'\n')
    return digest.hexdigest()


def prepare_preview(user_id):
    """Return signed choices from one consistent read transaction; do not write audits."""
    import app as wms
    db.session.rollback()
    if db.engine.dialect.name != 'sqlite':
        raise InitializationRefused('当前数据库不支持网页初始化，请使用停机维护流程')
    db.session.connection().exec_driver_sql('BEGIN')
    try:
        stats = wms._init_business_data_preview_stats()
        if any(item.get('error') for value in stats.values() if isinstance(value, list) for item in value):
            raise InitializationRefused('预览数据读取失败，已禁止初始化')
        nonce = uuid4().hex
        tokens = {str(int(choice)): _serializer().dumps({
            'user': user_id, 'database': _database_identity(), 'master': choice,
            'fingerprint': _snapshot_fingerprint(choice), 'nonce': nonce,
        }) for choice in (False, True)}
        return stats, tokens
    finally:
        db.session.rollback()


def _create_verified_backup(nonce):
    """Back up the locked database before deletion; require an independent verified file."""
    from backup_scheduler import get_backup_dir
    folder = (get_backup_dir() / 'initialization').resolve()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'before_init_{nonce}.db'
    # Never overwrite an earlier recovery artifact, even for a repeated request.
    with target.open('xb') as output:
        if db.engine.url.database in (None, '', ':memory:'):
            raw = db.session.connection().connection.driver_connection
            output.write(raw.serialize())
    if db.engine.url.database not in (None, '', ':memory:'):
        from app import create_sqlite_online_backup
        create_sqlite_online_backup(db.engine.url.database, target)
    with sqlite3.connect(target.as_uri() + '?mode=ro', uri=True, timeout=10) as backup:
        if backup.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise InitializationRefused('初始化前备份完整性校验失败，已中止')
        # The complete database includes both business logs and historical audits.
        backup.execute('SELECT count(*) FROM operation_log').fetchone()
        backup.execute('SELECT count(*) FROM operation_audit').fetchone()
    return target


def execute_initialization(token, include_master, user_id, username):
    """Lock, compare, back up, clear and audit; commit exactly once."""
    import app as wms
    try:
        expected = _serializer().loads(token, max_age=300)
    except (BadSignature, SignatureExpired):
        raise InitializationRefused('初始化预览已失效，请重新打开向导并确认') from None
    if (expected.get('user') != user_id or expected.get('database') != _database_identity()
            or expected.get('master') is not include_master):
        raise InitializationRefused('初始化对象或选项已改变，请重新预览确认')
    if db.engine.dialect.name != 'sqlite':
        raise InitializationRefused('当前数据库不支持网页初始化，请使用停机维护流程')
    db.session.rollback()
    try:
        db.session.connection().exec_driver_sql('BEGIN IMMEDIATE')
        db.session.connection().exec_driver_sql('PRAGMA defer_foreign_keys=ON')
        marker = 'init:' + expected['nonce']
        if wms.OperationAudit.query.filter_by(operation='init_business_data_done', target_name=marker).first():
            raise InitializationRefused('这次初始化已执行，请勿重复提交')
        if _snapshot_fingerprint(include_master) != expected.get('fingerprint'):
            raise InitializationRefused('数据已变化，已中止初始化；请重新预览并确认')
        backup = _create_verified_backup(expected['nonce'])
        stats = wms._init_business_data_preview_stats()
        deleted = wms._init_business_data_keep_users_and_settings(include_master_data=include_master)
        for key, definition in wms.SYSTEM_SETTING_DEFINITIONS.items():
            db.session.add(wms.SystemSetting(key=key, value=definition.get('default', ''),
                                            remark=definition.get('remark', '')))
        # Preserve historical audits. A verified full backup contains all logs being cleared.
        db.session.add(wms.OperationAudit(
            user_id=user_id, username=username, operation='init_business_data_done',
            target_type='system', target_id=0, target_name=marker, status='success',
            old_data=json.dumps(stats, ensure_ascii=False),
            new_data=json.dumps({'deleted': deleted, 'backup': str(backup),
                                 'include_master_data': include_master}, ensure_ascii=False),
            reason='预览指纹一致，初始化前完整备份校验通过',
        ))
        db.session.flush()
        if db.session.connection().exec_driver_sql('PRAGMA foreign_key_check').first():
            raise InitializationRefused('初始化后关联校验失败，所有清理已回滚')
        db.session.commit()
        return deleted, str(backup)
    except Exception:
        db.session.rollback()
        raise
