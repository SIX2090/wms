"""Bind human merge consent to the reviewed pair and current affected data."""
import hashlib
import json

from flask import current_app
from flask_login import current_user
from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy import select

from db import db

PREVIEW_MAX_AGE = 300

class MergePreviewChanged(ValueError):
    """The previous review no longer authorizes this operation."""

def _signer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='material-merge-preview-v1')

def _fingerprint(preview):
    from app import Material, MATERIAL_MERGE_REF_TABLES, MATERIAL_MERGE_QUANTITY_TABLES
    pair = sorted((preview['source']['id'], preview['target']['id']))
    digest = hashlib.sha256(json.dumps(preview, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8'))
    names = (Material.__tablename__, 'ai_material_alias') + tuple(MATERIAL_MERGE_REF_TABLES) + tuple(MATERIAL_MERGE_QUANTITY_TABLES)
    for name in sorted(set(names)):
        table = db.metadata.tables.get(name)
        if table is None:
            continue
        column = table.c.id if name == Material.__tablename__ else table.c.get('material_id')
        if column is None:
            continue
        query = select(table).where(column.in_(pair)).order_by(*table.primary_key.columns)
        for row in db.session.execute(query):
            value = [name, dict(row._mapping)]
            digest.update(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8'))
    return digest.hexdigest()

def issue_merge_preview(preview, keep_alias=True):
    """No writes: return the displayed preview with an expiring signed receipt."""
    claim = {'source': preview['source']['id'], 'target': preview['target']['id'],
             'actor': str(current_user.get_id()), 'keep_alias': bool(keep_alias),
             'fingerprint': _fingerprint(preview)}
    return dict(preview, preview_token=_signer().dumps(claim))

def require_merge_preview(token, target_id, source_id, keep_alias, identity_confirmed):
    """Verify consent and recheck under the same write transaction as merging."""
    from app import Material, material_merge_preview
    message = '预览已变化或失效，请重新预览并确认合并影响。'
    expected = {'source': source_id, 'target': target_id,
                'actor': str(current_user.get_id()), 'keep_alias': bool(keep_alias)}
    try:
        claim = _signer().loads(token, max_age=PREVIEW_MAX_AGE)
    except (BadData, TypeError, ValueError):
        raise MergePreviewChanged(message) from None
    if not isinstance(claim, dict) or any(claim.get(key) != value for key, value in expected.items()):
        raise MergePreviewChanged(message)
    if db.session.new or db.session.dirty or db.session.deleted:
        raise MergePreviewChanged('请先保存当前修改，再重新预览合并影响。')
    # End the read-only request transaction, then reload under a real write lock.
    # This does not commit incidental user changes or release the lock before merge.
    db.session.rollback()
    if db.engine.dialect.name == 'sqlite':
        db.session.connection().exec_driver_sql('BEGIN IMMEDIATE')
    else:
        db.session.execute(select(Material).where(Material.id.in_(sorted((target_id, source_id))))
                           .order_by(Material.id).with_for_update()).scalars().all()
    fresh = material_merge_preview(target_id, source_id, allow_identity_difference=identity_confirmed)
    if claim.get('fingerprint') != _fingerprint(fresh):
        raise MergePreviewChanged(message)
