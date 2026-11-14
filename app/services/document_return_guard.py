"""Check completed return dependencies inside the caller's locked transaction."""
import re


def sales_outbound_revert_check(outbound):
    from app import (SalesOrder, SalesOrderItem, db, _sales_returned_quantity_by_source_item,
                     round_to_2_decimals, STOCK_COMPARE_EPSILON)
    source = db.session.get(SalesOrder, outbound.source_sales_order_id) if outbound.source_sales_order_id else None
    if not source:
        match = re.search(r'来源销售订单\s+([^\s]+)', outbound.purpose or '')
        if match:
            source = SalesOrder.query.filter_by(order_no=match.group(1)).first()
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
