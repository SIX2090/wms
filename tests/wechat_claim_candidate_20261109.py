"""Isolated protocol prototype; not imported by WMS or connected to a server."""
import hashlib
import hmac
import secrets


def token_hash(token):
    if (not isinstance(token, str) or len(token) != 64
            or any(char not in '0123456789abcdef' for char in token)):
        return None
    return hashlib.sha256(token.encode('ascii')).hexdigest()


def claim(db, task_id, protocol, *, fail_before_commit=False):
    if protocol != 'v2':
        raise ValueError('旧版助手不支持安全领取，请升级后再使用')
    token = secrets.token_hex(32)
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT message FROM task WHERE id=? AND status='queued_v2'", (task_id,)).fetchone()
        if row is None:
            db.rollback()
            return None
        original = row[0] or ''
        suffix = '\n[claim-sha256:' + token_hash(token) + ']'
        if len(original + suffix) > 500:
            db.rollback()
            raise ValueError('记录信息过长，需人工核对，未领取')
        changed = db.execute("UPDATE task SET status='sending', message=? "
                             "WHERE id=? AND status='queued_v2' AND message IS ?",
                             (original + suffix, task_id, row[0])).rowcount
        if not changed:
            db.rollback()
            return None
        if fail_before_commit:
            raise RuntimeError('synthetic commit failure')
        db.commit()
        return token
    except Exception:
        db.rollback()
        raise


def can_read_image(db, task_id, token):
    digest = token_hash(token)
    if digest is None:
        return False
    row = db.execute("SELECT message FROM task WHERE id=? AND status='sending'", (task_id,)).fetchone()
    suffix = '\n[claim-sha256:' + digest + ']'
    return bool(row and row[0] and hmac.compare_digest(
        row[0][-len(suffix):].encode('utf-8'), suffix.encode('ascii')))


def report(db, task_id, token, result, report_message=''):
    digest = token_hash(token)
    if digest is None:
        return False
    # A failure or pending report may follow a real send: never auto-requeue.
    status = 'sent' if result == 'sent' else 'uncertain'
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT message FROM task WHERE id=? AND status='sending'", (task_id,)).fetchone()
        suffix = '\n[claim-sha256:' + digest + ']'
        if not row or not row[0] or not hmac.compare_digest(
                row[0][-len(suffix):].encode('utf-8'), suffix.encode('ascii')):
            db.rollback()
            return False
        original = row[0][:-len(suffix)]
        report_message = str(report_message or '')
        if token in report_message:
            db.rollback()
            return False
        updated_message = original + ('\n回报：' + report_message if report_message else '')
        if len(updated_message) > 500:
            db.rollback()
            return False
        changed = db.execute("UPDATE task SET status=?,message=? WHERE id=? AND status='sending' AND message=?",
                             (status, updated_message, task_id, row[0])).rowcount
        if not changed:
            db.rollback()
            return False
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def reserve_manual_force(db, task_id, confirmed):
    """Only after human confirmation; never steal an active task or direct attempt."""
    if confirmed is not True:
        return False
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT status FROM task WHERE id=?', (task_id,)).fetchone()
        active = db.execute("SELECT 1 FROM direct_attempt WHERE task_id=? AND state='sending'", (task_id,)).fetchone()
        if not row or row[0] in ('queued_v2', 'sending') or active:
            db.rollback()
            return False
        db.execute("INSERT INTO direct_attempt(task_id,state) VALUES (?, 'sending')", (task_id,))
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def cleanup_task(db, task_id):
    """No removal of queued, ambiguous or in-flight synthetic task records."""
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT status FROM task WHERE id=?', (task_id,)).fetchone()
        active = db.execute("SELECT 1 FROM direct_attempt WHERE task_id=? AND state='sending'", (task_id,)).fetchone()
        if not row or row[0] not in ('sent', 'failed', 'skipped') or active:
            db.rollback()
            return False
        db.execute('DELETE FROM task WHERE id=?', (task_id,))
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def visible_message(status, message):
    """Hide internal digest in UI while leaving human diagnostics untouched."""
    text = message or ''
    if status != 'sending':
        return text
    prefix, marker, suffix = text.rpartition('\n[claim-sha256:')
    if marker and len(suffix) == 65 and suffix.endswith(']'):
        digest = suffix[:-1]
        if all(char in '0123456789abcdef' for char in digest):
            return prefix
    return text


def remove_synthetic_expired_image(db, image_id):
    """Model selection only; real file deletion/atomicity is intentionally unproven."""
    try:
        db.execute('BEGIN IMMEDIATE')
        protected = db.execute("SELECT 1 FROM task_images ti JOIN task t ON t.id=ti.task_id "
                               "WHERE ti.image_id=? AND t.status IN ('pending','queued_v2','sending','uncertain') LIMIT 1",
                               (image_id,)).fetchone()
        direct = db.execute("SELECT 1 FROM task_images ti JOIN direct_attempt d ON d.task_id=ti.task_id "
                            "WHERE ti.image_id=? AND d.state='sending' LIMIT 1", (image_id,)).fetchone()
        if protected or direct:
            db.rollback()
            return False
        changed = db.execute('DELETE FROM synthetic_image WHERE id=?', (image_id,)).rowcount
        db.commit()
        return bool(changed)
    except Exception:
        db.rollback()
        raise


def fetch_claimed_image(session, base_url, task_id, token):
    """Use the configured origin and canonical task path, without redirects."""
    if (base_url != 'https://synthetic.invalid'
            or not isinstance(task_id, int) or isinstance(task_id, bool) or task_id <= 0
            or token_hash(token) is None):
        raise ValueError('模拟任务目标无效')
    response = session.get(base_url + '/api/wechat_helper/task/' + str(task_id) + '/image',
                           headers={'X-WMS-Task-Claim': token}, allow_redirects=False)
    if response.status_code < 200 or response.status_code >= 300:
        raise ValueError('模拟图片获取失败，保持领取占位')
    return response.content
