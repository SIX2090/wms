"""Reverted status and a real linked purchase reservation are separate facts."""
import re

import pytest

import app as wms
from app import (InOrder, InOrderItem, Material, PurchaseOrder, PurchaseOrderItem,
                 StockTransaction, User, Warehouse, db)


@pytest.fixture
def case(monkeypatch):
    monkeypatch.setitem(wms.app.config, 'TESTING', True)
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', False)
    with wms.app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        user = User(username='notice-test', role='admin', status='normal',
                    password_hash='unused-fixture', must_change_password=False)
        wh = Warehouse(code='NOTICE-WH', name='提示隔离仓', status='active', is_default=True)
        material = Material(code='NOTICE-M', name='提示隔离物料', stock=10)
        po = PurchaseOrder(order_no='NOTICE-PO')
        db.session.add_all([user, wh, material, po])
        db.session.flush()
        source = PurchaseOrderItem(purchase_order_id=po.id, material_id=material.id,
                                   quantity=10, received_quantity=2, price=1, amount=10)
        db.session.add(source)
        db.session.commit()
        client = wms.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user.id)
            session['_fresh'] = True
        yield client, wh, material, po, source
        db.session.remove()


def _order(case, kind, link=False, header=False, reverted=True, status='pending'):
    _, wh, material, po, source = case
    order = InOrder(order_no=f'NOTICE-{InOrder.query.count() + 1}', warehouse=wh.name,
                    business_type=kind, status=status,
                    source_purchase_order_id=po.id if header else None)
    db.session.add(order)
    db.session.flush()
    db.session.add(InOrderItem(in_order_id=order.id, material_id=material.id,
                               quantity=2, price=1, amount=2,
                               source_purchase_order_item_id=source.id if link else None))
    if reverted:
        db.session.add(StockTransaction(material_id=material.id, transaction_type='revert_in',
                                        quantity=-2, warehouse_id=wh.id, location=wh.name,
                                        reference_type='in_order', reference_id=order.id))
    db.session.commit()
    return order


def _detail_banner(case, order):
    response = case[0].get(f'/in_order/{order.id}')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    match = re.search(r'role="alert">(.*?)</div>\s*</div>', html, re.S)
    return match.group(1) if match else ''


@pytest.mark.parametrize('kind', ['采购入库', '产品入库', '其他入库', '销售退货入库'])
def test_no_source_detail_keeps_reverted_notice_without_reservation_claim(case, kind):
    order = _order(case, kind)
    banner = _detail_banner(case, order)
    assert '该单曾完成后反提交' in banner
    assert '库存已回退' in banner
    assert '收货预留' not in banner
    assert '删除草稿' not in banner
    assert '继续编辑' in banner


@pytest.mark.parametrize('kind', ['采购入库', '其他入库', '产品入库', '销售退货入库'])
def test_no_source_list_badge_tooltip_does_not_claim_purchase_reservation(case, kind):
    order = _order(case, kind)
    response = case[0].get('/in_order', query_string={'warehouse_id': case[1].id, 'search': order.order_no})
    assert response.status_code == 200
    title = re.search(r'badge bg-danger" title="([^"]+)"', response.get_data(as_text=True))
    assert title
    assert '库存已回退' in title[1]
    assert '预留' not in title[1]
    assert '删除' not in title[1]


def test_real_linked_reservation_retains_warning_and_read_is_pure(case):
    order = _order(case, '采购入库', link=True)
    before = (case[2].stock, case[4].received_quantity, StockTransaction.query.count(), order.status)
    assert '收货预留仍保留' in _detail_banner(case, order)
    html = case[0].get('/in_order', query_string={'warehouse_id': case[1].id}).get_data(as_text=True)
    assert '收货预留仍保留' in html
    db.session.expire_all()
    assert (case[2].stock, case[4].received_quantity, StockTransaction.query.count(), order.status) == before


@pytest.mark.parametrize('header,link,received', [(True, False, 2), (False, True, 0)])
def test_header_only_or_zero_counter_does_not_assert_reservation(case, header, link, received):
    case[4].received_quantity = received
    db.session.commit()
    order = _order(case, '采购入库', link=link, header=header)
    banner = _detail_banner(case, order)
    assert '该单曾完成后反提交' in banner
    assert '收货预留' not in banner


@pytest.mark.parametrize('reverted,status', [(False, 'pending'), (True, 'completed')])
def test_fresh_or_recompleted_order_has_no_reverted_banner(case, reverted, status):
    order = _order(case, '采购入库', link=True, reverted=reverted, status=status)
    assert '该单曾完成后反提交' not in _detail_banner(case, order)


def test_get_in_order_purchase_reservation_ids(case):
    from routes.in_order import get_in_order_purchase_reservation_ids
    linked = _order(case, '采购入库', link=True)
    unrelated = _order(case, '其他入库')
    assert get_in_order_purchase_reservation_ids([linked.id, linked.id, unrelated.id]) == {linked.id}
    assert get_in_order_purchase_reservation_ids([unrelated.id]) == set()
    assert get_in_order_purchase_reservation_ids([]) == set()
    assert get_in_order_purchase_reservation_ids(None) == set()
