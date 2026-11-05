"""Page-scoped optimistic edit checks, serialized with the business transaction.

Legacy clients without a revision retain their established API contract. Current
web pages send a signed, user-bound snapshot of their header and all item rows.
"""
import hashlib
import json

from flask import current_app, g, has_request_context, jsonify, make_response, request
from flask_login import current_user
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import event, inspect
from sqlalchemy.exc import OperationalError

from db import db


# family: (header model, child relationship, inline child model, parent key)
DOCUMENTS = {
    'in_order': ('InOrder', 'items', 'InOrderItem', 'in_order_id'),
    'out_order': ('OutOrder', 'items', 'OutOrderItem', 'out_order_id'),
    'after_sale_out': ('AfterSaleOutOrder', 'items', None, None),
    'transfer': ('TransferOrder', 'items', None, None),
    'check': ('InventoryCheck', 'items', None, None),
    'adjustment': ('AdjustmentOrder', 'items', None, None),
    'purchase_request': ('PurchaseRequest', 'items', None, None),
    'purchase_order': ('PurchaseOrder', 'items', None, None),
    'sales': ('SalesOrder', 'items', None, None),
    'requisition': ('ProductionRequisition', 'items', None, None),
    'subcontract': ('SubcontractOrder', 'items', None, None),
    'subcontract_issue': ('SubcontractIssue', 'items', None, None),
    'subcontract_receive': ('SubcontractReceive', 'items', None, None),
    'opening_stock': ('OpeningStockDoc', 'lines', 'OpeningStock', 'doc_id'),
}
HEADER = 'X-WMS-Document-Revision'
NEW_DOCUMENT_INTENTS = frozenset({
    'copy_in_order', 'copy_in_order_to_out', 'convert_in_order_to_out_order',
    'create_in_order_push', 'copy_out_order', 'copy_check', 'copy_transfer',
    'copy_after_sale_out_order', 'copy_purchase_order', 'copy_sales_order', 'copy_subcontract',
    'create_purchase_order_from_request', 'create_in_order_from_purchase_order',
    'create_sales_outbound_draft',
})


def _family():
    path = request.path.strip('/').split('/')
    if len(path) > 1 and path[0] == 'subcontract' and path[1] in ('issue', 'receive'):
        return 'subcontract_' + path[1]
    if path[0] in ('other_in_order', 'other_out_order'):
        return path[0][6:]
    return path[0] if path[0] in DOCUMENTS else None


def _identity(family):
    """Resolve parent identity; inline row IDs must never be treated as headers."""
    import app as w
    data = request.args if request.method == 'GET' else (
        request.get_json(silent=True) if request.is_json else request.form)
    if not isinstance(data, dict) and not hasattr(data, 'get'):
        return None
    args = request.view_args or {}
    child_model, parent_key = DOCUMENTS[family][2:]
    inline = request.path in ('/in_order/item/update', '/out_order/item/update')
    opening_line = family == 'opening_stock' and request.path.startswith('/opening_stock/edit/')
    if inline or opening_line:
        raw_id = args.get('id') if opening_line else data.get('id')
        try:
            child = db.session.get(getattr(w, child_model), int(raw_id))
        except (TypeError, ValueError):
            return None
        # A row may have been deleted/replaced since the signed page was read.
        # Keep this distinct from a genuinely new document with no identity.
        return getattr(child, parent_key) if child else -1
    header = data.get('header') or {}
    raw_id = args.get('id') or data.get('order_id') or data.get('doc_id')
    if not raw_id and family == 'purchase_request':
        raw_id = data.get('request_id')
    if not raw_id and isinstance(header, dict):
        raw_id = header.get('order_id') or header.get('id')
    # Some legacy edit forms use id. Avoid interpreting an item id on inline APIs.
    if not raw_id and '/item/' not in request.path:
        raw_id = data.get('id')
    try:
        return int(raw_id) if int(raw_id) > 0 else None
    except (TypeError, ValueError):
        return None


def _fingerprint(order, relationship):
    def _columns(row):
        return {c.key: getattr(row, c.key) for c in inspect(type(row)).columns}
    items = sorted(getattr(order, relationship), key=lambda row: row.id)
    value = {'header': _columns(order), 'items': [_columns(row) for row in items]}
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str,
                                     ensure_ascii=False).encode('utf-8')).hexdigest()


def _sign(family, order):
    return URLSafeSerializer(current_app.secret_key, salt='wms-document-edit').dumps({
        'family': family, 'id': order.id, 'user': current_user.id,
        'fingerprint': _fingerprint(order, DOCUMENTS[family][1]),
    })


def page_revision():
    """Revision of the same ORM snapshot used to render a single document page."""
    if not has_request_context() or request.method != 'GET' or not current_user.is_authenticated:
        return {}
    family = _family()
    if not family:
        return {}
    identity = _identity(family)
    if not identity:
        return {}
    import app as w
    order = db.session.get(getattr(w, DOCUMENTS[family][0]), identity)
    if order is None:
        return {}
    prefixes = ['/' + family + '/']
    if family in ('subcontract_issue', 'subcontract_receive'):
        prefixes.append('/subcontract/' + family.split('_')[1] + '/')
    return {'token': _sign(family, order), 'prefixes': ','.join(prefixes)}


def guarded_document_write(view, *args, **kwargs):
    """Called only after role authorization; share the lock with existing routes."""
    token = request.headers.get(HEADER) or request.form.get('document_revision')
    family = _family()
    if request.method != 'POST' or not token or not family or getattr(g, 'document_edit_guard', False):
        return view(*args, **kwargs)
    # Existing-record POSTs are writes regardless of URL spelling (e.g. a check
    # line has no /update suffix, and an opening date uses just /date).
    # Copies/pushes have their separate new-document intent and source protocol.
    if request.endpoint in NEW_DOCUMENT_INTENTS:
        return view(*args, **kwargs)
    identity = _identity(family)
    if not identity:
        return view(*args, **kwargs)
    try:
        expected = URLSafeSerializer(current_app.secret_key, salt='wms-document-edit').loads(token)
    except BadSignature:
        return jsonify(status='error', msg='单据页面校验失败，请刷新后重试'), 409
    if identity == -1 and isinstance(expected, dict) and expected.get('family') == family and expected.get('user') == current_user.id:
        return jsonify(status='error', code='DOCUMENT_EDIT_CONFLICT',
                       msg='单据明细已被其他操作更新，本次修改未保存，请保留输入并刷新核对后重试'), 409
    if not isinstance(expected, dict) or (expected.get('family'), expected.get('id'), expected.get('user')) != (family, identity, current_user.id):
        return jsonify(status='error', msg='单据页面已变化，请刷新后重试'), 409
    import app as w
    model = getattr(w, DOCUMENTS[family][0])
    db.session.rollback()
    try:
        if db.engine.dialect.name == 'sqlite':
            db.session.connection().exec_driver_sql('BEGIN IMMEDIATE')
            order = db.session.get(model, identity)
        else:
            order = model.query.filter_by(id=identity).with_for_update().first()
        if order is None or _fingerprint(order, DOCUMENTS[family][1]) != expected.get('fingerprint'):
            db.session.rollback()
            return jsonify(status='error', code='DOCUMENT_EDIT_CONFLICT',
                           msg='单据已被其他操作更新，本次修改未保存，请保留输入并刷新核对后重试'), 409
    except OperationalError:
        db.session.rollback()
        return jsonify(status='error', msg='单据正在保存，请保留当前输入并稍后重试'), 503
    g.document_edit_guard = True
    saved = []
    session = db.session()

    def _capture_revision(active_session):
        # Capture inside the committing transaction, never after another writer
        # could commit content the current page has not actually seen.
        if not saved and inspect(order).persistent and order not in active_session.deleted:
            active_session.flush()
            active_session.refresh(order)
            active_session.expire(order, [DOCUMENTS[family][1]])
            saved.append(_sign(family, order))

    event.listen(session, 'before_commit', _capture_revision)
    try:
        response = make_response(view(*args, **kwargs))
        payload = response.get_json(silent=True)
        failed = isinstance(payload, dict) and (payload.get('status') == 'error' or payload.get('success') is False)
        if response.status_code < 300 and saved and not failed:
            response.headers[HEADER] = saved[0]
        return response
    finally:
        event.remove(session, 'before_commit', _capture_revision)
        db.session.rollback()
        g.pop('document_edit_guard', None)
