# -*- coding: utf-8 -*-
"""Shared inbound completion helpers for PC single, batch, and mobile confirmation paths."""
from __future__ import annotations

from uuid import uuid4


def check_supplied_receipt_order(order):
    """Validate customer-supplied inbound ownership rules across all completion paths."""
    if any(getattr(row, 'is_customer_supplied', False) for row in (order.items or [])):
        if order.business_type != '其他入库':
            return '含客供料的单据只能使用其他入库类型'
        if not order.customer_id:
            return '含客供料的其他入库单必须选择客户'
    return None


def check_purchase_over_receive_for_order(order):
    """Validate purchase over-receive limits for a pending inbound order under write lock."""
    from sqlalchemy import func as sa_func
    from app import (
        InOrderItem,
        STOCK_COMPARE_EPSILON,
        db,
        round_to_2_decimals,
        should_block_purchase_over_receive,
    )

    if not should_block_purchase_over_receive():
        return True, None

    qty_by_source = {}
    source_by_id = {}
    code_by_source = {}
    for item in (order.items or []):
        if not item.source_purchase_order_item_id or not item.source_purchase_order_item:
            continue
        sid = item.source_purchase_order_item_id
        qty_by_source[sid] = round_to_2_decimals(qty_by_source.get(sid, 0) + (item.quantity or 0))
        source_by_id[sid] = item.source_purchase_order_item
        code_by_source[sid] = item.material.code if item.material else str(item.material_id)

    for sid, this_order_qty in qty_by_source.items():
        source_item = source_by_id[sid]
        other_linked_qty = float(
            db.session.query(sa_func.coalesce(sa_func.sum(InOrderItem.quantity), 0))
            .filter(
                InOrderItem.source_purchase_order_item_id == sid,
                InOrderItem.in_order_id != order.id,
            )
            .scalar() or 0
        )
        other_reserved = max(
            other_linked_qty,
            max(0.0, float(source_item.received_quantity or 0) - this_order_qty),
        )
        effective_remain = round_to_2_decimals((source_item.quantity or 0) - other_reserved)
        if (
            this_order_qty - effective_remain > STOCK_COMPARE_EPSILON
            or float(source_item.received_quantity or 0) - float(source_item.quantity or 0) > STOCK_COMPARE_EPSILON
        ):
            return False, f'物料 {code_by_source[sid]} 入库数量不能大于采购单未入库数量'
    return True, None


def sync_in_order_purchase_order_statuses(order):
    """Recalculate statuses for every purchase order linked at header or item level."""
    from app import PurchaseOrder, update_purchase_order_status

    affected_ids = set()
    if getattr(order, 'source_purchase_order_id', None):
        affected_ids.add(order.source_purchase_order_id)
    for item in (order.items or []):
        src = getattr(item, 'source_purchase_order_item', None)
        if src is not None and getattr(src, 'purchase_order_id', None):
            affected_ids.add(src.purchase_order_id)
    if not affected_ids:
        return []
    pos = PurchaseOrder.query.filter(PurchaseOrder.id.in_(affected_ids)).all()
    for po in pos:
        update_purchase_order_status(po)
    return pos


def execute_auto_push_requisition(order, actor=None, *, reason='采购入库自动完成领料'):
    """Create and post the paired completed requisition inside the caller's locked transaction.

    Returns (auto_requisition, error_message). Does NOT commit or rollback; the caller
    owns transaction commit/rollback so inbound + requisition + audit remain atomic.
    """
    from flask_login import current_user
    from app import (
        DocumentPushLine,
        OutOrder,
        OutOrderItem,
        _source_has_active_push,
        db,
        generate_order_no,
        recalculate_order_total,
        round_money_product,
        round_to_2_decimals,
    )
    from services.document_stock_audit import (
        stage_stock_document_snapshot,
        stock_document_audit_checkpoint,
    )
    from services.warehouse_stock_service import apply_stock_delta

    if not getattr(order, 'auto_push_requisition', False):
        return None, None
    if order.business_type != '采购入库':
        return None, '仅采购入库单可以自动下推领料单'
    if _source_has_active_push(order.id):
        return None, '自动下推领料单已处理，不能重复操作'

    resolved_actor = actor if actor is not None else (
        current_user if getattr(current_user, 'is_authenticated', False) else None
    )
    actor_id = getattr(resolved_actor, 'id', None) or order.operator_id
    request_id = f'auto-requisition-{order.id}-{uuid4().hex}'
    auto_requisition = OutOrder(
        order_no=generate_order_no('OUT'),
        date=order.date,
        business_type='领料单',
        warehouse=order.warehouse,
        location=order.location,
        purpose='自动下推领料单',
        status='completed',
        operator_id=actor_id,
        remark=f'由采购入库单 {order.order_no} 自动下推并完成领料',
    )
    db.session.add(auto_requisition)
    db.session.flush()
    requisition_checkpoint = stock_document_audit_checkpoint(auto_requisition, created=True)

    for source_item in (order.items or []):
        price = round_to_2_decimals(source_item.material.price or 0) if source_item.material else 0
        target_item = OutOrderItem(
            out_order_id=auto_requisition.id,
            material_id=source_item.material_id,
            quantity=source_item.quantity,
            price=price,
            amount=round_money_product(source_item.quantity or 0, price),
            contract_id=source_item.contract_id,
            contract_no=source_item.contract_no,
            project_name=source_item.project_name,
            remark=source_item.remark,
        )
        db.session.add(target_item)
        db.session.flush()
        stock_ok, stock_error = apply_stock_delta(
            source_item.material,
            -(source_item.quantity or 0),
            transaction_type='out',
            reference_type='out_order',
            reference_id=auto_requisition.id,
            warehouse=order.warehouse,
            location=order.location,
            operator_id=actor_id,
        )
        if not stock_ok:
            return None, stock_error or '自动下推领料单扣减库存失败'
        db.session.add(DocumentPushLine(
            source_document_type='purchase_in_order',
            source_document_id=order.id,
            source_document_no=order.order_no,
            source_item_id=source_item.id,
            target_document_type='requisition',
            target_document_id=auto_requisition.id,
            target_document_no=auto_requisition.order_no,
            target_item_id=target_item.id,
            pushed_quantity=source_item.quantity or 0,
            status='active',
            request_id=request_id,
            created_by=actor_id,
        ))
    recalculate_order_total(auto_requisition)
    stage_stock_document_snapshot(
        auto_requisition,
        deleting=False,
        actor=resolved_actor,
        operation='complete_out_order',
        checkpoint=requisition_checkpoint,
        reason=reason,
    )
    return auto_requisition, None
