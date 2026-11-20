"""随库存业务事务保存审计，提交和回滚均由业务入口负责。"""
import json

from flask import request
from flask_login import current_user


def stage_order_audit(operation, order, *, old=None, new=None, reason=None, actor=None, target_name=None,
                      target_type=None):
    from app import OperationAudit, db, get_request_ip

    user = current_user if actor is None else actor
    db.session.add(OperationAudit(
        operation=operation, target_type=target_type or order.__tablename__,
        target_id=order.id if order is not None else None,
        target_name=target_name if target_name is not None else order.order_no,
        user_id=user.id, username=user.username,
        ip_address=get_request_ip(), user_agent=request.headers.get('User-Agent', '')[:500],
        status='success', reason=reason,
        old_data=json.dumps(old, ensure_ascii=False, default=str) if old is not None else None,
        new_data=json.dumps(new, ensure_ascii=False, default=str) if new is not None else None,
    ))


def snapshot_audit_row(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def stock_document_audit_checkpoint(order, *, reference_type=None, created=False):
    from app import StockTransaction, db

    kind = reference_type or order.__tablename__
    last_movement_id = db.session.query(db.func.max(StockTransaction.id)).filter(
        StockTransaction.reference_type == kind, StockTransaction.reference_id == order.id,
    ).scalar() or 0
    return (None if created else {'status': order.status}), last_movement_id


def stage_stock_document_snapshot(order, *, deleting, actor=None, operation=None,
                                  previous_status=None, after_movement_id=None, checkpoint=None,
                                  reference_type=None, target_name=None, reason=None, warehouse=None):
    from app import StockTransaction

    kind = reference_type or order.__tablename__
    name = target_name if target_name is not None else order.order_no
    old = {'status': previous_status} if previous_status is not None else None
    if checkpoint is not None:
        old, after_movement_id = checkpoint
    movements = StockTransaction.query.filter_by(reference_type=kind, reference_id=order.id)
    if after_movement_id is not None:
        movements = movements.filter(StockTransaction.id > after_movement_id)
    snapshot = {
        'order_no': name, 'warehouse': order.warehouse if warehouse is None else warehouse, 'status': order.status,
        'operator_id': order.operator_id,
        'business_type': getattr(order, 'business_type', getattr(order, 'adjustment_type', None)),
        'items': [snapshot_audit_row(item) for item in sorted(order.items, key=lambda item: item.id)],
        'movements': [snapshot_audit_row(row) for row in movements.order_by(StockTransaction.id)],
    }
    if deleting:
        stage_order_audit(operation or 'delete_' + kind, order, old=snapshot, reason=reason or '草稿删除',
                          actor=actor, target_name=name, target_type=kind)
    else:
        operation = operation or ('native_inbound' if kind == 'in_order' else 'native_outbound')
        stage_order_audit(operation, order, old=old, new=snapshot, reason=reason or '移动端完成',
                          actor=actor, target_name=name, target_type=kind)
