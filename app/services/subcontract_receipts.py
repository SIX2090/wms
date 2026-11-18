"""委外履约按产品汇总已过账收货，草稿和报废数量均不计入实收。"""
from collections import defaultdict
from decimal import Decimal


def subcontract_receipt_balances(order):
    required = defaultdict(Decimal)
    received = defaultdict(Decimal)
    for row in order.items:
        required[row.material_id] += Decimal(str(row.quantity or 0))
    for receipt in order.receive_orders:
        if receipt.status == 'completed':
            for row in receipt.items:
                received[row.material_id] += Decimal(str(row.quantity or 0))
    return {mid: (quantity, received[mid]) for mid, quantity in required.items()}


def refresh_subcontract_receipts(order_id):
    """与收货同事务调整自动完结状态；人工或历史完结没有自动标记。"""
    from app import SubcontractOrder, SubcontractProgress, db
    if not order_id:
        return
    db.session.flush()
    order = SubcontractOrder.query.filter_by(id=order_id).with_for_update().populate_existing().one()
    if order.status == 'cancelled':
        return
    db.session.expire(order, ['items', 'receive_orders'])
    balances = subcontract_receipt_balances(order)
    fulfilled = bool(balances) and all(received >= planned for planned, received in balances.values())
    marker = SubcontractProgress.query.filter_by(subcontract_order_id=order_id, process_type='auto_receipt_close')
    if fulfilled and order.status != 'completed':
        order.status = 'completed'
        db.session.add(SubcontractProgress(subcontract_order_id=order_id, process_type='auto_receipt_close'))
    elif not fulfilled and order.status == 'completed':
        if marker.delete(synchronize_session=False):
            order.status = 'processing'
    elif order.status in ('partial', 'pending') and any(receipt.status == 'completed' for receipt in order.receive_orders):
        order.status = 'processing'
