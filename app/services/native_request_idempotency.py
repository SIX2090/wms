"""Native request ownership and business/result atomicity on the existing receipt table.

修复子项：AI-ASSISTANT-MOBILE-001-FIX-IDEMPOTENCY-20261107-001（交付状态见唯一台账）。
"""
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import json
import secrets

from flask import current_app, jsonify, make_response, request
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from db import db
from models.core import MobileApiRequest


_LEASE_SECONDS = 120


class _RequestOwnershipLost(RuntimeError):
    pass


def _error(message, code=503):
    return make_response(jsonify(status='error', success=False, msg=message), code)


def _busy():
    response = _error('该请求正在处理，请保留原请求编号稍后重试')
    response.headers['Retry-After'] = '1'
    return response


def _claim(user_id, endpoint, key, fingerprint, compatible_fingerprints=()):
    pending = json.dumps({'fingerprint': fingerprint, 'owner': secrets.token_hex(16)},
                         separators=(',', ':'))
    receipt = MobileApiRequest(user_id=user_id, endpoint=endpoint, request_key=key,
                               status_code=0, response_json=pending)
    db.session.rollback()  # Drop the authentication/read snapshot before the unique claim.
    try:
        db.session.add(receipt)
        db.session.flush()
        receipt_id = receipt.id
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = MobileApiRequest.query.filter_by(user_id=user_id, endpoint=endpoint,
                                                    request_key=key).first()
        if existing is None:
            return None, _busy()
        try:
            saved = json.loads(existing.response_json)
        except (TypeError, ValueError):
            saved = {}
        if not isinstance(saved, dict) or saved.get('fingerprint') not in (fingerprint, *compatible_fingerprints):
            return None, _error('请求内容不同或历史内容无法确认，请先核对原操作，勿重复提交', 409)
        if 200 <= existing.status_code < 300 and 'response' in saved:
            return None, make_response(jsonify(saved['response']), existing.status_code)
        if existing.status_code != 0 or not saved.get('owner'):
            return None, _error('历史请求结果无法确认，请先核对原操作', 409)
        if not existing.created_at or existing.created_at > datetime.now() - timedelta(seconds=_LEASE_SECONDS):
            return None, _busy()
        receipt_id, previous = existing.id, existing.response_json
        db.session.rollback()
        changed = MobileApiRequest.query.filter_by(id=receipt_id, status_code=0,
                                                   response_json=previous).update(
            {'response_json': pending, 'created_at': datetime.now()}, synchronize_session=False)
        if changed != 1:
            db.session.rollback()
            return None, _busy()
        db.session.commit()
    return {'id': receipt_id, 'pending': pending, 'fingerprint': fingerprint,
            'atomic': False, 'finalizing': False, 'invalid': False}, None


def activate_native_business_transaction():
    """Fence the owner before its first write, and keep all inner commits uncommitted."""
    session = db.session()
    state = session.info.get('native_request')
    if state is None or state['atomic']:
        return
    state['atomic'] = True
    with session.no_autoflush:
        owned = session.query(MobileApiRequest).filter_by(
            id=state['id'], status_code=0, response_json=state['pending']).update(
                {'status_code': 0}, synchronize_session=False)
    if owned != 1:
        state['invalid'] = True
        state['ownership_lost'] = True
        raise _RequestOwnershipLost('native request ownership changed')


def _release(state):
    try:
        MobileApiRequest.query.filter_by(id=state['id'], status_code=0,
                                         response_json=state['pending']).delete(synchronize_session='fetch')
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Native request reservation release failed; retry remains fenced')


def native_request_idempotent(endpoint):
    """Replay exact content and atomically commit every native business result."""
    def decorator(view):
        @wraps(view)
        def wrapped(user, *args, **kwargs):
            payload = request.get_json(silent=True)
            if payload is None:
                payload = {}
            if not isinstance(payload, dict):
                return _error('请求数据必须为JSON对象', 400)
            key = request.headers.get('X-Idempotency-Key') or payload.get('request_id')
            if key is None:
                key = ''
            if not isinstance(key, str):
                return _error('幂等请求号必须为字符串', 400)
            key = key.strip()
            if not key:
                return view(user, *args, **kwargs)
            if len(key) > 120:
                return _error('幂等请求号不能超过120个字符', 400)
            content = {'path': request.path, 'method': request.method,
                       'query': request.query_string.decode('latin1'),
                       'payload': {k: v for k, v in payload.items() if k != 'request_id'}}
            try:
                encoded = json.dumps(content, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode('utf-8')
            except (TypeError, ValueError):
                return _error('请求内容包含无效数值或格式', 400)
            fingerprint = hashlib.sha256(encoded).hexdigest()
            compatible = ()
            if request.method == 'POST' and not request.query_string:
                legacy = {'path': request.path, 'payload': content['payload']}
                compatible = (hashlib.sha256(json.dumps(
                    legacy, sort_keys=True, ensure_ascii=False, allow_nan=False,
                    separators=(',', ':')).encode('utf-8')).hexdigest(),)
            actor_id = user.id
            try:
                state, replay = _claim(actor_id, endpoint, key, fingerprint, compatible)
            except Exception:
                db.session.rollback()
                current_app.logger.exception('Native request reservation failed before business execution')
                return _error('请求暂未保存，请保留原请求编号重试')
            if state is None:
                return replay
            session = db.session()
            session.info['native_request'] = state
            committed = False
            try:
                response = make_response(view(user, *args, **kwargs))
                if state.get('ownership_lost'):
                    raise _RequestOwnershipLost('native request owner was replaced')
                if not 200 <= response.status_code < 300:
                    return response
                if state['invalid']:
                    raise _RequestOwnershipLost('native handler rolled back its transaction')
                activate_native_business_transaction()
                receipt = session.get(MobileApiRequest, state['id'])
                if receipt is None:
                    raise _RequestOwnershipLost('native receipt disappeared')
                receipt.status_code = response.status_code
                receipt.response_json = json.dumps(
                    {'fingerprint': fingerprint, 'response': response.get_json()}, ensure_ascii=False)
                state['finalizing'] = True
                session.commit()
                committed = True
                return response
            except HTTPException as exc:
                return make_response(exc)
            except Exception:
                # A durable commit may succeed before a listener or transport reports failure.
                # Reopen the session and trust only this actor/key's committed exact receipt.
                if state['finalizing']:
                    session.info.pop('native_request', None)
                    session.close()
                    db.session.remove()
                    try:
                        stored = MobileApiRequest.query.filter_by(
                            id=state['id'], user_id=actor_id, endpoint=endpoint, request_key=key).first()
                        saved = json.loads(stored.response_json) if stored is not None else {}
                        if (stored is not None and 200 <= stored.status_code < 300
                                and isinstance(saved, dict) and saved.get('fingerprint') == fingerprint
                                and isinstance(saved.get('response'), dict)):
                            committed = True
                            return make_response(jsonify(saved['response']), stored.status_code)
                    except Exception:
                        current_app.logger.exception('Native committed receipt recovery could not be confirmed')
                current_app.logger.exception('Native request transaction rolled back; retry with original key')
                return _error('本次操作未保存，请保留原请求编号重试')
            finally:
                session.info.pop('native_request', None)
                session.rollback()
                if not committed:
                    _release(state)
        return wrapped
    return decorator
