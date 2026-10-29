"""BUG-2026-10-29-015: request receipts follow completed inbound facts."""
from datetime import date
import re

import pytest
from sqlalchemy import event

import app as m
from app import (db, InOrder, InOrderItem, Material, PurchaseOrder,
                 PurchaseOrderItem, PurchaseRequest, PurchaseRequestItem, User,
                 Warehouse)


@pytest.fixture
def request_receipts(monkeypatch):
    monkeypatch.setitem(m.app.config, 'TESTING', True)
    monkeypatch.setitem(m.app.config, 'WTF_CSRF_ENABLED', False)
    with m.app.app_context():
        assert str(db.engine.url) == 'sqlite:///:memory:'
        db.session.remove()
        db.drop_all()
        db.create_all()
        material = Material(code='PR-M', name='申请物料', stock=0)
        user = User(username='pr-receipt-test', password_hash='fixture-unused',
                    role='admin', must_change_password=False)
        a = Warehouse(code='PR-A', name='申请仓A', status='active', is_default=True)
        b = Warehouse(code='PR-B', name='申请仓B', status='active')
        req = PurchaseRequest(request_no='PR-RECEIPT', date=date.today(),
                              applicant='验收', status='approved')
        db.session.add_all([material, user, a, b, req])
        db.session.flush()
        line = PurchaseRequestItem(purchase_request_id=req.id, material_id=material.id,
                                   material_code=material.code, material_name=material.name,
                                   quantity=2)
        po = PurchaseOrder(order_no='PO-RECEIPT', date=date.today(),
                           purchase_request_id=req.id, status='pending')
        db.session.add_all([line, po])
        db.session.flush()
        item = PurchaseOrderItem(purchase_order_id=po.id, material_id=material.id,
                                 purchase_request_item_id=line.id, quantity=2,
                                 received_quantity=2, price=1, amount=2)
        db.session.add(item)
        db.session.flush()
        counter = [0]

        def inbound(quantity=2, status='pending', warehouse=a.name, source=item, order=po):
            counter[0] += 1
            doc = InOrder(order_no='IN-PR-'+str(counter[0]), date=date.today(),
                          business_type='采购入库', warehouse=warehouse, status=status,
                          source_purchase_order_id=order.id)
            db.session.add(doc)
            db.session.flush()
            db.session.add(InOrderItem(in_order_id=doc.id, material_id=material.id,
                                       source_purchase_order_item_id=source.id if source else None,
                                       quantity=quantity, price=1, amount=quantity))
            db.session.flush()
            return doc

        draft = inbound()
        db.session.commit()
        client = m.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user.id)
            session['_fresh'] = True
        yield dict(material=material, a=a, b=b, req=req, line=line, po=po,
                   item=item, draft=draft, inbound=inbound, client=client)
        db.session.remove()


def execution(c):
    return m.build_purchase_request_execution(list(c['req'].items), c['req'])


def test_request_pages_follow_pending_complete_and_revert_without_releasing_push(request_receipts):
    c = request_receipts
    for status, expected, progress in [('pending', 0, 'partial'),
                                       ('completed', 2, 'completed'),
                                       ('pending', 0, 'partial')]:
        c['draft'].status = status
        db.session.commit()
        row = execution(c)[c['line'].id]
        assert row == dict(request_quantity=2, ordered_quantity=2, received_quantity=expected,
                           remaining_to_order=0, remaining_to_receive=2-expected, status=progress)
        for url in ['/purchase_request?embedded=1&search=PR-RECEIPT',
                    f"/purchase_request/{c['req'].id}?embedded=1"]:
            response = c['client'].get(url)
            assert response.status_code == 200
            html = response.get_data(as_text=True)
            assert re.findall(r'data-received-quantity="([^"]+)"', html) == [f'{expected:.2f}']
            assert re.findall(r'data-ordered-quantity="([^"]+)"', html) == ['2.00']
            assert re.findall(r'data-remaining-to-order="([^"]+)"', html) == ['0.00']
            assert re.findall(r'data-execution-status="([^"]+)"', html) == [progress]
        count = PurchaseOrder.query.count()
        reply = c['client'].post(f"/purchase_request/{c['req'].id}/create_purchase_order", json={})
        assert reply.status_code == 200
        assert '已全部下推' in reply.get_json()['msg']
        assert PurchaseOrder.query.count() == count
    assert c['item'].received_quantity == 2
    assert c['material'].stock == 0, 'this read model must not write inventory'


@pytest.mark.parametrize('request_link', ['line', 'header', 'remark'])
@pytest.mark.parametrize('receipt_link', ['line', 'header'])
def test_legacy_links_still_use_only_completed_receipts(request_receipts, request_link, receipt_link):
    c = request_receipts
    if request_link != 'line':
        c['item'].purchase_request_item_id = None
    if request_link == 'remark':
        c['po'].purchase_request_id = None
        c['po'].remark = f"由采购申请 {c['req'].request_no} 下推生成"
    if receipt_link == 'header':
        c['draft'].items[0].source_purchase_order_item_id = None
    db.session.commit()
    assert execution(c)[c['line'].id]['received_quantity'] == 0
    c['draft'].status = 'completed'
    db.session.commit()
    assert execution(c)[c['line'].id]['received_quantity'] == 2
    assert execution(c)[c['line'].id]['remaining_to_order'] == 0


@pytest.mark.parametrize('warehouse', ['申请仓B', 'PR-B', '历史未知仓', None])
def test_request_total_counts_all_receipt_warehouses_without_crossing_requests(request_receipts, warehouse):
    c = request_receipts
    c['inbound'](1, 'completed', c['a'].name)
    c['inbound'](1, 'completed', warehouse)
    other = PurchaseRequest(request_no='PR-OTHER', date=date.today(), status='approved')
    db.session.add(other)
    db.session.flush()
    other_line = PurchaseRequestItem(purchase_request_id=other.id,
                                     material_id=c['material'].id, quantity=10)
    other_po = PurchaseOrder(order_no='PO-OTHER', date=date.today(),
                             purchase_request_id=other.id, status='pending')
    db.session.add_all([other_line, other_po])
    db.session.flush()
    other_item = PurchaseOrderItem(purchase_order_id=other_po.id,
                                   material_id=c['material'].id,
                                   purchase_request_item_id=other_line.id,
                                   quantity=10, received_quantity=0)
    db.session.add(other_item)
    db.session.flush()
    c['inbound'](7, 'completed', warehouse, other_item, other_po)
    db.session.commit()
    assert execution(c)[c['line'].id]['received_quantity'] == 2
    other_ex = m.build_purchase_request_execution([other_line], other)[other_line.id]
    assert other_ex['received_quantity'] == 7
    assert c['draft'].status == 'pending'
    assert c['item'].received_quantity == 2


def test_manual_same_material_rows_allocate_completed_facts_once(request_receipts):
    c = request_receipts
    second = PurchaseRequestItem(purchase_request_id=c['req'].id,
                                 material_id=c['material'].id, quantity=3)
    db.session.add(second)
    c['item'].purchase_request_item_id = None
    c['item'].quantity = 5
    c['item'].received_quantity = 5
    c['inbound'](4, 'completed', c['b'].code, source=None)
    db.session.commit()
    db.session.expire(c['req'], ['items'])
    result = execution(c)
    assert [result[x]['ordered_quantity'] for x in (c['line'].id, second.id)] == [2, 3]
    assert [result[x]['received_quantity'] for x in (c['line'].id, second.id)] == [2, 2]
    assert sum(x['received_quantity'] for x in result.values()) == 4
    assert sum(x['remaining_to_order'] for x in result.values()) == 0
    assert c['item'].purchase_request_item_id is None


def test_completed_facts_do_not_depend_on_pushed_counter(request_receipts):
    c = request_receipts
    c['item'].received_quantity = 0
    c['draft'].status = 'completed'
    db.session.commit()
    assert execution(c)[c['line'].id]['received_quantity'] == 2
    assert c['item'].received_quantity == 0


def test_closed_orders_are_still_excluded(request_receipts):
    c = request_receipts
    c['draft'].status = 'completed'
    c['po'].status = 'closed'
    db.session.commit()
    assert execution(c)[c['line'].id]['ordered_quantity'] == 0
    assert execution(c)[c['line'].id]['received_quantity'] == 0


def test_query_count_does_not_grow_per_purchase_line(request_receipts):
    c = request_receipts
    c['draft'].status = 'completed'
    db.session.commit()
    statements = []
    _ = c['line'].id
    _ = c['req'].request_no

    def record(conn, cursor, statement, params, context, many):
        statements.append(statement)

    event.listen(db.engine, 'before_cursor_execute', record)
    try:
        m.build_purchase_request_execution([c['line']], c['req'])
        small_count = len(statements)
        event.remove(db.engine, 'before_cursor_execute', record)
        for _ in range(25):
            db.session.add(PurchaseOrderItem(purchase_order_id=c['po'].id,
                                             purchase_request_item_id=c['line'].id,
                                             material_id=c['material'].id,
                                             quantity=1, received_quantity=1))
        db.session.commit()
        # Expire/refresh cost is unrelated to the quantity of aggregate rows.
        line_id = c['line'].id
        _ = c['req'].request_no
        statements.clear()
        event.listen(db.engine, 'before_cursor_execute', record)
        result = m.build_purchase_request_execution([c['line']], c['req'])
        assert len(statements) == small_count
        assert result[line_id]['received_quantity'] == 2
    finally:
        event.remove(db.engine, 'before_cursor_execute', record)


def test_empty_request_has_no_receipts(request_receipts):
    assert m.build_purchase_request_execution([], request_receipts['req']) == {}
