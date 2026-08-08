import time, sys
sys.path.insert(0, '/workspace/app')
from app import app, db, InOrder, InOrderItem, OutOrder, OutOrderItem, _acquire_order_write_lock, _in_order_push_quantities, generate_order_no, round_to_2_decimals
from sqlalchemy.orm import selectinload, configure_mappers
configure_mappers()

with app.app_context():
    order_id = 2
    locked, ok = _acquire_order_write_lock(InOrder, order_id, 'completed', selectinload(InOrder.items))
    order = locked
    items = InOrderItem.query.filter_by(in_order_id=order_id).all()
    pushed = _in_order_push_quantities(order)
    selected = []
    for it in items:
        src = pushed.get(it.id, 0)
        avail = max(0, (it.quantity or 0) - src)
        if avail > 0:
            selected.append((it, round_to_2_decimals(avail)))
    print("selected=%d / %d items" % (len(selected), len(items)))
    from datetime import date
    t0 = time.time()
    target = OutOrder(order_no=generate_order_no('OUT'), date=date.today(), business_type='领料单',
                      warehouse=order.warehouse, status='pending', remark='test')
    db.session.add(target)
    db.session.flush()
    tmid = time.time()
    for source_item, quantity in selected:
        price = round_to_2_decimals(source_item.material.price or 0) if source_item.material else 0
        target_item = OutOrderItem(out_order_id=target.id, material_id=source_item.material_id,
                                   quantity=quantity, price=price, amount=round_to_2_decimals(quantity*price))
        db.session.add(target_item)
        db.session.flush()
    tloop = time.time()
    target.total_amount = round_to_2_decimals(sum(q*(si.material.price or 0) for si,q in selected))
    db.session.rollback()
    tcommit = time.time()
    print("header flush: %.3fs" % (tmid-t0))
    print("%d item add+flush: %.3fs" % (len(selected), tloop-tmid))
    print("rollback: %.3fs" % (tcommit-tloop))
    print("TOTAL(before rollback): %.3fs" % (tloop-t0))