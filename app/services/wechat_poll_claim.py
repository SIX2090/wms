"""Atomic poll claims and bounded token predicates for existing share logs."""
import hashlib
import hmac
import secrets


def digest_token(token):
    if (not isinstance(token, str) or len(token) != 64
            or any(char not in '0123456789abcdef' for char in token)):
        return None
    return hashlib.sha256(token.encode('ascii')).hexdigest()


def claim_log(session, Log, log_id):
    """CAS in caller transaction; caller commits before returning the token."""
    token = secrets.token_hex(32)
    row = session.query(Log).filter_by(id=log_id, status='queued_v2').first()
    if row is None:
        return None
    original = row.message or ''
    suffix = '\n[claim-sha256:' + digest_token(token) + ']'
    if len(original + suffix) > 500:
        session.query(Log).filter_by(id=log_id, status='queued_v2', message=row.message).update(
            {'status': 'uncertain'}, synchronize_session=False)
        return None
    changed = session.query(Log).filter_by(id=log_id, status='queued_v2', message=row.message).update(
        {'status': 'sending', 'message': original + suffix}, synchronize_session=False)
    return token if changed == 1 else None


def claimed_message(log, token):
    digest = digest_token(token)
    if digest is None or log.status not in ('sending', 'delivery_started') or not isinstance(log.message, str):
        return None
    suffix = '\n[claim-sha256:' + digest + ']'
    if not hmac.compare_digest(log.message[-len(suffix):].encode('utf-8'), suffix.encode('ascii')):
        return None
    return log.message[:-len(suffix)]


def visible_message(status, message):
    text = message or ''
    if status not in ('sending', 'delivery_started'):
        return text
    prefix, marker, suffix = text.rpartition('\n[claim-sha256:')
    if marker and len(suffix) == 65 and suffix.endswith(']') and all(c in '0123456789abcdef' for c in suffix[:-1]):
        return prefix
    return text
