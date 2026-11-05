"""Page-scoped optimistic edit checks, serialized with the business transaction.

Edits require the signed snapshot read by the operator. New-document intents and
explicit state commands retain their existing protocols.
"""
import hashlib
import json

from flask import abort, current_app, g, has_request_context, jsonify, make_response, request
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
# These handlers replace page content, rather than apply an explicit command to
# the current state (complete/revert/copy, etc.). An old client must reopen the
# document; silently treating its submitted content as current loses other edits.
EDIT_ENDPOINTS = frozenset({
    'add_in_order', 'update_in_order', 'add_in_order_item',
    'batch_add_in_order_items', 'update_in_order_item', 'update_completed_in_order',
    'delete_in_order_item', 'in_order_item_delete_alias',
    'add_out_order', 'update_out_order', 'add_out_order_item',
    'batch_add_out_order_items', 'update_out_order_item', 'delete_out_order_item',
    'add_after_sale_out_order', 'save_transfer_table', 'add_transfer',
    'update_transfer', 'add_transfer_item', 'update_transfer_item',
    'delete_transfer_item', 'batch_delete_transfer_items', 'batch_add_transfer_items',
    'save_check_table', 'add_check', 'update_check', 'add_check_item',
    'update_check_item', 'delete_check_item', 'add_adjustment',
    'add_purchase_request', 'save_purchase_order', 'sales_order_edit',
    'save_requisition_table', 'add_requisition', 'update_requisition',
    'add_requisition_item', 'update_requisition_item', 'delete_requisition_item',
    'batch_delete_requisition_items', 'batch_add_requisition_items',
    'edit_subcontract_header', 'add_subcontract_item', 'delete_subcontract_item',
    'add_subcontract_issue_item', 'add_subcontract_receive_item',
    'edit_opening_stock', 'batch_save_opening_stock', 'save_opening_stock_doc',
    'update_opening_stock_doc_date',
})
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
        data = {}
    args = request.view_args or {}
    if any(type(value) is int and value >= 2**63 for value in args.values()):
        return -3

    def positive_id(value):
        if value is None or (isinstance(value, str) and value.strip() in ('', 'None', 'null')):
            return 0
        if isinstance(value, str) and len(value.strip()) <= 19 and value.strip().isdecimal():
            value = int(value.strip())
        if type(value) is not int or not 0 <= value < 2**63:
            raise ValueError('Invalid document identity')
        return value

    child_model, parent_key = DOCUMENTS[family][2:]
    inline = request.path in ('/in_order/item/update', '/out_order/item/update')
    opening_line = family == 'opening_stock' and request.path.startswith('/opening_stock/edit/')
    if inline or opening_line:
        raw_id = args.get('id') if opening_line else data.get('id')
        try:
            child_id = positive_id(raw_id)
            if not child_id:
                return None
            child = db.session.get(getattr(w, child_model), child_id)
        except (TypeError, ValueError):
            return -3
        # A row may have been deleted/replaced since the signed page was read.
        # Keep this distinct from a genuinely new document with no identity.
        return (getattr(child, parent_key) or -2) if child else -1
    try:
        # URL identity is authoritative for handlers with a fixed target.
        if args.get('id') is not None:
            return positive_id(args['id']) or None
        header = data.get('header') or {}
        if not isinstance(header, dict):
            if request.is_json:
                return -3
            header = {}
        candidates = [data.get('order_id'), data.get('doc_id'),
                      header.get('order_id'), header.get('id')]
        if family == 'purchase_request':
            candidates.append(data.get('request_id'))
        if '/item/' not in request.path:
            candidates.append(data.get('id'))
        identities = {positive_id(value) for value in candidates} - {0}
        # Never let a zero/invalid alias hide the ID actually consumed by a view.
        return identities.pop() if len(identities) == 1 else (-3 if identities else None)
    except (TypeError, ValueError):
        return -3


def _fingerprint(order, relationship):
    def _columns(row):
        return {c.key: getattr(row, c.key) for c in inspect(type(row)).columns}
    value = _columns(order)
    if relationship:
        items = sorted(getattr(order, relationship), key=lambda row: row.id)
        value = {'header': value, 'items': [_columns(row) for row in items]}
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str,
                                     ensure_ascii=False).encode('utf-8')).hexdigest()


def _sign(family, order):
    return URLSafeSerializer(current_app.secret_key, salt='wms-document-edit').dumps({
        'family': family, 'id': order.id, 'user': current_user.id,
        'fingerprint': _fingerprint(order, DOCUMENTS[family][1]),
    })


def opening_line_revision(opening, user_id):
    """Version of exactly the native opening-stock row that the user read."""
    return URLSafeSerializer(current_app.secret_key, salt='wms-opening-line-edit').dumps({
        'id': opening.id, 'user': user_id, 'fingerprint': _fingerprint(opening, None),
    })


def opening_line_revision_matches(opening, user_id, token):
    """No unsigned fallback; malformed, foreign-user and stale versions fail."""
    if not isinstance(token, str) or not token:
        return False
    serializer = URLSafeSerializer(current_app.secret_key, salt='wms-opening-line-edit')
    try:
        return serializer.loads(token) == serializer.loads(opening_line_revision(opening, user_id))
    except BadSignature:
        return False


def page_revision():
    """Revision of the same ORM snapshot used to render a single document page."""
    if not has_request_context() or request.method != 'GET' or not current_user.is_authenticated:
        return {}
    family = _family()
    if not family:
        return {}
    identity = _identity(family)
    if identity == -3:
        return {}
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
    if request.method != 'POST' or not family or getattr(g, 'document_edit_guard', False):
        return view(*args, **kwargs)
    # Existing-record POSTs are writes regardless of URL spelling (e.g. a check
    # line has no /update suffix, and an opening date uses just /date).
    # Copies/pushes have their separate new-document intent and source protocol.
    if request.endpoint in NEW_DOCUMENT_INTENTS:
        return view(*args, **kwargs)
    identity = _identity(family)
    if identity == -3:
        return jsonify(status='error', code='INVALID_DOCUMENT_ID',
                       msg='单据标识格式不正确或不一致，请刷新核对后重试'), 400
    if not identity:
        return view(*args, **kwargs)
    import app as w
    orphan_line = identity == -2 and family == 'opening_stock'
    model = w.OpeningStock if orphan_line else getattr(w, DOCUMENTS[family][0])
    relationship = None if orphan_line else DOCUMENTS[family][1]
    if orphan_line:
        identity = (request.view_args or {})['id']
    if not token:
        if request.endpoint in EDIT_ENDPOINTS:
            if identity == -1 or db.session.get(model, identity) is None:
                abort(404)
            return jsonify(status='error', code='DOCUMENT_REVISION_REQUIRED',
                           msg='缺少单据版本，本次修改未保存，请保留输入并重新打开单据后再编辑'), 409
        return view(*args, **kwargs)
    try:
        salt = 'wms-opening-line-edit' if orphan_line else 'wms-document-edit'
        expected = URLSafeSerializer(current_app.secret_key, salt=salt).loads(token)
    except BadSignature:
        return jsonify(status='error', msg='单据页面校验失败，请刷新后重试'), 409
    if identity == -1 and isinstance(expected, dict) and expected.get('family') == family and expected.get('user') == current_user.id:
        return jsonify(status='error', code='DOCUMENT_EDIT_CONFLICT',
                       msg='单据明细已被其他操作更新，本次修改未保存，请保留输入并刷新核对后重试'), 409
    if (not isinstance(expected, dict) or
            (expected.get('id'), expected.get('user')) != (identity, current_user.id) or
            (not orphan_line and expected.get('family') != family)):
        return jsonify(status='error', msg='单据页面已变化，请刷新后重试'), 409
    db.session.rollback()
    try:
        if db.engine.dialect.name == 'sqlite':
            db.session.connection().exec_driver_sql('BEGIN IMMEDIATE')
            order = db.session.get(model, identity)
        else:
            order = model.query.filter_by(id=identity).with_for_update().first()
        if order is None or _fingerprint(order, relationship) != expected.get('fingerprint'):
            db.session.rollback()
            return jsonify(status='error', code='DOCUMENT_EDIT_CONFLICT',
                           msg='单据已被其他操作更新，本次修改未保存，请保留输入并刷新核对后重试'), 409
    except OperationalError:
        db.session.rollback()
        return jsonify(status='error', msg='单据正在保存，请保留当前输入并稍后重试'), 503
    # A comparison must not leave old details cached for a view that replaces
    # rows by foreign key and then calculates a total from the relationship.
    if relationship:
        db.session.expire(order, [relationship])
    g.document_edit_guard = True
    saved = []
    session = db.session()

    def _capture_revision(active_session):
        # Capture inside the committing transaction, never after another writer
        # could commit content the current page has not actually seen.
        if not saved and inspect(order).persistent and order not in active_session.deleted:
            active_session.flush()
            active_session.refresh(order)
            if relationship:
                active_session.expire(order, [relationship])
            saved.append(opening_line_revision(order, current_user.id) if orphan_line else _sign(family, order))

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
