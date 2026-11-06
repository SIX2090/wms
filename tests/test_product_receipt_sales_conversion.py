"""Finished goods convert to a linked sales draft without changing stock."""
import pytest
import app as w

from tests.test_document_edit_conflicts import revision
from tests.test_web_document_idempotency import receipt_case


@pytest.fixture
def product_sale_case(receipt_case):
    client, payload = receipt_case
    with w.app.app_context():
        customer = w.Customer(code='FG-C', name='成品客户')
        second = w.Warehouse(code='FG-B', name='成品二仓', status='active')
        other = w.User(username='second-product-operator', role='admin', password_hash='unused', must_change_password=False)
        w.db.session.add_all([customer, second, other]); w.db.session.commit()
        customer_id, second_id, other_id = customer.id, second.id, other.id
    payload.update(customer_id=customer_id, warehouse_id=second_id, contract_no='FG-HT', project_name='成品工程')
    payload['items'] = [dict(code='RETRY', quantity=1, price=5, box_no='001-A', remark='箱一'),
                        dict(code='RETRY', quantity=2, price=8, box_no='002-B', remark='箱二', contract_no='行合同', project_name='行工程')]
    saved = client.post('/in_order/add', json=payload)
    assert saved.status_code == 200, saved.json
    source_id = saved.json['id']
    with w.app.app_context():
        source = w.db.session.get(w.InOrder, source_id)
        source.location = '成品区'
        material = w.Material.query.one()
        material.stock = 8
        first = w.Warehouse.query.filter_by(code='RETRY').one()
        w.db.session.add_all([w.LocationInventory(material_id=material.id, warehouse_id=first.id, location='', quantity=8),
                             w.StockTransaction(material_id=material.id, warehouse_id=first.id,
                                                transaction_type='in', quantity=8, location='', reference_type='opening_stock')])
        w.db.session.commit()
    completed = client.post(f'/in_order/{source_id}/complete',
                            headers={'X-WMS-Document-Revision':revision(client,f'/in_order/{source_id}')})
    assert completed.status_code == 200, completed.json
    return client, source_id, other_id


def convert(client, source_id):
    return client.post(f'/in_order/{source_id}/convert_to_out_order',
                       headers={'X-WMS-Document-Revision': revision(client, f'/in_order/{source_id}')})


def stocks():
    return (w.Material.query.one().stock,
            sorted((row.warehouse_id, row.location, row.quantity) for row in w.LocationInventory.query.all()),
            w.StockTransaction.query.count())


def test_sales_draft_keeps_customer_contract_rows_and_both_warehouse_balances(product_sale_case):
    client, source_id, _ = product_sale_case
    with w.app.app_context(): before = stocks()
    response = convert(client, source_id)
    assert response.status_code == 200, response.json
    with w.app.app_context():
        target = w.db.session.get(w.OutOrder, response.json['out_order_id'])
        assert target.business_type == '销售出库' and target.order_no.startswith('SO')
        assert target.status == 'pending' and target.customer == '成品客户'
        assert target.warehouse == '成品二仓' and target.location == '成品区'
        assert (target.contract_no, target.project_name, target.total_amount) == ('FG-HT', '成品工程', 21)
        assert [(i.quantity, i.price, i.amount, i.remark) for i in target.items] == [(1, 5, 5, '箱一'), (2, 8, 16, '箱二')]
        assert [(i.contract_no, i.project_name) for i in target.items] == [('FG-HT', '成品工程'), ('行合同', '行工程')]
        assert all(i.source_in_order_item_id is None for i in target.items), 'do not misuse purchase-return source fields'
        links = w.DocumentPushLine.query.filter_by(source_document_type='product_in_order', source_document_id=source_id).all()
        assert len(links) == 2 and {x.target_document_type for x in links} == {'sales_out'}
        source_boxes = {i.id:i.box_no for i in w.db.session.get(w.InOrder,source_id).items}
        assert [source_boxes[x.source_item_id] for x in links] == ['001-A','002-B']
        assert {x.target_item_id for x in links} == {i.id for i in target.items}
        assert stocks() == before
        with w.app.test_request_context():
            history = w._in_order_push_history(w.db.session.get(w.InOrder,source_id))
        assert len(history) == 1 and history[0]['target_label'] == '销售出库单'
        assert history[0]['url'] == f'/out_order/{target.id}'


def test_two_operators_and_retry_open_the_same_active_sales_draft(product_sale_case):
    client, source_id, other_id = product_sale_case
    first = convert(client, source_id)
    assert first.status_code == 200, first.json
    second_client = w.app.test_client()
    with second_client.session_transaction() as session:
        session['_user_id'] = str(other_id); session['_fresh'] = True
    second = convert(second_client, source_id)
    retry = convert(client, source_id)
    assert second.status_code == retry.status_code == 200
    assert second.json['out_order_id'] == retry.json['out_order_id'] == first.json['out_order_id']
    with w.app.app_context():
        assert w.OutOrder.query.count() == 1 and w.DocumentPushLine.query.count() == 2
        assert w.OutOrder.query.one().operator_id != other_id


def test_legacy_product_copy_entry_uses_the_same_sales_target(product_sale_case):
    client,source_id,_ = product_sale_case
    copied = client.post(f'/in_order/{source_id}/copy_to_out',
                         headers={'X-WMS-Document-Revision':revision(client,f'/in_order/{source_id}')})
    assert copied.status_code == 200, copied.json
    replay = convert(client,source_id)
    assert replay.status_code == 200 and replay.json['out_order_id'] == copied.json['out_order_id']
    with w.app.app_context():
        assert w.OutOrder.query.one().business_type == '销售出库'
        assert w.DocumentPushLine.query.count() == 2


def test_conversion_failure_rolls_back_target_links_and_all_stock(product_sale_case, monkeypatch):
    client,source_id,_ = product_sale_case
    real_flush = w.db.session.flush
    def fail_after_line_allocation(*args, **kwargs):
        if any(isinstance(value,w.DocumentPushLine) for value in w.db.session.new):
            raise RuntimeError('synthetic allocation flush failure')
        return real_flush(*args, **kwargs)
    with w.app.app_context(): before = stocks()
    monkeypatch.setattr(w.db.session,'flush',fail_after_line_allocation)
    result = convert(client,source_id)
    assert result.status_code == 400 and result.json['status'] == 'error'
    with w.app.app_context():
        assert w.OutOrder.query.count() == 0 and w.DocumentPushLine.query.count() == 0
        assert stocks() == before


def test_active_sales_draft_blocks_source_revert_and_delete_releases_links(product_sale_case):
    client, source_id, _ = product_sale_case
    created = convert(client, source_id)
    assert created.status_code == 200, created.json
    result = client.post(f'/in_order/{source_id}/revert',
                         headers={'X-WMS-Document-Revision':revision(client,f'/in_order/{source_id}')})
    assert result.status_code == 409 and '下推' in result.json['msg']
    target_id = created.json['out_order_id']
    deleted = client.post(f'/out_order/{target_id}/delete',
                          headers={'X-WMS-Document-Revision':revision(client,f'/out_order/{target_id}')})
    assert deleted.status_code == 200, deleted.json
    with w.app.app_context():
        assert not w._source_has_active_push(source_id)
        assert {x.status for x in w.DocumentPushLine.query.all()} == {'released'}
    repeated = convert(client, source_id)
    assert repeated.status_code == 200, repeated.json
    with w.app.app_context():
        assert w.OutOrder.query.count() == 1
        assert w.DocumentPushLine.query.filter_by(status='active').count() == 2


@pytest.mark.parametrize('change,expected', [('customer','客户'),('status','已完成'),('business','产品入库'),('empty','明细'),('warehouse','仓库')])
def test_invalid_source_does_not_create_a_draft_or_change_stock(product_sale_case, change, expected):
    client, source_id, _ = product_sale_case
    with w.app.app_context():
        source = w.db.session.get(w.InOrder,source_id)
        if change == 'customer': source.customer_id = None
        elif change == 'status': source.status = 'pending'
        elif change == 'business': source.business_type = '采购入库'
        elif change == 'warehouse': source.warehouse = '不存在的历史仓'
        else:
            for item in list(source.items): w.db.session.delete(item)
        w.db.session.commit(); before = stocks()
    result = convert(client,source_id)
    assert result.status_code == 400, result.json
    assert expected in result.json['msg']
    with w.app.app_context():
        assert w.OutOrder.query.count() == 0 and w.DocumentPushLine.query.count() == 0
        assert stocks() == before


def test_legacy_blank_warehouse_uses_existing_default_without_changing_stock(product_sale_case):
    client,source_id,_ = product_sale_case
    with w.app.app_context():
        w.db.session.get(w.InOrder,source_id).warehouse = ''
        w.db.session.commit(); before = stocks()
    result = convert(client,source_id)
    assert result.status_code == 200, result.json
    with w.app.app_context():
        assert w.OutOrder.query.one().warehouse == '重试仓'
        assert stocks() == before


def test_product_detail_uses_sales_confirmation_and_destination(product_sale_case):
    client,source_id,_ = product_sale_case
    html = client.get(f'/in_order/{source_id}').text
    assert '转为销售出库单' in html and '销售出库草稿' in html
    assert '转为领料单' not in html and '领料单审核' not in html


def test_direct_sales_draft_can_be_manually_completed_in_its_source_warehouse(product_sale_case):
    client,source_id,_ = product_sale_case
    created = convert(client,source_id)
    assert created.status_code == 200, created.json
    target_id = created.json['out_order_id']
    completed = client.post(f'/out_order/{target_id}/complete',
                            headers={'X-WMS-Document-Revision':revision(client,f'/out_order/{target_id}')})
    assert completed.status_code == 200, completed.json
    with w.app.app_context():
        assert w.db.session.get(w.OutOrder,target_id).status == 'completed'
        assert w.Material.query.one().stock == 8
        first = w.Warehouse.query.filter_by(code='RETRY').one()
        second = w.Warehouse.query.filter_by(code='FG-B').one()
        assert sum(x.quantity for x in w.LocationInventory.query.filter_by(warehouse_id=first.id)) == 8
        assert sum(x.quantity for x in w.LocationInventory.query.filter_by(warehouse_id=second.id)) == 0
        assert sum(x.quantity for x in w.StockTransaction.query.all()) == 8
