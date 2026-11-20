"""Shared rules for warehouse counts and the adjustments they generate."""

from db import db
from models.documents import AdjustmentOrder, AdjustmentOrderItem, InventoryCheck, InventoryCheckItem
from models.inventory import StockTransaction
from sqlalchemy.orm import aliased


STOCKTAKE_SOURCES = ('check', 'check_scan')


def stocktake_adjustment_history(order_id):
    """Keep both sides of a posted and reversed adjustment in the ledger."""
    return StockTransaction.query.filter_by(reference_type='adjustment', reference_id=order_id).first() is not None


def grouped_stocktake_counts(check):
    """Return each material's first book balance and the rows actually counted."""
    grouped = {}
    for row in sorted(check.items, key=lambda item: item.id):
        if row.material_id:
            first, counted = grouped.setdefault(row.material_id, (row, []))
            if row.has_actual_count:
                counted.append(row)
    return grouped


def stocktake_quantities(first, counted):
    from app import normalize_stock_quantity, round_to_2_decimals

    book = normalize_stock_quantity(first.system_stock)
    total = round_to_2_decimals(sum(normalize_stock_quantity(row.actual_stock) for row in counted))
    return book, total, round_to_2_decimals(total - book)


def stocktake_report_totals(base):
    """SQL quantities for all matching rows, before paging."""
    item = InventoryCheckItem
    first = aliased(item)
    has_actual = db.or_(item.counted_by.is_not(None), item.counted_at.is_not(None),
                        item.actual_stock != item.system_stock)
    per_material = base.with_entities(
        db.func.min(item.id).label('first_id'),
        db.func.sum(db.case((has_actual, db.func.round(item.actual_stock, 2)), else_=0)).label('actual'),
        db.func.max(db.case((has_actual, 1), else_=0)).label('counted'),
    ).group_by(item.inventory_check_id, item.material_id).subquery()
    book = db.func.round(first.system_stock, 2)
    actual = per_material.c.actual
    net = db.case((per_material.c.counted == 1, db.func.round(actual - book, 2)), else_=0)
    return db.session.query(first.id.label('first_id'), book.label('book'),
                            actual.label('actual'), net.label('net')).select_from(
        per_material).join(first, first.id == per_material.c.first_id)


def overlapping_stocktake_adjustment(check, material_ids, warehouse, *, posting=False, exclude_order=None):
    """Find a competing draft or a posting made after this count began."""
    from app import _warehouse_document_match_clause

    query = (AdjustmentOrder.query.join(AdjustmentOrderItem)
             .filter(AdjustmentOrder.source_type.in_(STOCKTAKE_SOURCES),
                     AdjustmentOrderItem.material_id.in_(material_ids),
                     _warehouse_document_match_clause(AdjustmentOrder.warehouse, warehouse)))
    if exclude_order is not None:
        query = query.filter(AdjustmentOrder.id != exclude_order)
    if check is not None:
        query = query.filter(db.or_(AdjustmentOrder.source_type != 'check',
                                    AdjustmentOrder.source_id != check.id,
                                    AdjustmentOrder.source_id.is_(None)))
    started_at = (check.frozen_at or check.created_at) if check is not None else None
    if started_at:
        recent = db.and_(AdjustmentOrder.status == 'completed', db.exists().where(
            StockTransaction.reference_type == 'adjustment',
            StockTransaction.reference_id == AdjustmentOrder.id,
            StockTransaction.transaction_type.in_(('adjustment_in', 'adjustment_out')),
            StockTransaction.created_at >= started_at))
    else:
        recent = db.false()
    # If legacy duplicates already exist, either may be reviewed first. The next
    # posting is blocked by that first posting's ledger entry.
    condition = recent if posting else db.or_(recent, AdjustmentOrder.status == 'pending')
    return query.filter(condition).order_by(AdjustmentOrder.id).first()


def validate_stocktake_adjustment(order, warehouse):
    """Verify that a pending adjustment still matches its completed source."""
    from app import resolve_inventory_warehouse_id

    if order.source_type != 'check':
        return None
    check = db.session.get(InventoryCheck, order.source_id)
    if (check is None or check.status != 'completed'
            or resolve_inventory_warehouse_id(check.warehouse) != warehouse.id):
        return '调整单与来源盘点单的状态或仓库不一致，请从来源盘点单重新生成'
    expected = {}
    for material_id, (first, counted) in grouped_stocktake_counts(check).items():
        _, _, delta = stocktake_quantities(first, counted)
        if counted and delta and (delta > 0) == (order.adjustment_type == 'surplus'):
            expected[material_id] = (delta, (counted[0].area or '').strip())
    actual = {row.material_id: (row.quantity, (row.location or '').strip()) for row in order.items}
    if order.adjustment_type not in ('surplus', 'loss') or actual != expected or len(actual) != len(order.items):
        return '调整数量或库位与来源盘点单不一致，请从来源盘点单重新生成'
    conflict = overlapping_stocktake_adjustment(check, actual, warehouse, posting=True, exclude_order=order.id)
    if conflict:
        return f'同仓物料在本次盘点开始后已由调整单 {conflict.adjustment_no} 过账，请重新盘点'
    return None
