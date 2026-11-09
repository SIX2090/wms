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


def mobile_document_idempotent(view):
    """H5 session/Bearer requests share atomic receipts with web saves."""
    return _document_idempotent(view, mobile=True)


# no-test:reason=Shared implementation exercised through both public decorators.
def _document_idempotent(view, *, mobile):
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
            if editing and not mobile:
                return view(*args, **kwargs)
            payload = {k: v for k, v in payload.items() if k != 'csrf_token'}
            if mobile:
                payload.pop('request_id', None)
                payload = {'payload': payload, 'path': request.path}
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                                 separators=(',', ':')).encode()).hexdigest()
        if mobile and not current_user.is_authenticated:
            from app import get_bearer_user
            user_id = get_bearer_user().id
        else:
            user_id = current_user.id
        endpoint = ('mobile:' if mobile else 'web:') + view.__name__
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
    """Native business writes and their exact successful response share one commit."""
    def _decorate(view):
        @wraps(view)
        def _wrapped(user, *args, **kwargs):
            from app import api_json_error
            payload = request.get_json(silent=True) or {}
            if not isinstance(payload, dict):
                return api_json_error('请求数据必须为JSON对象', 400)
            key = request.headers.get('X-Idempotency-Key') or payload.get('request_id')
            if key is None:
                key = ''
            if not isinstance(key, str):
                return api_json_error('幂等请求号必须为字符串', 400)
            key = key.strip()
            if not key:
                return view(user, *args, **kwargs)
            if len(key) > 120:
                return api_json_error('幂等请求号不能超过120个字符', 400)
            try:
                content = {name: value for name, value in payload.items() if name != 'request_id'}
                fingerprint = hashlib.sha256(json.dumps(
                    {'payload':content, 'path':request.path, 'method':request.method,
                     'query':request.query_string.decode('latin1')},
                    sort_keys=True, ensure_ascii=False, allow_nan=False,
                    separators=(',', ':')).encode('utf-8')).hexdigest()
            except (ValueError, TypeError, UnicodeError):
                return api_json_error('请求数据包含无效数值或字符', 400)

            def _replay(existing):
                try:
                    saved = json.loads(existing.response_json)
                    if not isinstance(saved, dict) or not 100 <= existing.status_code <= 599:
                        raise ValueError('Invalid native receipt')
                except (TypeError, ValueError):
                    return api_json_error('历史保存响应无法确认，请人工核对原单据', 503)
                if 'fingerprint' in saved and 'response' in saved:
                    if saved['fingerprint'] != fingerprint:
                        return api_json_error('本次请求已保存其他内容，请使用原单据核对', 409)
                    saved = saved['response']
                # Old native receipts contain the response itself; do not guess their payload.
                return jsonify(saved), existing.status_code

            actor_id = user.id
            if getattr(g, 'web_document_receipt', None) is not None:
                return api_json_error('保存事务不能重复嵌套，请稍后重试', 500)
            db.session.rollback()
            existing = MobileApiRequest.query.filter_by(
                user_id=actor_id, endpoint=endpoint, request_key=key).first()
            if existing is not None:
                return _replay(existing)
            receipt = MobileApiRequest(user_id=actor_id, endpoint=endpoint, request_key=key,
                                       status_code=0, response_json='')
            try:
                db.session.add(receipt)
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
                existing = MobileApiRequest.query.filter_by(
                    user_id=actor_id, endpoint=endpoint, request_key=key).first()
                if existing is None:
                    return api_json_error('保存请求未能确认，请稍后重试', 503)
                return _replay(existing)
            except OperationalError:
                db.session.rollback()
                return api_json_error('保存暂时繁忙，请保留输入并重试', 503)

            session = db.session()
            staged = None
            committed = None

            def _before_commit(active):
                nonlocal staged
                if active is not session or inspect(receipt).session is not session:
                    raise RuntimeError('Native receipt was detached before business commit')
                if receipt.status_code != 200:
                    raise RuntimeError('Native response must be staged before business commit')
                saved = json.loads(receipt.response_json)
                if saved.get('fingerprint') != fingerprint or not isinstance(saved.get('response'), dict):
                    raise RuntimeError('Native response receipt does not match this request')
                staged = saved['response']

            def _after_commit(active):
                nonlocal committed
                # Releasing a SAVEPOINT is not a durable business commit.
                if active is session and not active.in_nested_transaction():
                    committed = staged

            g.web_document_receipt = (receipt, fingerprint)
            g.native_document_session = session
            event.listen(session, 'before_commit', _before_commit)
            event.listen(session, 'after_commit', _after_commit)
            try:
                response = view(user, *args, **kwargs)
                if committed is not None:
                    return jsonify(committed), 200
                response_object = response[0] if isinstance(response, tuple) else response
                code = response[1] if isinstance(response, tuple) else response_object.status_code
                if 200 <= code < 300:
                    return api_json_error('保存事务未完成，请保留输入并重试', 500)
                return response
            except Exception:
                if committed is not None:
                    return jsonify(committed), 200
                from flask import current_app
                current_app.logger.exception('Native atomic document save failed')
                return api_json_error('保存未完成，请保留输入并重试', 500)
            finally:
                event.remove(session, 'before_commit', _before_commit)
                event.remove(session, 'after_commit', _after_commit)
                db.session.rollback()
                g.pop('native_document_session', None)
                g.pop('web_document_receipt', None)
        return _wrapped
    return _decorate


def begin_native_document_write():
    """Keep a flushed native claim; otherwise obtain the existing SQLite write lock."""
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
