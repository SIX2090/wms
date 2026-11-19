"""随库存业务事务保存审计，提交和回滚均由业务入口负责。"""
import json

from flask import request
from flask_login import current_user


def stage_order_audit(operation, order, *, old=None, new=None, reason=None, actor=None, target_name=None):
    from app import OperationAudit, db, get_request_ip

    user = current_user if actor is None else actor
    db.session.add(OperationAudit(
        operation=operation, target_type=order.__tablename__, target_id=order.id,
        target_name=target_name if target_name is not None else order.order_no,
        user_id=user.id, username=user.username,
        ip_address=get_request_ip(), user_agent=request.headers.get('User-Agent', '')[:500],
        status='success', reason=reason,
        old_data=json.dumps(old, ensure_ascii=False, default=str) if old is not None else None,
        new_data=json.dumps(new, ensure_ascii=False, default=str) if new is not None else None,
    ))


def snapshot_audit_row(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def stage_stock_document_snapshot(order, *, deleting, actor=None, operation=None,
                                  previous_status=None, after_movement_id=None):
    from app import StockTransaction

    kind = order.__tablename__
    movements = StockTransaction.query.filter_by(reference_type=kind, reference_id=order.id)
    if after_movement_id is not None:
        movements = movements.filter(StockTransaction.id > after_movement_id)
    snapshot = {
        'order_no': order.order_no, 'warehouse': order.warehouse, 'status': order.status,
        'operator_id': order.operator_id, 'business_type': order.business_type,
        'items': [snapshot_audit_row(item) for item in sorted(order.items, key=lambda item: item.id)],
        'movements': [snapshot_audit_row(row) for row in movements.order_by(StockTransaction.id)],
    }
    if deleting:
        stage_order_audit('delete_' + kind, order, old=snapshot, reason='草稿删除', actor=actor)
    else:
        operation = operation or ('native_inbound' if kind == 'in_order' else 'native_outbound')
        old = {'status': previous_status} if previous_status is not None else None
        stage_order_audit(operation, order, old=old, new=snapshot, reason='移动端完成', actor=actor)
