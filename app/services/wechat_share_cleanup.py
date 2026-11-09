"""Explicit, previewed history cleanup; delivery claims survive log removal.

Tests: tests/test_wechat_share_cleanup.py. No inventory or document writes.
"""
from datetime import date, datetime, time, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4

from flask import current_app
from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import db
from models.wechat import WechatShareDispatch as Dispatch, WechatShareLog as Log
from services.wechat_share_dispatch import SAFE_FAILURE_CODES

_REMOVABLE = {'sent', 'failed', 'skipped'}
_PROTECTED = {'pending', 'queued_v2', 'sending', 'delivery_started', 'uncertain', 'preparing'}


class CleanupChanged(ValueError):
    """The human must review a fresh preview before deleting."""


def _key(row):
    return row.module_key, row.order_id, row.share_date


def _signer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='wechat-history-cleanup-v1')


def _selection(session, cutoff, status=None):
    logs = session.query(Log).order_by(Log.id).all()
    claims = {_key(row): row for row in session.query(Dispatch).all()}
    protected = {_key(row) for row in logs if row.status in _PROTECTED}
    protected.update(key for key, row in claims.items() if row.state in _PROTECTED)
    selected = [row for row in logs if row.status in _REMOVABLE and _key(row) not in protected
                and (status is None or row.status == status)
                and (cutoff is None or (row.created_at is not None and row.created_at < cutoff))]
    fingerprint = sha256(json.dumps([
        [row.id, row.status, row.message, row.image_path, str(row.created_at), str(_key(row)),
         [claims[_key(row)].state, claims[_key(row)].token, claims[_key(row)].log_id]
         if _key(row) in claims else None] for row in selected
    ], ensure_ascii=True).encode()).hexdigest()
    return logs, claims, selected, fingerprint, sum(_key(row) in protected for row in logs)


def preview_share_cleanup(retention_days, delete_images, actor):
    cutoff = datetime.combine(date.today()-timedelta(days=retention_days), time.min) if retention_days else None
    with Session(db.engine) as session:
        _, _, selected, fingerprint, protected = _selection(session, cutoff)
        token = _signer().dumps({'actor': str(actor), 'days': retention_days, 'images': delete_images,
            'cutoff': cutoff.isoformat() if cutoff else None, 'fingerprint': fingerprint})
        return {'count': len(selected), 'protected_count': protected, 'preview_token': token,
                'cutoff': cutoff.strftime('%Y-%m-%d') if cutoff else None}


def _lock(session):
    # SQLite writer reservation serializes selection/deletion with claim CAS.
    if db.engine.dialect.name == 'sqlite':
        session.execute(text('BEGIN IMMEDIATE'))
    else:
        raise ValueError('当前数据库暂不支持历史分享清理')


def _preserve_claims(session, logs, claims, selected):
    removed = {row.id for row in selected}
    keys = {_key(row) for row in selected}
    for key in keys:
        claim = claims.get(key)
        history = [row for row in logs if _key(row) == key]
        unsafe = any(row.status == 'failed' and not any(
            f'（错误码：{code}）' in (row.message or '') for code in SAFE_FAILURE_CODES) for row in history)
        state = 'uncertain' if unsafe else 'sent' if any(row.status == 'sent' for row in history) else None
        if claim:
            if claim.log_id in removed:
                claim.log_id = None
            if claim.state == 'failed' and state:
                claim.state = state
            continue
        if state:
            session.add(Dispatch(module_key=key[0], order_id=key[1], share_date=key[2],
                token=uuid4().hex, state=state, lease_until=datetime.now(), updated_at=datetime.now()))


def _image_path(raw, root):
    """Reject traversal, links/junctions, outside paths and non-PNG files."""
    try:
        path = Path(raw)
        if not path.is_absolute() or path.suffix.lower() != '.png':
            return None
        resolved = path.resolve()
        if not resolved.is_relative_to(root) or resolved == root:
            return None
        for part in [path, *path.parents]:
            if part.is_symlink() or (part.exists() and getattr(part.stat(), 'st_file_attributes', 0) & 0x400):
                return None
        return resolved
    except (OSError, ValueError, RuntimeError):
        return None


def _cleanup_images(candidates, output_dir):
    deleted = skipped = failed = 0
    root = Path(output_dir).resolve()
    # Recheck retained references after the record transaction commits. A file
    # failure never rolls back records or removes the durable duplicate guard.
    with Session(db.engine) as session:
        _lock(session)
        references = {os.path.normcase(os.path.realpath(row.image_path))
                      for row in session.query(Log).all() if row.image_path}
        active = {_key(row) for row in session.query(Dispatch).all() if row.state in _PROTECTED}
        paths = {}
        for raw, key in candidates:
            if raw:
                paths.setdefault(raw, set()).add(key)
        seen = set()
        for raw, keys in paths.items():
            path = _image_path(raw, root)
            normalized = os.path.normcase(str(path)) if path else None
            if not path or normalized in references or keys & active:
                skipped += 1
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            try:
                path.unlink()
                deleted += 1
            except FileNotFoundError:
                skipped += 1
            except OSError:
                failed += 1
                current_app.logger.warning('微信分享历史图片清理失败，文件保留')
        session.rollback()  # read/recheck lock only
    return deleted, skipped, failed


def cleanup_share_history(retention_days, delete_images, actor, preview_token=None, *, legacy_status=None):
    cutoff = None
    if legacy_status is None:
        try:
            plan = _signer().loads(preview_token, max_age=600)
            if (plan['actor'], plan['days'], plan['images']) != (str(actor), retention_days, delete_images):
                raise ValueError()
            cutoff = datetime.fromisoformat(plan['cutoff']) if plan['cutoff'] else None
        except (BadData, KeyError, TypeError, ValueError):
            raise CleanupChanged('清理预览已失效或选项已变化，请重新预览后确认') from None
    elif legacy_status not in {'failed', 'skipped'}:
        raise ValueError('只能清理失败或跳过的分享记录')
    candidates = []
    with Session(db.engine) as session:
        _lock(session)
        logs, claims, selected, fingerprint, _ = _selection(session, cutoff, legacy_status)
        if legacy_status is None and fingerprint != plan['fingerprint']:
            raise CleanupChanged('分享记录已变化，请重新预览后确认')
        _preserve_claims(session, logs, claims, selected)
        for row in selected:
            candidates.append((row.image_path, _key(row)))
            session.delete(row)
        session.commit()
    images_deleted = images_skipped = images_failed = 0
    if delete_images:
        try:
            images_deleted, images_skipped, images_failed = _cleanup_images(candidates, output_dir=_output_dir())
        except Exception:
            current_app.logger.exception('分享记录已清理，但图片清理未完成')
            images_failed = sum(bool(raw) for raw, _ in candidates)
    message = f'已清理 {len(candidates)} 条分享记录'
    if delete_images:
        message += f'；图片已清理 {images_deleted} 张，保留或不存在 {images_skipped} 张，清理失败 {images_failed} 张'
    else:
        message += '；图片文件已保留'
    return {'status': 'success', 'msg': message, 'deleted': len(candidates),
            'images_deleted': images_deleted, 'images_skipped': images_skipped, 'images_failed': images_failed}


def _output_dir():
    from app import _wechat_share_output_dir
    return _wechat_share_output_dir()
