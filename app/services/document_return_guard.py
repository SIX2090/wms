"""Check completed return dependencies inside the caller's locked transaction."""
import re


def completed_sales_return_check(inbound):
    """Check persisted completed totals, including this edited order exactly once.

    Caller owns the write transaction. SQLite's existing BEGIN IMMEDIATE fence
    serializes different return documents, completion and source reversal.
    Other dialects' current per-document row locks do not establish that
    cross-document guarantee; their shared-source locking remains unverified.
    """
    from app import (SalesOrderItem, db,
                     _sales_returned_quantity_by_source_item,
                     round_to_2_decimals, STOCK_COMPARE_EPSILON)
    db.session.flush()
    # FK-based deletes/additions do not refresh an already-loaded relationship.
    db.session.expire(inbound, ['items'])
    source_ids = {
        row.source_sales_order_item_id for row in inbound.items
        if row.source_sales_order_item_id
    }
    returned = _sales_returned_quantity_by_source_item(list(source_ids))
    for source in SalesOrderItem.query.filter(SalesOrderItem.id.in_(source_ids)).all():
        shipped = round_to_2_decimals(source.shipped_quantity or 0)
        total = returned.get(source.id, 0)
        if total - shipped > STOCK_COMPARE_EPSILON:
            number = source.sales_order.order_no if source.sales_order else f'item#{source.id}'
            return False, f'已完成退货总数量 {total:.2f} 超过销售订单 {number} 的已发货数量 {shipped:.2f}'
    # No-source and dangling historical sources retain existing compatibility.
    return True, ''


def is_detached_sales_copy(outbound):
    """旧复制件有复制备注且只有文字销售来源；普通独立销售出库不受影响。"""
    remark = getattr(outbound, 'remark', '') or ''
    purpose = getattr(outbound, 'purpose', '') or ''
    return (not outbound.source_sales_order_id and not any(row.source_sales_order_item_id for row in outbound.items)
            and remark.startswith('由出库单 ') and '复制生成' in remark
            and ('来源销售订单' in purpose or purpose == '选单生成销售出库' or '已剥离销售订单来源' in remark))


def sales_outbound_revert_check(outbound):
    from app import (SalesOrder, SalesOrderItem, db, _sales_returned_quantity_by_source_item,
                     round_to_2_decimals, STOCK_COMPARE_EPSILON)
    source = db.session.get(SalesOrder, outbound.source_sales_order_id) if outbound.source_sales_order_id else None
    if not source:
        match = re.search(r'来源销售订单\s+([^\s]+)', outbound.purpose or '')
        if match:
            source = SalesOrder.query.filter_by(order_no=match.group(1)).first()
    if is_detached_sales_copy(outbound) and not source and '来源销售订单' in (outbound.purpose or ''):
        return False, '历史复制单指向的销售订单无法核对，请先核对原订单'
    if source and is_detached_sales_copy(outbound):
        from app import OutOrder, OutOrderItem
        # 旧进度有订货量封顶。其他已完成、明确关联的出库已能证明全部已发时，
        # 只回冲复制件库存；剩余历史进度无法证明时交人工核对。
        for material_id in {item.material_id for item in outbound.items}:
            rows = [item for item in source.items if item.material_id == material_id]
            if len(rows) != 1:
                return False, '历史复制单的销售来源行不明确，请先核对原订单的发货记录'
            row = rows[0]
            proven = db.session.query(db.func.sum(OutOrderItem.quantity)).join(OutOrder).filter(
                OutOrder.status == 'completed', OutOrder.id != outbound.id,
                OutOrderItem.material_id == material_id, OutOrderItem.source_sales_order_item_id == row.id,
            ).scalar() or 0
            if proven + STOCK_COMPARE_EPSILON < (row.shipped_quantity or 0):
                return False, '历史复制单缺少足以核对已发数量的来源记录，请先核对原订单'
        return True, ''
    by_material = {}
    if source:
        for row in source.items:
            by_material.setdefault(row.material_id, []).append(row)
    requested, source_rows = {}, {}
    # Resolve legacy rows exactly as sync_sales_order_shipment does.
    for row in outbound.items:
        target = db.session.get(SalesOrderItem, row.source_sales_order_item_id) if row.source_sales_order_item_id else None
        if target and (target.material_id != row.material_id or (source and target.sales_order_id != source.id)):
            target = None
        if not target:
            candidates = by_material.get(row.material_id, [])
            target = candidates[0] if len(candidates) == 1 else None
        if target:
            source_rows[target.id] = target
            requested[target.id] = round_to_2_decimals(requested.get(target.id, 0) + (row.quantity or 0))
    returned = _sales_returned_quantity_by_source_item(list(requested))
    for sid, quantity in requested.items():
        remaining = round_to_2_decimals((source_rows[sid].shipped_quantity or 0) - quantity)
        if (returned.get(sid, 0) > STOCK_COMPARE_EPSILON
                and returned[sid] - remaining > STOCK_COMPARE_EPSILON):
            return False, '反提交后有效发货数量不足以覆盖已完成销售退货，请先处理对应退货单'
    return True, ''


def purchase_inbound_revert_check(inbound):
    from app import _purchase_returned_quantity_by_source_item
    returned = _purchase_returned_quantity_by_source_item([row.id for row in inbound.items])
    if returned:
        return False, '该入库单明细存在已完成采购退货，请先反提交对应退货单，再处理原入库单'
    return True, ''
