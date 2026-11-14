"""Atomic replay for authenticated document saves; shares the existing receipt table."""
from functools import wraps
import hashlib
import json

from flask import g, jsonify, request
from flask_login import current_user
from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError, OperationalError

from db import db
from models.core import MobileApiRequest


def web_document_idempotent(view):
    return _document_idempotent(view, mobile=False)


def web_document_command_idempotent(view):
    """Replay one explicit copy/push intent; a new key remains a new command."""
    return _document_idempotent(view, mobile=False, command=True)


def mobile_document_idempotent(view):
    """H5 session/Bearer requests share atomic receipts with web saves."""
    return _document_idempotent(view, mobile=True)


# no-test:reason=Shared implementation exercised through both public decorators.
def _document_idempotent(view, *, mobile, command=False):
    """Claim a request before business writes; receipt commits with the document."""
    @wraps(view)
    def _wrapped(*args, **kwargs):
        key = (request.headers.get('X-Idempotency-Key') or '').strip()
        if mobile and not key:
            body = request.get_json(silent=True)
            key = body.get('request_id', '') if isinstance(body, dict) else ''
            if not isinstance(key, str):
                return jsonify(status='error', msg='保存请求编号必须为字符串'), 400
            key = key.strip()
        if not key:
            return view(*args, **kwargs)
        if len(key) > 120:
            return jsonify(status='error', msg='保存请求编号过长'), 400
        payload = request.get_json(silent=True) if request.is_json else request.form.to_dict(flat=False)
        if isinstance(payload, dict):
            header = payload.get('header') or {}
            identity = payload.get('order_id') or payload.get('id') or payload.get('request_id')
            if not identity and isinstance(header, dict):
                identity = header.get('order_id') or header.get('id') or header.get('request_id')
            if isinstance(identity, list):
                identity = identity[0] if identity else None
            try:
                editing = int(identity or 0) > 0
            except (TypeError, ValueError):
                editing = False
            if editing and not mobile and not command:
                return view(*args, **kwargs)
            payload = {k: v for k, v in payload.items() if k != 'csrf_token'}
            if mobile:
                payload.pop('request_id', None)
                payload = {'payload': payload, 'path': request.path}
        if command:
            payload = {'payload': payload, 'path': request.path, 'view_args': request.view_args or {}}
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                                 separators=(',', ':')).encode()).hexdigest()
        if mobile and not current_user.is_authenticated:
            from app import get_bearer_user
            user_id = get_bearer_user().id
        else:
            user_id = current_user.id
        endpoint_name = (request.endpoint or view.__name__) if command else view.__name__
        endpoint = ('mobile:' if mobile else 'web:') + endpoint_name
        # Authentication may have opened a read transaction. Start the claim without
        # upgrading a stale SQLite snapshot; this decorator runs before business writes.
        db.session.rollback()
        receipt = MobileApiRequest(user_id=user_id, endpoint=endpoint, request_key=key,
                                   status_code=0, response_json='')
        try:
            db.session.add(receipt)
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            existing = MobileApiRequest.query.filter_by(user_id=user_id, endpoint=endpoint,
                                                        request_key=key).first()
            if existing is None:
                return jsonify(status='error', msg='保存请求未能确认，请稍后重试'), 503
            saved = json.loads(existing.response_json or '{}')
            if saved.get('fingerprint') != fingerprint:
                return jsonify(status='error', msg='本次请求已保存其他内容，请打开原单据核对后再编辑'), 409
            return jsonify(saved['response']), existing.status_code
        except OperationalError:
            db.session.rollback()
            return jsonify(status='error', msg='保存暂时繁忙，请保留当前页面并重试'), 503
        g.web_document_receipt = (receipt, fingerprint)
        try:
            return view(*args, **kwargs)
        finally:
            # All error/validation exits release the claim. Committed receipts survive.
            db.session.rollback()
            g.pop('web_document_receipt', None)
    return _wrapped


def stage_document_response(payload):
    """Persist the exact success payload inside the caller's business transaction."""
    pending = getattr(g, 'web_document_receipt', None)
    if pending is None:
        return
    receipt, fingerprint = pending
    receipt.status_code = 200
    receipt.response_json = json.dumps({'fingerprint': fingerprint, 'response': payload},
                                      ensure_ascii=False)


def native_document_idempotent(endpoint):
    """Compatibility entrypoint for the unified fenced native request transaction."""
    from services.native_request_idempotency import native_request_idempotent
    return native_request_idempotent(endpoint)


def begin_native_document_write():
    """Keep a flushed native claim; otherwise obtain the existing SQLite write lock."""
    if db.session().info.get('native_request') is not None:
        from services.native_request_idempotency import activate_native_business_transaction
        activate_native_business_transaction()
        return
    active = getattr(g, 'native_document_session', None)
    if active is not None:
        pending = getattr(g, 'web_document_receipt', None)
        if (active is not db.session() or not pending or
                inspect(pending[0]).session is not active or not active.in_transaction()):
            raise RuntimeError('Native request lost its atomic write claim')
        return
    db.session.rollback()
    if db.engine.dialect.name == 'sqlite':
        db.session.connection().exec_driver_sql('BEGIN IMMEDIATE')
