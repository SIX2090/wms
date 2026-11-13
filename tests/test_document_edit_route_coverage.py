"""Registered existing-document POSTs must not depend on a verb in their URL."""
import re

from flask import jsonify, make_response
import app as w
import pytest
from tests.test_document_edit_conflicts import revision


@pytest.fixture
def subcontract_case(monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    monkeypatch.setenv('WMS_THREE_LEDGER_ASSERT', '1')
    with w.app.app_context():
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.session.remove(); w.db.drop_all(); w.db.create_all()
        user = w.User(username='signed-subcontract', role='admin', password_hash='unused', must_change_password=False)
        unit = w.Unit(code='SIGN-U', name='个')
        a = w.Warehouse(code='SIGN-A', name='签名委外甲仓', status='active', is_default=True)
        b = w.Warehouse(code='SIGN-B', name='签名委外乙仓', status='active')
        supplier = w.Supplier(code='SIGN-S', name='合成供应商')
        w.db.session.add_all([user,unit,a,b,supplier]); w.db.session.flush()
        material = w.Material(code='SIGN-M', name='合成委外物料', unit_id=unit.id, price=1, stock=25)
        w.db.session.add(material); w.db.session.flush()
        for wh,qty in [(a,20),(b,5)]:
            w.db.session.add(w.LocationInventory(material_id=material.id,warehouse_id=wh.id,location='L-1',quantity=qty))
            w.db.session.add(w.StockTransaction(material_id=material.id,warehouse_id=wh.id,location='L-1',quantity=qty,transaction_type='in'))
        parent = w.SubcontractOrder(order_no='SIGN-SC',supplier_id=supplier.id,warehouse=a.name,status='pending',operator_id=user.id)
        w.db.session.add(parent); w.db.session.flush()
        w.db.session.add(w.SubcontractItem(subcontract_order_id=parent.id,material_id=material.id,quantity=10))
        w.set_system_setting('location_management_enabled','1')
        w.db.session.commit()
        ids = dict(user=user.id,order=parent.id,material=material.id,a=a.id,b=b.id)
    client = w.app.test_client()
    with client.session_transaction() as session:
        session['_user_id']=str(ids['user']); session['_fresh']=True
    yield client,ids
    with w.app.app_context():
        w.db.session.remove(); w.db.drop_all()


def test_registered_document_writes_all_reach_revision_check():
    from services.document_edit_guard import DOCUMENTS, NEW_DOCUMENT_INTENTS, guarded_document_write
    domains = {'in_order','out_order','after_sale_out','check','transfer','adjustment',
               'purchase_request','purchase_order','sales','requisition','subcontract',
               'subcontract_issue','subcontract_receive','opening_stock','bom'}
    new_intents = {'copy_in_order','copy_in_order_to_out','convert_in_order_to_out_order',
                   'create_in_order_push','copy_out_order','copy_check','copy_transfer',
                   'copy_after_sale_out_order','copy_purchase_order','copy_sales_order','copy_subcontract',
                   'create_purchase_order_from_request','create_in_order_from_purchase_order','create_sales_outbound_draft',
                   'create_requisition_from_bom'}
    assert set(DOCUMENTS) == domains
    assert set(NEW_DOCUMENT_INTENTS) == new_intents
    checked = set()
    bom_checked = set()
    for rule in w.app.url_map.iter_rules():
        if 'POST' not in rule.methods or rule.rule.strip('/').split('/')[0] not in domains:
            continue
        if 'id' not in rule.arguments or rule.endpoint in new_intents:
            continue
        # This ID is a row ID, covered separately with a persisted parent/line.
        if rule.endpoint == 'edit_opening_stock':
            continue
        assert hasattr(w.app.view_functions[rule.endpoint], '_required_roles'), rule.endpoint
        path = re.sub(r'<(?:[^:<>]+:)?[^<>]+>', '1', rule.rule)
        with w.app.test_request_context(path, method='POST', headers={'X-WMS-Document-Revision': 'invalid-signed-page'}):
            response = make_response(guarded_document_write(lambda: jsonify(status='unexpected-handler-call')))
            assert response.status_code == 409, (rule.endpoint, rule.rule, response.json)
        checked.add(rule.endpoint)
        if rule.rule.strip('/').split('/')[0] == 'bom':
            bom_checked.add((rule.endpoint, rule.rule))
    assert {'update_check_item','quick_issue_subcontract','quick_receive_subcontract',
            'update_in_order','update_out_order','update_opening_stock_doc_date',
            'update_bom','add_bom_item','add_bom_item_alias','delete_bom_item','delete_bom_item_alias',
            'delete_bom','delete_bom_alias','calculate_bom_cost'} <= checked
    assert {
        ('update_bom', '/bom/<int:id>/update'),
        ('add_bom_item', '/bom/<int:id>/item/add'),
        ('add_bom_item_alias', '/bom/<int:id>/add_item'),
        ('delete_bom_item', '/bom/<int:id>/item/<int:item_id>/delete'),
        ('delete_bom_item_alias', '/bom/<int:id>/delete_item/<int:item_id>'),
        ('delete_bom', '/bom/<int:id>/delete'),
        ('delete_bom_alias', '/bom/delete/<int:id>'),
        ('calculate_bom_cost', '/bom/<int:id>/calculate_cost'),
    } <= bom_checked


@pytest.mark.parametrize('action,quantity,expected', [('issue',6,14),('receive',4,24)])
def test_signed_quick_subcontract_actions_keep_three_ledgers(subcontract_case, action, quantity, expected):
    client,ids = subcontract_case
    oid = ids['order']
    token = revision(client, f'/subcontract/{oid}')
    assert token
    response = client.post(f'/subcontract/{oid}/{action}',
                           data={'material_code':'SIGN-M','quantity':str(quantity),'price':'1','location':'L-1'},
                           headers={'X-WMS-Document-Revision': token})
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    assert response.headers.get('X-WMS-Document-Revision')
    with w.app.app_context():
        material = w.db.session.get(w.Material,ids['material'])
        assert material.stock == expected + 5
        a = w.LocationInventory.query.filter_by(material_id=material.id,warehouse_id=ids['a'],location='L-1').one()
        b = w.LocationInventory.query.filter_by(material_id=material.id,warehouse_id=ids['b'],location='L-1').one()
        assert a.quantity == expected and b.quantity == 5
        assert sum(t.quantity for t in w.StockTransaction.query.filter_by(material_id=material.id)) == material.stock
