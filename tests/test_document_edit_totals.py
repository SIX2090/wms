"""Header totals must use the current rows even when revisions read old rows."""
from datetime import date
import json
import pytest
import app as w
from tests.test_document_create_number_conflicts import case
from tests.test_document_edit_conflicts import revision
from tests.test_document_edit_route_coverage import subcontract_case


@pytest.mark.parametrize('model_name,item_name,parent_key', [
    ('InOrder','InOrderItem','in_order_id'), ('OutOrder','OutOrderItem','out_order_id')])
def test_recalculate_order_total(case, model_name, item_name, parent_key):
    _, ids = case
    model, item_model = getattr(w, model_name), getattr(w, item_name)
    with w.app.app_context():
        order = model(order_no='CACHED-'+model_name, warehouse=ids['names'][0], status='pending')
        w.db.session.add(order); w.db.session.flush()
        w.db.session.add(item_model(**{parent_key:order.id}, material_id=ids['mats'][0], quantity=3, price=2, amount=6))
        w.db.session.commit()
        assert len(order.items) == 1
        item_model.query.filter_by(**{parent_key:order.id}).delete(synchronize_session='fetch')
        w.db.session.add(item_model(**{parent_key:order.id}, material_id=ids['mats'][0], quantity=2, price=0, amount=0))
        assert w.recalculate_order_total(order) == 0
        w.db.session.commit(); w.db.session.expire_all()
        assert order.total_amount == sum(item.amount for item in order.items) == 0
        assert w.db.session.get(w.Material, ids['mats'][0]).stock == 30


def test_recalculate_sales_order(case):
    clients, ids = case
    with w.app.app_context():
        customer = w.Customer(code='CACHE-C', name='合成缓存客户')
        w.db.session.add(customer); w.db.session.commit(); cid = customer.id
    data = dict(customer_id=cid, warehouse_id=ids['a'], date=date.today().isoformat(),
                items=json.dumps([{'code':'DC-M1','quantity':3,'price':19.95,'tax_rate':0,'batch_no':'B'*80}]))
    created = clients[0].post('/sales/add', json=data)
    assert created.status_code == 200, created.json
    oid = created.json['id']; token = revision(clients[0], f'/sales/{oid}/edit')
    data['items'] = [{'code':'DC-M1','quantity':2,'price':0,'tax_rate':0,'batch_no':'B'*80}]
    saved = clients[0].post(f'/sales/{oid}/edit', json=data, headers={'X-WMS-Document-Revision':token})
    assert saved.status_code == 200, saved.json
    with w.app.app_context():
        order = w.db.session.get(w.SalesOrder, oid)
        assert order.total_amount == order.tax_amount == 0
        assert len(order.items) == 1 and order.items[0].price == 0 and order.items[0].quantity == 2
        assert order.items[0].batch_no == 'B'*80
        assert w.db.session.get(w.Material, ids['mats'][0]).stock == 30


def test_guard_snapshot_does_not_stale_subcontract_total(subcontract_case):
    client, ids = subcontract_case
    token = revision(client, f"/subcontract/{ids['order']}")
    response = client.post(f"/subcontract/{ids['order']}/item/add",
        data={'material_code':'SIGN-M','quantity':'4'}, headers={'X-WMS-Document-Revision':token})
    assert response.status_code == 200, response.json
    with w.app.app_context():
        order = w.db.session.get(w.SubcontractOrder, ids['order'])
        expected = sum(item.quantity * item.material.price for item in order.items)
        assert expected == 14 and order.total_amount == expected
        assert w.db.session.get(w.Material, ids['material']).stock == 25
