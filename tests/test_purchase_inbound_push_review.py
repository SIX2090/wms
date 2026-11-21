from bs4 import BeautifulSoup
from tests.test_auto_push_requisition import _seed, _login, _reset_db, _create_purchase_in_order, app_module
from app import InOrder, Material, db


def scene():
    with app_module.app.app_context():
        _reset_db()
        supplier = _seed()
    client = app_module.app.test_client()
    _login(client)
    return client, supplier, _create_purchase_in_order(client, supplier, True)


def finished(client, path):
    response = client.post(path)
    result = response.get_json()
    assert result and result["status"] == "success", (path, result)
    return result


def test_reverted_receipt_keeps_automatic_issue_when_saved_again():
    client, supplier, receipt = scene()
    target = finished(client, f'/in_order/{receipt}/complete?force=1')['auto_requisition_id']
    finished(client, f'/out_order/{target}/revert')
    finished(client, f'/out_order/{target}/delete')
    finished(client, f'/in_order/{receipt}/revert')
    with app_module.app.app_context():
        original = db.session.get(InOrder, receipt)
        assert original.auto_push_requisition
        item_id = original.items[0].id
    response = client.get(f"/in_order/add?order_id={receipt}")
    assert response.status_code == 200
    form = BeautifulSoup(response.get_data(as_text=True), 'html.parser')
    checkbox = form.select_one('#autoPushRequisition')
    assert checkbox and checkbox.has_attr('checked')
    data = dict(order_id=receipt, supplier_id=supplier, business_type='采购入库', warehouse='自动领料仓',
                auto_push_requisition=checkbox.has_attr('checked'),
                items=[dict(line_id=item_id, code='AUTO_MAT', quantity=5, price=12)])
    revision = form.select_one('meta[name="document-revision"]')['content']
    assert revision
    result = client.post('/in_order/add', json=data,
                         headers={'X-WMS-Document-Revision':revision}).get_json()
    assert result['status'] == 'success', result
    complete = finished(client, f'/in_order/{receipt}/complete?force=1')
    assert complete['auto_requisition_id']
    with app_module.app.app_context():
        assert Material.query.filter_by(code='AUTO_MAT').one().stock == 0


def test_recreated_downstream_quantity_and_revert_block():
    client, supplier, receipt = scene()
    first = finished(client, f'/in_order/{receipt}/complete?force=1')['auto_requisition_id']
    response = client.post(f'/in_order/{receipt}/revert')
    assert response.status_code == 409
    assert '下游单据' in response.get_json()['msg']
    detail = BeautifulSoup(client.get(f'/in_order/{receipt}').get_data(as_text=True), 'html.parser')
    action = detail.find('button', onclick=f'revertOrder({receipt})')
    assert action and action.has_attr('disabled')
    assert detail.select_one('a[href="#inboundPushHistory"]')
    finished(client, f'/out_order/{first}/revert')
    assert client.post(f'/in_order/{receipt}/revert').status_code == 409
    finished(client, f'/out_order/{first}/delete')
    finished(client, f'/in_order/{receipt}/revert')
    second = finished(client, f'/in_order/{receipt}/complete?force=1')['auto_requisition_id']
    assert first == second
    page = BeautifulSoup(client.get(f'/in_order/{receipt}').get_data(as_text=True), 'html.parser')
    heading = next(h for h in page.select('.card-header-custom') if '下推记录' in h.get_text())
    rows = heading.parent.select('tbody tr')
    assert len(rows) == 2
    active, released = [row.select('td') for row in rows]
    assert float(active[2].get_text()) == float(released[2].get_text()) == 5
    assert '已完成' in active[3].get_text() and active[1].a['href'] == f'/out_order/{second}'
    assert released[3].get_text(strip=True) == '已释放' and released[1].a is None
    with app_module.app.app_context():
        from app import OutOrder
        assert sum(line.quantity for line in db.session.get(OutOrder, second).items) == 5
